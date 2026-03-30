"""
Database schema for storing test results.
Provides better querying and analysis than JSON files.
"""
import logging
import os
import sqlite3
from datetime import datetime

logger = logging.getLogger(__name__)


class TestResultsDB:
    """Database for storing and querying test results."""

    def __init__(self, db_path: str | None = None):
        """
        Initialize test results database.

        Args:
            db_path: Path to SQLite database (default: test_results.db)
        """
        self.db_path = db_path or os.getenv("TEST_RESULTS_DB", "test_results.db")
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        """Create database tables for test results."""
        cursor = self.conn.cursor()

        # Test runs table (summary of each test run)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT UNIQUE NOT NULL,
                timestamp TEXT NOT NULL,
                prompt_version TEXT,
                model_version TEXT,
                agent_config_version TEXT,
                total_tests INTEGER,
                passed INTEGER,
                failed INTEGER,
                pass_rate REAL,
                avg_execution_time_ms REAL,
                total_cost_usd REAL,
                test_suite TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Test results table (individual test results)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                test_name TEXT NOT NULL,
                passed INTEGER NOT NULL,
                execution_time_ms REAL,
                actual_response TEXT,
                actual_type TEXT,
                request_id TEXT,
                prompt_used TEXT,
                model_version TEXT,
                prompt_version TEXT,
                agent_config_version TEXT,
                errors TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (run_id) REFERENCES test_runs(run_id)
            )
        """)

        # Criteria results table (individual criteria evaluations)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS criteria_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_result_id INTEGER NOT NULL,
                criterion_name TEXT NOT NULL,
                passed INTEGER NOT NULL,
                message TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (test_result_id) REFERENCES test_results(id)
            )
        """)

        # Search results table (search information from tests)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_search_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_result_id INTEGER NOT NULL,
                search_query TEXT,
                rank INTEGER,
                source TEXT,
                url TEXT,
                title TEXT,
                published_at TEXT,
                last_updated_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (test_result_id) REFERENCES test_results(id)
            )
        """)

        # Create indexes for faster queries
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_test_runs_timestamp ON test_runs(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_test_runs_prompt_version ON test_runs(prompt_version)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_test_results_run_id ON test_results(run_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_test_results_test_name ON test_results(test_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_test_results_passed ON test_results(passed)")

        self.conn.commit()
        logger.info("Test results database tables created successfully")

    def save_test_run(self, run_data: dict) -> str:
        """
        Save a complete test run to the database.

        Args:
            run_data: Dictionary with test run data (from evaluator.generate_report)

        Returns:
            run_id: Unique identifier for this test run
        """
        import uuid
        run_id = str(uuid.uuid4())
        timestamp = run_data.get('timestamp', datetime.now().isoformat())
        summary = run_data.get('summary', {})

        cursor = self.conn.cursor()

        # Insert test run summary
        cursor.execute("""
            INSERT INTO test_runs (
                run_id, timestamp, prompt_version, model_version, agent_config_version,
                total_tests, passed, failed, pass_rate, avg_execution_time_ms,
                total_cost_usd, test_suite
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run_id,
            timestamp,
            run_data.get('prompt_version'),
            run_data.get('model_version'),
            run_data.get('agent_config_version'),
            summary.get('total_tests', 0),
            summary.get('passed', 0),
            summary.get('failed', 0),
            summary.get('pass_rate', 0),
            summary.get('avg_execution_time_ms', 0),
            run_data.get('total_cost_usd', 0),
            run_data.get('test_suite', 'all')
        ))

        # Insert individual test results
        for test_result in run_data.get('results', []):
            cursor.execute("""
                INSERT INTO test_results (
                    run_id, test_name, passed, execution_time_ms,
                    actual_response, actual_type, request_id, prompt_used,
                    model_version, prompt_version, agent_config_version, errors
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run_id,
                test_result.get('test_name'),
                1 if test_result.get('passed') else 0,
                test_result.get('execution_time_ms', 0),
                test_result.get('actual_response', ''),
                test_result.get('actual_type'),
                test_result.get('request_id'),
                test_result.get('prompt_used', ''),
                test_result.get('model_version'),
                test_result.get('prompt_version'),
                test_result.get('agent_config_version'),
                ', '.join(test_result.get('errors', []))
            ))

            test_result_id = cursor.lastrowid

            # Insert criteria results
            for criterion_name, passed, message in test_result.get('criteria_results', []):
                cursor.execute("""
                    INSERT INTO criteria_results (
                        test_result_id, criterion_name, passed, message
                    ) VALUES (?, ?, ?, ?)
                """, (test_result_id, criterion_name, 1 if passed else 0, message))

            # Insert search results
            for search_group in test_result.get('searches', []):
                for result in search_group.get('results', []):
                    cursor.execute("""
                        INSERT INTO test_search_results (
                            test_result_id, search_query, rank, source, url, title,
                            published_at, last_updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        test_result_id,
                        search_group.get('query', ''),
                        result.get('rank'),
                        result.get('source', ''),
                        result.get('url', ''),
                        result.get('title', ''),
                        result.get('published_at'),
                        result.get('last_updated_at')
                    ))

        self.conn.commit()
        logger.info(f"Saved test run {run_id} with {summary.get('total_tests', 0)} tests")
        return run_id

    def get_test_runs(self, limit: int = 100, prompt_version: str | None = None,
                     start_date: str | None = None, end_date: str | None = None) -> list[dict]:
        """Get test runs with optional filtering."""
        cursor = self.conn.cursor()
        where_clauses = []
        params = []

        if prompt_version:
            where_clauses.append("prompt_version = ?")
            params.append(prompt_version)

        if start_date:
            where_clauses.append("timestamp >= ?")
            params.append(start_date)

        if end_date:
            where_clauses.append("timestamp <= ?")
            params.append(end_date)

        where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        params.append(limit)

        cursor.execute(f"""
            SELECT * FROM test_runs
            {where_sql}
            ORDER BY timestamp DESC
            LIMIT ?
        """, params)

        rows = cursor.fetchall()
        return [dict(zip([col[0] for col in cursor.description], row, strict=False)) for row in rows]

    def get_test_statistics(self, prompt_version: str | None = None,
                           days: int = 30) -> dict:
        """Get aggregated statistics for test runs."""
        cursor = self.conn.cursor()
        params = []

        where_clause = "WHERE timestamp >= datetime('now', '-' || ? || ' days')"
        params.append(str(days))

        if prompt_version:
            where_clause += " AND prompt_version = ?"
            params.append(prompt_version)

        cursor.execute(f"""
            SELECT
                COUNT(*) as total_runs,
                AVG(pass_rate) as avg_pass_rate,
                AVG(avg_execution_time_ms) as avg_execution_time,
                SUM(total_tests) as total_tests_run,
                SUM(passed) as total_passed,
                SUM(failed) as total_failed,
                AVG(total_cost_usd) as avg_cost_per_run
            FROM test_runs
            {where_clause}
        """, params)

        row = cursor.fetchone()
        if row:
            return dict(zip([col[0] for col in cursor.description], row, strict=False))
        return {}

    def get_test_by_name_history(self, test_name: str, limit: int = 50) -> list[dict]:
        """Get history of a specific test across all runs."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT
                tr.run_id,
                tr.timestamp,
                tr.prompt_version,
                tr.model_version,
                t.test_name,
                t.passed,
                t.execution_time_ms,
                t.actual_type
            FROM test_results t
            JOIN test_runs tr ON t.run_id = tr.run_id
            WHERE t.test_name = ?
            ORDER BY tr.timestamp DESC
            LIMIT ?
        """, (test_name, limit))

        rows = cursor.fetchall()
        return [dict(zip([col[0] for col in cursor.description], row, strict=False)) for row in rows]

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()

