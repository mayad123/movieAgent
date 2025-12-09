"""
Test runner for CineMind agent tests.
Uses real OpenAI and Tavily APIs with confirmation prompt.
"""
import asyncio
import json
import sys
import os
from pathlib import Path
from typing import List, Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from test_cases import TEST_CASES, TEST_SUITES, TestCase
from evaluator import TestEvaluator
from cinemind.agent import CineMind


async def run_tests(
    suite_name: str = "all",
    output_file: Optional[str] = None,
    verbose: bool = False,
    skip_confirmation: bool = False
):
    """
    Run test suite with real APIs.
    
    Args:
        suite_name: Name of test suite to run
        output_file: Optional file to save results
        verbose: Show detailed output
        skip_confirmation: Skip confirmation prompt (for automation)
    """
    # Get test cases
    if suite_name not in TEST_SUITES:
        print(f"Unknown test suite: {suite_name}")
        print(f"Available suites: {', '.join(TEST_SUITES.keys())}")
        return
    
    test_cases = TEST_SUITES[suite_name]
    print(f"\n{'='*80}")
    print(f"Running test suite: {suite_name}")
    print(f"Test cases: {len(test_cases)}")
    print(f"{'='*80}\n")
    
    print("WARNING: This will make REAL API calls to OpenAI and Tavily.")
    print(f"Estimated costs:")
    print(f"  - OpenAI: ~${len(test_cases) * 0.002:.4f} (approximate)")
    print(f"  - Tavily: ~${len(test_cases) * 0.001:.4f} (approximate)")
    print(f"  - Total: ~${len(test_cases) * 0.003:.4f}")
    print(f"\nThis will execute {len(test_cases)} test queries.\n")
    
    if not skip_confirmation:
        response = input("Do you want to proceed? (yes/no): ").strip().lower()
        if response not in ['yes', 'y']:
            print("Test run cancelled.")
            return None
        print("\nStarting tests...\n")
    
    # Run tests with real APIs
    evaluator = TestEvaluator(enable_observability=False)
    report = await run_test_suite_real_apis(test_cases, evaluator, verbose)
    
    # Print summary
    print(f"\n{'='*80}")
    print("TEST SUMMARY")
    print(f"{'='*80}")
    summary = report["summary"]
    print(f"Total Tests: {summary['total_tests']}")
    print(f"Passed: {summary['passed']}")
    print(f"Failed: {summary['failed']}")
    print(f"Pass Rate: {summary['pass_rate']:.1%}")
    print(f"Avg Execution Time: {summary['avg_execution_time_ms']:.2f}ms")
    print(f"{'='*80}\n")
    
    # Show failures
    failures = [r for r in report["results"] if not r["passed"]]
    if failures:
        print(f"FAILED TESTS ({len(failures)}):")
        for failure in failures:
            print(f"\n  - {failure['test_name']}")
            for criterion_name, passed, message in failure["criteria_results"]:
                if not passed:
                    print(f"    - {criterion_name}: {message}")
            if failure["errors"]:
                print(f"    Errors: {', '.join(failure['errors'])}")
    
    # Save results - always save to test_results directory with timestamp
    from datetime import datetime
    from pathlib import Path
    
    # Create test_results directory if it doesn't exist
    results_dir = Path(__file__).parent.parent / "data" / "test_results"
    results_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate automatic filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suite_suffix = f"_{suite_name}" if suite_name != "all" else ""
    auto_filename = f"test_results{suite_suffix}_{timestamp}.json"
    auto_path = results_dir / auto_filename
    
    # Save to automatic location
    with open(auto_path, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"\nResults automatically saved to: {auto_path}")
    
    # Also save to user-specified location if provided
    if output_file:
        output_path = Path(output_file)
        # If relative path, save in test_results directory
        if not output_path.is_absolute():
            output_path = results_dir / output_file
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"Results also saved to: {output_path}")
    
    return report


