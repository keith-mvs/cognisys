"""
Unit Tests for StatsCollector
Tests statistics collection and tracking functionality
"""

import pytest
import sqlite3
import tempfile
from pathlib import Path
from datetime import datetime

from cognisys.utils.stats_collector import (
    ClassificationStats,
    StatsCollector,
    ProgressTracker,
)


class TestClassificationStats:
    """Test ClassificationStats dataclass functionality."""

    def test_initial_state(self):
        """Stats should initialize with zeros."""
        stats = ClassificationStats()

        assert stats.total == 0
        assert stats.classified == 0
        assert stats.high_confidence == 0
        assert stats.low_confidence == 0
        assert stats.failed == 0
        assert len(stats.by_type) == 0
        assert len(stats.by_method) == 0

    def test_record_successful_classification(self):
        """Should track successful classifications."""
        stats = ClassificationStats()

        stats.record(
            doc_type='technical_script',
            confidence=0.95,
            method='pattern_override'
        )

        assert stats.total == 1
        assert stats.classified == 1
        assert stats.high_confidence == 1
        assert stats.failed == 0
        assert stats.by_type['technical_script'] == 1
        assert stats.by_method['pattern_override'] == 1

    def test_record_low_confidence(self):
        """Should track low confidence classifications."""
        stats = ClassificationStats()

        stats.record(
            doc_type='document_pdf',
            confidence=0.55,
            method='ml_model',
            confidence_threshold=0.70
        )

        assert stats.classified == 1
        assert stats.high_confidence == 0
        assert stats.low_confidence == 1

    def test_record_failed_classification(self):
        """Should track failed classifications."""
        stats = ClassificationStats()

        stats.record(
            doc_type=None,
            confidence=0.0,
            method='no_match'
        )

        assert stats.total == 1
        assert stats.classified == 0
        assert stats.failed == 1

    def test_record_with_old_type_changed(self):
        """Should track when classification changed."""
        stats = ClassificationStats()

        stats.record(
            doc_type='technical_script',
            confidence=0.95,
            method='pattern_override',
            old_type='unknown'
        )

        assert stats.changed == 1
        assert stats.unchanged == 0

    def test_record_with_old_type_unchanged(self):
        """Should track when classification unchanged."""
        stats = ClassificationStats()

        stats.record(
            doc_type='technical_script',
            confidence=0.95,
            method='pattern_override',
            old_type='technical_script'
        )

        assert stats.changed == 0
        assert stats.unchanged == 1

    def test_success_rate(self):
        """Should calculate success rate correctly."""
        stats = ClassificationStats()

        stats.record(doc_type='type1', confidence=0.9, method='m1')
        stats.record(doc_type='type2', confidence=0.8, method='m1')
        stats.record(doc_type=None, confidence=0.0, method='fail')

        assert stats.success_rate == pytest.approx(2/3)

    def test_high_confidence_rate(self):
        """Should calculate high confidence rate correctly."""
        stats = ClassificationStats()

        stats.record(doc_type='type1', confidence=0.95, method='m1')  # high
        stats.record(doc_type='type2', confidence=0.80, method='m1')  # high
        stats.record(doc_type='type3', confidence=0.50, method='m1')  # low

        assert stats.high_confidence_rate == pytest.approx(2/3)

    def test_to_dict(self):
        """Should convert to dictionary correctly."""
        stats = ClassificationStats()
        stats.record(doc_type='test', confidence=0.9, method='test')

        d = stats.to_dict()

        assert 'total' in d
        assert 'classified' in d
        assert 'success_rate' in d
        assert 'by_type' in d
        assert d['total'] == 1

    def test_summary(self):
        """Should generate summary string."""
        stats = ClassificationStats()
        stats.record(doc_type='test', confidence=0.9, method='test')

        summary = stats.summary()

        assert 'Total files' in summary
        assert 'Classified' in summary


