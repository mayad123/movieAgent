"""
Enhanced scenario loader for constructing RequestPlan and EvidenceBundle from fixtures.
"""
import yaml
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

from cinemind.request_plan import RequestPlan, ResponseFormat, ToolType
from cinemind.prompting import EvidenceBundle


def load_scenario_file(scenario_path: Path) -> Dict[str, Any]:
    """
    Load a scenario file (YAML or JSON).
    
    Args:
        scenario_path: Path to scenario file
        
    Returns:
        Dictionary containing scenario data
    """
    with open(scenario_path, "r", encoding="utf-8") as f:
        if scenario_path.suffix in (".yaml", ".yml"):
            return yaml.safe_load(f)
        else:
            return json.load(f)


def load_all_scenarios() -> List[Dict[str, Any]]:
    """
    Load all scenario files from tests/fixtures/scenarios/.
    
    Returns:
        List of scenario dictionaries
    """
    fixtures_dir = Path(__file__).parent
    scenarios_dir = fixtures_dir / "scenarios"
    
    if not scenarios_dir.exists():
        return []
    
    scenarios = []
    for ext in ["yaml", "yml", "json"]:
        for path in scenarios_dir.glob(f"*.{ext}"):
            try:
                scenario = load_scenario_file(path)
                scenario["_file_path"] = str(path)
                scenarios.append(scenario)
            except Exception as e:
                print(f"Warning: Failed to load scenario {path}: {e}")
                continue
    
    return scenarios


def build_request_plan(scenario: Dict[str, Any]) -> RequestPlan:
    """
    Construct a RequestPlan from scenario data.
    
    Args:
        scenario: Scenario dictionary with "request_plan" key
        
    Returns:
        RequestPlan object
    """
    rp_data = scenario.get("request_plan", {})
    
    # Extract required fields
    intent = rp_data.get("intent", "general_info")
    request_type = rp_data.get("request_type", "info")
    
    # Extract entities_typed
    entities_typed = rp_data.get("entities_typed", {})
    if not isinstance(entities_typed, dict):
        entities_typed = {"movies": [], "people": []}
    if "movies" not in entities_typed:
        entities_typed["movies"] = []
    if "people" not in entities_typed:
        entities_typed["people"] = []
    
    # Extract optional fields with defaults
    need_freshness = rp_data.get("need_freshness", False)
    freshness_ttl_hours = rp_data.get("freshness_ttl_hours", 24.0)
    require_tier_a = rp_data.get("require_tier_a", False)
    allowed_source_tiers = rp_data.get("allowed_source_tiers", ["A", "B"])
    reject_tier_c = rp_data.get("reject_tier_c", True)
    response_format_str = rp_data.get("response_format", "short_fact")
    entity_years = rp_data.get("entity_years", {})
    
    # Convert response_format string to enum
    try:
        response_format = ResponseFormat(response_format_str)
    except ValueError:
        response_format = ResponseFormat.SHORT_FACT
    
    # Build RequestPlan
    # Note: constraints are not stored in RequestPlan, they're part of StructuredIntent
    return RequestPlan(
        intent=intent,
        request_type=request_type,
        entities_typed=entities_typed,
        entity_years=entity_years,
        need_freshness=need_freshness,
        freshness_ttl_hours=freshness_ttl_hours,
        freshness_reason=rp_data.get("freshness_reason"),
        require_tier_a=require_tier_a,
        allowed_source_tiers=allowed_source_tiers,
        reject_tier_c=reject_tier_c,
        response_format=response_format,
        original_query=scenario.get("user_query", ""),
        tools_to_call=[ToolType.SEARCH],  # Default, can be overridden if needed
    )


def build_evidence_bundle(scenario: Dict[str, Any]) -> EvidenceBundle:
    """
    Construct an EvidenceBundle from scenario data.
    
    Args:
        scenario: Scenario dictionary with "evidence_input" key
        
    Returns:
        EvidenceBundle object
    """
    evidence_input = scenario.get("evidence_input", [])
    
    # Convert evidence items to search_results format
    search_results = []
    for item in evidence_input:
        result = {
            "source": item.get("source", "unknown"),
            "url": item.get("url", ""),
            "title": item.get("title", ""),
            "content": item.get("content", ""),
            "year": item.get("year"),
            "tier": item.get("tier", "UNKNOWN"),
        }
        # Add release_year if year is present
        if "year" in item:
            result["release_year"] = item["year"]
        search_results.append(result)
    
    return EvidenceBundle(
        search_results=search_results,
        verified_facts=None
    )


def get_expected_checks(scenario: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract expected checks from scenario.
    
    Args:
        scenario: Scenario dictionary with "expected" key
        
    Returns:
        Dictionary with expected checks
    """
    return scenario.get("expected", {})

