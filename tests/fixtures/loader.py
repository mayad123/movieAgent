"""
Fixture loader utility for loading scenario JSON/YAML files.
"""
import json
import yaml
from pathlib import Path
from typing import Dict, Any, Optional


def load_scenario(scenario_name: str, format: str = "json") -> Dict[str, Any]:
    """
    Load a scenario file from tests/fixtures/scenarios/.
    
    Args:
        scenario_name: Name of the scenario file (without extension)
        format: File format, either "json" or "yaml"
    
    Returns:
        Dictionary containing scenario data
    
    Raises:
        FileNotFoundError: If scenario file doesn't exist
        ValueError: If format is invalid
    """
    if format not in ("json", "yaml", "yml"):
        raise ValueError(f"Invalid format: {format}. Must be 'json' or 'yaml'")
    
    # Determine file extension
    ext = "yaml" if format == "yml" else format
    
    # Build path to scenario file
    fixtures_dir = Path(__file__).parent
    scenarios_dir = fixtures_dir / "scenarios"
    scenario_path = scenarios_dir / f"{scenario_name}.{ext}"
    
    if not scenario_path.exists():
        raise FileNotFoundError(f"Scenario file not found: {scenario_path}")
    
    # Load and parse file
    with open(scenario_path, "r", encoding="utf-8") as f:
        if format in ("json",):
            return json.load(f)
        else:  # yaml or yml
            return yaml.safe_load(f)


def list_scenarios(format: Optional[str] = None) -> list[str]:
    """
    List all available scenario files.
    
    Args:
        format: Optional filter by format ("json" or "yaml")
    
    Returns:
        List of scenario names (without extensions)
    """
    fixtures_dir = Path(__file__).parent
    scenarios_dir = fixtures_dir / "scenarios"
    
    if not scenarios_dir.exists():
        return []
    
    scenarios = []
    for ext in ["json", "yaml", "yml"]:
        if format and ext != format and (format == "yaml" and ext != "yml"):
            continue
        for path in scenarios_dir.glob(f"*.{ext}"):
            scenarios.append(path.stem)
    
    # Remove duplicates while preserving order
    return list(dict.fromkeys(scenarios))

