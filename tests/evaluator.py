"""
Evaluation logic for testing CineMind agent responses.
"""
import asyncio
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from test_cases import TestCase
from cinemind.agent import CineMind


@dataclass
class TestResult:
    """Result of a single test case evaluation."""
    test_name: str
    passed: bool
    criteria_results: List[Tuple[str, bool, str]]  # (criterion_name, passed, message)
    actual_response: str
    actual_type: Optional[str]
    request_id: Optional[str]
    execution_time_ms: float
    errors: List[str]
    metadata: Dict
    prompt_used: Optional[str] = None  # The full prompt that was sent to the LLM
    searches: Optional[List[Dict]] = None  # Search information
    model_version: Optional[str] = None  # Model version used
    prompt_version: Optional[str] = None  # Prompt version used
    agent_config_version: Optional[str] = None  # Agent config version


class TestEvaluator:
    """Evaluates test cases against agent responses."""
    
    def __init__(self, enable_observability: bool = False):
        """
        Initialize evaluator.
        
        Args:
            enable_observability: Whether to enable observability tracking
        """
        self.enable_observability = enable_observability
    
    async def run_test(
        self, 
        test_case: TestCase, 
        agent: Optional[CineMind] = None
    ) -> TestResult:
        """
        Run a single test case with real APIs.
        
        Args:
            test_case: Test case to run
            agent: Optional pre-initialized agent (for reuse)
            
        Returns:
            TestResult with evaluation details
        """
        import time
        
        start_time = time.time()
        errors = []
        actual_response = ""
        actual_type = None
        request_id = None
        
        try:
            # Create agent if not provided
            if agent is None:
                agent = CineMind(enable_observability=self.enable_observability)
            
            # Run the test with real APIs
            result = await agent.search_and_analyze(
                test_case.prompt,
                use_live_data=True  # Always use real search
            )
            
            actual_response = result.get("response", "")
            actual_type = result.get("request_type")
            request_id = result.get("request_id")
            prompt_used = result.get("prompt", "")
            searches = result.get("searches", [])
            model_version = result.get("model_version")
            prompt_version = result.get("prompt_version")
            agent_config_version = result.get("agent_config_version")
            
        except Exception as e:
            errors.append(str(e))
            actual_response = f"ERROR: {e}"
            prompt_used = ""
            searches = []
            model_version = None
            prompt_version = None
            agent_config_version = None
        
        execution_time = (time.time() - start_time) * 1000
        
        # Evaluate against criteria
        criteria_results = self._evaluate_criteria(test_case, actual_response)
        
        # Determine if test passed
        all_passed = all(result[1] for result in criteria_results) and len(errors) == 0
        
        # Type check
        type_correct = True
        if test_case.expected_type and actual_type:
            if test_case.expected_type != actual_type:
                type_correct = False
                criteria_results.append((
                    "request_type_match",
                    False,
                    f"Expected type '{test_case.expected_type}', got '{actual_type}'"
                ))
            else:
                criteria_results.append((
                    "request_type_match",
                    True,
                    f"Type correctly classified as '{actual_type}'"
                ))
        
        passed = all_passed and type_correct
        
        return TestResult(
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
    
    def _evaluate_criteria(self, test_case: TestCase, response: str) -> List[Tuple[str, bool, str]]:
        """Evaluate response against acceptance criteria."""
        results = []
        
        for i, criterion in enumerate(test_case.acceptance_criteria):
            try:
                passed, message = criterion(response)
                results.append((f"criterion_{i+1}", passed, message))
            except Exception as e:
                results.append((f"criterion_{i+1}", False, f"Error evaluating: {e}"))
        
        return results
    
    def generate_report(self, results: List[TestResult]) -> Dict:
        """Generate evaluation report."""
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = total - passed
        
        avg_time = sum(r.execution_time_ms for r in results) / total if total > 0 else 0
        
        return {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_tests": total,
                "passed": passed,
                "failed": failed,
                "pass_rate": passed / total if total > 0 else 0,
                "avg_execution_time_ms": avg_time
            },
            "results": [asdict(r) for r in results]
        }


async def run_test_suite(
    test_cases: List[TestCase],
    evaluator: Optional[TestEvaluator] = None
) -> Dict:
    """
    Run a suite of test cases with real APIs.
    
    Args:
        test_cases: List of test cases to run
        evaluator: Optional evaluator instance
        
    Returns:
        Evaluation report
    """
    if evaluator is None:
        evaluator = TestEvaluator()
    
    results = []
    agent = None
    
    try:
        # Create agent once for all tests
        agent = CineMind(enable_observability=evaluator.enable_observability)
        
        for test_case in test_cases:
            print(f"Running: {test_case.name}...")
            result = await evaluator.run_test(test_case, agent=agent)
            results.append(result)
            
            status = "PASS" if result.passed else "FAIL"
            print(f"  {status}: {test_case.name} ({result.execution_time_ms:.2f}ms)")
            
            if not result.passed:
                for criterion_name, passed, message in result.criteria_results:
                    if not passed:
                        print(f"    - {criterion_name}: {message}")
    
    finally:
        if agent:
            await agent.close()
    
    return evaluator.generate_report(results)

