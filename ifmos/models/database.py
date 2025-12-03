"""
Database layer for IFMOS using SQLite.
Handles all database operations including schema creation and queries.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import uuid


class Database:
    """SQLite database manager for file indexing and analysis."""

    def __init__(self, db_path: str):
        """Initialize database connection and create schema if needed."""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_schema()

    def _create_schema(self):
        """Create all necessary tables."""
        cursor = self.conn.cursor()

        # Files table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS files (
                file_id TEXT PRIMARY KEY,
                path TEXT NOT NULL,
                parent_id TEXT,
                name TEXT NOT NULL,
                extension TEXT,
                size_bytes INTEGER,
                created_at DATETIME,
                modified_at DATETIME,
                accessed_at DATETIME,
                mime_type TEXT,
                file_category TEXT,
                file_subcategory TEXT,
                hash_quick TEXT,
                hash_full TEXT,
                access_count INTEGER DEFAULT 0,
                last_opened DATETIME,
                owner TEXT,
                permissions TEXT,
                attributes TEXT,
                is_duplicate BOOLEAN DEFAULT 0,
                duplicate_group TEXT,
                is_orphaned BOOLEAN DEFAULT 0,
                is_temp BOOLEAN DEFAULT 0,
                scan_session_id TEXT NOT NULL,
                indexed_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Indexes for performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_path ON files(path)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_hash_quick ON files(hash_quick)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_hash_full ON files(hash_full)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_size ON files(size_bytes)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_modified ON files(modified_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_category ON files(file_category)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_session ON files(scan_session_id)")

        # Folders table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS folders (
                folder_id TEXT PRIMARY KEY,
                path TEXT NOT NULL UNIQUE,
                parent_id TEXT,
                name TEXT NOT NULL,
                depth INTEGER,
                total_size INTEGER,
                file_count INTEGER,
                subfolder_count INTEGER,
                folder_type TEXT,
                created_at DATETIME,
                modified_at DATETIME,
                scan_session_id TEXT NOT NULL
            )
        """)

        # Duplicate groups
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS duplicate_groups (
                group_id TEXT PRIMARY KEY,
                canonical_file TEXT,
                member_count INTEGER,
                total_size INTEGER,
                similarity_type TEXT,
                detection_rule TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS duplicate_members (
                group_id TEXT,
                file_id TEXT,
                priority_score REAL,
                reason TEXT,
                PRIMARY KEY (group_id, file_id)
            )
        """)

        # Scan sessions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scan_sessions (
                session_id TEXT PRIMARY KEY,
                started_at DATETIME,
                completed_at DATETIME,
                root_paths TEXT,
                files_scanned INTEGER DEFAULT 0,
                status TEXT,
                config_snapshot TEXT
            )
        """)

        # Migration plans
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS migration_plans (
                plan_id TEXT PRIMARY KEY,
                created_at DATETIME,
                session_id TEXT,
                approved BOOLEAN DEFAULT 0,
                executed_at DATETIME,
                status TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS migration_actions (
                action_id TEXT PRIMARY KEY,
                plan_id TEXT,
                source_path TEXT,
                target_path TEXT,
                action_type TEXT,
                rule_id TEXT,
                reason TEXT,
                file_size INTEGER,
                executed BOOLEAN DEFAULT 0,
                execution_time DATETIME,
                rollback_data TEXT
            )
        """)

        # ML Classifications table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ml_classifications (
                classification_id TEXT PRIMARY KEY,
                file_id TEXT NOT NULL,
                model_name TEXT NOT NULL,
                predicted_category TEXT,
                confidence REAL,
                probabilities TEXT,
                classified_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                session_id TEXT,
                FOREIGN KEY (file_id) REFERENCES files(file_id)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ml_file ON ml_classifications(file_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ml_model ON ml_classifications(model_name)")

        self.conn.commit()

    def create_session(self, root_paths: List[str], config: Dict) -> str:
        """Create a new scan session."""
        session_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}"
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO scan_sessions
            (session_id, started_at, root_paths, status, config_snapshot)
            VALUES (?, ?, ?, ?, ?)
        """, (
            session_id,
            datetime.now(),
            json.dumps(root_paths),
            'running',
            json.dumps(config)
        ))
        self.conn.commit()
        return session_id

    def update_session(self, session_id: str, **kwargs):
        """Update session fields."""
        cursor = self.conn.cursor()
        for key, value in kwargs.items():
            cursor.execute(f"""
                UPDATE scan_sessions
                SET {key} = ?
                WHERE session_id = ?
            """, (value, session_id))
        self.conn.commit()

    def insert_file(self, file_record: Dict[str, Any]):
        """Insert a file record into the database."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO files (
                file_id, path, parent_id, name, extension, size_bytes,
                created_at, modified_at, accessed_at, mime_type, file_category,
                file_subcategory, hash_quick, hash_full, access_count, scan_session_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            file_record.get('file_id'),
            file_record.get('path'),
            file_record.get('parent_id'),
            file_record.get('name'),
            file_record.get('extension'),
            file_record.get('size_bytes'),
            file_record.get('created_at'),
            file_record.get('modified_at'),
            file_record.get('accessed_at'),
            file_record.get('mime_type'),
            file_record.get('file_category'),
            file_record.get('file_subcategory'),
            file_record.get('hash_quick'),
            file_record.get('hash_full'),
            file_record.get('access_count', 0),
            file_record.get('scan_session_id')
        ))
        self.conn.commit()

    def insert_folder(self, folder_record: Dict[str, Any]):
        """Insert a folder record into the database."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO folders (
                folder_id, path, parent_id, name, depth, total_size,
                file_count, subfolder_count, folder_type, created_at,
                modified_at, scan_session_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            folder_record.get('folder_id'),
            folder_record.get('path'),
            folder_record.get('parent_id'),
            folder_record.get('name'),
            folder_record.get('depth'),
            folder_record.get('total_size', 0),
            folder_record.get('file_count', 0),
            folder_record.get('subfolder_count', 0),
            folder_record.get('folder_type'),
            folder_record.get('created_at'),
            folder_record.get('modified_at'),
            folder_record.get('scan_session_id')
        ))
        self.conn.commit()

    def get_files_by_session(self, session_id: str) -> List[Dict]:
        """Retrieve all files from a scan session."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM files WHERE scan_session_id = ?", (session_id,))
        return [dict(row) for row in cursor.fetchall()]

    def get_duplicate_candidates(self, session_id: str) -> List[Dict]:
        """Find potential duplicate files by size and extension."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT size_bytes, extension, COUNT(*) as cnt,
                   GROUP_CONCAT(file_id) as file_ids
            FROM files
            WHERE scan_session_id = ? AND size_bytes > 0
            GROUP BY size_bytes, extension
            HAVING cnt > 1
        """, (session_id,))
        return [dict(row) for row in cursor.fetchall()]

    def get_files_by_hash(self, hash_value: str, hash_type: str = 'quick') -> List[Dict]:
        """Get all files with a specific hash value."""
        cursor = self.conn.cursor()
        column = 'hash_quick' if hash_type == 'quick' else 'hash_full'
        cursor.execute(f"SELECT * FROM files WHERE {column} = ?", (hash_value,))
        return [dict(row) for row in cursor.fetchall()]

    def update_file_hash(self, file_id: str, hash_type: str, hash_value: str):
        """Update hash value for a file."""
        cursor = self.conn.cursor()
        column = 'hash_quick' if hash_type == 'quick' else 'hash_full'
        cursor.execute(f"""
            UPDATE files SET {column} = ? WHERE file_id = ?
        """, (hash_value, file_id))
        self.conn.commit()

    def create_duplicate_group(self, group_data: Dict) -> str:
        """Create a duplicate group."""
        group_id = f"dup-{uuid.uuid4().hex[:8]}"
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO duplicate_groups
            (group_id, canonical_file, member_count, total_size,
             similarity_type, detection_rule)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            group_id,
            group_data['canonical_file'],
            group_data['member_count'],
            group_data['total_size'],
            group_data['similarity_type'],
            group_data['detection_rule']
        ))

        # Insert members
        for member in group_data['members']:
            cursor.execute("""
                INSERT INTO duplicate_members
                (group_id, file_id, priority_score, reason)
                VALUES (?, ?, ?, ?)
            """, (group_id, member['file_id'], member['priority_score'], member['reason']))

        # Mark files as duplicates
        for member in group_data['members']:
            cursor.execute("""
                UPDATE files
                SET is_duplicate = 1, duplicate_group = ?
                WHERE file_id = ?
            """, (group_id, member['file_id']))

        self.conn.commit()
        return group_id

    def get_overview_stats(self, session_id: str) -> Dict:
        """Get overview statistics for a session."""
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT
                COUNT(*) as total_files,
                SUM(size_bytes) as total_size,
                COUNT(DISTINCT extension) as unique_extensions,
                MIN(created_at) as oldest,
                MAX(created_at) as newest
            FROM files
            WHERE scan_session_id = ?
        """, (session_id,))

        stats = dict(cursor.fetchone())

        cursor.execute("""
            SELECT COUNT(*) as total_folders
            FROM folders
            WHERE scan_session_id = ?
        """, (session_id,))

        stats.update(dict(cursor.fetchone()))
        return stats

    def get_file_type_distribution(self, session_id: str) -> List[Dict]:
        """Get file distribution by category."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT
                file_category,
                COUNT(*) as count,
                SUM(size_bytes) as total_size,
                ROUND(100.0 * SUM(size_bytes) /
                      (SELECT SUM(size_bytes) FROM files WHERE scan_session_id = ?), 2)
                      as pct_of_total
            FROM files
            WHERE scan_session_id = ?
            GROUP BY file_category
            ORDER BY total_size DESC
        """, (session_id, session_id))
        return [dict(row) for row in cursor.fetchall()]

    def get_largest_files(self, session_id: str, limit: int = 20) -> List[Dict]:
        """Get the largest files."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT name, path, size_bytes, modified_at
            FROM files
            WHERE scan_session_id = ?
            ORDER BY size_bytes DESC
            LIMIT ?
        """, (session_id, limit))
        return [dict(row) for row in cursor.fetchall()]

    def get_duplication_metrics(self, session_id: str) -> Dict:
        """Get duplication analysis metrics."""
        cursor = self.conn.cursor()

        # Get all duplicate groups for this session
        cursor.execute("""
            SELECT COUNT(DISTINCT dg.group_id) as duplicate_sets,
                   SUM(dg.member_count - 1) as total_duplicate_files,
                   SUM((dg.member_count - 1) * dg.total_size) as wasted_space
            FROM duplicate_groups dg
            JOIN files f ON dg.canonical_file = f.file_id
            WHERE f.scan_session_id = ?
        """, (session_id,))

        metrics = dict(cursor.fetchone())

        # By type
        cursor.execute("""
            SELECT
                dg.similarity_type,
                COUNT(*) as sets,
                SUM((dg.member_count - 1) * dg.total_size) as wasted_bytes
            FROM duplicate_groups dg
            JOIN files f ON dg.canonical_file = f.file_id
            WHERE f.scan_session_id = ?
            GROUP BY dg.similarity_type
        """, (session_id,))

        metrics['by_type'] = [dict(row) for row in cursor.fetchall()]
        return metrics

    def insert_ml_classification(self, classification: Dict):
        """Insert ML classification result."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO ml_classifications
            (classification_id, file_id, model_name, predicted_category,
             confidence, probabilities, session_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            classification.get('classification_id', str(uuid.uuid4())),
            classification['file_id'],
            classification['model_name'],
            classification['predicted_category'],
            classification['confidence'],
            json.dumps(classification.get('probabilities', {})),
            classification.get('session_id')
        ))
        self.conn.commit()

    def insert_ml_classifications_batch(self, classifications: List[Dict]):
        """Batch insert ML classifications."""
        cursor = self.conn.cursor()
        cursor.executemany("""
            INSERT OR REPLACE INTO ml_classifications
            (classification_id, file_id, model_name, predicted_category,
             confidence, probabilities, session_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [
            (
                c.get('classification_id', str(uuid.uuid4())),
                c['file_id'],
                c['model_name'],
                c['predicted_category'],
                c['confidence'],
                json.dumps(c.get('probabilities', {})),
                c.get('session_id')
            )
            for c in classifications
        ])
        self.conn.commit()

    def get_ml_classifications(self, session_id: str, model_name: str = None) -> List[Dict]:
        """Get ML classifications for a session."""
        cursor = self.conn.cursor()
        if model_name:
            cursor.execute("""
                SELECT mc.*, f.path, f.name
                FROM ml_classifications mc
                JOIN files f ON mc.file_id = f.file_id
                WHERE mc.session_id = ? AND mc.model_name = ?
            """, (session_id, model_name))
        else:
            cursor.execute("""
                SELECT mc.*, f.path, f.name
                FROM ml_classifications mc
                JOIN files f ON mc.file_id = f.file_id
                WHERE mc.session_id = ?
            """, (session_id,))
        return [dict(row) for row in cursor.fetchall()]

    def get_classification_stats(self, session_id: str) -> Dict:
        """Get ML classification statistics for a session."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT
                model_name,
                COUNT(*) as total,
                AVG(confidence) as avg_confidence,
                COUNT(CASE WHEN confidence >= 0.7 THEN 1 END) as high_conf,
                COUNT(CASE WHEN confidence < 0.5 THEN 1 END) as low_conf
            FROM ml_classifications
            WHERE session_id = ?
            GROUP BY model_name
        """, (session_id,))
        return [dict(row) for row in cursor.fetchall()]

    def close(self):
        """Close database connection."""
        self.conn.close()
