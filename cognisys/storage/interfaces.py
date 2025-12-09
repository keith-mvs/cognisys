"""
Storage Interface Definitions

Abstract base classes for file system operations that can be implemented
by different backends (local, network, cloud).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import (
    Any,
    BinaryIO,
    Dict,
    Iterator,
    List,
    Optional,
    Tuple,
    Union,
)
import mimetypes


class ChangeType(Enum):
    """Type of file change for sync operations."""
    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"


class FileNotAvailableError(Exception):
    """Raised when a file is not locally available (e.g., cloud placeholder)."""
    pass


class SourceNotFoundError(Exception):
    """Raised when a source path does not exist."""
    pass


@dataclass
class FileMetadata:
    """
    Metadata for a single file.

    This is the common data structure returned by all FileSource implementations.
    """

    path: str                              # Full path (relative to source root or absolute)
    name: str                              # File name only
    size_bytes: int                        # File size in bytes
    created_at: Optional[datetime] = None  # Creation time
    modified_at: Optional[datetime] = None # Last modification time
    accessed_at: Optional[datetime] = None # Last access time
    mime_type: Optional[str] = None        # MIME type (guessed from extension)
    is_directory: bool = False             # True if this is a directory
    source_type: str = 'local'             # 'local', 'network', 'onedrive', etc.
    source_id: Optional[str] = None        # Cloud provider's file ID
    etag: Optional[str] = None             # ETag for change detection
    content_hash: Optional[str] = None     # Content hash if available
    is_placeholder: bool = False           # True if cloud placeholder (not downloaded)
    extra: Dict[str, Any] = field(default_factory=dict)  # Provider-specific data

    @property
    def extension(self) -> str:
        """File extension (lowercase, without dot)."""
        if '.' in self.name:
            return self.name.rsplit('.', 1)[-1].lower()
        return ''

    @property
    def stem(self) -> str:
        """File name without extension."""
        if '.' in self.name:
            return self.name.rsplit('.', 1)[0]
        return self.name

    def guess_mime_type(self) -> Optional[str]:
        """Guess MIME type from file extension."""
        if self.mime_type:
            return self.mime_type
        mime, _ = mimetypes.guess_type(self.name)
        return mime


@dataclass
class FolderMetadata:
    """
    Metadata for a folder/directory.
    """

    path: str                              # Full path
    name: str                              # Folder name
    depth: int = 0                         # Depth from root
    created_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None
    source_type: str = 'local'
    source_id: Optional[str] = None        # Cloud provider's folder ID
    file_count: int = 0                    # Number of files (if known)
    subfolder_count: int = 0               # Number of subfolders (if known)
    total_size_bytes: int = 0              # Total size (if known)


@dataclass
class ChangeRecord:
    """
    Record of a file change (for delta sync).
    """

    path: str
    change_type: ChangeType
    modified_at: Optional[datetime] = None
    size: Optional[int] = None
    old_path: Optional[str] = None  # For renames
    metadata: Optional[FileMetadata] = None
    cloud_id: Optional[str] = None
    etag: Optional[str] = None


class FileSource(ABC):
    """
    Abstract interface for reading files from a storage backend.

    Implementations:
    - LocalFileSource: Local filesystem
    - NetworkFileSource: Network shares (SMB/NFS)
    - MountedCloudSource: Cloud storage mounted locally
    - OneDriveSource: OneDrive via Microsoft Graph API
    - GoogleDriveSource: Google Drive via Drive API
    """

    @property
    @abstractmethod
    def source_type(self) -> str:
        """Return the source type identifier (e.g., 'local', 'onedrive')."""
        pass

    @property
    @abstractmethod
    def root_path(self) -> str:
        """Return the root path of this source."""
        pass

    @abstractmethod
    def walk(self, path: str = '') -> Iterator[Tuple[str, List[str], List[str]]]:
        """
        Walk directory tree (os.walk compatible).

        Args:
            path: Starting path relative to source root

        Yields:
            Tuples of (dirpath, dirnames, filenames)
        """
        pass

    @abstractmethod
    def list_directory(self, path: str = '') -> List[FileMetadata]:
        """
        List files and folders in a directory.

        Args:
            path: Path relative to source root

        Returns:
            List of FileMetadata for all items in directory
        """
        pass

    @abstractmethod
    def get_metadata(self, path: str) -> FileMetadata:
        """
        Get metadata for a single file.

        Args:
            path: Path relative to source root

        Returns:
            FileMetadata for the file

        Raises:
            SourceNotFoundError: If file does not exist
        """
        pass

    @abstractmethod
    def read_stream(self, path: str) -> BinaryIO:
        """
        Get a readable binary stream for file content.

        Args:
            path: Path relative to source root

        Returns:
            Binary file-like object

        Raises:
            FileNotAvailableError: If file is a placeholder
            SourceNotFoundError: If file does not exist
        """
        pass

    @abstractmethod
    def read_bytes(self, path: str, limit: Optional[int] = None) -> bytes:
        """
        Read file content as bytes.

        Args:
            path: Path relative to source root
            limit: Maximum bytes to read (None = all)

        Returns:
            File content as bytes

        Raises:
            FileNotAvailableError: If file is a placeholder
            SourceNotFoundError: If file does not exist
        """
        pass

    @abstractmethod
    def exists(self, path: str) -> bool:
        """Check if path exists."""
        pass

    @abstractmethod
    def is_file(self, path: str) -> bool:
        """Check if path is a file."""
        pass

    @abstractmethod
    def is_directory(self, path: str) -> bool:
        """Check if path is a directory."""
        pass

    def resolve_path(self, path: str) -> str:
        """
        Resolve a path relative to source root.

        Args:
            path: Relative or absolute path

        Returns:
            Absolute path
        """
        if not path:
            return self.root_path
        # Default implementation - subclasses may override
        return str(Path(self.root_path) / path)


class FileDestination(ABC):
    """
    Abstract interface for writing files to a storage backend.
    """

    @property
    @abstractmethod
    def source_type(self) -> str:
        """Return the source type identifier."""
        pass

    @property
    @abstractmethod
    def root_path(self) -> str:
        """Return the root path of this destination."""
        pass

    @abstractmethod
    def write_stream(self, path: str, stream: BinaryIO, size: Optional[int] = None) -> bool:
        """
        Write stream content to a file.

        Args:
            path: Destination path relative to root
            stream: Binary stream to write
            size: Expected size (optional, for progress)

        Returns:
            True if successful
        """
        pass

    @abstractmethod
    def write_bytes(self, path: str, data: bytes) -> bool:
        """
        Write bytes to a file.

        Args:
            path: Destination path relative to root
            data: Bytes to write

        Returns:
            True if successful
        """
        pass

    @abstractmethod
    def mkdir(self, path: str, parents: bool = True) -> bool:
        """
        Create a directory.

        Args:
            path: Directory path relative to root
            parents: Create parent directories if needed

        Returns:
            True if successful (or already exists)
        """
        pass

    @abstractmethod
    def move(self, source: str, dest: str) -> bool:
        """
        Move a file or directory.

        Args:
            source: Source path relative to root
            dest: Destination path relative to root

        Returns:
            True if successful
        """
        pass

    @abstractmethod
    def copy(self, source: str, dest: str) -> bool:
        """
        Copy a file or directory.

        Args:
            source: Source path relative to root
            dest: Destination path relative to root

        Returns:
            True if successful
        """
        pass

    @abstractmethod
    def delete(self, path: str) -> bool:
        """
        Delete a file or directory.

        Args:
            path: Path relative to root

        Returns:
            True if successful
        """
        pass

    @abstractmethod
    def exists(self, path: str) -> bool:
        """Check if path exists."""
        pass


class SyncableSource(FileSource, FileDestination):
    """
    A source that supports bidirectional synchronization.

    Extends both FileSource and FileDestination, adding
    sync-specific operations like delta queries and uploads.
    """

    @abstractmethod
    def get_changes_since(
        self,
        path: str = '',
        delta_token: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> Tuple[List[ChangeRecord], Optional[str]]:
        """
        Get changes since a timestamp or sync token.

        Args:
            path: Path to get changes for
            delta_token: Sync token from previous call (more efficient)
            timestamp: Get changes since this time (fallback)

        Returns:
            Tuple of (changes list, new sync token)
        """
        pass

    @abstractmethod
    def upload(self, local_path: str, remote_path: str) -> bool:
        """
        Upload a local file to the cloud.

        Args:
            local_path: Path on local filesystem
            remote_path: Path in cloud storage

        Returns:
            True if successful
        """
        pass

    @abstractmethod
    def download(self, remote_path: str, local_path: str) -> bool:
        """
        Download a file from the cloud.

        Args:
            remote_path: Path in cloud storage
            local_path: Path on local filesystem

        Returns:
            True if successful
        """
        pass

    def get_sync_token(self) -> Optional[str]:
        """
        Get current sync token for delta queries.

        Returns:
            Sync token string or None
        """
        return None


class SourceRegistry:
    """
    Registry for managing multiple file sources.
    """

    def __init__(self):
        self._sources: Dict[str, FileSource] = {}
        self._destinations: Dict[str, FileDestination] = {}

    def register_source(self, name: str, source: FileSource):
        """Register a file source."""
        self._sources[name] = source

    def register_destination(self, name: str, destination: FileDestination):
        """Register a file destination."""
        self._destinations[name] = destination

    def get_source(self, name: str) -> Optional[FileSource]:
        """Get a registered source by name."""
        return self._sources.get(name)

    def get_destination(self, name: str) -> Optional[FileDestination]:
        """Get a registered destination by name."""
        return self._destinations.get(name)

    def list_sources(self) -> List[str]:
        """List all registered source names."""
        return list(self._sources.keys())

    def list_destinations(self) -> List[str]:
        """List all registered destination names."""
        return list(self._destinations.keys())
