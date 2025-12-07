"""
Unit Tests for Database Layer
Tests SQLite operations and schema management
"""

import pytest
import json
from datetime import datetime

from cognisys.models.database import Database


class TestDatabase:
    """Test database operations."""

    def test_database_creation(self, temp_db):
        """Database should be created with proper schema."""
        cursor = temp_db.conn.cursor()

        # Check core tables exist
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table'
            ORDER BY name
        """)
        tables = [row[0] for row in cursor.fetchall()]

        assert 'files' in tables
        assert 'folders' in tables
        assert 'scan_sessions' in tables
        assert 'duplicate_groups' in tables
        assert 'migration_plans' in tables

    def test_create_session(self, temp_db):
        """Should create scan session with proper ID format."""
        session_id = temp_db.create_session(
            root_paths=['/test/path'],
            config={'test': 'config'}
        )

        assert session_id is not None
        # Format: YYYYMMDD-HHMMSS-xxxx
        assert len(session_id) == 20
        assert '-' in session_id

    def test_insert_and_get_file(self, temp_db):
        """Should insert and retrieve file records."""
        session_id = temp_db.create_session(['/test'], {})

        file_record = {
            'file_id': 'test-file-001',
            'path': '/test/document.pdf',
            'parent_id': None,
            'name': 'document.pdf',
            'extension': '.pdf',
            'size_bytes': 1024,
            'created_at': datetime.now(),
            'modified_at': datetime.now(),
            'accessed_at': datetime.now(),
            'mime_type': 'application/pdf',
            'file_category': 'document',
            'file_subcategory': 'pdf',
            'hash_quick': 'abc123',
            'hash_full': 'abc123full',
            'scan_session_id': session_id
        }

        temp_db.insert_file(file_record)

        files = temp_db.get_files_by_session(session_id)
        assert len(files) == 1
        assert files[0]['name'] == 'document.pdf'
        assert files[0]['size_bytes'] == 1024

    def test_insert_folder(self, temp_db):
        """Should insert folder records."""
        session_id = temp_db.create_session(['/test'], {})

        folder_record = {
            'folder_id': 'folder-001',
            'path': '/test/documents',
            'parent_id': None,
            'name': 'documents',
            'depth': 1,
            'total_size': 5000,
            'file_count': 10,
            'subfolder_count': 2,
            'folder_type': 'documents',
            'created_at': datetime.now(),
            'modified_at': datetime.now(),
            'scan_session_id': session_id
        }

        temp_db.insert_folder(folder_record)

        cursor = temp_db.conn.cursor()
        cursor.execute("SELECT * FROM folders WHERE folder_id = ?", ('folder-001',))
        folder = cursor.fetchone()

        assert folder is not None
        assert folder['name'] == 'documents'

    def test_get_duplicate_candidates(self, temp_db):
        """Should find potential duplicates by size and extension."""
        session_id = temp_db.create_session(['/test'], {})

        # Insert multiple files with same size and extension
        for i in range(3):
            temp_db.insert_file({
                'file_id': f'file-{i}',
                'path': f'/test/file{i}.txt',
                'name': f'file{i}.txt',
                'extension': '.txt',
                'size_bytes': 1000,  # Same size
                'scan_session_id': session_id
            })

        # Insert a unique file
        temp_db.insert_file({
            'file_id': 'file-unique',
            'path': '/test/unique.txt',
            'name': 'unique.txt',
            'extension': '.txt',
            'size_bytes': 2000,  # Different size
            'scan_session_id': session_id
        })

        candidates = temp_db.get_duplicate_candidates(session_id)

        # Should find the 3 files with same size
        assert len(candidates) == 1
        assert candidates[0]['cnt'] == 3

    def test_update_file_hash(self, temp_db):
        """Should update file hashes."""
        session_id = temp_db.create_session(['/test'], {})

        temp_db.insert_file({
            'file_id': 'file-001',
            'path': '/test/file.txt',
            'name': 'file.txt',
            'extension': '.txt',
            'size_bytes': 100,
            'hash_quick': 'initial',
            'scan_session_id': session_id
        })

        temp_db.update_file_hash('file-001', 'full', 'computed_full_hash')

        cursor = temp_db.conn.cursor()
        cursor.execute("SELECT hash_full FROM files WHERE file_id = ?", ('file-001',))
        result = cursor.fetchone()

        assert result['hash_full'] == 'computed_full_hash'

    def test_create_duplicate_group(self, temp_db):
        """Should create duplicate groups with members."""
        session_id = temp_db.create_session(['/test'], {})

        # Create files first
        for i in range(3):
            temp_db.insert_file({
                'file_id': f'dup-file-{i}',
                'path': f'/test/dup{i}.txt',
                'name': f'dup{i}.txt',
                'extension': '.txt',
                'size_bytes': 1000,
                'scan_session_id': session_id
            })

        group_data = {
            'canonical_file': 'dup-file-0',
            'member_count': 3,
            'total_size': 1000,
            'similarity_type': 'exact',
            'detection_rule': 'full_hash_match',
            'members': [
                {'file_id': 'dup-file-0', 'priority_score': 100, 'reason': 'canonical'},
                {'file_id': 'dup-file-1', 'priority_score': 80, 'reason': 'duplicate'},
                {'file_id': 'dup-file-2', 'priority_score': 60, 'reason': 'duplicate'},
            ]
        }

        group_id = temp_db.create_duplicate_group(group_data)

        assert group_id is not None
        assert group_id.startswith('dup-')

        # Verify files are marked as duplicates
        cursor = temp_db.conn.cursor()
        cursor.execute("SELECT is_duplicate FROM files WHERE file_id = ?", ('dup-file-1',))
        result = cursor.fetchone()
        assert result['is_duplicate'] == 1

    def test_ml_classification_operations(self, temp_db):
        """Should handle ML classification records."""
        session_id = temp_db.create_session(['/test'], {})

        temp_db.insert_file({
            'file_id': 'ml-file-001',
            'path': '/test/doc.pdf',
            'name': 'doc.pdf',
            'extension': '.pdf',
            'size_bytes': 5000,
            'scan_session_id': session_id
        })

        classification = {
            'file_id': 'ml-file-001',
            'model_name': 'distilbert_v2',
            'predicted_category': 'tax_document',
            'confidence': 0.95,
            'probabilities': {'tax_document': 0.95, 'receipt': 0.03, 'other': 0.02},
            'session_id': session_id
        }

        temp_db.insert_ml_classification(classification)

        results = temp_db.get_ml_classifications(session_id)
        assert len(results) == 1
        assert results[0]['predicted_category'] == 'tax_document'
        assert results[0]['confidence'] == 0.95

    def test_batch_classification_insert(self, temp_db):
        """Should handle batch classification inserts."""
        session_id = temp_db.create_session(['/test'], {})

        # Create test files
        for i in range(5):
            temp_db.insert_file({
                'file_id': f'batch-file-{i}',
                'path': f'/test/doc{i}.pdf',
                'name': f'doc{i}.pdf',
                'extension': '.pdf',
                'size_bytes': 1000,
                'scan_session_id': session_id
            })

        classifications = [
            {
                'file_id': f'batch-file-{i}',
                'model_name': 'test_model',
                'predicted_category': 'document',
                'confidence': 0.8 + i * 0.02,
                'session_id': session_id
            }
            for i in range(5)
        ]

        temp_db.insert_ml_classifications_batch(classifications)

        stats = temp_db.get_classification_stats(session_id)
        assert len(stats) == 1
        assert stats[0]['total'] == 5

    def test_overview_stats(self, temp_db):
        """Should compute correct overview statistics."""
        session_id = temp_db.create_session(['/test'], {})

        # Insert test data
        for i in range(10):
            temp_db.insert_file({
                'file_id': f'stat-file-{i}',
                'path': f'/test/file{i}.txt',
                'name': f'file{i}.txt',
                'extension': '.txt',
                'size_bytes': 100 * (i + 1),
                'scan_session_id': session_id
            })

        stats = temp_db.get_overview_stats(session_id)

        assert stats['total_files'] == 10
        assert stats['total_size'] == sum(100 * (i + 1) for i in range(10))


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
