"""
Test runner for comparing different prompt versions using real APIs.
"""
import asyncio
import json
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from test_cases import TEST_CASES, TEST_SUITES
from evaluator import TestEvaluator
from test_runner import run_test_suite_real_apis
from prompt_versions import PROMPT_VERSIONS, list_versions
from config import get_system_prompt


async def compare_prompt_versions(
    versions: list = None,
    test_suite: str = "all",
    output_dir: str = "prompt_comparison",
    skip_confirmation: bool = False
):
    """
    Compare multiple prompt versions on the same test suite using real APIs.
    
    Args:
        versions: List of versions to compare (default: all)
        test_suite: Test suite to use
        output_dir: Directory to save comparison results
        skip_confirmation: Skip confirmation prompt
    """
    import os
    
    if versions is None:
        versions = list(PROMPT_VERSIONS.keys())
    
    # Get test cases
    test_cases = TEST_SUITES.get(test_suite, TEST_CASES)
    
    print(f"\n{'='*80}")
    print(f"PROMPT VERSION COMPARISON")
    print(f"{'='*80}")
    print(f"Versions: {', '.join(versions)}")
    print(f"Test Suite: {test_suite} ({len(test_cases)} tests)")
    print(f"\nWARNING: This will make REAL API calls to OpenAI and Tavily.")
    total_tests = len(versions) * len(test_cases)
    print(f"Total API calls: {total_tests}")
    print(f"Estimated cost: ~${total_tests * 0.003:.4f}\n")
    
    if not skip_confirmation:
        response = input("Do you want to proceed? (yes/no): ").strip().lower()
        if response not in ['yes', 'y']:
            print("Comparison cancelled.")
            return None
    
    print(f"{'='*80}\n")
    
    results = {}
    
    for version in versions:
        print(f"\nTesting version: {version}")
        print(f"Prompt length: {len(PROMPT_VERSIONS[version])} chars")
        
        # Update config to use this version
        import config
        original_prompt = config.SYSTEM_PROMPT
        config.SYSTEM_PROMPT = get_system_prompt(version)
        
        try:
            # Run tests with real APIs
            evaluator = TestEvaluator(enable_observability=False)
            report = await run_test_suite_real_apis(test_cases, evaluator, verbose=False)
            results[version] = report
            
            print(f"  Pass Rate: {report['summary']['pass_rate']:.1%}")
            print(f"  Avg Time: {report['summary']['avg_execution_time_ms']:.2f}ms")
            
        finally:
            # Restore original
            config.SYSTEM_PROMPT = original_prompt
    
    # Generate comparison
    comparison = {
        "test_suite": test_suite,
        "test_count": len(test_cases),
        "versions": {},
        "summary": {}
    }
    
    for version, report in results.items():
        comparison["versions"][version] = {
            "pass_rate": report["summary"]["pass_rate"],
            "passed": report["summary"]["passed"],
            "failed": report["summary"]["failed"],
            "avg_time_ms": report["summary"]["avg_execution_time_ms"],
            "prompt_length": len(PROMPT_VERSIONS[version])
        }
    
    # Find best version
    best_version = max(
        results.keys(),
        key=lambda v: results[v]["summary"]["pass_rate"]
    )
    
    comparison["summary"]["best_version"] = best_version
    comparison["summary"]["best_pass_rate"] = results[best_version]["summary"]["pass_rate"]
    
    # Save results
    os.makedirs(output_dir, exist_ok=True)
    
    # Save individual results
    for version, report in results.items():
        filename = os.path.join(output_dir, f"{version}_results.json")
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
    
    # Save comparison
    comparison_file = os.path.join(output_dir, "comparison.json")
    with open(comparison_file, 'w') as f:
        json.dump(comparison, f, indent=2)
    
    # Print summary
    print(f"\n{'='*80}")
    print("COMPARISON SUMMARY")
    print(f"{'='*80}")
    for version in versions:
        stats = comparison["versions"][version]
        print(f"{version}:")
        print(f"  Pass Rate: {stats['pass_rate']:.1%} ({stats['passed']}/{len(test_cases)})")
        print(f"  Avg Time: {stats['avg_time_ms']:.2f}ms")
        print(f"  Prompt Length: {stats['prompt_length']} chars")
    
    print(f"\nBest Version: {best_version} ({comparison['summary']['best_pass_rate']:.1%})")
    print(f"\nResults saved to: {output_dir}/")
    print(f"{'='*80}\n")
    
    return comparison


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Compare prompt versions using real APIs")
    parser.add_argument(
        '--versions',
        nargs='+',
        default=None,
        help='Versions to compare (default: all)'
    )
    parser.add_argument(
        '--suite',
        default='all',
        help='Test suite to use'
    )
    parser.add_argument(
        '--output',
        default='prompt_comparison',
        help='Output directory'
    )
    parser.add_argument(
        '--yes',
        '-y',
        action='store_true',
        help='Skip confirmation prompt'
    )
    
    args = parser.parse_args()
    
    result = asyncio.run(compare_prompt_versions(
        versions=args.versions,
        test_suite=args.suite,
        output_dir=args.output,
        skip_confirmation=args.yes
    ))
    
    if result is None:
        sys.exit(0)


if __name__ == "__main__":
    main()

