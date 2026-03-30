"""
Database models and operations for CineMind observability.
Supports SQLite (local) and PostgreSQL (production).
"""

import json
import logging
import os
import sqlite3
from datetime import datetime

logger = logging.getLogger(__name__)


class Database:
    """Database interface for storing requests, responses, and metrics."""

    def __init__(self, db_path: str | None = None, use_postgres: bool = False):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database (default: cinemind.db)
            use_postgres: If True, use PostgreSQL instead of SQLite
        """
        self.use_postgres = use_postgres
        self.db_path = db_path or os.getenv("DATABASE_URL", "cinemind.db")

        if use_postgres:
            try:
                import psycopg2
                from psycopg2.extras import RealDictCursor

                self.conn = psycopg2.connect(self.db_path)
                self.conn.autocommit = True
                self.cursor_type = RealDictCursor
            except ImportError:
                logger.warning("psycopg2 not installed, falling back to SQLite")
                self.use_postgres = False
                self._init_sqlite()
        else:
            self._init_sqlite()

        self._create_tables()

    def _init_sqlite(self):
        """Initialize SQLite connection."""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cursor_type = None

    def _create_tables(self):
        """Create database tables if they don't exist."""
        if self.use_postgres:
            self._create_postgres_tables()
        else:
            self._create_sqlite_tables()

    def _create_sqlite_tables(self):
        """Create SQLite tables."""
        cursor = self.conn.cursor()

        # Requests table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                id TEXT PRIMARY KEY,
                request_id TEXT UNIQUE,
                user_query TEXT NOT NULL,
                prompt TEXT,
                timestamp TEXT NOT NULL,
                use_live_data INTEGER DEFAULT 1,
                model TEXT,
                status TEXT,
                error_message TEXT,
                response_time_ms REAL,
                request_type TEXT,
                outcome TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Add prompt column if it doesn't exist (for existing databases)
        cursor.execute("PRAGMA table_info(requests)")
        columns = [row[1] for row in cursor.fetchall()]
        if "prompt" not in columns:
            try:
                cursor.execute("ALTER TABLE requests ADD COLUMN prompt TEXT")
            except sqlite3.OperationalError:
                # Column already exists, ignore
                pass

        # Responses table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT NOT NULL,
                response_text TEXT,
                sources TEXT,
                token_usage TEXT,
                cost_usd REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (request_id) REFERENCES requests(request_id)
            )
        """)

        # Metrics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT,
                metric_type TEXT NOT NULL,
                metric_name TEXT NOT NULL,
                metric_value REAL,
                metric_data TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (request_id) REFERENCES requests(request_id)
            )
        """)

        # Search operations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS search_operations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT,
                search_query TEXT,
                search_provider TEXT,
                results_count INTEGER,
                search_time_ms REAL,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (request_id) REFERENCES requests(request_id)
            )
        """)

        self.conn.commit()
        logger.info("SQLite tables created successfully")

    def _create_postgres_tables(self):
        """Create PostgreSQL tables."""
        cursor = self.conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                id SERIAL PRIMARY KEY,
                request_id VARCHAR(255) UNIQUE NOT NULL,
                user_query TEXT NOT NULL,
                prompt TEXT,
                timestamp TIMESTAMP NOT NULL,
                use_live_data BOOLEAN DEFAULT TRUE,
                model VARCHAR(100),
                status VARCHAR(50),
                error_message TEXT,
                response_time_ms REAL,
                request_type VARCHAR(50),
                outcome VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Add prompt column if it doesn't exist (for existing databases)
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name='requests' AND column_name='prompt'
        """)
        if not cursor.fetchone():
            try:
                cursor.execute("ALTER TABLE requests ADD COLUMN prompt TEXT")
            except Exception:
                # Column already exists, ignore
                pass

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS responses (
                id SERIAL PRIMARY KEY,
                request_id VARCHAR(255) NOT NULL,
                response_text TEXT,
                sources JSONB,
                token_usage JSONB,
                cost_usd REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (request_id) REFERENCES requests(request_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                id SERIAL PRIMARY KEY,
                request_id VARCHAR(255),
                metric_type VARCHAR(50) NOT NULL,
                metric_name VARCHAR(100) NOT NULL,
                metric_value REAL,
                metric_data JSONB,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (request_id) REFERENCES requests(request_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS search_operations (
                id SERIAL PRIMARY KEY,
                request_id VARCHAR(255),
                search_query TEXT,
                search_provider VARCHAR(50),
                results_count INTEGER,
                search_time_ms REAL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (request_id) REFERENCES requests(request_id)
            )
        """)

        self.conn.commit()
        logger.info("PostgreSQL tables created successfully")

    def save_request(
        self,
        request_id: str,
        user_query: str,
        use_live_data: bool = True,
        model: str | None = None,
        status: str = "pending",
        request_type: str | None = None,
        outcome: str | None = None,
        prompt: str | None = None,
    ) -> bool:
        """Save a request record."""
        try:
            cursor = self.conn.cursor()
            timestamp = datetime.utcnow().isoformat()

            if self.use_postgres:
                cursor.execute(
                    """
                    INSERT INTO requests (request_id, user_query, prompt, timestamp, use_live_data, model, status, request_type, outcome)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (request_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        request_type = EXCLUDED.request_type,
                        outcome = EXCLUDED.outcome,
                        prompt = EXCLUDED.prompt
                """,
                    (request_id, user_query, prompt, timestamp, use_live_data, model, status, request_type, outcome),
                )
            else:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO requests
                    (id, request_id, user_query, prompt, timestamp, use_live_data, model, status, request_type, outcome)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        request_id,
                        request_id,
                        user_query,
                        prompt,
                        timestamp,
                        int(use_live_data),
                        model,
                        status,
                        request_type,
                        outcome,
                    ),
                )

            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error saving request: {e}")
            self.conn.rollback()
            return False

    def update_request(
        self,
        request_id: str,
        status: str | None = None,
        response_time_ms: float | None = None,
        error_message: str | None = None,
        request_type: str | None = None,
        outcome: str | None = None,
        prompt: str | None = None,
    ):
        """Update request record with completion data."""
        try:
            cursor = self.conn.cursor()
            updates = []
            params = []

            if status:
                updates.append("status = ?" if not self.use_postgres else "status = %s")
                params.append(status)
            if response_time_ms is not None:
                updates.append("response_time_ms = ?" if not self.use_postgres else "response_time_ms = %s")
                params.append(response_time_ms)
            if error_message:
                updates.append("error_message = ?" if not self.use_postgres else "error_message = %s")
                params.append(error_message)
            if request_type:
                updates.append("request_type = ?" if not self.use_postgres else "request_type = %s")
                params.append(request_type)
            if outcome:
                updates.append("outcome = ?" if not self.use_postgres else "outcome = %s")
                params.append(outcome)
            if prompt:
                updates.append("prompt = ?" if not self.use_postgres else "prompt = %s")
                params.append(prompt)

            if updates:
                params.append(request_id)
                query = (
                    f"UPDATE requests SET {', '.join(updates)} WHERE request_id = ?"
                    if not self.use_postgres
                    else f"UPDATE requests SET {', '.join(updates)} WHERE request_id = %s"
                )
                cursor.execute(query, params)
                self.conn.commit()
        except Exception as e:
            logger.error(f"Error updating request: {e}")
            self.conn.rollback()

    def save_response(
        self,
        request_id: str,
        response_text: str,
        sources: list[dict] | None = None,
        token_usage: dict | None = None,
        cost_usd: float | None = None,
    ):
        """Save response data."""
        try:
            cursor = self.conn.cursor()
            sources_json = json.dumps(sources) if sources else None
            token_usage_json = json.dumps(token_usage) if token_usage else None

            if self.use_postgres:
                cursor.execute(
                    """
                    INSERT INTO responses (request_id, response_text, sources, token_usage, cost_usd)
                    VALUES (%s, %s, %s, %s, %s)
                """,
                    (request_id, response_text, sources_json, token_usage_json, cost_usd),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO responses (request_id, response_text, sources, token_usage, cost_usd)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (request_id, response_text, sources_json, token_usage_json, cost_usd),
                )

            self.conn.commit()
        except Exception as e:
            logger.error(f"Error saving response: {e}")
            self.conn.rollback()

    def save_metric(
        self,
        request_id: str,
        metric_type: str,
        metric_name: str,
        metric_value: float | None = None,
        metric_data: dict | None = None,
    ):
        """Save a metric."""
        try:
            cursor = self.conn.cursor()
            metric_data_json = json.dumps(metric_data) if metric_data else None

            if self.use_postgres:
                cursor.execute(
                    """
                    INSERT INTO metrics (request_id, metric_type, metric_name, metric_value, metric_data)
                    VALUES (%s, %s, %s, %s, %s)
                """,
                    (request_id, metric_type, metric_name, metric_value, metric_data_json),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO metrics (request_id, metric_type, metric_name, metric_value, metric_data)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (request_id, metric_type, metric_name, metric_value, metric_data_json),
                )

            self.conn.commit()
        except Exception as e:
            logger.error(f"Error saving metric: {e}")
            self.conn.rollback()

    def save_search_operation(
        self, request_id: str, search_query: str, search_provider: str, results_count: int, search_time_ms: float
    ):
        """Save search operation data."""
        try:
            cursor = self.conn.cursor()

            if self.use_postgres:
                cursor.execute(
                    """
                    INSERT INTO search_operations (request_id, search_query, search_provider, results_count, search_time_ms)
                    VALUES (%s, %s, %s, %s, %s)
                """,
                    (request_id, search_query, search_provider, results_count, search_time_ms),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO search_operations (request_id, search_query, search_provider, results_count, search_time_ms)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (request_id, search_query, search_provider, results_count, search_time_ms),
                )

            self.conn.commit()
        except Exception as e:
            logger.error(f"Error saving search operation: {e}")
            self.conn.rollback()

    def get_request(self, request_id: str) -> dict | None:
        """Get a request by ID."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT * FROM requests WHERE request_id = ?"
                if not self.use_postgres
                else "SELECT * FROM requests WHERE request_id = %s",
                (request_id,),
            )
            row = cursor.fetchone()

            if row:
                if self.use_postgres:
                    return dict(row)
                else:
                    return dict(zip([col[0] for col in cursor.description], row, strict=False))
            return None
        except Exception as e:
            logger.error(f"Error getting request: {e}")
            return None

    def get_recent_requests(self, limit: int = 100) -> list[dict]:
        """Get recent requests."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT * FROM requests
                ORDER BY created_at DESC
                LIMIT ?
            """
                if not self.use_postgres
                else """
                SELECT * FROM requests
                ORDER BY created_at DESC
                LIMIT %s
            """,
                (limit,),
            )

            rows = cursor.fetchall()
            if self.use_postgres:
                return [dict(row) for row in rows]
            else:
                return [dict(zip([col[0] for col in cursor.description], row, strict=False)) for row in rows]
        except Exception as e:
            logger.error(f"Error getting recent requests: {e}")
            return []

    def get_stats(self, days: int = 7, request_type: str | None = None, outcome: str | None = None) -> dict:
        """Get statistics for the last N days, optionally filtered by type/outcome."""
        try:
            cursor = self.conn.cursor()
            where_clauses = []
            params = []

            if self.use_postgres:
                where_clauses.append("r.created_at >= NOW() - INTERVAL %s")
                params = [f"{days} days"]
            else:
                where_clauses.append("datetime(r.created_at) >= datetime('now', '-' || ? || ' days')")
                params = [str(days)]

            if request_type:
                where_clauses.append("r.request_type = ?" if not self.use_postgres else "r.request_type = %s")
                params.append(request_type)

            if outcome:
                where_clauses.append("r.outcome = ?" if not self.use_postgres else "r.outcome = %s")
                params.append(outcome)

            where_sql = " AND ".join(where_clauses)

            if self.use_postgres:
                cursor.execute(
                    f"""
                    SELECT
                        COUNT(*) as total_requests,
                        COUNT(CASE WHEN status = 'success' THEN 1 END) as successful_requests,
                        COUNT(CASE WHEN status = 'error' THEN 1 END) as failed_requests,
                        AVG(response_time_ms) as avg_response_time_ms,
                        SUM(CASE WHEN cost_usd IS NOT NULL THEN cost_usd ELSE 0 END) as total_cost_usd,
                        COUNT(DISTINCT request_type) as unique_request_types,
                        COUNT(DISTINCT outcome) as unique_outcomes
                    FROM requests r
                    LEFT JOIN responses res ON r.request_id = res.request_id
                    WHERE {where_sql}
                """,
                    tuple(params),
                )
            else:
                cursor.execute(
                    f"""
                    SELECT
                        COUNT(*) as total_requests,
                        SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful_requests,
                        SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as failed_requests,
                        AVG(response_time_ms) as avg_response_time_ms,
                        SUM(CASE WHEN res.cost_usd IS NOT NULL THEN res.cost_usd ELSE 0 END) as total_cost_usd,
                        COUNT(DISTINCT request_type) as unique_request_types,
                        COUNT(DISTINCT outcome) as unique_outcomes
                    FROM requests r
                    LEFT JOIN responses res ON r.request_id = res.request_id
                    WHERE {where_sql}
                """,
                    tuple(params),
                )

            row = cursor.fetchone()
            if row:
                if self.use_postgres:
                    return dict(row)
                else:
                    return dict(zip([col[0] for col in cursor.description], row, strict=False))
            return {}
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {}

    def get_tag_distribution(self, days: int = 7) -> dict:
        """Get distribution of request types and outcomes."""
        try:
            cursor = self.conn.cursor()

            if self.use_postgres:
                cursor.execute(
                    """
                    SELECT
                        request_type,
                        COUNT(*) as count
                    FROM requests
                    WHERE created_at >= NOW() - INTERVAL '%s days'
                    AND request_type IS NOT NULL
                    GROUP BY request_type
                    ORDER BY count DESC
                """,
                    (days,),
                )
            else:
                cursor.execute(f"""
                    SELECT
                        request_type,
                        COUNT(*) as count
                    FROM requests
                    WHERE datetime(created_at) >= datetime('now', '-{days} days')
                    AND request_type IS NOT NULL
                    GROUP BY request_type
                    ORDER BY count DESC
                """)

            type_rows = cursor.fetchall()
            request_types = {}
            if type_rows:
                if self.use_postgres:
                    request_types = {row["request_type"]: row["count"] for row in type_rows}
                else:
                    request_types = {row[0]: row[1] for row in type_rows}

            if self.use_postgres:
                cursor.execute(
                    """
                    SELECT
                        outcome,
                        COUNT(*) as count
                    FROM requests
                    WHERE created_at >= NOW() - INTERVAL '%s days'
                    AND outcome IS NOT NULL
                    GROUP BY outcome
                    ORDER BY count DESC
                """,
                    (days,),
                )
            else:
                cursor.execute(f"""
                    SELECT
                        outcome,
                        COUNT(*) as count
                    FROM requests
                    WHERE datetime(created_at) >= datetime('now', '-{days} days')
                    AND outcome IS NOT NULL
                    GROUP BY outcome
                    ORDER BY count DESC
                """)

            outcome_rows = cursor.fetchall()
            outcomes = {}
            if outcome_rows:
                if self.use_postgres:
                    outcomes = {row["outcome"]: row["count"] for row in outcome_rows}
                else:
                    outcomes = {row[0]: row[1] for row in outcome_rows}

            return {"request_types": request_types, "outcomes": outcomes}
        except Exception as e:
            logger.error(f"Error getting tag distribution: {e}")
            return {"request_types": {}, "outcomes": {}}

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
