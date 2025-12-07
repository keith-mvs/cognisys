#!/usr/bin/env python3
"""
CogniSys Database Initialization
Creates the file_registry.db with complete schema for provenance tracking
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent.parent
COGNISYS_DIR = PROJECT_ROOT / ".cognisys"
DB_PATH = COGNISYS_DIR / "file_registry.db"


def create_schema(conn):
    """Create complete CogniSys database schema"""
    cursor = conn.cursor()

    # File provenance and current state
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS file_registry (
            file_id INTEGER PRIMARY KEY AUTOINCREMENT,

            -- Provenance
            original_path TEXT NOT NULL,
            drop_timestamp TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            file_size INTEGER,

            -- Current canonical location
            canonical_path TEXT,
            canonical_state TEXT DEFAULT 'pending',  -- 'pending', 'classified', 'organized', 'review'

            -- Classification
            document_type TEXT,
            confidence REAL,
            classification_method TEXT,  -- 'ml_model', 'keyword', 'manual', 'pattern'

            -- Metadata (JSON blob)
            extracted_metadata TEXT,  -- JSON: {invoice_numbers, vins, dates, etc.}

            -- Move history tracking
            move_count INTEGER DEFAULT 0,
            last_moved TEXT,

            -- Flags
            requires_review INTEGER DEFAULT 0,  -- Boolean: needs manual review
            is_duplicate INTEGER DEFAULT 0,     -- Boolean: duplicate of another file
            duplicate_of INTEGER,               -- Foreign key to original file_id
            is_missing INTEGER DEFAULT 0,       -- Boolean: file not found on disk

            -- Timestamps
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (duplicate_of) REFERENCES file_registry(file_id)
        )
    """)

    # Create indexes for fast lookups
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_content_hash
        ON file_registry(content_hash)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_canonical_path
        ON file_registry(canonical_path)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_document_type
        ON file_registry(document_type)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_canonical_state
        ON file_registry(canonical_state)
    """)

    # Move history log
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS move_history (
            move_id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL,
            from_path TEXT NOT NULL,
            to_path TEXT NOT NULL,
            move_timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            reason TEXT,           -- 'initial_classification', 'reclassification', 'manual_override', 'rule_update'
            rule_applied TEXT,     -- Which rule triggered this move

            FOREIGN KEY (file_id) REFERENCES file_registry(file_id)
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_move_file_id
        ON move_history(file_id)
    """)

    # Classification rules (version-controlled)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS classification_rules (
            rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_name TEXT NOT NULL,
            rule_version INTEGER NOT NULL,
            rule_type TEXT NOT NULL,       -- 'pattern', 'keyword', 'ml_model'
            rule_pattern TEXT,             -- Regex or keyword pattern
            target_document_type TEXT,
            target_path_template TEXT,     -- e.g., "Financial/{YYYY}/{MM}/{invoice_id}_{original}"
            priority INTEGER DEFAULT 100,
            active INTEGER DEFAULT 1,      -- Boolean: rule is active
            created_timestamp TEXT DEFAULT CURRENT_TIMESTAMP,

            UNIQUE(rule_name, rule_version)
        )
    """)

    # Manual corrections (for accuracy tracking)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS manual_corrections (
            correction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL,
            wrong_type TEXT,               -- What IFMOS classified it as
            correct_type TEXT,             -- What user corrected it to
            correction_reason TEXT,        -- Why user made this correction
            correction_timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            corrected_by TEXT,             -- Username (optional)

            FOREIGN KEY (file_id) REFERENCES file_registry(file_id)
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_correction_file_id
        ON manual_corrections(file_id)
    """)

    # Metrics snapshots (daily)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS metrics_snapshots (
            snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_date TEXT NOT NULL,
            metric_type TEXT NOT NULL,     -- 'accuracy', 'stability', 'duplication', etc.
            metric_value REAL,
            metric_data TEXT,              -- JSON blob with detailed data
            created_timestamp TEXT DEFAULT CURRENT_TIMESTAMP,

            UNIQUE(snapshot_date, metric_type)
        )
    """)

    # Schema metadata
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_info (
            schema_version INTEGER PRIMARY KEY,
            applied_at TEXT DEFAULT CURRENT_TIMESTAMP,
            description TEXT
        )
    """)

    # Insert schema version
    cursor.execute("""
        INSERT OR IGNORE INTO schema_info (schema_version, description)
        VALUES (1, 'Initial schema - file provenance and accuracy tracking')
    """)

    conn.commit()
    print("[OK] Database schema created successfully")


