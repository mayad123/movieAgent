"""
Violation artifact writer for scenario test violations.

Writes detailed JSON artifacts when scenarios produce validator violations,
even if the test passes. This allows tracking violations separately from test failures.
"""
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from tests.failure_artifact_writer import sanitize_filename


def write_violation_artifact(
    scenario_name: str,
    template_id: Optional[str],
    user_query: str,
    violations: List[str],
    offending_text: str,
    fixed_text: Optional[str] = None,
    repair_instruction: Optional[str] = None,
    artifacts_dir: Optional[Path] = None,
    kaggle_outcome: Optional[Dict[str, Any]] = None  # Kaggle behavior outcome
) -> Optional[Path]:
    """
    Write a violation artifact JSON file for a scenario with validator violations.
    
    Args:
        scenario_name: Name of the scenario
        template_id: Selected template ID
        user_query: Original user query
        violations: List of violation messages from OutputValidator
        offending_text: The text that was validated (sample_model_output or generated text)
        fixed_text: Corrected text if auto-fix was applied (optional)
        repair_instruction: Repair instruction if validator requires reprompt (optional)
        artifacts_dir: Directory to write artifacts (defaults to tests/test_reports/violations/)
    
    Returns:
        Path to the written artifact file, or None if writing failed
    """
    if artifacts_dir is None:
        # Default to tests/test_reports/violations/
        artifacts_dir = Path(__file__).parent / "test_reports" / "violations"
    
    # Don't write if there are no violations
    if not violations:
        return None
    
    # Create directory if it doesn't exist
    try:
        artifacts_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"Warning: Failed to create violations directory {artifacts_dir}: {e}")
        return None
    
    # Sanitize scenario name for filename
    safe_name = sanitize_filename(scenario_name)
    artifact_file = artifacts_dir / f"{safe_name}.json"
    
    # Parse violations into structured format (type + message)
    structured_violations = []
    for violation in violations:
        violation_lower = violation.lower()
        violation_type = "unknown"
        
        if "forbidden" in violation_lower or "term" in violation_lower:
            violation_type = "forbidden_terms"
        elif "sentence" in violation_lower or "word" in violation_lower or "length" in violation_lower or "verbosity" in violation_lower:
            violation_type = "verbosity"
        elif "freshness" in violation_lower or "timestamp" in violation_lower or "date" in violation_lower or "as of" in violation_lower:
            violation_type = "freshness"
        elif "section" in violation_lower or "required" in violation_lower:
            violation_type = "missing_required_section"
        
        structured_violations.append({
            "type": violation_type,
            "message": violation
        })
    
    # Extract unique violation types for summary
    violation_types = list(set(v["type"] for v in structured_violations))
    
    # Extract Kaggle metadata if available
    kaggle_metadata = None
    if kaggle_outcome:
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
            "item_count": kaggle_outcome.get("evidence_count", 0),
            "fallback_reason": fallback_reason,
            "warnings": kaggle_outcome.get("warnings", [])
        }
    
    # Build artifact JSON
    artifact = {
        "scenario_name": scenario_name,
        "template_id": template_id,
        "user_query": user_query,
        "violations": structured_violations,
        "violation_types": violation_types,
        "violation_count": len(violations),
        "offending_text": offending_text,
        "fixed_text": fixed_text,
        "repair_instruction": repair_instruction,
        "kaggle": kaggle_metadata,  # Kaggle provenance and adapter decision metadata
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")
    }
    
    # Write JSON file
    try:
        with open(artifact_file, "w", encoding="utf-8") as f:
            json.dump(artifact, f, indent=2, ensure_ascii=False)
        return artifact_file
    except Exception as e:
        print(f"Warning: Failed to write violation artifact to {artifact_file}: {e}")
        return None


def generate_violations_index(artifacts_dir: Optional[Path] = None) -> Optional[Path]:
    """
    Generate an index file listing all violation artifacts.
    
    Args:
        artifacts_dir: Directory containing violation artifacts (defaults to tests/test_reports/violations/)
    
    Returns:
        Path to the written index file, or None if writing failed
    """
    if artifacts_dir is None:
        artifacts_dir = Path(__file__).parent / "test_reports" / "violations"
    
    index_file = artifacts_dir.parent / "violations_index.json"
    
    # Check if violations directory exists
    if not artifacts_dir.exists():
        # Write empty index if no violations directory
        index_data = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "total_scenarios_with_violations": 0,
            "scenarios": []
        }
        try:
            with open(index_file, "w", encoding="utf-8") as f:
                json.dump(index_data, f, indent=2, ensure_ascii=False)
            return index_file
        except Exception as e:
            print(f"Warning: Failed to write violations index to {index_file}: {e}")
            return None
    
    # Load all violation artifacts
    scenarios = []
    try:
        for artifact_file in artifacts_dir.glob("*.json"):
            try:
                with open(artifact_file, "r", encoding="utf-8") as f:
                    artifact = json.load(f)
                    
                    scenarios.append({
                        "scenario_name": artifact.get("scenario_name", artifact_file.stem),
                        "template_id": artifact.get("template_id"),
                        "user_query": artifact.get("user_query", ""),
                        "violation_types": artifact.get("violation_types", []),
                        "violation_count": artifact.get("violation_count", len(artifact.get("violations", []))),
                        "artifact_path": str(artifact_file.relative_to(artifacts_dir.parent))
                    })
            except Exception as e:
                print(f"Warning: Failed to load violation artifact {artifact_file}: {e}")
                continue
        
        # Sort by scenario name
        scenarios.sort(key=lambda x: x["scenario_name"])
        
        # Build index
        index_data = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "total_scenarios_with_violations": len(scenarios),
            "scenarios": scenarios
        }
        
        # Write index file
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(index_data, f, indent=2, ensure_ascii=False)
        return index_file
    except Exception as e:
        print(f"Warning: Failed to generate violations index: {e}")
        return None