class TestStatsCollector:
    """Test StatsCollector with actual database."""

    @pytest.fixture
    def test_db(self, tmp_path):
        """Create a temporary test database with sample data."""
        db_path = tmp_path / 'test_registry.db'

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Create minimal file_registry table
        cursor.execute('''
            CREATE TABLE file_registry (
                file_id TEXT PRIMARY KEY,
                original_path TEXT,
                canonical_path TEXT,
                file_size INTEGER,
                document_type TEXT,
                confidence REAL,
                classification_method TEXT,
                updated_at TEXT
            )
        ''')

        # Insert sample data
        sample_data = [
            ('f1', '/path/script.py', None, 1000, 'technical_script', 0.95, 'pattern_override', '2024-01-01'),
            ('f2', '/path/config.json', None, 500, 'technical_config', 0.98, 'pattern_override', '2024-01-01'),
            ('f3', '/path/report.pdf', None, 50000, 'document_pdf', 0.70, 'ml_model', '2024-01-01'),
            ('f4', '/path/video.mp4', None, 1000000, 'media_video', 0.95, 'pattern_extension', '2024-01-01'),
            ('f5', '/path/unknown.xyz', None, 200, 'unknown', 0.30, 'ml_model', '2024-01-01'),
            ('f6', '/path/null.abc', None, 100, None, None, None, None),
        ]

        cursor.executemany('''
            INSERT INTO file_registry
            (file_id, original_path, canonical_path, file_size, document_type, confidence, classification_method, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', sample_data)

        conn.commit()
        conn.close()

        yield str(db_path)

    def test_collector_initialization(self, test_db):
        """Collector should initialize correctly."""
        collector = StatsCollector(test_db)

        assert collector.db_path == test_db
        collector.close()

    def test_context_manager(self, test_db):
        """Collector should work as context manager."""
        with StatsCollector(test_db) as collector:
            assert collector is not None

    def test_get_overview(self, test_db):
        """Should return overview statistics."""
        with StatsCollector(test_db) as collector:
            overview = collector.get_overview()

        assert overview['total_files'] == 6
        assert overview['total_size_bytes'] > 0
        assert overview['classified'] == 4  # Not unknown or null
        assert overview['null_type'] == 1
        assert overview['unknown_type'] == 1

    def test_get_by_document_type(self, test_db):
        """Should return stats grouped by document type."""
        with StatsCollector(test_db) as collector:
            by_type = collector.get_by_document_type()

        assert len(by_type) > 0
        type_names = [t['document_type'] for t in by_type]
        assert 'technical_script' in type_names

    def test_get_by_classification_method(self, test_db):
        """Should return stats grouped by classification method."""
        with StatsCollector(test_db) as collector:
            by_method = collector.get_by_classification_method()

        assert len(by_method) > 0
        methods = [m['method'] for m in by_method]
        assert 'pattern_override' in methods

    def test_get_confidence_distribution(self, test_db):
        """Should return confidence distribution."""
        with StatsCollector(test_db) as collector:
            dist = collector.get_confidence_distribution()

        assert len(dist) > 0
        # Should have 'null' bucket
        assert 'null' in dist

    def test_get_unknown_files(self, test_db):
        """Should return unknown/null type files."""
        with StatsCollector(test_db) as collector:
            unknown = collector.get_unknown_files()

        assert len(unknown) == 2  # One 'unknown', one NULL

    def test_get_low_confidence_files(self, test_db):
        """Should return low confidence files."""
        with StatsCollector(test_db) as collector:
            low_conf = collector.get_low_confidence_files(threshold=0.5)

        assert len(low_conf) == 1  # Only the 0.30 confidence file
        assert low_conf[0]['confidence'] == 0.30

    def test_generate_report(self, test_db):
        """Should generate text report."""
        with StatsCollector(test_db) as collector:
            report = collector.generate_report()

        assert 'FILE REGISTRY STATISTICS REPORT' in report
        assert 'Total files' in report
        assert 'DOCUMENT TYPES' in report


class TestProgressTracker:
    """Test ProgressTracker functionality."""

    def test_tracker_initialization(self):
        """Tracker should initialize correctly."""
        tracker = ProgressTracker(total=100)

        assert tracker.total == 100
        assert tracker.processed == 0

    def test_update_returns_message_at_interval(self):
        """Should return progress message at report interval."""
        tracker = ProgressTracker(total=1000, report_interval=100)

        # First updates should return None
        for _ in range(99):
            msg = tracker.update()
            assert msg is None

        # 100th update should return message
        msg = tracker.update()
        assert msg is not None
        assert 'Progress' in msg
        assert '100' in msg

    def test_update_accumulates(self):
        """Should accumulate update counts."""
        tracker = ProgressTracker(total=100)

        tracker.update(5)
        tracker.update(10)
        tracker.update(3)

        assert tracker.processed == 18

    def test_finish_message(self):
        """Should generate completion message."""
        tracker = ProgressTracker(total=100)

        for _ in range(100):
            tracker.update()

        msg = tracker.finish()

        assert 'Completed' in msg
        assert '100' in msg

    def test_progress_percentage(self):
        """Should calculate correct percentage."""
        tracker = ProgressTracker(total=100, report_interval=10)

        for _ in range(50):
            tracker.update()

        # Manual check of percentage calculation
        msg = tracker._progress_message()
        assert '50.0%' in msg


class TestStatsCollectorEdgeCases:
    """Test edge cases for StatsCollector."""

    @pytest.fixture
    def empty_db(self, tmp_path):
        """Create an empty test database."""
        db_path = tmp_path / 'empty_registry.db'

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE file_registry (
                file_id TEXT PRIMARY KEY,
                original_path TEXT,
                canonical_path TEXT,
                file_size INTEGER,
                document_type TEXT,
                confidence REAL,
                classification_method TEXT,
                updated_at TEXT
            )
        ''')

        conn.commit()
        conn.close()

        yield str(db_path)

    def test_empty_database(self, empty_db):
        """Should handle empty database gracefully."""
        with StatsCollector(empty_db) as collector:
            overview = collector.get_overview()

        assert overview['total_files'] == 0
        assert overview['classification_rate'] == 0

    def test_duplicates_summary_unsupported(self, empty_db):
        """Should indicate when duplicate tracking not supported."""
        with StatsCollector(empty_db) as collector:
            summary = collector.get_duplicates_summary()

        assert summary['supported'] is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
