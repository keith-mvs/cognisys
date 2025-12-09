"""
Database Migration: Add Sources Table

Adds support for multiple file sources (local, network, cloud).

Schema Version: 3
"""

import sqlite3
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 3
DESCRIPTION = "Add sources table and source_id to file_registry"


def check_table_exists(cursor, table_name: str) -> bool:
    """Check if a table exists."""
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    return cursor.fetchone() is not None


def check_column_exists(cursor, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns


def migrate(db_path: str) -> bool:
    """
    Run the migration.

    Args:
        db_path: Path to the database file

    Returns:
        True if successful
    """
    logger.info(f"Running migration {SCHEMA_VERSION}: {DESCRIPTION}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Create sources table
        if not check_table_exists(cursor, 'sources'):
            logger.info("Creating sources table...")
            cursor.execute("""
                CREATE TABLE sources (
                    source_id TEXT PRIMARY KEY,
                    source_name TEXT NOT NULL UNIQUE,
                    source_type TEXT NOT NULL,
                    provider TEXT,
                    path TEXT NOT NULL,
                    scan_mode TEXT DEFAULT 'manual',
                    schedule TEXT,
                    priority INTEGER DEFAULT 50,
                    is_active INTEGER DEFAULT 1,
                    last_scan_at TEXT,
                    last_scan_files INTEGER,
                    last_scan_errors INTEGER,
                    config_json TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sources_name ON sources(source_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sources_type ON sources(source_type)")
            logger.info("Created sources table")
        else:
            logger.info("Sources table already exists")

        # Create cloud_providers table
        if not check_table_exists(cursor, 'cloud_providers'):
            logger.info("Creating cloud_providers table...")
            cursor.execute("""
                CREATE TABLE cloud_providers (
                    provider_id TEXT PRIMARY KEY,
                    provider_type TEXT NOT NULL,
                    account_name TEXT,
                    account_email TEXT,
                    last_auth_at TEXT,
                    token_expires_at TEXT,
                    is_active INTEGER DEFAULT 1,
                    config_json TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            logger.info("Created cloud_providers table")
        else:
            logger.info("cloud_providers table already exists")

        # Create scan_history table
        if not check_table_exists(cursor, 'scan_history'):
            logger.info("Creating scan_history table...")
            cursor.execute("""
                CREATE TABLE scan_history (
                    scan_id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    files_scanned INTEGER DEFAULT 0,
                    files_new INTEGER DEFAULT 0,
                    files_updated INTEGER DEFAULT 0,
                    files_deleted INTEGER DEFAULT 0,
                    errors INTEGER DEFAULT 0,
                    status TEXT,
                    error_message TEXT,
                    FOREIGN KEY (source_id) REFERENCES sources(source_id)
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_scan_history_source ON scan_history(source_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_scan_history_started ON scan_history(started_at)")
            logger.info("Created scan_history table")
        else:
            logger.info("scan_history table already exists")

        # Add source_id column to file_registry if not exists
        if check_table_exists(cursor, 'file_registry'):
            if not check_column_exists(cursor, 'file_registry', 'source_id'):
                logger.info("Adding source_id column to file_registry...")
                cursor.execute("ALTER TABLE file_registry ADD COLUMN source_id TEXT")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_file_registry_source ON file_registry(source_id)")
                logger.info("Added source_id column")
            else:
                logger.info("source_id column already exists")

            if not check_column_exists(cursor, 'file_registry', 'source_path'):
                logger.info("Adding source_path column to file_registry...")
                cursor.execute("ALTER TABLE file_registry ADD COLUMN source_path TEXT")
                logger.info("Added source_path column")

            if not check_column_exists(cursor, 'file_registry', 'cloud_id'):
                logger.info("Adding cloud_id column to file_registry...")
                cursor.execute("ALTER TABLE file_registry ADD COLUMN cloud_id TEXT")
                logger.info("Added cloud_id column")

            if not check_column_exists(cursor, 'file_registry', 'etag'):
                logger.info("Adding etag column to file_registry...")
                cursor.execute("ALTER TABLE file_registry ADD COLUMN etag TEXT")
                logger.info("Added etag column")

            if not check_column_exists(cursor, 'file_registry', 'sync_status'):
                logger.info("Adding sync_status column to file_registry...")
                cursor.execute("ALTER TABLE file_registry ADD COLUMN sync_status TEXT")
                logger.info("Added sync_status column")

            if not check_column_exists(cursor, 'file_registry', 'last_seen_at'):
                logger.info("Adding last_seen_at column to file_registry...")
                cursor.execute("ALTER TABLE file_registry ADD COLUMN last_seen_at TEXT")
                logger.info("Added last_seen_at column")

        # Update schema_info table
        cursor.execute("""
            INSERT OR REPLACE INTO schema_info (schema_version, applied_at, description)
            VALUES (?, ?, ?)
        """, (SCHEMA_VERSION, datetime.now().isoformat(), DESCRIPTION))

        conn.commit()
        logger.info(f"Migration {SCHEMA_VERSION} completed successfully")
        return True

    except Exception as e:
        logger.error(f"Migration {SCHEMA_VERSION} failed: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()


def rollback(db_path: str) -> bool:
    """
    Rollback the migration.

    Note: This is destructive and will drop the sources table.
    """
    logger.warning(f"Rolling back migration {SCHEMA_VERSION}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Drop tables (columns cannot be easily dropped in SQLite)
        cursor.execute("DROP TABLE IF EXISTS scan_history")
        cursor.execute("DROP TABLE IF EXISTS cloud_providers")
        cursor.execute("DROP TABLE IF EXISTS sources")

        # Remove schema version entry
        cursor.execute("DELETE FROM schema_info WHERE schema_version = ?", (SCHEMA_VERSION,))

        conn.commit()
        logger.info(f"Rollback of migration {SCHEMA_VERSION} completed")
        return True

    except Exception as e:
        logger.error(f"Rollback failed: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()


if __name__ == '__main__':
    import sys

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2:
        print("Usage: python 003_add_sources.py <db_path> [--rollback]")
        sys.exit(1)

    db_path = sys.argv[1]
    rollback_mode = '--rollback' in sys.argv

    if rollback_mode:
        success = rollback(db_path)
    else:
        success = migrate(db_path)

    sys.exit(0 if success else 1)
