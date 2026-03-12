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


def remove_failure_artifact(
    scenario_name: str,
    artifacts_dir: Optional[Path] = None
) -> bool:
    """
    Remove a failure artifact file for a scenario that has passed.
    
    Args:
        scenario_name: Name of the scenario
        artifacts_dir: Directory containing artifacts (defaults to tests/test_reports/failures/)
    
    Returns:
        True if file was removed (or didn't exist), False if removal failed
    """
    if artifacts_dir is None:
        artifacts_dir = Path(__file__).parent.parent / "test_reports" / "failures"

    # Sanitize scenario name for filename
    safe_name = sanitize_filename(scenario_name)
    artifact_file = artifacts_dir / f"{safe_name}.json"
    
    # Remove the file if it exists
    try:
        if artifact_file.exists():
            artifact_file.unlink()
            return True
        return True  # File doesn't exist, which is fine
    except Exception as e:
        print(f"Warning: Failed to remove old artifact file {artifact_file}: {e}")
        return False


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
    template: Optional[Any] = None,  # ResponseTemplate for building repair instruction
    kaggle_outcome: Optional[Dict[str, Any]] = None  # Kaggle behavior outcome
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
        artifacts_dir = Path(__file__).parent.parent / "test_reports" / "failures"
    
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
    response_format = getattr(request_plan, "response_format", None)
    # Convert ResponseFormat enum to its value for JSON serialization
    response_format_str = None
    if response_format is not None:
        try:
            # Try to get the enum value
            if hasattr(response_format, 'value'):
                response_format_str = response_format.value
            elif hasattr(response_format, 'name'):
                response_format_str = response_format.name
            else:
                response_format_str = str(response_format)
        except Exception:
            response_format_str = str(response_format) if response_format else None
    
    request_plan_dict = {
        "request_type": getattr(request_plan, "request_type", None),
        "intent": getattr(request_plan, "intent", None),
        "entities_typed": getattr(request_plan, "entities_typed", {}),
        "need_freshness": getattr(request_plan, "need_freshness", False),
        "freshness_ttl_hours": getattr(request_plan, "freshness_ttl_hours", None),
        "require_tier_a": getattr(request_plan, "require_tier_a", False),
        "allowed_source_tiers": getattr(request_plan, "allowed_source_tiers", []),
        "reject_tier_c": getattr(request_plan, "reject_tier_c", True),
        "response_format": response_format_str,
    }
    
    # Extract formatted evidence data
    evidence_dict = {
        "text": str(formatted_evidence.text) if formatted_evidence and hasattr(formatted_evidence, 'text') else "",
        "counts": dict(formatted_evidence.counts) if formatted_evidence and hasattr(formatted_evidence, 'counts') else {"before": 0, "after": 0},
        "max_snippet_len": int(formatted_evidence.max_snippet_len) if formatted_evidence and hasattr(formatted_evidence, 'max_snippet_len') else 0,
        "dedupe_removed": int(formatted_evidence.dedupe_removed) if formatted_evidence and hasattr(formatted_evidence, 'dedupe_removed') else 0,
        "items_count": len(formatted_evidence.items) if formatted_evidence and hasattr(formatted_evidence, 'items') else 0
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
    
    # Extract Kaggle metadata if available
    kaggle_metadata = None
    if kaggle_outcome:
        # Count Kaggle items before and after formatter
        kaggle_items_before = kaggle_outcome.get("evidence_count", 0)
        # Count Kaggle items in formatted evidence (after formatter)
        kaggle_items_after = 0
        if formatted_evidence and hasattr(formatted_evidence, 'items'):
            kaggle_items_after = sum(
                1 for item in formatted_evidence.items 
                if hasattr(item, 'source_label') and 'imdb' in item.source_label.lower()
            )
        
        # Determine reason for fallback if Kaggle was attempted but not used
        fallback_reason = None
        if kaggle_outcome.get("attempted") and not kaggle_outcome.get("evidence_used"):
            # Check warnings for reason
            warnings = kaggle_outcome.get("warnings", [])
            if any("not relevant" in w.lower() for w in warnings):
                fallback_reason = "not_relevant"
            elif any("threshold" in w.lower() for w in warnings):
                fallback_reason = "below_threshold"
            elif any("timeout" in w.lower() for w in warnings):
                fallback_reason = "timeout"
            elif any("error" in w.lower() or "failed" in w.lower() for w in warnings):
                fallback_reason = "error"
            else:
                fallback_reason = "no_evidence"
        
        kaggle_metadata = {
            "attempted": kaggle_outcome.get("attempted", False),
            "used": kaggle_outcome.get("evidence_used", False),
            "item_count_before_formatter": kaggle_items_before,
            "item_count_after_formatter": kaggle_items_after,
            "fallback_reason": fallback_reason,
            "warnings": kaggle_outcome.get("warnings", [])
        }
    
    # Build artifact JSON
    artifact = {
        "scenario": {
            "name": scenario_data.get("name", scenario_name),
            "user_query": scenario_data.get("user_query", ""),
            "expected": scenario_data.get("expected", {})
        },
        "request_plan": request_plan_dict,
        "template_id": template_id,
        "messages": [dict(msg) if not isinstance(msg, dict) else msg for msg in messages] if messages else [],
        "formatted_evidence": evidence_dict,
        "validator": validator_dict,
        "kaggle": kaggle_metadata,  # Kaggle provenance and adapter decision metadata
        "failures": failures,
        "timing_ms": timing_ms,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")
    }
    
    # Write JSON file with better error handling
    try:
        # Use a custom JSON encoder to handle edge cases
        def json_serial(obj):
            """JSON serializer for objects not serializable by default json code"""
            if hasattr(obj, '__dict__'):
                return obj.__dict__
            elif hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes)):
                return list(obj)
            else:
                return str(obj)
        
        # Write to temporary file first, then rename (atomic write)
        temp_file = artifact_file.with_suffix('.tmp')
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(artifact, f, indent=2, ensure_ascii=False, default=json_serial)
            # Atomic rename
            temp_file.replace(artifact_file)
            return artifact_file
        except Exception as e:
            # Clean up temp file if it exists
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except:
                    pass
            raise e
    except (TypeError, ValueError) as e:
        # Try to identify what's not serializable
        import traceback
        error_msg = f"Failed to serialize artifact: {e}\n"
        error_msg += "Attempting to identify non-serializable objects...\n"
        try:
            # Try serializing each part individually to find the issue
            for key, value in artifact.items():
                try:
                    json.dumps(value, default=str)
                except Exception as e2:
                    error_msg += f"  - Problem with '{key}': {e2}\n"
        except:
            pass
        error_msg += f"Traceback: {traceback.format_exc()}"
        print(f"Warning: Failed to write failure artifact to {artifact_file}")
        print(error_msg)
        # Write a minimal artifact with just the failures and error info
        try:
            minimal_artifact = {
                "scenario": artifact.get("scenario", {}),
                "failures": artifact.get("failures", []),
                "serialization_error": str(e),
                "timestamp": artifact.get("timestamp", time.strftime("%Y-%m-%dT%H:%M:%S"))
            }
            with open(artifact_file, "w", encoding="utf-8") as f:
                json.dump(minimal_artifact, f, indent=2, ensure_ascii=False)
            print(f"  Wrote minimal artifact to {artifact_file}")
            return artifact_file
        except Exception as e3:
            print(f"  Failed to write even minimal artifact: {e3}")
            return None
    except Exception as e:
        import traceback
        print(f"Warning: Failed to write failure artifact to {artifact_file}: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        return None

