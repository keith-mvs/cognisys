"""
Unit Tests for Storage Interfaces
Tests FileSource, FileDestination, and related data structures
"""

import pytest
from pathlib import Path
from datetime import datetime
from io import BytesIO

from cognisys.storage.interfaces import (
    FileMetadata,
    FolderMetadata,
    ChangeRecord,
    ChangeType,
    SourceRegistry,
    FileNotAvailableError,
    SourceNotFoundError,
)


class TestFileMetadata:
    """Test FileMetadata dataclass functionality."""

    def test_create_file_metadata(self):
        """Should create FileMetadata with required fields."""
        metadata = FileMetadata(
            path='/test/document.pdf',
            name='document.pdf',
            size_bytes=5000
        )

        assert metadata.path == '/test/document.pdf'
        assert metadata.name == 'document.pdf'
        assert metadata.size_bytes == 5000
        assert metadata.is_directory is False
        assert metadata.source_type == 'local'

    def test_file_metadata_extension(self):
        """Extension property should return lowercase extension without dot."""
        metadata = FileMetadata(
            path='/test/file.PDF',
            name='file.PDF',
            size_bytes=100
        )

        assert metadata.extension == 'pdf'

    def test_file_metadata_extension_no_ext(self):
        """Extension should be empty for files without extension."""
        metadata = FileMetadata(
            path='/test/Makefile',
            name='Makefile',
            size_bytes=100
        )

        assert metadata.extension == ''

    def test_file_metadata_stem(self):
        """Stem property should return filename without extension."""
        metadata = FileMetadata(
            path='/test/report.pdf',
            name='report.pdf',
            size_bytes=100
        )

        assert metadata.stem == 'report'

    def test_file_metadata_stem_no_ext(self):
        """Stem should return full name when no extension."""
        metadata = FileMetadata(
            path='/test/README',
            name='README',
            size_bytes=100
        )

        assert metadata.stem == 'README'

    def test_file_metadata_stem_multiple_dots(self):
        """Stem should handle files with multiple dots."""
        metadata = FileMetadata(
            path='/test/backup.tar.gz',
            name='backup.tar.gz',
            size_bytes=100
        )

        assert metadata.stem == 'backup.tar'
        assert metadata.extension == 'gz'

    def test_guess_mime_type(self):
        """Should guess MIME type from extension."""
        metadata = FileMetadata(
            path='/test/doc.pdf',
            name='doc.pdf',
            size_bytes=100
        )

        mime = metadata.guess_mime_type()
        assert mime == 'application/pdf'

    def test_guess_mime_type_with_existing(self):
        """Should return existing MIME type if set."""
        metadata = FileMetadata(
            path='/test/doc.txt',
            name='doc.txt',
            size_bytes=100,
            mime_type='text/plain'
        )

        assert metadata.guess_mime_type() == 'text/plain'

    def test_file_metadata_with_timestamps(self):
        """Should accept timestamp fields."""
        now = datetime.now()
        metadata = FileMetadata(
            path='/test/file.txt',
            name='file.txt',
            size_bytes=100,
            created_at=now,
            modified_at=now,
            accessed_at=now
        )

        assert metadata.created_at == now
        assert metadata.modified_at == now
        assert metadata.accessed_at == now

    def test_file_metadata_cloud_fields(self):
        """Should support cloud-specific fields."""
        metadata = FileMetadata(
            path='/Documents/file.docx',
            name='file.docx',
            size_bytes=1000,
            source_type='onedrive',
            source_id='ABC123XYZ',
            etag='\"abc123\"',
            is_placeholder=True
        )

        assert metadata.source_type == 'onedrive'
        assert metadata.source_id == 'ABC123XYZ'
        assert metadata.etag == '\"abc123\"'
        assert metadata.is_placeholder is True

    def test_file_metadata_extra_dict(self):
        """Should store provider-specific data in extra."""
        metadata = FileMetadata(
            path='/test/file.txt',
            name='file.txt',
            size_bytes=100,
            extra={'onedrive_weburl': 'https://onedrive.com/file'}
        )

        assert metadata.extra['onedrive_weburl'] == 'https://onedrive.com/file'


class TestFolderMetadata:
    """Test FolderMetadata dataclass functionality."""

    def test_create_folder_metadata(self):
        """Should create FolderMetadata with required fields."""
        metadata = FolderMetadata(
            path='/test/documents',
            name='documents'
        )

        assert metadata.path == '/test/documents'
        assert metadata.name == 'documents'
        assert metadata.depth == 0
        assert metadata.source_type == 'local'

    def test_folder_metadata_with_stats(self):
        """Should support file/folder count statistics."""
        metadata = FolderMetadata(
            path='/test/docs',
            name='docs',
            depth=2,
            file_count=100,
            subfolder_count=10,
            total_size_bytes=50000000
        )

        assert metadata.file_count == 100
        assert metadata.subfolder_count == 10
        assert metadata.total_size_bytes == 50000000


