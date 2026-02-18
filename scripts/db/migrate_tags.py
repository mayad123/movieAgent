"""
Migration script to add tag columns to existing databases.
Run this once to update your existing database schema.
"""
import sqlite3
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate_sqlite(db_path: str = "cinemind.db"):
    """Add tag columns to SQLite database."""
    if not os.path.exists(db_path):
        logger.info(f"Database {db_path} does not exist. Migration not needed.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(requests)")
        columns = [row[1] for row in cursor.fetchall()]

        if "request_type" not in columns:
            logger.info("Adding request_type column...")
            cursor.execute("ALTER TABLE requests ADD COLUMN request_type TEXT")

        if "outcome" not in columns:
            logger.info("Adding outcome column...")
            cursor.execute("ALTER TABLE requests ADD COLUMN outcome TEXT")

        conn.commit()
        logger.info("Migration completed successfully!")

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    db_path = os.getenv("DATABASE_URL", "cinemind.db")

    if db_path.startswith("postgresql://"):
        logger.info("PostgreSQL migration not needed - tables are auto-created.")
        logger.info("If you have existing data, you'll need to manually add columns or recreate tables.")
    else:
        migrate_sqlite(db_path)
