"""
Interactive test runner with flexible test case and prompt version selection.

Allows selecting:
- Specific test cases (by name, suite, or all)
- Specific prompt versions (multiple or all)
- Run combinations of tests x versions
"""
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


from evaluator import TestEvaluator
from test_runner import run_test_suite_real_apis

import config
from cinemind.prompting.versions import PROMPT_VERSIONS, get_prompt_version, list_versions
from test_cases import TEST_CASES, TEST_SUITES, TestCase


def display_test_cases() -> dict[str, TestCase]:
    """Display all test cases and return a mapping of name to test case."""
    print("\n" + "=" * 80)
    print("AVAILABLE TEST CASES")
    print("=" * 80)

    test_map = {}
    suites = {}

    # Group by suite
    for suite_name, suite_tests in TEST_SUITES.items():
        if suite_name != "all":
            suites[suite_name] = suite_tests

    # Display by suite
    for suite_name, suite_tests in sorted(suites.items()):
        print(f"\n[{suite_name.upper()}] ({len(suite_tests)} tests)")
        for test in suite_tests:
            test_map[test.name] = test
            print(f"  {test.name}: {test.prompt[:60]}...")

    # Also show all individual tests
    print(f"\n[ALL INDIVIDUAL TESTS] ({len(TEST_CASES)} tests)")
    for test in TEST_CASES:
        if test.name not in test_map:
            test_map[test.name] = test
        print(f"  {test.name}")

    print("\n" + "=" * 80)
    return test_map


def display_prompt_versions() -> dict[str, dict]:
    """Display all prompt versions and return metadata."""
    print("\n" + "=" * 80)
    print("AVAILABLE PROMPT VERSIONS")
    print("=" * 80)

    versions = list_versions()
    for version, meta in sorted(versions.items()):
        print(f"\n{version}:")
        print(f"  Description: {meta.get('description', 'N/A')}")
        print(f"  Length: {meta.get('length', 0)} chars, {meta.get('tokens', 0)} tokens")

    print("\n" + "=" * 80)
    return versions


def select_test_cases(interactive: bool = True) -> list[TestCase]:
    """Select test cases to run."""
    if interactive:
        display_test_cases()
        print("\nSelect test cases to run:")
        print("  - Enter test case names separated by commas (e.g., simple_fact_director,simple_fact_release_date)")
        print("  - Enter suite names (e.g., simple,multi_hop)")
        print("  - Enter 'all' for all test cases")
        print("  - Enter 'suite:simple' for a specific suite")
        print()

        selection = input("Selection: ").strip()
    else:
        # For non-interactive, default to all
        selection = "all"

    return parse_test_selection(selection)


def parse_test_selection(selection: str) -> list[TestCase]:
    """Parse test case selection string."""
    selection = selection.strip().lower()

    if selection == "all":
        return list(TEST_CASES)

    selected_tests = []
    parts = [p.strip() for p in selection.split(",")]

    test_map = {test.name: test for test in TEST_CASES}

    for part in parts:
        if part.startswith("suite:"):
            suite_name = part.replace("suite:", "").strip()
            if suite_name in TEST_SUITES:
                selected_tests.extend(TEST_SUITES[suite_name])
            else:
                print(f"Warning: Unknown suite '{suite_name}'")
        elif part in TEST_SUITES:
            # Direct suite name
            selected_tests.extend(TEST_SUITES[part])
        elif part in test_map:
            # Individual test name
            selected_tests.append(test_map[part])
        else:
            print(f"Warning: Unknown test case or suite '{part}'")

    # Remove duplicates while preserving order
    seen = set()
    unique_tests = []
    for test in selected_tests:
        if test.name not in seen:
            seen.add(test.name)
            unique_tests.append(test)

    return unique_tests


def select_prompt_versions(interactive: bool = True) -> list[str]:
    """Select prompt versions to run."""
    available_versions = list(PROMPT_VERSIONS.keys())

    if interactive:
        display_prompt_versions()
        print("\nSelect prompt versions to test:")
        print("  - Enter version names separated by commas (e.g., v1,v2_optimized)")
        print(f"  - Enter 'all' for all versions ({', '.join(available_versions)})")
        print()

        selection = input("Selection: ").strip()
    else:
        selection = "all"

    return parse_version_selection(selection)


def parse_version_selection(selection: str) -> list[str]:
    """Parse prompt version selection string."""
    selection = selection.strip().lower()

    if selection == "all":
        return list(PROMPT_VERSIONS.keys())

    selected_versions = []
    parts = [p.strip() for p in selection.split(",")]

    for part in parts:
        if part in PROMPT_VERSIONS:
            selected_versions.append(part)
        else:
            print(f"Warning: Unknown prompt version '{part}'")

    # Remove duplicates
    return list(dict.fromkeys(selected_versions))  # Preserves order


