"""
Export database data to CSV files for analysis.
Exports requests, responses, metrics, and search operations.
"""
import os
import sys
import csv
import json
from pathlib import Path
from datetime import datetime
from typing import Optional
import argparse

# Add src to path (repo root = parent of scripts/)
_repo_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_repo_root / "src"))

from cinemind.database import Database


def export_requests_to_csv(db: Database, output_file: str = "requests.csv"):
    """Export requests table to CSV."""
    cursor = db.conn.cursor()

    if db.use_postgres:
        cursor.execute("SELECT * FROM requests ORDER BY created_at DESC")
    else:
        cursor.execute("SELECT * FROM requests ORDER BY created_at DESC")

    rows = cursor.fetchall()

    if not rows:
        print(f"No requests found in database.")
        return

    if db.use_postgres:
        columns = [desc[0] for desc in cursor.description]
        rows_data = [dict(row) for row in rows]
    else:
        columns = [description[0] for description in cursor.description]
        rows_data = [dict(zip(columns, row)) for row in rows]

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows_data)

    print(f"Exported {len(rows_data)} requests to {output_file}")


def export_responses_to_csv(db: Database, output_file: str = "responses.csv"):
    """Export responses table to CSV."""
    cursor = db.conn.cursor()

    if db.use_postgres:
        cursor.execute("SELECT * FROM responses ORDER BY created_at DESC")
    else:
        cursor.execute("SELECT * FROM responses ORDER BY created_at DESC")

    rows = cursor.fetchall()

    if not rows:
        print(f"No responses found in database.")
        return

    if db.use_postgres:
        columns = [desc[0] for desc in cursor.description]
        rows_data = [dict(row) for row in rows]
    else:
        columns = [description[0] for description in cursor.description]
        rows_data = [dict(zip(columns, row)) for row in rows]

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows_data)

    print(f"Exported {len(rows_data)} responses to {output_file}")


def export_metrics_to_csv(db: Database, output_file: str = "metrics.csv"):
    """Export metrics table to CSV."""
    cursor = db.conn.cursor()

    if db.use_postgres:
        cursor.execute("SELECT * FROM metrics ORDER BY timestamp DESC")
    else:
        cursor.execute("SELECT * FROM metrics ORDER BY timestamp DESC")

    rows = cursor.fetchall()

    if not rows:
        print(f"No metrics found in database.")
        return

    if db.use_postgres:
        columns = [desc[0] for desc in cursor.description]
        rows_data = [dict(row) for row in rows]
    else:
        columns = [description[0] for description in cursor.description]
        rows_data = [dict(zip(columns, row)) for row in rows]

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows_data)

    print(f"Exported {len(rows_data)} metrics to {output_file}")


def export_search_operations_to_csv(db: Database, output_file: str = "search_operations.csv"):
    """Export search operations table to CSV."""
    cursor = db.conn.cursor()

    if db.use_postgres:
        cursor.execute("SELECT * FROM search_operations ORDER BY timestamp DESC")
    else:
        cursor.execute("SELECT * FROM search_operations ORDER BY timestamp DESC")

    rows = cursor.fetchall()

    if not rows:
        print(f"No search operations found in database.")
        return

    if db.use_postgres:
        columns = [desc[0] for desc in cursor.description]
        rows_data = [dict(row) for row in rows]
    else:
        columns = [description[0] for description in cursor.description]
        rows_data = [dict(zip(columns, row)) for row in rows]

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows_data)

    print(f"Exported {len(rows_data)} search operations to {output_file}")


def export_test_results_to_csv(test_results_dir: str = "data/test_results",
                               output_file: str = "test_results.csv"):
    """Export test results from JSON files to CSV."""
    results_dir = Path(test_results_dir)
    if not results_dir.exists():
        print(f"Test results directory not found: {results_dir}")
        return

    all_results = []

    for result_file in sorted(results_dir.glob("test_results*.json")):
        try:
            with open(result_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                timestamp = data.get('timestamp', '')
                summary = data.get('summary', {})

                all_results.append({
                    'file': result_file.name,
                    'timestamp': timestamp,
                    'type': 'summary',
                    'test_name': '',
                    'total_tests': summary.get('total_tests', 0),
                    'passed': summary.get('passed', 0),
                    'failed': summary.get('failed', 0),
                    'pass_rate': summary.get('pass_rate', 0),
                    'avg_execution_time_ms': summary.get('avg_execution_time_ms', 0),
                    'prompt_version': data.get('prompt_version', ''),
                    'model_version': '',
                    'actual_response': '',
                    'actual_type': '',
                    'request_id': '',
                    'execution_time_ms': '',
                    'errors': ''
                })

                for test_result in data.get('results', []):
                    all_results.append({
                        'file': result_file.name,
                        'timestamp': timestamp,
                        'type': 'test_result',
                        'test_name': test_result.get('test_name', ''),
                        'total_tests': '',
                        'passed': test_result.get('passed', False),
                        'failed': '' if test_result.get('passed') else 'FAILED',
                        'pass_rate': '',
                        'avg_execution_time_ms': '',
                        'prompt_version': test_result.get('prompt_version', ''),
                        'model_version': test_result.get('model_version', ''),
                        'actual_response': test_result.get('actual_response', '')[:200] + '...' if len(test_result.get('actual_response', '')) > 200 else test_result.get('actual_response', ''),
                        'actual_type': test_result.get('actual_type', ''),
                        'request_id': test_result.get('request_id', ''),
                        'execution_time_ms': test_result.get('execution_time_ms', 0),
                        'errors': ', '.join(test_result.get('errors', []))
                    })
        except Exception as e:
            print(f"Error loading {result_file}: {e}")

    if not all_results:
        print(f"No test results found in {results_dir}")
        return

    fieldnames = ['file', 'timestamp', 'type', 'test_name', 'total_tests', 'passed',
                  'failed', 'pass_rate', 'avg_execution_time_ms', 'prompt_version',
                  'model_version', 'actual_response', 'actual_type', 'request_id',
                  'execution_time_ms', 'errors']

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_results)

    print(f"Exported {len(all_results)} test result rows to {output_file}")


