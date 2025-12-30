"""
Offline scenario matrix test harness for CineMind.

Tests routing, prompt construction, evidence formatting, and validator behavior
using YAML/JSON fixtures without calling external APIs.
"""
import os
import sys
import pytest
import time
from pathlib import Path
from typing import Dict, Any, List, Tuple

# Add src to path so we can import cinemind
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from cinemind.request_plan import RequestPlan
from cinemind.prompting import PromptBuilder, EvidenceBundle, get_template
from cinemind.prompting.evidence_formatter import EvidenceFormatter
from cinemind.prompting.output_validator import OutputValidator

from tests.fixtures.scenario_loader import (
    load_all_scenarios,
    build_request_plan,
    build_evidence_bundle,
    get_expected_checks,
)
from tests.report_generator import get_collector
from tests.failure_artifact_writer import write_failure_artifact, remove_failure_artifact
from tests.violation_artifact_writer import write_violation_artifact


def get_enforce_clean_policy(scenario: Dict[str, Any]) -> bool:
    """
    Determine if clean passes are enforced for a scenario.
    
    Policy:
    - gold scenarios default to enforce_clean=True
    - explore scenarios default to enforce_clean=False
    - Per-scenario override via expected.validator_checks.enforce_clean takes precedence
    
    Args:
        scenario: Scenario dictionary
        
    Returns:
        True if clean passes are enforced, False otherwise
    """
    scenario_set = scenario.get("scenario_set", "").lower()
    expected = get_expected_checks(scenario)
    validator_checks = expected.get("validator_checks", {})
    
    # Check for per-scenario override first
    if "enforce_clean" in validator_checks:
        return bool(validator_checks["enforce_clean"])
    
    # Apply default policy based on scenario_set
    if scenario_set == "gold":
        return True
    elif scenario_set == "explore":
        return False
    
    # Default to strict (enforce_clean=True) for unknown sets
    return True


