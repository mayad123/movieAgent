"""
Advanced analysis tool for test results stored in database.
Provides SQL-like queries and trend analysis.
"""
import sys
import argparse
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime, timedelta

# Add src to path (repo root = parent of scripts/)
_repo_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_repo_root / "src"))

from cinemind.test_results_db import TestResultsDB


def analyze_pass_rates(db: TestResultsDB, days: int = 30):
    """Analyze pass rates over time."""
    print(f"\n{'='*60}")
    print(f"PASS RATE ANALYSIS (Last {days} days)")
    print(f"{'='*60}\n")

    runs = db.get_test_runs(limit=1000)
    if not runs:
        print("No test runs found.")
        return

    by_version = {}
    for run in runs:
        version = run.get('prompt_version', 'unknown')
        if version not in by_version:
            by_version[version] = []
        by_version[version].append(run)

    print("Pass Rates by Prompt Version:")
    print("-" * 60)
    for version, version_runs in sorted(by_version.items()):
        if version_runs:
            avg_pass_rate = sum(r.get('pass_rate', 0) for r in version_runs) / len(version_runs)
            total_runs = len(version_runs)
            print(f"{version:20} {avg_pass_rate:6.1%} ({total_runs} runs)")

    stats = db.get_test_statistics(days=days)
    if stats:
        print(f"\nOverall Statistics (Last {days} days):")
        print("-" * 60)
        print(f"Total Runs: {stats.get('total_runs', 0)}")
        print(f"Avg Pass Rate: {stats.get('avg_pass_rate', 0):.1%}")
        print(f"Avg Execution Time: {stats.get('avg_execution_time', 0):.2f}ms")
        print(f"Total Tests Run: {stats.get('total_tests_run', 0)}")
        print(f"Total Passed: {stats.get('total_passed', 0)}")
        print(f"Total Failed: {stats.get('total_failed', 0)}")
        print(f"Avg Cost per Run: ${stats.get('avg_cost_per_run', 0):.4f}")


def analyze_test_history(db: TestResultsDB, test_name: str, limit: int = 20):
    """Analyze history of a specific test."""
    print(f"\n{'='*60}")
    print(f"TEST HISTORY: {test_name}")
    print(f"{'='*60}\n")

    history = db.get_test_by_name_history(test_name, limit=limit)
    if not history:
        print(f"No history found for test: {test_name}")
        return

    passed_count = sum(1 for h in history if h.get('passed'))
    total_count = len(history)
    pass_rate = passed_count / total_count if total_count > 0 else 0

    print(f"Pass Rate: {pass_rate:.1%} ({passed_count}/{total_count})")
    print(f"\nRecent Runs:")
    print("-" * 60)
    print(f"{'Date':<20} {'Version':<15} {'Status':<8} {'Time (ms)':<12}")
    print("-" * 60)

    for h in history[:limit]:
        timestamp = h.get('timestamp', '')[:19]
        version = h.get('prompt_version', 'unknown')
        status = "PASS" if h.get('passed') else "FAIL"
        exec_time = h.get('execution_time_ms', 0)
        print(f"{timestamp:<20} {version:<15} {status:<8} {exec_time:<12.0f}")


def find_flaky_tests(db: TestResultsDB, min_runs: int = 5):
    """Find tests that sometimes pass and sometimes fail (flaky tests)."""
    print(f"\n{'='*60}")
    print(f"FLAKY TEST DETECTION (Min {min_runs} runs)")
    print(f"{'='*60}\n")

    cursor = db.conn.cursor()
    cursor.execute("""
        SELECT 
            test_name,
            COUNT(*) as total_runs,
            SUM(passed) as passed_count,
            COUNT(*) - SUM(passed) as failed_count,
            CAST(SUM(passed) AS REAL) / COUNT(*) as pass_rate
        FROM test_results
        GROUP BY test_name
        HAVING COUNT(*) >= ?
        ORDER BY ABS(0.5 - (CAST(SUM(passed) AS REAL) / COUNT(*))) ASC
    """, (min_runs,))

    rows = cursor.fetchall()
    flaky_tests = []

    for row in rows:
        test_name, total, passed, failed, pass_rate = row
        if 0.2 < pass_rate < 0.8:
            flaky_tests.append({
                'test_name': test_name,
                'total_runs': total,
                'passed': passed,
                'failed': failed,
                'pass_rate': pass_rate
            })

    if not flaky_tests:
        print("No flaky tests found!")
        return

    print(f"{'Test Name':<40} {'Runs':<8} {'Passed':<8} {'Failed':<8} {'Pass Rate':<12}")
    print("-" * 80)
    for test in flaky_tests:
        print(f"{test['test_name']:<40} {test['total_runs']:<8} {test['passed']:<8} {test['failed']:<8} {test['pass_rate']:<12.1%}")


def compare_versions(db: TestResultsDB, versions: List[str]):
    """Compare performance across prompt versions."""
    print(f"\n{'='*60}")
    print("PROMPT VERSION COMPARISON")
    print(f"{'='*60}\n")

    cursor = db.conn.cursor()
    print(f"{'Version':<20} {'Runs':<8} {'Avg Pass Rate':<15} {'Avg Time (ms)':<15} {'Avg Cost':<12}")
    print("-" * 80)

    for version in versions:
        cursor.execute("""
            SELECT 
                COUNT(*) as runs,
                AVG(pass_rate) as avg_pass_rate,
                AVG(avg_execution_time_ms) as avg_time,
                AVG(total_cost_usd) as avg_cost
            FROM test_runs
            WHERE prompt_version = ?
        """, (version,))

        row = cursor.fetchone()
        if row and row[0] > 0:
            runs, pass_rate, avg_time, avg_cost = row
            print(f"{version:<20} {runs:<8} {pass_rate:<15.1%} {avg_time:<15.0f} {avg_cost:<12.4f}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Analyze test results from database")
    parser.add_argument('--db', default='test_results.db', help='Test results database path (default: test_results.db)')
    parser.add_argument('--pass-rates', action='store_true', help='Show pass rate analysis')
    parser.add_argument('--test', help='Show history for specific test name')
    parser.add_argument('--flaky', action='store_true', help='Find flaky tests')
    parser.add_argument('--compare-versions', nargs='+', help='Compare specific prompt versions')
    parser.add_argument('--days', type=int, default=30, help='Number of days to analyze (default: 30)')

    args = parser.parse_args()
    db = TestResultsDB(db_path=args.db)

    try:
        if args.pass_rates:
            analyze_pass_rates(db, days=args.days)
        if args.test:
            analyze_test_history(db, args.test)
        if args.flaky:
            find_flaky_tests(db)
        if args.compare_versions:
            compare_versions(db, args.compare_versions)
        if not any([args.pass_rates, args.test, args.flaky, args.compare_versions]):
            analyze_pass_rates(db, days=args.days)
    finally:
        db.close()


if __name__ == "__main__":
    main()