def export_prompt_comparison_to_csv(comparison_dir: str = "data/prompt_comparison",
                                    output_file: str = "prompt_comparison.csv"):
    """Export prompt comparison results to CSV."""
    comp_dir = Path(comparison_dir)
    if not comp_dir.exists():
        print(f"Prompt comparison directory not found: {comp_dir}")
        return

    all_results = []

    for result_file in sorted(comp_dir.glob("*_results.json")):
        try:
            with open(result_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                version = data.get('prompt_version', result_file.stem.replace('_results', ''))
                timestamp = data.get('timestamp', '')
                summary = data.get('summary', {})

                all_results.append({
                    'version': version,
                    'timestamp': timestamp,
                    'type': 'summary',
                    'test_name': '',
                    'total_tests': summary.get('total_tests', 0),
                    'passed': summary.get('passed', 0),
                    'failed': summary.get('failed', 0),
                    'pass_rate': summary.get('pass_rate', 0),
                    'avg_execution_time_ms': summary.get('avg_execution_time_ms', 0),
                    'prompt_length': len(data.get('prompt_text', '')),
                    'model_version': '',
                    'actual_response': '',
                    'actual_type': '',
                    'request_id': '',
                    'execution_time_ms': '',
                    'errors': ''
                })

                for test_result in data.get('results', []):
                    all_results.append({
                        'version': version,
                        'timestamp': timestamp,
                        'type': 'test_result',
                        'test_name': test_result.get('test_name', ''),
                        'total_tests': '',
                        'passed': test_result.get('passed', False),
                        'failed': '' if test_result.get('passed') else 'FAILED',
                        'pass_rate': '',
                        'avg_execution_time_ms': '',
                        'prompt_length': '',
                        'model_version': test_result.get('model_version', ''),
                        'actual_response': test_result.get('actual_response', '')[:200] + '...' if len(test_result.get('actual_response', '')) > 200 else test_result.get('actual_response', ''),
                        'actual_type': test_result.get('actual_type', ''),
                        'request_id': test_result.get('request_id', ''),
                        'execution_time_ms': test_result.get('execution_time_ms', 0),
                        'errors': ', '.join(test_result.get('errors', []))
                    })
        except Exception as e:
            print(f"Error loading {result_file}: {e}")

    if not all_results:
        print(f"No prompt comparison results found in {comp_dir}")
        return

    fieldnames = ['version', 'timestamp', 'type', 'test_name', 'total_tests', 'passed',
                  'failed', 'pass_rate', 'avg_execution_time_ms', 'prompt_length',
                  'model_version', 'actual_response', 'actual_type', 'request_id',
                  'execution_time_ms', 'errors']

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_results)

    print(f"Exported {len(all_results)} prompt comparison rows to {output_file}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Export database and test data to CSV")
    parser.add_argument('--db', default='cinemind.db', help='Database file path (default: cinemind.db)')
    parser.add_argument('--output-dir', default='data/exports', help='Output directory for CSV files (default: data/exports)')
    parser.add_argument('--table', choices=['requests', 'responses', 'metrics', 'search_operations', 'all', 'test_results', 'prompt_comparison'], default='all', help='Which table/data to export (default: all)')

    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("EXPORTING DATA TO CSV")
    print("=" * 60)
    print(f"Output directory: {output_dir}\n")

    if args.table in ['requests', 'responses', 'metrics', 'search_operations', 'all']:
        db = Database(db_path=args.db)
        try:
            if args.table in ['requests', 'all']:
                export_requests_to_csv(db, str(output_dir / "requests.csv"))
            if args.table in ['responses', 'all']:
                export_responses_to_csv(db, str(output_dir / "responses.csv"))
            if args.table in ['metrics', 'all']:
                export_metrics_to_csv(db, str(output_dir / "metrics.csv"))
            if args.table in ['search_operations', 'all']:
                export_search_operations_to_csv(db, str(output_dir / "search_operations.csv"))
        finally:
            db.close()

    if args.table in ['test_results', 'all']:
        export_test_results_to_csv(test_results_dir="data/test_results", output_file=str(output_dir / "test_results.csv"))

    if args.table in ['prompt_comparison', 'all']:
        export_prompt_comparison_to_csv(comparison_dir="data/prompt_comparison", output_file=str(output_dir / "prompt_comparison.csv"))

    print("\n" + "=" * 60)
    print("EXPORT COMPLETE")
    print("=" * 60)
    print(f"CSV files saved to: {output_dir}/")


if __name__ == "__main__":
    main()
