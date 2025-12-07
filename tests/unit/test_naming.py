"""
Unit Tests for Naming Utilities
Tests filename normalization and sanitization
"""

import pytest
from cognisys.utils.naming import normalize_filename, sanitize_name


class TestNaming:
    """Test filename normalization and sanitization"""

    def test_normalize_basic(self):
        """Test basic filename normalization"""
        assert normalize_filename("Test_File.pdf") == "test_file.pdf"
        assert normalize_filename("UPPERCASE.TXT") == "uppercase.txt"

    def test_normalize_with_spaces(self):
        """Test normalization with spaces"""
        filename = "My Document File.pdf"
        normalized = normalize_filename(filename)
        assert " " not in normalized
        assert "_" in normalized or "-" in normalized

    def test_sanitize_special_characters(self):
        """Test sanitization of special characters"""
        dangerous = "file<name>.txt"
        safe = sanitize_name(dangerous)
        assert "<" not in safe
        assert ">" not in safe

    def test_sanitize_path_traversal(self):
        """Test protection against path traversal"""
        malicious = "../../../etc/passwd"
        safe = sanitize_name(malicious)
        assert ".." not in safe
        assert "/" not in safe

    def test_sanitize_windows_reserved(self):
        """Test handling of Windows reserved characters"""
        reserved = "file:name?.txt"
        safe = sanitize_name(reserved)
        assert ":" not in safe
        assert "?" not in safe

    def test_sanitize_unicode(self):
        """Test handling of unicode characters"""
        unicode_name = "文档.pdf"
        safe = sanitize_name(unicode_name)
        # Should either preserve or convert to safe ASCII
        assert len(safe) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
