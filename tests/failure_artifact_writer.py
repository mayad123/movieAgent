"""
Failure artifact writer for scenario test failures.

Writes detailed JSON artifacts when scenario tests fail to aid in debugging.
"""
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
import re


def sanitize_filename(name: str) -> str:
    """
    Sanitize scenario name to safe filename.
    
    Args:
        name: Scenario name
        
    Returns:
        Safe filename string
    """
    # Replace unsafe characters with underscores
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', name)
    # Remove leading/trailing dots and spaces
    sanitized = sanitized.strip('. ')
    # Replace multiple consecutive underscores with single underscore
    sanitized = re.sub(r'_+', '_', sanitized)
    # Ensure it's not empty
    if not sanitized:
        sanitized = "unknown_scenario"
    # Limit length
    if len(sanitized) > 100:
        sanitized = sanitized[:100]
    return sanitized


def write_failure_artifact(
    scenario_name: str,
    scenario_data: Dict[str, Any],
    request_plan: Any,
    template_id: Optional[str],
    messages: List[Dict[str, str]],
    formatted_evidence: Any,  # EvidenceFormatResult
    validator_result: Optional[Any],  # ValidationResult
    failures: List[str],
    timing_ms: Optional[float] = None,
    artifacts_dir: Optional[Path] = None,
    template: Optional[Any] = None  # ResponseTemplate for building repair instruction
) -> Optional[Path]:
    """
    Write a failure artifact JSON file for a failed scenario test.
    
    Args:
        scenario_name: Name of the scenario
        scenario_data: Original scenario input data
        request_plan: RequestPlan object
        template_id: Selected template ID
        messages: List of messages from PromptBuilder
        formatted_evidence: EvidenceFormatResult from EvidenceFormatter
        validator_result: ValidationResult from OutputValidator (if validation was run)
        failures: List of failure messages
        timing_ms: Test execution time in milliseconds
        artifacts_dir: Directory to write artifacts (defaults to tests/test_reports/failures/)
    
    Returns:
        Path to the written artifact file, or None if writing failed
    """
    if artifacts_dir is None:
        # Default to tests/test_reports/failures/
        artifacts_dir = Path(__file__).parent / "test_reports" / "failures"
    
    # Create directory if it doesn't exist
    try:
        artifacts_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"Warning: Failed to create artifacts directory {artifacts_dir}: {e}")
        return None
    
    # Sanitize scenario name for filename
    safe_name = sanitize_filename(scenario_name)
    artifact_file = artifacts_dir / f"{safe_name}.json"
    
    # Extract request_plan fields
    request_plan_dict = {
        "request_type": getattr(request_plan, "request_type", None),
        "intent": getattr(request_plan, "intent", None),
        "entities_typed": getattr(request_plan, "entities_typed", {}),
        "need_freshness": getattr(request_plan, "need_freshness", False),
        "freshness_ttl_hours": getattr(request_plan, "freshness_ttl_hours", None),
        "require_tier_a": getattr(request_plan, "require_tier_a", False),
        "allowed_source_tiers": getattr(request_plan, "allowed_source_tiers", []),
        "reject_tier_c": getattr(request_plan, "reject_tier_c", True),
        "response_format": getattr(request_plan, "response_format", None),
    }
    
    # Extract formatted evidence data
    evidence_dict = {
        "text": formatted_evidence.text if formatted_evidence else "",
        "counts": formatted_evidence.counts if formatted_evidence else {"before": 0, "after": 0},
        "max_snippet_len": formatted_evidence.max_snippet_len if formatted_evidence else 0,
        "dedupe_removed": formatted_evidence.dedupe_removed if formatted_evidence else 0,
        "items_count": len(formatted_evidence.items) if formatted_evidence else 0
    }
    
    # Extract validator result
    validator_dict = None
    if validator_result:
        validator_dict = {
            "is_valid": getattr(validator_result, "is_valid", None),
            "violations": getattr(validator_result, "violations", []),
            "corrected_text": getattr(validator_result, "corrected_text", None),
            "requires_reprompt": getattr(validator_result, "requires_reprompt", False),
        }
        # Build repair instruction if validator requires reprompt
        # (This is generated on-demand, so we build it if needed)
        if validator_result.requires_reprompt and validator_result.violations and template:
            try:
                # Import here to avoid circular dependencies
                from cinemind.prompting.output_validator import OutputValidator
                
                validator = OutputValidator()
                repair_instruction = validator.build_correction_instruction(
                    validator_result.violations,
                    template
                )
                validator_dict["repair_instruction"] = repair_instruction
            except Exception:
                # If we can't build repair instruction, just leave it out
                pass
    
    # Build artifact JSON
    artifact = {
        "scenario": {
            "name": scenario_data.get("name", scenario_name),
            "user_query": scenario_data.get("user_query", ""),
            "expected": scenario_data.get("expected", {})
        },
        "request_plan": request_plan_dict,
        "template_id": template_id,
        "messages": messages,
        "formatted_evidence": evidence_dict,
        "validator": validator_dict,
        "failures": failures,
        "timing_ms": timing_ms,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")
    }
    
    # Write JSON file
    try:
        with open(artifact_file, "w", encoding="utf-8") as f:
            json.dump(artifact, f, indent=2, ensure_ascii=False)
        return artifact_file
    except Exception as e:
        print(f"Warning: Failed to write failure artifact to {artifact_file}: {e}")
        return None