def insert_default_rules(conn):
    """Insert default classification rules"""
    cursor = conn.cursor()

    default_rules = [
        {
            'name': 'financial_invoice_pattern',
            'version': 1,
            'type': 'pattern',
            'pattern': r'invoice|bill|receipt|payment',
            'doc_type': 'financial_invoice',
            'path_template': 'Financial/Invoices/{YYYY}/{MM}/{YYYY-MM-DD}_{vendor}_{invoice_id}_{original}',
            'priority': 90
        },
        {
            'name': 'automotive_technical_pattern',
            'version': 1,
            'type': 'pattern',
            'pattern': r'bmw|audi|mercedes|technical|manual|schematic',
            'doc_type': 'automotive_technical',
            'path_template': 'Automotive/Technical/{vehicle}/{YYYY-MM-DD}_{original}',
            'priority': 90
        },
        {
            'name': 'hr_resume_pattern',
            'version': 1,
            'type': 'pattern',
            'pattern': r'resume|cv|curriculum|vitae',
            'doc_type': 'hr_resume',
            'path_template': 'HR/Resumes/{YYYY}/{candidate}_{YYYY-MM-DD}_{original}',
            'priority': 95
        },
        {
            'name': 'tax_document_pattern',
            'version': 1,
            'type': 'pattern',
            'pattern': r'tax|1040|w2|w-2|1099',
            'doc_type': 'tax_document',
            'path_template': 'Tax/{tax_year}/{YYYY-MM-DD}_{form_type}_{original}',
            'priority': 100
        },
        {
            'name': 'ml_classifier',
            'version': 1,
            'type': 'ml_model',
            'pattern': None,
            'doc_type': None,  # Determined by model
            'path_template': '{domain}/{YYYY}/{MM}/{YYYY-MM-DD}_{original}',
            'priority': 50
        }
    ]

    for rule in default_rules:
        cursor.execute("""
            INSERT OR IGNORE INTO classification_rules
            (rule_name, rule_version, rule_type, rule_pattern, target_document_type,
             target_path_template, priority)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            rule['name'],
            rule['version'],
            rule['type'],
            rule['pattern'],
            rule['doc_type'],
            rule['path_template'],
            rule['priority']
        ))

    conn.commit()
    print(f"[OK] Inserted {len(default_rules)} default classification rules")


def verify_database(conn):
    """Verify database was created correctly"""
    cursor = conn.cursor()

    # Check tables exist
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """)
    tables = [row[0] for row in cursor.fetchall()]

    expected_tables = [
        'file_registry',
        'move_history',
        'classification_rules',
        'manual_corrections',
        'metrics_snapshots',
        'schema_info'
    ]

    missing = set(expected_tables) - set(tables)
    if missing:
        print(f"[FAIL] Missing tables: {missing}")
        return False

    # Check schema version
    cursor.execute("SELECT schema_version, description FROM schema_info")
    version, description = cursor.fetchone()

    print(f"\n[OK] Database verified successfully")
    print(f"  Schema version: {version}")
    print(f"  Description: {description}")
    print(f"\n  Tables created: {len(tables)}")
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"    - {table}: {count} rows")

    return True


def main():
    """Initialize CogniSys database"""
    print("="*80)
    print("COGNISYS DATABASE INITIALIZATION")
    print("="*80)
    print(f"Database path: {DB_PATH}")
    print()

    # Check if database already exists
    if DB_PATH.exists():
        response = input("Database already exists. Overwrite? [y/N]: ")
        if response.lower() != 'y':
            print("Aborted.")
            return 1

        # Backup existing database
        backup_path = DB_PATH.with_suffix(f'.db.backup.{datetime.now().strftime("%Y%m%d_%H%M%S")}')
        print(f"Backing up existing database to: {backup_path}")
        import shutil
        shutil.copy2(DB_PATH, backup_path)
        DB_PATH.unlink()

    # Ensure .cognisys directory exists
    COGNISYS_DIR.mkdir(exist_ok=True)
    (COGNISYS_DIR / "logs").mkdir(exist_ok=True)
    (COGNISYS_DIR / "snapshots").mkdir(exist_ok=True)

    # Create database
    print("Creating database...")
    conn = sqlite3.connect(DB_PATH)

    try:
        create_schema(conn)
        insert_default_rules(conn)

        if verify_database(conn):
            print("\n" + "="*80)
            print("[OK] INITIALIZATION COMPLETE")
            print("="*80)
            print(f"\nDatabase ready at: {DB_PATH}")
            print("\nNext steps:")
            print("  1. Create config: .cognisys/config.yml")
            print("  2. Initialize CogniSys: cognisys init")
            print("  3. Register files: cognisys register --scan-drop")
            return 0
        else:
            print("\n[FAIL] Verification failed")
            return 1

    except Exception as e:
        print(f"\n[FAIL] Error during initialization: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        conn.close()


if __name__ == '__main__':
    sys.exit(main())
