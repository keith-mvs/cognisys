"""
Integration Tests for Content Extraction
Tests the complete content extraction pipeline with real files
"""

import pytest
import tempfile
import os
from pathlib import Path
from ifmos.ml.utils.content_extractor import ContentExtractor


class TestContentExtraction:
    """Test content extraction from various file types"""

    @pytest.fixture
    def extractor(self):
        """Create content extractor instance"""
        return ContentExtractor()

    @pytest.fixture
    def sample_txt_file(self):
        """Create a sample text file"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("This is a test document.\nIt has multiple lines.\n")
            f.write("Testing content extraction functionality.\n")
            temp_path = f.name

        yield temp_path
        try:
            os.unlink(temp_path)
        except:
            pass

    @pytest.fixture
    def sample_csv_file(self):
        """Create a sample CSV file"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
            f.write("Name,Age,City\n")
            f.write("John,30,New York\n")
            f.write("Jane,25,Los Angeles\n")
            temp_path = f.name

        yield temp_path
        try:
            os.unlink(temp_path)
        except:
            pass

    def test_extract_text_file(self, extractor, sample_txt_file):
        """Test extraction from plain text file"""
        result = extractor.extract_content(sample_txt_file)

        assert result['success'] is True
        assert len(result['text']) > 0
        assert "test document" in result['text'].lower()
        assert result['method'] == 'text'

    def test_extract_csv_file(self, extractor, sample_csv_file):
        """Test extraction from CSV file"""
        result = extractor.extract_content(sample_csv_file)

        assert result['success'] is True
        assert len(result['text']) > 0
        assert "Name" in result['text'] or "name" in result['text'].lower()
        assert result['method'] == 'text'

    def test_nonexistent_file(self, extractor):
        """Test handling of nonexistent file"""
        result = extractor.extract_content("/nonexistent/file.pdf")

        assert result['success'] is False
        assert 'not found' in result.get('error', '').lower()

    def test_unsupported_format(self, extractor):
        """Test handling of unsupported file format"""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.unknown') as f:
            temp_path = f.name

        try:
            result = extractor.extract_content(temp_path)
            assert result['success'] is False
            assert 'unsupported' in result.get('error', '').lower()
        finally:
            try:
                os.unlink(temp_path)
            except:
                pass

    def test_metadata_extraction(self, extractor, sample_txt_file):
        """Test that metadata is extracted correctly"""
        result = extractor.extract_content(sample_txt_file)

        assert 'metadata' in result
        assert 'file_name' in result['metadata']
        assert 'file_size' in result['metadata']
        assert result['metadata']['file_size'] > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
