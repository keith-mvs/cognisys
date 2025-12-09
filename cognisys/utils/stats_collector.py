"""
Statistics collection utilities.
Consolidates stats tracking from multiple scripts into a reusable module.
"""

import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from collections import Counter


@dataclass
class ClassificationStats:
    """Statistics for classification operations."""
    total: int = 0
    classified: int = 0
    high_confidence: int = 0
    low_confidence: int = 0
    failed: int = 0
    changed: int = 0
    unchanged: int = 0
    by_type: Dict[str, int] = field(default_factory=dict)
    by_method: Dict[str, int] = field(default_factory=dict)

    def record(self, doc_type: Optional[str], confidence: float, method: str,
               old_type: Optional[str] = None, confidence_threshold: float = 0.70):
        """Record a classification result."""
        self.total += 1

        if doc_type:
            self.classified += 1
            self.by_type[doc_type] = self.by_type.get(doc_type, 0) + 1
            self.by_method[method] = self.by_method.get(method, 0) + 1

            if confidence >= confidence_threshold:
                self.high_confidence += 1
            else:
                self.low_confidence += 1

            if old_type is not None:
                if doc_type != old_type:
                    self.changed += 1
                else:
                    self.unchanged += 1
        else:
            self.failed += 1

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        return self.classified / self.total if self.total > 0 else 0.0

    @property
    def high_confidence_rate(self) -> float:
        """Calculate high confidence rate."""
        return self.high_confidence / self.classified if self.classified > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'total': self.total,
            'classified': self.classified,
            'high_confidence': self.high_confidence,
            'low_confidence': self.low_confidence,
            'failed': self.failed,
            'changed': self.changed,
            'unchanged': self.unchanged,
            'success_rate': self.success_rate,
            'high_confidence_rate': self.high_confidence_rate,
            'by_type': self.by_type,
            'by_method': self.by_method,
        }

    def summary(self) -> str:
        """Generate summary string."""
        lines = [
            f"Total files:        {self.total:6}",
            f"Classified:         {self.classified:6} ({self.success_rate*100:.1f}%)",
            f"High confidence:    {self.high_confidence:6} ({self.high_confidence_rate*100:.1f}%)",
            f"Low confidence:     {self.low_confidence:6}",
            f"Failed:             {self.failed:6}",
        ]
        if self.changed > 0 or self.unchanged > 0:
            lines.append(f"Changed:            {self.changed:6}")
            lines.append(f"Unchanged:          {self.unchanged:6}")
        return '\n'.join(lines)


