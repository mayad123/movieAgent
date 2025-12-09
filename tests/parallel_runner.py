"""
Parallel test execution for faster test runs.
Runs multiple tests concurrently while respecting API rate limits.
"""
import asyncio
import time
from typing import List, Optional
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from test_cases import TEST_CASES, TestCase
from evaluator import TestEvaluator, TestResult
from cinemind.agent import CineMind


async def run_tests_parallel(
    test_cases: List[TestCase],
    max_concurrent: int = 3,
    evaluator: Optional[TestEvaluator] = None,
    verbose: bool = False
) -> List[TestResult]:
    """
    Run tests in parallel batches.
    
    Args:
        test_cases: List of test cases to run
        max_concurrent: Maximum number of tests to run concurrently
        evaluator: Optional evaluator instance
        verbose: Show detailed output
        
    Returns:
        List of test results
    """
    if evaluator is None:
        evaluator = TestEvaluator(enable_observability=False)
    
    results = []
    agent = None
    
    try:
        # Create agent once for all tests
        agent = CineMind(enable_observability=evaluator.enable_observability)
        
        # Create semaphore to limit concurrent executions
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def run_single_test(test_case: TestCase) -> TestResult:
            """Run a single test with semaphore limiting."""
            async with semaphore:
                if verbose:
                    print(f"Running: {test_case.name}...")
                else:
                    print(f"[{test_cases.index(test_case) + 1}/{len(test_cases)}] {test_case.name}...", end=" ", flush=True)
                
                result = await evaluator.run_test(test_case, agent=agent)
                
                status = "PASS" if result.passed else "FAIL"
                if not verbose:
                    print(f"{status} ({result.execution_time_ms:.0f}ms)")
                else:
                    print(f"  {status}: {test_case.name} ({result.execution_time_ms:.2f}ms)")
                    if not result.passed:
                        for criterion_name, passed, message in result.criteria_results:
                            if not passed:
                                print(f"    - {criterion_name}: {message}")
                
                return result
        
        # Run all tests in parallel (with concurrency limit)
        start_time = time.time()
        results = await asyncio.gather(*[run_single_test(tc) for tc in test_cases])
        total_time = time.time() - start_time
        
        print(f"\nCompleted {len(results)} tests in {total_time:.2f}s")
        print(f"Average: {total_time / len(results):.2f}s per test")
        
    finally:
        if agent:
            await agent.close()
    
    return results


async def run_test_suite_parallel(
    test_cases: List[TestCase],
    evaluator: Optional[TestEvaluator] = None,
    max_concurrent: int = 3,
    verbose: bool = False
) -> dict:
    """
    Run test suite in parallel and generate report.
    
    Args:
        test_cases: List of test cases
        evaluator: Optional evaluator
        max_concurrent: Max concurrent tests
        verbose: Verbose output
        
    Returns:
        Evaluation report
    """
    if evaluator is None:
        evaluator = TestEvaluator(enable_observability=False)
    
    results = await run_tests_parallel(
        test_cases=test_cases,
        max_concurrent=max_concurrent,
        evaluator=evaluator,
        verbose=verbose
    )
    
    return evaluator.generate_report(results)

