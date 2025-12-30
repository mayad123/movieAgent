"""
CLI entry point for CineMind evaluation tools.

Usage:
    python -m cinemind.eval list-violations
    python -m cinemind.eval show-violation --scenario <name>
"""
import sys
import argparse
from pathlib import Path
import json


def find_test_reports_dir() -> Path:
    """
    Find the test_reports directory relative to the project root.
    
    Returns:
        Path to test_reports directory
    """
    # Try to find from current working directory
    current = Path.cwd()
    
    # Look for test_reports in common locations
    possible_paths = [
        current / "tests" / "test_reports",
        current / "test_reports",
        # If running from src/cinemind/eval, go up multiple levels
        current.parent.parent.parent / "tests" / "test_reports",
    ]
    
    for path in possible_paths:
        if path.exists() and path.is_dir():
            return path
    
    # Default assumption: we're in project root
    return current / "tests" / "test_reports"


def load_violations_index(reports_dir: Path) -> dict:
    """
    Load the violations index JSON file.
    
    Args:
        reports_dir: Path to test_reports directory
    
    Returns:
        Dictionary containing violations index data
    
    Raises:
        FileNotFoundError: If violations_index.json doesn't exist
        json.JSONDecodeError: If file is not valid JSON
    """
    index_file = reports_dir / "violations_index.json"
    
    if not index_file.exists():
        raise FileNotFoundError(
            f"Violations index not found at {index_file}. "
            "Run tests first to generate violation artifacts."
        )
    
    with open(index_file, "r", encoding="utf-8") as f:
        return json.load(f)


def load_violation_artifact(reports_dir: Path, scenario_name: str) -> dict:
    """
    Load a violation artifact JSON file for a specific scenario.
    
    Args:
        reports_dir: Path to test_reports directory
        scenario_name: Name of the scenario (will be sanitized to match filename)
    
    Returns:
        Dictionary containing violation artifact data
    
    Raises:
        FileNotFoundError: If artifact file doesn't exist
        json.JSONDecodeError: If file is not valid JSON
    """
    violations_dir = reports_dir / "violations"
    
    # Sanitize scenario name to match how it's stored in filename
    safe_name = sanitize_filename(scenario_name)
    artifact_file = violations_dir / f"{safe_name}.json"
    
    if not artifact_file.exists():
        raise FileNotFoundError(
            f"Violation artifact not found for scenario '{scenario_name}'. "
            f"Expected: {artifact_file}"
        )
    
    with open(artifact_file, "r", encoding="utf-8") as f:
        return json.load(f)


def sanitize_filename(name: str) -> str:
    """
    Sanitize scenario name to safe filename (matching violation_artifact_writer logic).
    
    Args:
        name: Scenario name
    
    Returns:
        Safe filename string
    """
    import re
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


def cmd_list_violations(args):
    """List all scenarios with violations."""
    try:
        reports_dir = find_test_reports_dir()
        index = load_violations_index(reports_dir)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse violations index: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    
    scenarios = index.get("scenarios", [])
    total = index.get("total_scenarios_with_violations", len(scenarios))
    
    if total == 0:
        print("✓ No violations found. All scenarios are clean!")
        return
    
    print(f"\nFound {total} scenario(s) with violations:\n")
    print(f"{'Scenario Name':<40} {'Template ID':<20} {'Violations':<15} {'Types'}")
    print("=" * 100)
    
    for scenario in scenarios:
        name = scenario.get("scenario_name", "unknown")
        template_id = scenario.get("template_id", "unknown")
        count = scenario.get("violation_count", 0)
        types = ", ".join(scenario.get("violation_types", []))
        
        print(f"{name:<40} {template_id:<20} {count:<15} {types}")
    
    print(f"\nUse 'python -m cinemind.eval show-violation --scenario <name>' to see details.")


def cmd_show_violation(args):
    """Show detailed violation information for a specific scenario."""
    scenario_name = args.scenario
    
    try:
        reports_dir = find_test_reports_dir()
        artifact = load_violation_artifact(reports_dir, scenario_name)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        print(f"\nAvailable scenarios can be listed with: python -m cinemind.eval list-violations", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse violation artifact: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Print scenario information
    print(f"\n{'='*80}")
    print(f"Scenario: {artifact.get('scenario_name', scenario_name)}")
    print(f"{'='*80}\n")
    
    # User query
    user_query = artifact.get("user_query", "")
    if user_query:
        print(f"User Query:")
        print(f"  {user_query}\n")
    
    # Template ID
    template_id = artifact.get("template_id")
    if template_id:
        print(f"Template ID: {template_id}\n")
    
    # Violations
    violations = artifact.get("violations", [])
    violation_count = artifact.get("violation_count", len(violations))
    
    if violations:
        print(f"Violations ({violation_count}):")
        print("-" * 80)
        for i, violation in enumerate(violations, 1):
            violation_type = violation.get("type", "unknown")
            message = violation.get("message", "")
            print(f"  {i}. [{violation_type}] {message}")
        print()
    else:
        print("No violations found.\n")
    
    # Offending text
    offending_text = artifact.get("offending_text", "")
    if offending_text:
        print("Offending Text:")
        print("-" * 80)
        print(offending_text)
        print("-" * 80)
        print()
    
    # Fixed text (if any)
    fixed_text = artifact.get("fixed_text")
    if fixed_text:
        print("Fixed Text (auto-corrected):")
        print("-" * 80)
        print(fixed_text)
        print("-" * 80)
        print()
    
    # Repair instruction (if any)
    repair_instruction = artifact.get("repair_instruction")
    if repair_instruction:
        print("Repair Instruction:")
        print("-" * 80)
        print(repair_instruction)
        print("-" * 80)
        print()


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="CineMind evaluation tools for inspecting test violations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all scenarios with violations
  python -m cinemind.eval list-violations
  
  # Show detailed violation information for a specific scenario
  python -m cinemind.eval show-violation --scenario director_matrix
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    subparsers.required = True
    
    # list-violations command
    list_parser = subparsers.add_parser(
        "list-violations",
        help="List all scenarios with violations"
    )
    list_parser.set_defaults(func=cmd_list_violations)
    
    # show-violation command
    show_parser = subparsers.add_parser(
        "show-violation",
        help="Show detailed violation information for a specific scenario"
    )
    show_parser.add_argument(
        "--scenario",
        required=True,
        help="Name of the scenario to show violations for"
    )
    show_parser.set_defaults(func=cmd_show_violation)
    
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

