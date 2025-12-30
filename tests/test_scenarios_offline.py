"""
Offline scenario matrix test harness for CineMind.

Tests routing, prompt construction, evidence formatting, and validator behavior
using YAML/JSON fixtures without calling external APIs.
"""
import pytest
import time
from typing import Dict, Any, List

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
from tests.failure_artifact_writer import write_failure_artifact
from tests.violation_artifact_writer import write_violation_artifact


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
        
        # Check must_contain
        must_contain = prompt_checks.get("must_contain", [])
        for term in must_contain:
            if term.lower() not in all_content.lower():
                failures.append(f"Prompt must contain '{term}' but doesn't")
        
        # Check must_not_contain
        must_not_contain = prompt_checks.get("must_not_contain", [])
        for term in must_not_contain:
            if term.lower() in all_content.lower():
                failures.append(f"Prompt must NOT contain '{term}' but does")
        
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


# Load all scenarios once at module import time
_all_scenarios = None

def get_all_scenarios():
    """Lazy load all scenarios."""
    global _all_scenarios
    if _all_scenarios is None:
        _all_scenarios = load_all_scenarios()
    return _all_scenarios


# Pre-load scenarios for parametrize (called at module import)
_SCENARIOS = get_all_scenarios()

@pytest.fixture
def scenario_tester():
    """Fixture providing ScenarioTester instance."""
    return ScenarioTester()


@pytest.mark.parametrize("scenario", _SCENARIOS, ids=lambda s: s.get("name", "unknown"))
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
                    repair_instruction=repair_instruction
                )
            except Exception as e:
                # Don't fail the test because violation artifact writing failed
                print(f"Warning: Failed to write violation artifact for '{scenario_name}': {e}")
    
    # Calculate duration
    duration_ms = (time.time() - start_time) * 1000
    
    # Record result with collector
    passed = len(all_failures) == 0
    collector.record_scenario_result(
        scenario_name=scenario_name,
        template_id=template_id,
        passed=passed,
        duration_ms=duration_ms,
        failures=all_failures,
        violation_types=violation_types,
        evidence_items=evidence_items,
        evidence_deduped_count=evidence_deduped_count,
        evidence_max_snippet_len=evidence_max_snippet_len
    )
    
    # Write failure artifact if test failed
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
                template=template_for_artifact
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
    assert len(scenarios) >= 20, f"Expected at least 20 scenarios, found {len(scenarios)}"
    print(f"\nLoaded {len(scenarios)} scenarios for testing")


if __name__ == "__main__":
    # Quick test to verify scenarios load
    scenarios = get_all_scenarios()
    print(f"Loaded {len(scenarios)} scenarios")
    for scenario in scenarios[:5]:
        print(f"  - {scenario.get('name', 'unknown')}")

