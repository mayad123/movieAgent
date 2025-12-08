"""
Utility to view and compare historical test results.
"""
import json
import sys
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import argparse


def load_all_results(results_dir: Path) -> List[Dict]:
    """Load all test result files from directory."""
    results = []
    
    if not results_dir.exists():
        print(f"Results directory not found: {results_dir}")
        return results
    
    for result_file in sorted(results_dir.glob("test_results*.json"), reverse=True):
        try:
            with open(result_file, 'r') as f:
                data = json.load(f)
                data['_filename'] = result_file.name
                data['_filepath'] = str(result_file)
                results.append(data)
        except Exception as e:
            print(f"Error loading {result_file}: {e}")
    
    return results


def print_summary(results: List[Dict]):
    """Print summary of all test runs."""
    print(f"\n{'='*80}")
    print("TEST RESULTS SUMMARY")
    print(f"{'='*80}\n")
    
    if not results:
        print("No test results found.")
        return
    
    print(f"Total test runs: {len(results)}\n")
    
    for i, result in enumerate(results, 1):
        summary = result.get("summary", {})
        timestamp = result.get("timestamp", "Unknown")
        filename = result.get("_filename", "Unknown")
        
        # Parse timestamp for display
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            time_str = timestamp
        
        print(f"{i}. {filename}")
        print(f"   Time: {time_str}")
        print(f"   Tests: {summary.get('total_tests', 0)} | "
              f"Passed: {summary.get('passed', 0)} | "
              f"Failed: {summary.get('failed', 0)} | "
              f"Pass Rate: {summary.get('pass_rate', 0):.1%}")
        print(f"   Avg Time: {summary.get('avg_execution_time_ms', 0):.2f}ms")
        print()


def print_detailed(result: Dict):
    """Print detailed view of a single test result."""
    print(f"\n{'='*80}")
    print(f"DETAILED TEST RESULTS: {result.get('_filename', 'Unknown')}")
    print(f"{'='*80}\n")
    
    summary = result.get("summary", {})
    print(f"Summary:")
    print(f"  Total Tests: {summary.get('total_tests', 0)}")
    print(f"  Passed: {summary.get('passed', 0)}")
    print(f"  Failed: {summary.get('failed', 0)}")
    print(f"  Pass Rate: {summary.get('pass_rate', 0):.1%}")
    print(f"  Avg Execution Time: {summary.get('avg_execution_time_ms', 0):.2f}ms")
    print(f"  Timestamp: {result.get('timestamp', 'Unknown')}")
    
    print(f"\n{'='*80}")
    print("INDIVIDUAL TEST RESULTS")
    print(f"{'='*80}\n")
    
    for test_result in result.get("results", []):
        status = "PASS" if test_result.get("passed") else "FAIL"
        print(f"{status}: {test_result.get('test_name', 'Unknown')}")
        print(f"  Type: {test_result.get('actual_type', 'N/A')}")
        print(f"  Time: {test_result.get('execution_time_ms', 0):.2f}ms")
        
        # Show failed criteria
        failed_criteria = [
            (name, msg) for name, passed, msg in test_result.get("criteria_results", [])
            if not passed
        ]
        if failed_criteria:
            print(f"  Failed Criteria:")
            for name, msg in failed_criteria:
                print(f"    - {name}: {msg}")
        
        # Show response preview
        response = test_result.get("actual_response", "")
        if response:
            preview = response[:200] + "..." if len(response) > 200 else response
            print(f"  Response: {preview}")
        print()