class ScenarioTester:
    """Helper class for running scenario tests."""
    
    def __init__(self):
        self.prompt_builder = PromptBuilder()
        self.evidence_formatter = EvidenceFormatter()
        self.output_validator = OutputValidator(enable_auto_fix=True)
    
    def test_prompt_construction(
        self,
        request_plan: RequestPlan,
        evidence_bundle: EvidenceBundle,
        user_query: str,
        expected: Dict[str, Any]
    ) -> List[str]:
        """Test prompt construction and return list of failures."""
        failures = []
        prompt_checks = expected.get("prompt_checks", {})
        
        # Build messages (returns tuple: (messages, artifacts))
        messages, artifacts = self.prompt_builder.build_messages(
            request_plan=request_plan,
            evidence=evidence_bundle,
            user_query=user_query
        )
        
        # Check required sections
        required_sections = prompt_checks.get("required_sections", [])
        message_roles = [msg.get("role") for msg in messages]
        
        for section in required_sections:
            if section == "system" and "system" not in message_roles:
                failures.append(f"Missing required section: system")
            elif section == "developer":
                # Developer instructions are combined into system message
                # Check that system message exists (which contains developer instructions)
                if "system" not in message_roles:
                    failures.append(f"Missing required section: developer (combined in system)")
            elif section == "user" and "user" not in message_roles:
                failures.append(f"Missing required section: user")
        
        # Combine all message content for content checks
        all_content = "\n".join([msg.get("content", "") for msg in messages])
        
        # For must_not_contain, check only user message content (where evidence is included)
        # This avoids false positives from system/developer prompts that mention these terms in rules
        user_message_content = "\n".join([
            msg.get("content", "") for msg in messages 
            if msg.get("role") == "user"  # user message contains query + evidence
        ])
        
        # Check must_contain (checks entire prompt)
        must_contain = prompt_checks.get("must_contain", [])
        for term in must_contain:
            # Convert term to string for comparison (handles integers like years)
            term_str = str(term).lower()
            if term_str not in all_content.lower():
                failures.append(f"Prompt must contain '{term}' but doesn't")
        
        # Check must_not_contain (checks user message and evidence only, not system/developer instructions)
        must_not_contain = prompt_checks.get("must_not_contain", [])
        for term in must_not_contain:
            # Convert term to string for comparison
            term_str = str(term).lower()
            # Check only user message content (contains evidence), not system/developer instructions
            # (system/developer prompts may mention these terms in rules about not using them)
            if term_str in user_message_content.lower():
                failures.append(f"Prompt must NOT contain '{term}' but does (found in user message/evidence)")
        
        return failures
    
    def test_template_selection(
        self,
        request_plan: RequestPlan,
        expected: Dict[str, Any]
    ) -> List[str]:
        """Test that correct template is selected."""
        failures = []
        expected_template_id = expected.get("template_id")
        
        if expected_template_id:
            template = get_template(request_plan.request_type, request_plan.intent)
            if template.template_id != expected_template_id:
                failures.append(
                    f"Expected template_id '{expected_template_id}', "
                    f"got '{template.template_id}'"
                )
        
        return failures
    
    def test_evidence_formatting(
        self,
        evidence_bundle: EvidenceBundle,
        expected: Dict[str, Any]
    ) -> List[str]:
        """Test evidence formatting and return list of failures."""
        failures = []
        evidence_checks = expected.get("evidence_checks", {})
        
        # Format evidence (returns EvidenceFormatResult)
        format_result = self.evidence_formatter.format(evidence_bundle)
        formatted_evidence = format_result.text  # Get string for content checks
        
        # Check deduplication count using structured metadata
        expected_count = evidence_checks.get("dedupe_expected_count")
        if expected_count is not None:
            actual_count = format_result.counts["after"]
            if actual_count != expected_count:
                failures.append(
                    f"Expected {expected_count} deduplicated items, got {actual_count}"
                )
        
        # Check max snippet length using structured metadata
        max_snippet_len = evidence_checks.get("max_snippet_len")
        if max_snippet_len:
            if format_result.max_snippet_len > max_snippet_len:
                failures.append(
                    f"Max snippet length {format_result.max_snippet_len} exceeds limit {max_snippet_len}"
                )
        
        # Check must_not_contain_terms
        must_not_contain = evidence_checks.get("must_not_contain_terms", [])
        for term in must_not_contain:
            if term.lower() in formatted_evidence.lower():
                failures.append(
                    f"Formatted evidence must NOT contain '{term}' but does"
                )
        
        return failures
    
    def test_output_validation(
        self,
        request_plan: RequestPlan,
        sample_output: str,
        expected: Dict[str, Any]
    ) -> List[str]:
        """Test output validation and return list of failures."""
        failures = []
        validator_checks = expected.get("validator_checks", {})
        
        # Get template
        template = get_template(request_plan.request_type, request_plan.intent)
        
        # Validate
        result = self.output_validator.validate(
            response_text=sample_output,
            template=template,
            need_freshness=request_plan.need_freshness
        )
        
        # Check expected_valid
        expected_valid = validator_checks.get("expected_valid", True)
        if result.is_valid != expected_valid:
            failures.append(
                f"Expected valid={expected_valid}, got valid={result.is_valid}. "
                f"Violations: {result.violations}"
            )
        
        # Check expected violation types
        expected_violation_types = validator_checks.get("expected_violation_types", [])
        if expected_violation_types:
            # Extract violation types from violation messages
            violation_types_found = []
            for violation in result.violations:
                if "forbidden" in violation.lower() or "term" in violation.lower():
                    violation_types_found.append("forbidden_terms")
                elif "sentence" in violation.lower() or "word" in violation.lower() or "length" in violation.lower():
                    violation_types_found.append("verbosity")
                elif "freshness" in violation.lower() or "timestamp" in violation.lower() or "date" in violation.lower():
                    violation_types_found.append("freshness")
            
            for expected_type in expected_violation_types:
                if expected_type not in violation_types_found:
                    failures.append(
                        f"Expected violation type '{expected_type}' not found. "
                        f"Found: {violation_types_found}"
                    )
        
        return failures
    
    def test_kaggle_behavior(
        self,
        evidence_bundle: EvidenceBundle,
        expected: Dict[str, Any]
    ) -> Tuple[List[str], Dict[str, Any]]:
        """
        Test Kaggle behavior and return (failures, kaggle_outcome).
        
        Args:
            evidence_bundle: EvidenceBundle to check for Kaggle evidence
            expected: Expected checks dictionary
            
        Returns:
            Tuple of (failures: List[str], kaggle_outcome: Dict[str, Any])
            kaggle_outcome contains:
            - attempted: bool (whether Kaggle was attempted - inferred from evidence)
            - evidence_used: bool (whether Kaggle evidence is present)
            - evidence_count: int (number of Kaggle evidence items)
            - warnings: List[str] (warnings about Kaggle behavior)
        """
        failures = []
        kaggle_checks = expected.get("kaggle_checks", {})
        
        # Count Kaggle evidence items
        kaggle_evidence_items = [
            r for r in evidence_bundle.search_results 
            if r.get("source") == "kaggle_imdb"
        ]
        kaggle_evidence_count = len(kaggle_evidence_items)
        kaggle_evidence_used = kaggle_evidence_count > 0
        
        # Infer if Kaggle was attempted (if we have Kaggle evidence, it was attempted)
        # Note: In offline tests, we can't know if Kaggle was attempted but returned nothing
        # So we infer from presence of evidence
        kaggle_attempted = kaggle_evidence_used
        
        # Build outcome dictionary
        kaggle_outcome = {
            "attempted": kaggle_attempted,
            "evidence_used": kaggle_evidence_used,
            "evidence_count": kaggle_evidence_count,
            "warnings": []
        }
        
        # Check expectations if kaggle_checks are specified
        if kaggle_checks:
            # Check if Kaggle was expected to be attempted
            expected_attempted = kaggle_checks.get("expected_attempted")
            if expected_attempted is not None:
                if expected_attempted and not kaggle_attempted:
                    failures.append(
                        "Kaggle was expected to be attempted but no Kaggle evidence found"
                    )
                elif not expected_attempted and kaggle_attempted:
                    failures.append(
                        "Kaggle was not expected to be attempted but Kaggle evidence found"
                    )
            
            # Check if Kaggle evidence was expected
            expected_evidence_used = kaggle_checks.get("expected_evidence_used")
            if expected_evidence_used is not None:
                if expected_evidence_used and not kaggle_evidence_used:
                    failures.append(
                        "Kaggle evidence was expected but not found in evidence bundle"
                    )
                elif not expected_evidence_used and kaggle_evidence_used:
                    # This is a warning, not a failure (unless explicitly required)
                    kaggle_outcome["warnings"].append(
                        "Kaggle evidence was not expected but found in evidence bundle"
                    )
            
            # Check minimum evidence count
            min_evidence_count = kaggle_checks.get("min_evidence_count")
            if min_evidence_count is not None:
                if kaggle_evidence_count < min_evidence_count:
                    failures.append(
                        f"Expected at least {min_evidence_count} Kaggle evidence items, "
                        f"got {kaggle_evidence_count}"
                    )
        
        return failures, kaggle_outcome