async def run_test_combination(
    test_cases: list[TestCase],
    prompt_versions: list[str],
    verbose: bool = False,
    parallel: bool = False,
    max_concurrent: int = 3,
    skip_confirmation: bool = False
) -> dict:
    """
    Run tests with all combinations of test_cases x prompt_versions.

    Returns a dictionary with results organized by prompt version.
    """
    total_combinations = len(test_cases) * len(prompt_versions)

    print("\n" + "=" * 80)
    print("TEST RUN CONFIGURATION")
    print("=" * 80)
    print(f"Test Cases: {len(test_cases)}")
    print(f"Prompt Versions: {len(prompt_versions)} ({', '.join(prompt_versions)})")
    print(f"Total Test Runs: {total_combinations}")
    print(f"Parallel Execution: {'Yes' if parallel else 'No'}")
    if parallel:
        print(f"Max Concurrent: {max_concurrent}")

    # Estimate costs
    estimated_cost = total_combinations * 0.003
    print(f"\nEstimated Cost: ~${estimated_cost:.4f}")
    print("=" * 80)

    if not skip_confirmation:
        response = input("\nProceed with test run? (yes/no): ").strip().lower()
        if response not in ['yes', 'y']:
            print("Test run cancelled.")
            return None

    print("\nStarting test runs...\n")

    results = {}

    # Store original prompt
    original_prompt = config.SYSTEM_PROMPT

    try:
        for version_idx, version in enumerate(prompt_versions, 1):
            print(f"\n{'='*80}")
            print(f"[{version_idx}/{len(prompt_versions)}] Testing Prompt Version: {version}")
            print(f"{'='*80}")

            # Update config to use this version
            config.SYSTEM_PROMPT = get_prompt_version(version)

            # Run tests for this version
            evaluator = TestEvaluator(enable_observability=False)

            if parallel:
                from parallel_runner import run_test_suite_parallel
                report = await run_test_suite_parallel(
                    test_cases, evaluator, max_concurrent=max_concurrent, verbose=verbose
                )
            else:
                report = await run_test_suite_real_apis(test_cases, evaluator, verbose)

            # Add version metadata
            report['prompt_version'] = version
            report['prompt_text'] = get_prompt_version(version)

            results[version] = report

            # Print summary for this version
            summary = report['summary']
            print(f"\n{version} Results:")
            print(f"  Pass Rate: {summary['pass_rate']:.1%} ({summary['passed']}/{summary['total_tests']})")
            print(f"  Avg Time: {summary['avg_execution_time_ms']:.2f}ms")
            if summary['failed'] > 0:
                print(f"  Failed: {summary['failed']}")

    finally:
        # Restore original prompt
        config.SYSTEM_PROMPT = original_prompt

    return results


def save_results(results: dict, output_dir: str | None = None) -> Path:
    """Save test results to files."""
    from pathlib import Path

    if output_dir is None:
        # Default location with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path(__file__).parent.parent / "data" / "test_results" / f"interactive_{timestamp}"
    else:
        output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Save individual version results
    for version, report in results.items():
        filename = output_dir / f"{version}_results.json"
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)

    # Create combined summary
    summary = {
        "timestamp": datetime.now().isoformat(),
        "test_count": len(results[next(iter(results.keys()))]["results"]) if results else 0,
        "versions": {},
        "comparison": {}
    }

    # Collect stats per version
    for version, report in results.items():
        summary["versions"][version] = {
            "pass_rate": report["summary"]["pass_rate"],
            "passed": report["summary"]["passed"],
            "failed": report["summary"]["failed"],
            "avg_time_ms": report["summary"]["avg_execution_time_ms"],
            "total_tests": report["summary"]["total_tests"]
        }

    # Find best version
    if results:
        best_version = max(
            results.keys(),
            key=lambda v: results[v]["summary"]["pass_rate"]
        )
        summary["comparison"]["best_version"] = best_version
        summary["comparison"]["best_pass_rate"] = results[best_version]["summary"]["pass_rate"]

    # Save summary
    summary_file = output_dir / "summary.json"
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)

    return output_dir