def compare_results(results: List[Dict], limit: int = 5):
    """Compare the most recent N test runs."""
    if len(results) < 2:
        print("Need at least 2 test runs to compare.")
        return
    
    recent = results[:limit]
    
    print(f"\n{'='*80}")
    print(f"COMPARING LAST {len(recent)} TEST RUNS")
    print(f"{'='*80}\n")
    
    # Compare summary metrics
    print("Summary Comparison:")
    print(f"{'Run':<30} {'Tests':<8} {'Passed':<8} {'Failed':<8} {'Pass Rate':<12} {'Avg Time':<12}")
    print("-" * 80)
    
    for result in recent:
        summary = result.get("summary", {})
        filename = result.get("_filename", "Unknown")[:28]
        print(f"{filename:<30} "
              f"{summary.get('total_tests', 0):<8} "
              f"{summary.get('passed', 0):<8} "
              f"{summary.get('failed', 0):<8} "
              f"{summary.get('pass_rate', 0):.1%:<12} "
              f"{summary.get('avg_execution_time_ms', 0):.2f}ms")
    
    # Compare individual test results
    if len(recent) >= 2:
        print(f"\n{'='*80}")
        print("TEST-BY-TEST COMPARISON")
        print(f"{'='*80}\n")
        
        # Get all unique test names
        all_test_names = set()
        for result in recent:
            for test in result.get("results", []):
                all_test_names.add(test.get("test_name"))
        
        for test_name in sorted(all_test_names):
            print(f"\n{test_name}:")
            for i, result in enumerate(recent, 1):
                filename = result.get("_filename", "Unknown")[:30]
                test_result = next(
                    (t for t in result.get("results", []) if t.get("test_name") == test_name),
                    None
                )
                if test_result:
                    status = "PASS" if test_result.get("passed") else "FAIL"
                    print(f"  Run {i} ({filename}): {status}")
                else:
                    print(f"  Run {i} ({filename}): Not found")


def find_failures(results: List[Dict]):
    """Find tests that consistently fail across runs."""
    if not results:
        return
    
    print(f"\n{'='*80}")
    print("FAILURE ANALYSIS")
    print(f"{'='*80}\n")
    
    # Count failures per test
    failure_count = {}
    for result in results:
        for test_result in result.get("results", []):
            test_name = test_result.get("test_name")
            if not test_result.get("passed"):
                if test_name not in failure_count:
                    failure_count[test_name] = []
                failure_count[test_name].append(result.get("_filename"))
    
    if not failure_count:
        print("No failures found across all test runs!")
        return
    
    print("Tests that failed (with run counts):")
    for test_name, files in sorted(failure_count.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"\n  {test_name}: Failed in {len(files)}/{len(results)} runs")
        if len(files) <= 5:
            for f in files:
                print(f"    - {f}")
        else:
            for f in files[:3]:
                print(f"    - {f}")
            print(f"    ... and {len(files) - 3} more")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="View and compare test results")
    parser.add_argument(
        '--dir',
        default='test_results',
        help='Directory containing test results (default: test_results)'
    )
    parser.add_argument(
        '--detailed',
        action='store_true',
        help='Show detailed view of most recent test run'
    )
    parser.add_argument(
        '--compare',
        type=int,
        metavar='N',
        help='Compare last N test runs (default: 5)'
    )
    parser.add_argument(
        '--failures',
        action='store_true',
        help='Show failure analysis across all runs'
    )
    parser.add_argument(
        '--file',
        help='Show detailed view of specific result file'
    )
    
    args = parser.parse_args()
    
    # Get results directory
    results_dir = Path(__file__).parent.parent / args.dir
    
    # Load all results
    results = load_all_results(results_dir)
    
    if not results:
        print(f"No test results found in {results_dir}")
        return
    
    # Handle different modes
    if args.file:
        # Load specific file
        file_path = results_dir / args.file
        if not file_path.exists():
            print(f"File not found: {file_path}")
            return
        with open(file_path, 'r') as f:
            result = json.load(f)
            result['_filename'] = args.file
        print_detailed(result)
    
    elif args.detailed:
        # Show detailed view of most recent
        print_detailed(results[0])
    
    elif args.compare:
        # Compare last N runs
        compare_results(results, limit=args.compare)
    
    elif args.failures:
        # Show failure analysis
        find_failures(results)
    
    else:
        # Default: show summary
        print_summary(results)


if __name__ == "__main__":
    main()