async def run_test_suite_real_apis(
    test_cases: List[TestCase],
    evaluator: TestEvaluator,
    verbose: bool = False
):
    """Run tests with real OpenAI and Tavily APIs."""
    import time
    
    results = []
    agent = None
    
    try:
        # Create agent once for all tests
        agent = CineMind(enable_observability=False)
        
        for i, test_case in enumerate(test_cases, 1):
            if verbose:
                print(f"\n[{i}/{len(test_cases)}] Running: {test_case.name}")
                print(f"  Prompt: {test_case.prompt}")
            else:
                print(f"[{i}/{len(test_cases)}] Running: {test_case.name}...")
            
            start_time = time.time()
            errors = []
            actual_response = ""
            actual_type = None
            request_id = None
            prompt_used = ""
            searches = []
            model_version = None
            prompt_version = None
            agent_config_version = None
            
            try:
                # Run with real APIs
                api_result = await agent.search_and_analyze(
                    test_case.prompt,
                    use_live_data=True  # Use real search
                )
                
                actual_response = api_result.get("response", "")
                actual_type = api_result.get("request_type")
                request_id = api_result.get("request_id")
                prompt_used = api_result.get("prompt", "")
                searches = api_result.get("searches", [])
                model_version = api_result.get("model_version")
                prompt_version = api_result.get("prompt_version")
                agent_config_version = api_result.get("agent_config_version")
                
            except Exception as e:
                errors.append(str(e))
                actual_response = f"ERROR: {e}"
                if verbose:
                    import traceback
                    traceback.print_exc()
            
            execution_time = (time.time() - start_time) * 1000
            
            # Evaluate criteria
            criteria_results = evaluator._evaluate_criteria(test_case, actual_response)
            
            # Type check
            if test_case.expected_type and actual_type:
                if test_case.expected_type != actual_type:
                    criteria_results.append((
                        "request_type_match",
                        False,
                        f"Expected '{test_case.expected_type}', got '{actual_type}'"
                    ))
                else:
                    criteria_results.append((
                        "request_type_match",
                        True,
                        f"Type correctly classified as '{actual_type}'"
                    ))
            
            passed = all(r[1] for r in criteria_results) and len(errors) == 0
            
            from evaluator import TestResult
            result = TestResult(
                test_name=test_case.name,
                passed=passed,
                criteria_results=criteria_results,
                actual_response=actual_response,
                actual_type=actual_type,
                request_id=request_id,
                execution_time_ms=execution_time,
                errors=errors,
                metadata=test_case.metadata,
                prompt_used=prompt_used,
                searches=searches,
                model_version=model_version,
                prompt_version=prompt_version,
                agent_config_version=agent_config_version
            )
            results.append(result)
            
            status = "PASS" if passed else "FAIL"
            if verbose:
                print(f"  {status}")
                print(f"  Response: {actual_response[:200]}...")
                if result.errors:
                    print(f"  Errors: {result.errors}")
            else:
                print(f"  {status}: {test_case.name} ({execution_time:.2f}ms)")
    
    finally:
        if agent:
            await agent.close()
    
    return evaluator.generate_report(results)


def main():
    """Main entry point for test runner."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run CineMind agent tests with real APIs")
    parser.add_argument(
        '--suite',
        default='all',
        choices=list(TEST_SUITES.keys()),
        help='Test suite to run'
    )
    parser.add_argument(
        '--output',
        help='Output file for results (JSON)'
    )
    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help='Verbose output'
    )
    parser.add_argument(
        '--yes',
        '-y',
        action='store_true',
        help='Skip confirmation prompt (for automation)'
    )
    
    args = parser.parse_args()
    
    # Run tests
    report = asyncio.run(run_tests(
        suite_name=args.suite,
        output_file=args.output,
        verbose=args.verbose,
        skip_confirmation=args.yes
    ))
    
    if report is None:
        # User cancelled
        sys.exit(0)
    
    # Exit with error code if tests failed
    if report["summary"]["failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()