class StatsCollector:
    """
    Collect and aggregate statistics from the file registry database.

    Consolidates statistics logic from:
    - calculate_stats.py
    - check_stats.py
    - analyze_*.py scripts
    - report generation scripts
    """

    def __init__(self, db_path: str = '.cognisys/file_registry.db'):
        """
        Initialize collector.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None

    @property
    def conn(self) -> sqlite3.Connection:
        """Lazy connection getter."""
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def close(self):
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def get_overview(self) -> Dict[str, Any]:
        """Get high-level overview statistics."""
        cursor = self.conn.cursor()

        # Total files
        cursor.execute('SELECT COUNT(*) FROM file_registry')
        total_files = cursor.fetchone()[0]

        # Total size
        cursor.execute('SELECT SUM(file_size) FROM file_registry')
        total_size = cursor.fetchone()[0] or 0

        # Classified vs unclassified
        cursor.execute('''
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN document_type IS NOT NULL AND document_type != 'unknown' THEN 1 ELSE 0 END) as classified,
                SUM(CASE WHEN document_type IS NULL THEN 1 ELSE 0 END) as null_type,
                SUM(CASE WHEN document_type = 'unknown' THEN 1 ELSE 0 END) as unknown_type
            FROM file_registry
        ''')
        row = cursor.fetchone()

        return {
            'total_files': total_files,
            'total_size_bytes': total_size,
            'total_size_gb': total_size / 1e9 if total_size else 0,
            'classified': row['classified'] or 0,
            'null_type': row['null_type'] or 0,
            'unknown_type': row['unknown_type'] or 0,
            'classification_rate': (row['classified'] or 0) / total_files if total_files > 0 else 0,
        }

    def get_by_document_type(self, limit: int = 50) -> List[Dict]:
        """Get file counts grouped by document type."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT document_type, COUNT(*) as count, SUM(file_size) as total_size
            FROM file_registry
            GROUP BY document_type
            ORDER BY count DESC
            LIMIT ?
        ''', (limit,))

        return [
            {
                'document_type': row['document_type'] or 'NULL',
                'count': row['count'],
                'total_size': row['total_size'] or 0,
            }
            for row in cursor.fetchall()
        ]

    def get_by_extension(self, limit: int = 50) -> List[Dict]:
        """Get file counts grouped by extension."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT
                LOWER(SUBSTR(original_path, INSTR(original_path, '.') + 1)) as extension,
                COUNT(*) as count,
                SUM(file_size) as total_size
            FROM file_registry
            WHERE original_path LIKE '%.%'
            GROUP BY extension
            ORDER BY count DESC
            LIMIT ?
        ''', (limit,))

        return [
            {
                'extension': row['extension'],
                'count': row['count'],
                'total_size': row['total_size'] or 0,
            }
            for row in cursor.fetchall()
        ]

    def get_by_classification_method(self) -> List[Dict]:
        """Get file counts grouped by classification method."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT
                classification_method,
                COUNT(*) as count,
                AVG(confidence) as avg_confidence
            FROM file_registry
            WHERE classification_method IS NOT NULL
            GROUP BY classification_method
            ORDER BY count DESC
        ''')

        return [
            {
                'method': row['classification_method'],
                'count': row['count'],
                'avg_confidence': row['avg_confidence'],
            }
            for row in cursor.fetchall()
        ]

    def get_confidence_distribution(self) -> Dict[str, int]:
        """Get distribution of confidence scores."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT
                CASE
                    WHEN confidence IS NULL THEN 'null'
                    WHEN confidence >= 0.9 THEN 'very_high (90%+)'
                    WHEN confidence >= 0.7 THEN 'high (70-90%)'
                    WHEN confidence >= 0.5 THEN 'medium (50-70%)'
                    WHEN confidence >= 0.3 THEN 'low (30-50%)'
                    ELSE 'very_low (<30%)'
                END as bucket,
                COUNT(*) as count
            FROM file_registry
            GROUP BY bucket
            ORDER BY count DESC
        ''')

        return {row['bucket']: row['count'] for row in cursor.fetchall()}

    def get_unknown_files(self, limit: int = 100) -> List[Dict]:
        """Get files marked as unknown."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT file_id, original_path, canonical_path, confidence, classification_method
            FROM file_registry
            WHERE document_type = 'unknown' OR document_type IS NULL
            LIMIT ?
        ''', (limit,))

        return [dict(row) for row in cursor.fetchall()]

    def get_low_confidence_files(self, threshold: float = 0.5, limit: int = 100) -> List[Dict]:
        """Get files with low classification confidence."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT file_id, original_path, document_type, confidence, classification_method
            FROM file_registry
            WHERE confidence IS NOT NULL AND confidence < ?
            ORDER BY confidence ASC
            LIMIT ?
        ''', (threshold, limit))

        return [dict(row) for row in cursor.fetchall()]

    def get_duplicates_summary(self) -> Dict[str, Any]:
        """Get summary of duplicate files if tracked."""
        cursor = self.conn.cursor()

        # Check if duplicate tracking columns exist
        cursor.execute("PRAGMA table_info(file_registry)")
        columns = {row['name'] for row in cursor.fetchall()}

        if 'content_hash' not in columns:
            return {'supported': False}

        cursor.execute('''
            SELECT content_hash, COUNT(*) as count, SUM(file_size) as total_size
            FROM file_registry
            WHERE content_hash IS NOT NULL
            GROUP BY content_hash
            HAVING COUNT(*) > 1
        ''')

        duplicates = cursor.fetchall()

        return {
            'supported': True,
            'duplicate_groups': len(duplicates),
            'total_duplicates': sum(row['count'] for row in duplicates),
            'wasted_space': sum(row['total_size'] * (row['count'] - 1) for row in duplicates),
        }

    def generate_report(self) -> str:
        """Generate a full text report of statistics."""
        lines = []
        lines.append("=" * 80)
        lines.append("FILE REGISTRY STATISTICS REPORT")
        lines.append(f"Generated: {datetime.now().isoformat()}")
        lines.append("=" * 80)

        # Overview
        overview = self.get_overview()
        lines.append("\n[OVERVIEW]")
        lines.append(f"  Total files:        {overview['total_files']:,}")
        lines.append(f"  Total size:         {overview['total_size_gb']:.2f} GB")
        lines.append(f"  Classified:         {overview['classified']:,} ({overview['classification_rate']*100:.1f}%)")
        lines.append(f"  NULL type:          {overview['null_type']:,}")
        lines.append(f"  Unknown type:       {overview['unknown_type']:,}")

        # By document type
        by_type = self.get_by_document_type(20)
        lines.append("\n[TOP 20 DOCUMENT TYPES]")
        for item in by_type:
            lines.append(f"  {item['document_type']:30} {item['count']:8,}")

        # By method
        by_method = self.get_by_classification_method()
        lines.append("\n[CLASSIFICATION METHODS]")
        for item in by_method:
            lines.append(f"  {item['method']:30} {item['count']:8,} (avg conf: {item['avg_confidence']:.2%})")

        # Confidence distribution
        conf_dist = self.get_confidence_distribution()
        lines.append("\n[CONFIDENCE DISTRIBUTION]")
        for bucket, count in conf_dist.items():
            lines.append(f"  {bucket:25} {count:8,}")

        lines.append("\n" + "=" * 80)

        return '\n'.join(lines)


class ProgressTracker:
    """Track progress for batch operations."""

    def __init__(self, total: int, report_interval: int = 100):
        """
        Initialize tracker.

        Args:
            total: Total items to process
            report_interval: How often to report progress
        """
        self.total = total
        self.processed = 0
        self.report_interval = report_interval
        self.start_time = datetime.now()
        self._last_report = 0

    def update(self, count: int = 1) -> Optional[str]:
        """
        Update progress.

        Args:
            count: Number of items processed

        Returns:
            Progress message if at report interval, else None
        """
        self.processed += count

        if self.processed - self._last_report >= self.report_interval:
            self._last_report = self.processed
            return self._progress_message()

        return None

    def _progress_message(self) -> str:
        """Generate progress message."""
        pct = self.processed / self.total * 100 if self.total > 0 else 0
        elapsed = (datetime.now() - self.start_time).total_seconds()
        rate = self.processed / elapsed if elapsed > 0 else 0
        remaining = (self.total - self.processed) / rate if rate > 0 else 0

        return f"Progress: {self.processed:,}/{self.total:,} ({pct:.1f}%) - {rate:.1f}/sec - ETA: {remaining:.0f}s"

    def finish(self) -> str:
        """Generate completion message."""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        rate = self.processed / elapsed if elapsed > 0 else 0

        return f"Completed: {self.processed:,} items in {elapsed:.1f}s ({rate:.1f}/sec)"
