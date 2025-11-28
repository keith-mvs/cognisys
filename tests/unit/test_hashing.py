"""
Unit Tests for Hashing Utilities
Tests progressive hashing strategy and hash calculations
"""

import pytest
import tempfile
import os
from pathlib import Path
from ifmos.utils.hashing import calculate_quick_hash, calculate_full_hash, calculate_adaptive_hash


class TestHashing:
    """Test progressive hashing functionality"""

    @pytest.fixture
    def temp_files(self):
        """Create temporary test files"""
        files = {}

        # Small file (<1MB)
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("Small file content for testing" * 100)
            files['small'] = f.name

        # Medium file (2MB)
        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.dat') as f:
            f.write(b"Medium file content" * 100000)
            files['medium'] = f.name

        yield files

        # Cleanup
        for file_path in files.values():
            try:
                os.unlink(file_path)
            except:
                pass

    def test_quick_hash_consistency(self, temp_files):
        """Quick hash should be consistent for same file"""
        file_path = temp_files['medium']

        hash1 = calculate_quick_hash(file_path)
        hash2 = calculate_quick_hash(file_path)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex string

    def test_full_hash_consistency(self, temp_files):
        """Full hash should be consistent for same file"""
        file_path = temp_files['small']

        hash1 = calculate_full_hash(file_path)
        hash2 = calculate_full_hash(file_path)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex string

    def test_adaptive_hash_small_file(self, temp_files):
        """Adaptive hash should use full hash for small files"""
        file_path = temp_files['small']
        file_size = os.path.getsize(file_path)

        quick_hash, full_hash = calculate_adaptive_hash(file_path, file_size)
        expected_full = calculate_full_hash(file_path)

        # Small files should have both hashes equal to full hash
        assert full_hash == expected_full
        assert quick_hash == expected_full

    def test_adaptive_hash_large_file(self, temp_files):
        """Adaptive hash should use quick hash for large files"""
        file_path = temp_files['medium']
        file_size = os.path.getsize(file_path)

        quick_hash, full_hash = calculate_adaptive_hash(file_path, file_size)
        expected_quick = calculate_quick_hash(file_path)

        # Large files should have quick hash
        assert quick_hash == expected_quick
        # Full hash should be None for large files initially
        assert full_hash is None or full_hash == quick_hash

    def test_hash_different_files(self, temp_files):
        """Different files should have different hashes"""
        hash1 = calculate_full_hash(temp_files['small'])
        hash2 = calculate_full_hash(temp_files['medium'])

        assert hash1 != hash2

    def test_nonexistent_file(self):
        """Should handle nonexistent files gracefully"""
        result = calculate_full_hash("/nonexistent/file.txt")
        # Functions return None for errors instead of raising exceptions
        assert result is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