# Load all scenarios once at module import time
_all_scenarios = None
_scenario_set_filter = None

def get_all_scenarios():
    """Lazy load all scenarios with optional filtering by scenario_set."""
    global _all_scenarios, _scenario_set_filter
    
    # Check for environment variable first
    # Treat empty string as None (no filter)
    env_filter_raw = os.environ.get("CINEMIND_SCENARIO_SET")
    env_filter = env_filter_raw.strip().lower() if env_filter_raw and env_filter_raw.strip() else None
    
    # Only reload if filter changed or scenarios not yet loaded
    if _all_scenarios is None or env_filter != _scenario_set_filter:
        _scenario_set_filter = env_filter
        _all_scenarios = load_all_scenarios(scenario_set_filter=env_filter)
    
    return _all_scenarios


@pytest.fixture
def scenario_tester():
    """Fixture providing ScenarioTester instance."""
    return ScenarioTester()


def pytest_generate_tests(metafunc):
    """Generate test parameters dynamically based on markers and env vars."""
    if "scenario" in metafunc.fixturenames:
        # Check for environment variable first
        # Treat empty string as None (no filter)
        env_filter_raw = os.environ.get("CINEMIND_SCENARIO_SET")
        env_filter = env_filter_raw.strip().lower() if env_filter_raw and env_filter_raw.strip() else None
        
        # Load scenarios with filter (env var takes precedence)
        scenarios = load_all_scenarios(scenario_set_filter=env_filter)
        
        # Validate we have scenarios
        if not scenarios:
            raise ValueError(f"No scenarios found for filter: {env_filter}")
        
        # Check for duplicate names (which would cause pytest to deduplicate)
        scenario_names = [s.get("name") for s in scenarios]
        duplicate_names = [name for name in set(scenario_names) if scenario_names.count(name) > 1]
        if duplicate_names:
            import warnings
            warnings.warn(f"Duplicate scenario names found: {duplicate_names}. Pytest will deduplicate these!")
        
        # Debug: print scenario count and names
        if env_filter:
            print(f"\n[DEBUG] Collected {len(scenarios)} {env_filter} scenarios")
            for i, s in enumerate(scenarios, 1):
                print(f"  {i}. {s.get('name', 'unknown')}")
        else:
            gold_count = sum(1 for s in scenarios if s.get("scenario_set") == "gold")
            explore_count = sum(1 for s in scenarios if s.get("scenario_set") == "explore")
            print(f"\n[DEBUG] Collected {len(scenarios)} total scenarios (gold: {gold_count}, explore: {explore_count})")
        
        # Generate parametrize with unique IDs
        def scenario_id(scenario):
            name = scenario.get("name", "unknown")
            # Use file path as fallback for uniqueness if name is missing
            file_path = scenario.get("_file_path", "")
            if not name or name == "unknown":
                # Extract filename as fallback
                if file_path:
                    import os
                    name = os.path.splitext(os.path.basename(file_path))[0]
            return f"{name}"
        
        metafunc.parametrize(
            "scenario",
            scenarios,
            ids=scenario_id
        )