class TestChangeRecord:
    """Test ChangeRecord dataclass functionality."""

    def test_create_change_record(self):
        """Should create ChangeRecord with required fields."""
        record = ChangeRecord(
            path='/test/file.txt',
            change_type=ChangeType.CREATED
        )

        assert record.path == '/test/file.txt'
        assert record.change_type == ChangeType.CREATED

    def test_change_record_with_metadata(self):
        """Should support optional metadata."""
        metadata = FileMetadata(
            path='/test/file.txt',
            name='file.txt',
            size_bytes=1000
        )

        record = ChangeRecord(
            path='/test/file.txt',
            change_type=ChangeType.MODIFIED,
            modified_at=datetime.now(),
            size=1000,
            metadata=metadata
        )

        assert record.metadata is not None
        assert record.size == 1000

    def test_change_record_rename(self):
        """Should support rename with old_path."""
        record = ChangeRecord(
            path='/test/new_name.txt',
            change_type=ChangeType.RENAMED,
            old_path='/test/old_name.txt'
        )

        assert record.change_type == ChangeType.RENAMED
        assert record.old_path == '/test/old_name.txt'


class TestChangeType:
    """Test ChangeType enum."""

    def test_change_type_values(self):
        """Should have expected change types."""
        assert ChangeType.CREATED.value == 'created'
        assert ChangeType.MODIFIED.value == 'modified'
        assert ChangeType.DELETED.value == 'deleted'
        assert ChangeType.RENAMED.value == 'renamed'


class TestSourceRegistry:
    """Test SourceRegistry for managing multiple sources."""

    def test_registry_initialization(self):
        """Registry should initialize with empty sources."""
        registry = SourceRegistry()

        assert len(registry.list_sources()) == 0
        assert len(registry.list_destinations()) == 0

    def test_register_and_get_source(self):
        """Should register and retrieve sources by name."""
        registry = SourceRegistry()

        # Create a mock source (just need something with the right interface for testing)
        class MockSource:
            pass

        source = MockSource()
        registry.register_source('test_source', source)

        assert registry.get_source('test_source') == source
        assert 'test_source' in registry.list_sources()

    def test_get_nonexistent_source(self):
        """Should return None for nonexistent source."""
        registry = SourceRegistry()

        assert registry.get_source('nonexistent') is None

    def test_register_multiple_sources(self):
        """Should handle multiple registered sources."""
        registry = SourceRegistry()

        class MockSource:
            pass

        registry.register_source('source1', MockSource())
        registry.register_source('source2', MockSource())
        registry.register_source('source3', MockSource())

        sources = registry.list_sources()
        assert len(sources) == 3
        assert 'source1' in sources
        assert 'source2' in sources
        assert 'source3' in sources

    def test_register_destination(self):
        """Should register and retrieve destinations."""
        registry = SourceRegistry()

        class MockDestination:
            pass

        dest = MockDestination()
        registry.register_destination('canonical', dest)

        assert registry.get_destination('canonical') == dest
        assert 'canonical' in registry.list_destinations()


class TestExceptions:
    """Test custom exception types."""

    def test_file_not_available_error(self):
        """FileNotAvailableError should be raisable with message."""
        with pytest.raises(FileNotAvailableError):
            raise FileNotAvailableError("File is a cloud placeholder")

    def test_source_not_found_error(self):
        """SourceNotFoundError should be raisable with message."""
        with pytest.raises(SourceNotFoundError):
            raise SourceNotFoundError("Path does not exist")


class TestLocalFileSourceInterface:
    """Test expectations for LocalFileSource implementations."""

    def test_interface_expectations(self):
        """Document expected interface methods for FileSource."""
        # This test documents the interface that implementations must provide
        expected_methods = [
            'source_type',  # property
            'root_path',    # property
            'walk',
            'list_directory',
            'get_metadata',
            'read_stream',
            'read_bytes',
            'exists',
            'is_file',
            'is_directory',
            'resolve_path',
        ]

        # This is documentation, not enforcement
        # Real tests would verify concrete implementations
        assert len(expected_methods) == 11


class TestFileDestinationInterface:
    """Test expectations for FileDestination implementations."""

    def test_interface_expectations(self):
        """Document expected interface methods for FileDestination."""
        expected_methods = [
            'source_type',  # property
            'root_path',    # property
            'write_stream',
            'write_bytes',
            'mkdir',
            'move',
            'copy',
            'delete',
            'exists',
        ]

        assert len(expected_methods) == 9


class TestSyncableSourceInterface:
    """Test expectations for SyncableSource implementations."""

    def test_interface_expectations(self):
        """Document expected interface for bidirectional sync."""
        expected_methods = [
            # FileSource methods
            'walk',
            'list_directory',
            'get_metadata',
            'read_stream',
            'read_bytes',
            'exists',
            'is_file',
            'is_directory',
            # FileDestination methods
            'write_stream',
            'write_bytes',
            'mkdir',
            'move',
            'copy',
            'delete',
            # SyncableSource specific
            'get_changes_since',
            'upload',
            'download',
            'get_sync_token',
        ]

        assert len(expected_methods) == 18


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
