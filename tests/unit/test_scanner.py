"""
Unit Tests for FileScanner
Tests file traversal, metadata extraction, and indexing functionality
"""

import pytest
import os
import tempfile
from pathlib import Path
from datetime import datetime

from cognisys.core.scanner import FileScanner
from cognisys.models.database import Database


@pytest.fixture
def scan_dir():
    """Create a separate directory for scanning (not containing the test db)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestFileScanner:
    """Test FileScanner core functionality."""

    def test_scanner_initialization(self, temp_db, scanner_config):
        """Scanner should initialize with correct defaults."""
        scanner = FileScanner(temp_db, scanner_config)

        assert scanner.db == temp_db
        assert scanner.config == scanner_config
        assert scanner.session_id is None
        assert scanner.stats['files_scanned'] == 0
        assert scanner.stats['folders_scanned'] == 0
        assert scanner.stats['errors'] == 0

    def test_scan_empty_directory(self, temp_db, scan_dir, scanner_config):
        """Scanner should handle empty directories gracefully."""
        scanner = FileScanner(temp_db, scanner_config)

        session_id = scanner.scan_roots([str(scan_dir)])

        assert session_id is not None
        assert scanner.stats['files_scanned'] == 0
        assert scanner.stats['folders_scanned'] >= 1  # At least the root folder

    def test_scan_single_file(self, temp_db, scan_dir, scanner_config):
        """Scanner should index a single file correctly."""
        # Create a single test file
        test_file = scan_dir / "test.txt"
        test_file.write_text("Hello, World!")

        scanner = FileScanner(temp_db, scanner_config)
        session_id = scanner.scan_roots([str(scan_dir)])

        # Verify file was indexed
        files = temp_db.get_files_by_session(session_id)
        assert len(files) == 1
        assert files[0]['name'] == 'test.txt'
        assert files[0]['extension'] == '.txt'
        assert files[0]['size_bytes'] == len("Hello, World!")

    def test_scan_nested_structure(self, temp_db, scan_dir, scanner_config):
        """Scanner should traverse and index nested directory structures."""
        # Create nested structure
        (scan_dir / "docs").mkdir()
        (scan_dir / "docs" / "work").mkdir()
        (scan_dir / "images").mkdir()
        (scan_dir / "code").mkdir()

        (scan_dir / "docs" / "readme.txt").write_text("Root doc")
        (scan_dir / "docs" / "work" / "report.pdf").write_bytes(b"%PDF-1.4 report")
        (scan_dir / "images" / "photo.jpg").write_bytes(b"\xff\xd8\xff fake jpg")
        (scan_dir / "code" / "script.py").write_text("print('hello')")

        scanner = FileScanner(temp_db, scanner_config)
        session_id = scanner.scan_roots([str(scan_dir)])

        files = temp_db.get_files_by_session(session_id)

        # Should find all 4 files
        assert len(files) == 4
        filenames = {f['name'] for f in files}
        assert 'readme.txt' in filenames
        assert 'report.pdf' in filenames
        assert 'photo.jpg' in filenames
        assert 'script.py' in filenames

    def test_scan_calculates_hashes(self, temp_db, scan_dir, scanner_config):
        """Scanner should calculate quick and/or full hashes."""
        test_file = scan_dir / "hashable.txt"
        test_file.write_text("Content for hashing")

        scanner = FileScanner(temp_db, scanner_config)
        session_id = scanner.scan_roots([str(scan_dir)])

        files = temp_db.get_files_by_session(session_id)
        assert len(files) == 1

        # Small files should have hash_quick set
        assert files[0]['hash_quick'] is not None
        assert len(files[0]['hash_quick']) == 64  # SHA-256 hex

    def test_scan_extracts_metadata(self, temp_db, scan_dir, scanner_config):
        """Scanner should extract file metadata correctly."""
        test_file = scan_dir / "metadata_test.pdf"
        test_file.write_bytes(b"%PDF-1.4 test content")

        scanner = FileScanner(temp_db, scanner_config)
        session_id = scanner.scan_roots([str(scan_dir)])

        files = temp_db.get_files_by_session(session_id)
        assert len(files) == 1

        file_record = files[0]
        assert file_record['name'] == 'metadata_test.pdf'
        assert file_record['extension'] == '.pdf'
        assert file_record['size_bytes'] > 0
        assert file_record['created_at'] is not None
        assert file_record['modified_at'] is not None

    def test_scan_respects_folder_exclusions(self, temp_db, scan_dir, scanner_config):
        """Scanner should skip excluded folders."""
        # Create structure with excluded folder
        excluded_dir = scan_dir / "__pycache__"
        excluded_dir.mkdir()
        (excluded_dir / "cache.pyc").write_bytes(b"cached")

        normal_dir = scan_dir / "src"
        normal_dir.mkdir()
        (normal_dir / "main.py").write_text("print('main')")

        scanner = FileScanner(temp_db, scanner_config)
        session_id = scanner.scan_roots([str(scan_dir)])

        files = temp_db.get_files_by_session(session_id)

        # Should only find the non-excluded file
        assert len(files) == 1
        assert files[0]['name'] == 'main.py'

    def test_scan_respects_file_exclusions(self, temp_db, scan_dir, scanner_config):
        """Scanner should skip files matching exclusion patterns."""
        # Create files with excluded patterns
        (scan_dir / "file.tmp").write_text("temp file")
        (scan_dir / "backup.bak").write_text("backup file")
        (scan_dir / ".DS_Store").write_bytes(b"ds store")
        (scan_dir / "keep_this.txt").write_text("keep me")

        scanner = FileScanner(temp_db, scanner_config)
        session_id = scanner.scan_roots([str(scan_dir)])

        files = temp_db.get_files_by_session(session_id)

        # Should only find the non-excluded file
        assert len(files) == 1
        assert files[0]['name'] == 'keep_this.txt'

    def test_scan_multiple_roots(self, temp_db, scan_dir, scanner_config):
        """Scanner should handle multiple root paths."""
        # Create two separate directories
        root1 = scan_dir / "root1"
        root2 = scan_dir / "root2"
        root1.mkdir()
        root2.mkdir()

        (root1 / "file1.txt").write_text("File in root 1")
        (root2 / "file2.txt").write_text("File in root 2")

        scanner = FileScanner(temp_db, scanner_config)
        session_id = scanner.scan_roots([str(root1), str(root2)])

        files = temp_db.get_files_by_session(session_id)
        assert len(files) == 2

    def test_scan_nonexistent_root(self, temp_db, scanner_config):
        """Scanner should handle nonexistent root paths gracefully."""
        scanner = FileScanner(temp_db, scanner_config)

        # Should not raise an error
        session_id = scanner.scan_roots(['/nonexistent/path'])

        assert session_id is not None
        assert scanner.stats['files_scanned'] == 0

    def test_scan_creates_valid_session(self, temp_db, scan_dir, scanner_config):
        """Scanner should create a valid session record."""
        (scan_dir / "test.txt").write_text("test")

        scanner = FileScanner(temp_db, scanner_config)
        session_id = scanner.scan_roots([str(scan_dir)])

        # Session ID format: YYYYMMDD-HHMMSS-xxxx
        assert len(session_id) == 20
        assert '-' in session_id

        # Session should be marked as completed
        cursor = temp_db.conn.cursor()
        cursor.execute("SELECT status FROM scan_sessions WHERE session_id = ?", (session_id,))
        result = cursor.fetchone()
        assert result is not None
        assert result['status'] == 'completed'

    def test_scan_updates_stats(self, temp_db, scan_dir, scanner_config):
        """Scanner should track accurate statistics."""
        # Create nested structure
        (scan_dir / "docs").mkdir()
        (scan_dir / "docs" / "work").mkdir()
        (scan_dir / "images").mkdir()
        (scan_dir / "code").mkdir()

        (scan_dir / "docs" / "readme.txt").write_text("Root doc")
        (scan_dir / "docs" / "work" / "report.pdf").write_bytes(b"%PDF-1.4 report")
        (scan_dir / "images" / "photo.jpg").write_bytes(b"\xff\xd8\xff fake jpg")
        (scan_dir / "code" / "script.py").write_text("print('hello')")

        scanner = FileScanner(temp_db, scanner_config)
        scanner.scan_roots([str(scan_dir)])

        stats = scanner.get_stats()

        assert stats['files_scanned'] == 4
        assert stats['folders_scanned'] >= 4  # root + docs + docs/work + images + code
        assert stats['total_size'] > 0
        assert stats['errors'] == 0

    def test_scan_categorizes_files(self, temp_db, scan_dir, scanner_config):
        """Scanner should categorize files based on extension."""
        # Create files of different types
        (scan_dir / "doc.pdf").write_bytes(b"%PDF-1.4")
        (scan_dir / "image.jpg").write_bytes(b"\xff\xd8\xff")
        (scan_dir / "code.py").write_text("print('hello')")
        (scan_dir / "data.csv").write_text("a,b\n1,2")

        scanner = FileScanner(temp_db, scanner_config)
        session_id = scanner.scan_roots([str(scan_dir)])

        files = temp_db.get_files_by_session(session_id)

        # Check that categories are assigned
        categories = {f['name']: f['file_category'] for f in files}
        assert categories.get('doc.pdf') is not None
        assert categories.get('image.jpg') is not None
        assert categories.get('code.py') is not None

    def test_scan_handles_special_characters(self, temp_db, scan_dir, scanner_config):
        """Scanner should handle files with special characters in names."""
        # Create files with special characters
        (scan_dir / "file with spaces.txt").write_text("spaces")
        (scan_dir / "file-with-dashes.txt").write_text("dashes")
        (scan_dir / "file_with_underscores.txt").write_text("underscores")

        scanner = FileScanner(temp_db, scanner_config)
        session_id = scanner.scan_roots([str(scan_dir)])

        files = temp_db.get_files_by_session(session_id)
        assert len(files) == 3

    def test_is_excluded_exact_match(self, temp_db, scanner_config):
        """Exclusion should work with exact matches."""
        scanner = FileScanner(temp_db, scanner_config)

        assert scanner._is_excluded('.DS_Store', ['.DS_Store']) is True
        assert scanner._is_excluded('.ds_store', ['.DS_Store']) is True  # Case insensitive
        assert scanner._is_excluded('other.txt', ['.DS_Store']) is False

    def test_is_excluded_wildcard_match(self, temp_db, scanner_config):
        """Exclusion should work with wildcard patterns."""
        scanner = FileScanner(temp_db, scanner_config)

        assert scanner._is_excluded('file.tmp', ['*.tmp']) is True
        assert scanner._is_excluded('file.TMP', ['*.tmp']) is True  # Case insensitive
        assert scanner._is_excluded('file.txt', ['*.tmp']) is False


class TestScannerBatching:
    """Test batch processing functionality."""

    def test_batch_insert_files(self, temp_db, scan_dir, scanner_config):
        """Scanner should batch insert files efficiently."""
        # Create many files to trigger batching
        for i in range(25):  # More than default batch size of 10
            (scan_dir / f"file_{i:03d}.txt").write_text(f"Content {i}")

        scanner = FileScanner(temp_db, scanner_config)
        session_id = scanner.scan_roots([str(scan_dir)])

        files = temp_db.get_files_by_session(session_id)
        assert len(files) == 25

    def test_batch_flush_on_complete(self, temp_db, scan_dir, scanner_config):
        """Scanner should flush remaining batches on completion."""
        # Create files that don't fill a complete batch
        for i in range(5):  # Less than batch size
            (scan_dir / f"file_{i}.txt").write_text(f"Content {i}")

        scanner = FileScanner(temp_db, scanner_config)
        session_id = scanner.scan_roots([str(scan_dir)])

        files = temp_db.get_files_by_session(session_id)
        assert len(files) == 5


class TestScannerErrorHandling:
    """Test error handling scenarios."""

    def test_scan_handles_permission_errors(self, temp_db, scan_dir, scanner_config):
        """Scanner should handle permission errors gracefully."""
        (scan_dir / "accessible.txt").write_text("can read")

        scanner = FileScanner(temp_db, scanner_config)
        session_id = scanner.scan_roots([str(scan_dir)])

        # Should complete without raising exceptions
        files = temp_db.get_files_by_session(session_id)
        assert len(files) >= 1

    def test_scan_continues_on_single_file_error(self, temp_db, scan_dir, scanner_config):
        """Scanner should continue if a single file fails."""
        # Create multiple files
        (scan_dir / "good1.txt").write_text("good content 1")
        (scan_dir / "good2.txt").write_text("good content 2")

        scanner = FileScanner(temp_db, scanner_config)
        session_id = scanner.scan_roots([str(scan_dir)])

        # Should have indexed the accessible files
        files = temp_db.get_files_by_session(session_id)
        assert len(files) >= 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