def pytest_collection_modifyitems(config, items):
    """Add markers to test items based on scenario_set for marker-based filtering."""
    # Get marker expression if specified
    marker_expr = config.getoption("-m", default="")
    
    # If no marker expression, skip marker-based filtering
    if not marker_expr or marker_expr == "":
        # Check if env var is set - if so, we've already filtered in pytest_generate_tests
        return
    
    # Add markers to test items based on their scenario_set
    # This allows pytest's marker filtering to work
    for item in items:
        if hasattr(item, "callspec") and item.callspec:
            # Get scenario from parametrize
            scenario = item.callspec.params.get("scenario")
            if scenario:
                scenario_set = scenario.get("scenario_set")
                if scenario_set == "gold":
                    item.add_marker(pytest.mark.gold)
                elif scenario_set == "explore":
                    item.add_marker(pytest.mark.explore)


def test_scenario(scenario: Dict[str, Any], scenario_tester: ScenarioTester):
    """
    Test a single scenario.
    
    This test runs offline and validates:
    - Template selection
    - Prompt construction
    - Evidence formatting
    - Output validation
    """
    collector = get_collector()
    start_time = time.time()
    
    # Build objects from scenario
    request_plan = build_request_plan(scenario)
    evidence_bundle = build_evidence_bundle(scenario)
    expected = get_expected_checks(scenario)
    user_query = scenario.get("user_query", "")
    scenario_name = scenario.get("name", "unknown")
    
    # Get template ID for reporting
    template = get_template(request_plan.request_type, request_plan.intent)
    template_id = template.template_id if template else None
    
    all_failures = []
    violation_types = []
    kaggle_outcome = None  # Will be set by test_kaggle_behavior
    
    # Build messages for artifact (do this early so we have them even if tests fail)
    messages = []
    try:
        messages, _ = scenario_tester.prompt_builder.build_messages(
            request_plan=request_plan,
            evidence=evidence_bundle,
            user_query=user_query
        )
    except Exception as e:
        # If message building fails, we'll still write the artifact with empty messages
        messages = []
    
    # Test template selection
    template_failures = scenario_tester.test_template_selection(request_plan, expected)
    all_failures.extend(template_failures)
    
    # Test prompt construction
    prompt_failures = scenario_tester.test_prompt_construction(
        request_plan, evidence_bundle, user_query, expected
    )
    all_failures.extend(prompt_failures)
    
    # Test evidence formatting
    evidence_failures = scenario_tester.test_evidence_formatting(
        evidence_bundle, expected
    )
    all_failures.extend(evidence_failures)
    
    # Test Kaggle behavior
    kaggle_failures, kaggle_outcome = scenario_tester.test_kaggle_behavior(
        evidence_bundle, expected
    )
    all_failures.extend(kaggle_failures)
    
    # Collect evidence statistics using structured metadata
    evidence_format_result = scenario_tester.evidence_formatter.format(evidence_bundle)
    evidence_items = evidence_format_result.counts["before"]
    evidence_deduped_count = evidence_format_result.counts["after"]
    evidence_max_snippet_len = evidence_format_result.max_snippet_len
    
    # Test output validation (if sample output provided)
    validation_result = None
    sample_output = expected.get("sample_model_output")
    if sample_output:
        validation_failures = scenario_tester.test_output_validation(
            request_plan, sample_output, expected
        )
        all_failures.extend(validation_failures)
        
        # Extract violation types from validation result
        template = get_template(request_plan.request_type, request_plan.intent)
        validation_result = scenario_tester.output_validator.validate(
            response_text=sample_output,
            template=template,
            need_freshness=request_plan.need_freshness
        )
        
        # Extract violation types from violation messages
        for violation in validation_result.violations:
            violation_lower = violation.lower()
            if "forbidden" in violation_lower or "term" in violation_lower:
                violation_types.append("forbidden_terms")
            elif "sentence" in violation_lower or "word" in violation_lower or "length" in violation_lower or "verbosity" in violation_lower:
                violation_types.append("verbosity")
            elif "freshness" in violation_lower or "timestamp" in violation_lower or "date" in violation_lower or "as of" in violation_lower:
                violation_types.append("freshness")
            elif "section" in violation_lower or "required" in violation_lower:
                violation_types.append("missing_required_section")
        
        # Write violation artifact if there are violations (even if test passes)
        if validation_result and validation_result.violations:
            try:
                # Build repair instruction if needed
                repair_instruction = None
                if validation_result.requires_reprompt and template:
                    try:
                        repair_instruction = scenario_tester.output_validator.build_correction_instruction(
                            validation_result.violations,
                            template
                        )
                    except Exception:
                        # If we can't build repair instruction, just leave it out
                        pass
                
                write_violation_artifact(
                    scenario_name=scenario_name,
                    template_id=template_id,
                    user_query=user_query,
                    violations=validation_result.violations,
                    offending_text=sample_output,
                    fixed_text=validation_result.corrected_text,
                    repair_instruction=repair_instruction,
                    kaggle_outcome=kaggle_outcome
                )
            except Exception as e:
                # Don't fail the test because violation artifact writing failed
                print(f"Warning: Failed to write violation artifact for '{scenario_name}': {e}")
    
    # Write Kaggle warning artifact if there are Kaggle warnings (similar to violations)
    if kaggle_outcome and kaggle_outcome.get("warnings"):
        try:
            # Write Kaggle warnings as a violation-like artifact
            # This makes Kaggle behavior visible without breaking tests
            kaggle_warnings = kaggle_outcome.get("warnings", [])
            write_violation_artifact(
                scenario_name=f"{scenario_name}_kaggle",
                template_id=template_id,
                user_query=user_query,
                violations=kaggle_warnings,
                offending_text="",  # No offending text for Kaggle warnings
                fixed_text="",
                repair_instruction=None,
                kaggle_outcome=kaggle_outcome
            )
        except Exception as e:
            # Don't fail the test because Kaggle artifact writing failed
            print(f"Warning: Failed to write Kaggle artifact for '{scenario_name}': {e}")
    
    # Apply strictness policy: check if violations should cause failure
    scenario_set = scenario.get("scenario_set")
    enforce_clean = get_enforce_clean_policy(scenario)
    
    # Check for violations (only if validation was performed)
    has_violations = False
    if validation_result is not None:
        has_violations = len(validation_result.violations) > 0
        
        # If enforce_clean is True and there are violations, add a failure
        if enforce_clean and has_violations:
            violation_msg = f"Scenario requires clean pass but has {len(validation_result.violations)} validator violation(s): {', '.join(validation_result.violations)}"
            all_failures.append(violation_msg)
    
    # Calculate duration
    duration_ms = (time.time() - start_time) * 1000
    
    # Determine final pass status and clean pass status
    passed = len(all_failures) == 0
    passed_clean = passed and not has_violations
    
    # Record result with collector
    collector.record_scenario_result(
        scenario_name=scenario_name,
        template_id=template_id,
        passed=passed,
        duration_ms=duration_ms,
        failures=all_failures,
        violation_types=violation_types,
        evidence_items=evidence_items,
        evidence_deduped_count=evidence_deduped_count,
        evidence_max_snippet_len=evidence_max_snippet_len,
        scenario_set=scenario_set,
        passed_clean=passed_clean,
        has_violations=has_violations
    )
    
    # If test passed, remove any old failure artifacts
    if passed:
        try:
            remove_failure_artifact(scenario_name)
        except Exception as e:
            # Don't fail the test if artifact cleanup fails
            print(f"Warning: Failed to remove old artifact for '{scenario_name}': {e}")
    
    # Write failure artifact if test failed and fail the test
    if all_failures:
        try:
            # Get template for repair instruction building
            template_for_artifact = get_template(request_plan.request_type, request_plan.intent) if request_plan else None
            
            artifact_path = write_failure_artifact(
                scenario_name=scenario_name,
                scenario_data=scenario,
                request_plan=request_plan,
                template_id=template_id,
                messages=messages,
                formatted_evidence=evidence_format_result,
                validator_result=validation_result,
                failures=all_failures,
                timing_ms=duration_ms,
                template=template_for_artifact,
                kaggle_outcome=kaggle_outcome
            )
            if artifact_path:
                # Add artifact path to failure message for easy access
                failure_msg = f"Scenario '{scenario_name}' failed:\n"
                failure_msg += "\n".join(f"  - {f}" for f in all_failures)
                failure_msg += f"\n\nFailure artifact written to: {artifact_path}"
                pytest.fail(failure_msg)
            else:
                # Artifact writing failed, but test still fails for real reason
                failure_msg = f"Scenario '{scenario_name}' failed:\n"
                failure_msg += "\n".join(f"  - {f}" for f in all_failures)
                pytest.fail(failure_msg)
        except Exception as e:
            # Don't fail the test because artifact writing failed
            # Log the error but still fail for the real reason
            print(f"Warning: Failed to write failure artifact for '{scenario_name}': {e}")
            failure_msg = f"Scenario '{scenario_name}' failed:\n"
            failure_msg += "\n".join(f"  - {f}" for f in all_failures)
            pytest.fail(failure_msg)


def test_scenario_count():
    """Ensure we have a reasonable number of scenarios."""
    scenarios = get_all_scenarios()
    # Check that we have scenarios in both gold and explore sets when loading all
    gold_count = sum(1 for s in scenarios if s.get("scenario_set") == "gold")
    explore_count = sum(1 for s in scenarios if s.get("scenario_set") == "explore")
    
    # If loading all (no filter), expect both sets
    env_filter = os.environ.get("CINEMIND_SCENARIO_SET")
    if not env_filter:
        assert gold_count >= 10, f"Expected at least 10 gold scenarios, found {gold_count}"
        assert explore_count >= 10, f"Expected at least 10 explore scenarios, found {explore_count}"
    
    assert len(scenarios) >= 10, f"Expected at least 10 scenarios, found {len(scenarios)}"
    print(f"\nLoaded {len(scenarios)} scenarios for testing (gold: {gold_count}, explore: {explore_count})")


if __name__ == "__main__":
    # Quick test to verify scenarios load
    scenarios = get_all_scenarios()
    print(f"Loaded {len(scenarios)} scenarios")
    for scenario in scenarios[:5]:
        print(f"  - {scenario.get('name', 'unknown')}")