def print_final_summary(results: dict):
    """Print final summary of all test runs."""
    print("\n" + "=" * 80)
    print("FINAL SUMMARY")
    print("=" * 80)

    if not results:
        print("No results to display.")
        return

    # Compare versions
    print("\nVersion Comparison:")
    for version in sorted(results.keys()):
        report = results[version]
        summary = report["summary"]
        print(f"\n{version}:")
        print(f"  Pass Rate: {summary['pass_rate']:.1%} ({summary['passed']}/{summary['total_tests']})")
        print(f"  Failed: {summary['failed']}")
        print(f"  Avg Time: {summary['avg_execution_time_ms']:.2f}ms")

    # Best version
    best_version = max(
        results.keys(),
        key=lambda v: results[v]["summary"]["pass_rate"]
    )
    best_rate = results[best_version]["summary"]["pass_rate"]

    print(f"\n{'='*80}")
    print(f"Best Version: {best_version} ({best_rate:.1%} pass rate)")
    print("=" * 80)


async def run_interactive_mode():
    """Run in interactive mode with menus."""
    print("\n" + "=" * 80)
    print("CINEMIND INTERACTIVE TEST RUNNER")
    print("=" * 80)

    # Select test cases
    test_cases = select_test_cases(interactive=True)

    if not test_cases:
        print("No test cases selected. Exiting.")
        return

    print(f"\n✓ Selected {len(test_cases)} test case(s)")

    # Select prompt versions
    prompt_versions = select_prompt_versions(interactive=True)

    if not prompt_versions:
        print("No prompt versions selected. Exiting.")
        return

    print(f"\n✓ Selected {len(prompt_versions)} prompt version(s): {', '.join(prompt_versions)}")

    # Additional options
    print("\nAdditional Options:")
    verbose = input("Verbose output? (y/n, default: n): ").strip().lower() == 'y'
    parallel = input("Parallel execution? (y/n, default: n): ").strip().lower() == 'y'
    max_concurrent = 3
    if parallel:
        try:
            max_concurrent = int(input("Max concurrent tests (default: 3): ").strip() or "3")
        except ValueError:
            max_concurrent = 3

    # Run tests
    results = await run_test_combination(
        test_cases=test_cases,
        prompt_versions=prompt_versions,
        verbose=verbose,
        parallel=parallel,
        max_concurrent=max_concurrent,
        skip_confirmation=False
    )

    if results:
        # Save results
        output_dir = save_results(results)
        print(f"\nResults saved to: {output_dir}")

        # Print summary
        print_final_summary(results)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Interactive test runner with flexible test case and prompt version selection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode (menu-based selection)
  python tests/test_runner_interactive.py

  # Command-line mode - specific test cases and versions
  python tests/test_runner_interactive.py --tests simple_fact_director,simple_fact_release_date --versions v1,v2_optimized

  # Command-line mode - test suite and all versions
  python tests/test_runner_interactive.py --tests suite:simple --versions all

  # Command-line mode - all tests, specific versions, parallel execution
  python tests/test_runner_interactive.py --tests all --versions v1,v4 --parallel --max-concurrent 5
        """
    )

    parser.add_argument(
        '--tests',
        type=str,
        default=None,
        help='Test cases to run: comma-separated names, suite names, "suite:name", or "all"'
    )
    parser.add_argument(
        '--versions',
        type=str,
        default=None,
        help='Prompt versions to test: comma-separated names or "all"'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Output directory for results (default: auto-generated with timestamp)'
    )
    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help='Verbose output'
    )
    parser.add_argument(
        '--parallel',
        action='store_true',
        help='Run tests in parallel'
    )
    parser.add_argument(
        '--max-concurrent',
        type=int,
        default=3,
        help='Max concurrent tests when using --parallel (default: 3)'
    )
    parser.add_argument(
        '--yes',
        '-y',
        action='store_true',
        help='Skip confirmation prompt'
    )

    args = parser.parse_args()

    # Determine mode
    if args.tests is None and args.versions is None:
        # Interactive mode
        asyncio.run(run_interactive_mode())
    else:
        # Command-line mode
        # Parse selections
        test_cases = parse_test_selection(args.tests) if args.tests else list(TEST_CASES)

        prompt_versions = parse_version_selection(args.versions) if args.versions else list(PROMPT_VERSIONS.keys())

        if not test_cases:
            print("Error: No valid test cases selected.")
            sys.exit(1)

        if not prompt_versions:
            print("Error: No valid prompt versions selected.")
            sys.exit(1)

        print(f"\nSelected {len(test_cases)} test case(s) and {len(prompt_versions)} prompt version(s)")

        # Run tests
        results = asyncio.run(run_test_combination(
            test_cases=test_cases,
            prompt_versions=prompt_versions,
            verbose=args.verbose,
            parallel=args.parallel,
            max_concurrent=args.max_concurrent,
            skip_confirmation=args.yes
        ))

        if results:
            # Save results
            output_dir = save_results(results, args.output)
            print(f"\nResults saved to: {output_dir}")

            # Print summary
            print_final_summary(results)
        else:
            sys.exit(0)


if __name__ == "__main__":
    main()

