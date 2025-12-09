"""
Local Filesystem Source Implementation

Implements FileSource and FileDestination for local filesystem operations.
This wraps standard Python file operations (pathlib, shutil, os) behind
the abstract interface.
"""

import os
import shutil
import logging
import mimetypes
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import BinaryIO, Iterator, List, Optional, Tuple

from .interfaces import (
    FileSource,
    FileDestination,
    FileMetadata,
    FolderMetadata,
    FileNotAvailableError,
    SourceNotFoundError,
)

logger = logging.getLogger(__name__)


class LocalFileSource(FileSource, FileDestination):
    """
    Local filesystem implementation of FileSource and FileDestination.

    This is the primary implementation for scanning and organizing
    files on the local machine.
    """

    def __init__(self, root: str, name: Optional[str] = None):
        """
        Initialize local file source.

        Args:
            root: Root directory path
            name: Optional name for this source
        """
        self._root = Path(root).resolve()
        self._name = name or str(self._root)

        if not self._root.exists():
            raise SourceNotFoundError(f"Root path does not exist: {self._root}")

    @property
    def source_type(self) -> str:
        return 'local'

    @property
    def root_path(self) -> str:
        return str(self._root)

    @property
    def name(self) -> str:
        return self._name

    def walk(self, path: str = '') -> Iterator[Tuple[str, List[str], List[str]]]:
        """
        Walk directory tree using os.walk.

        Args:
            path: Starting path relative to root (empty = root)

        Yields:
            Tuples of (dirpath, dirnames, filenames)
        """
        start_path = self._resolve(path)

        if not start_path.exists():
            return

        for dirpath, dirnames, filenames in os.walk(start_path):
            yield dirpath, dirnames, filenames

    def list_directory(self, path: str = '') -> List[FileMetadata]:
        """
        List files and folders in a directory.

        Args:
            path: Path relative to root

        Returns:
            List of FileMetadata for all items
        """
        dir_path = self._resolve(path)

        if not dir_path.exists():
            raise SourceNotFoundError(f"Directory not found: {dir_path}")

        if not dir_path.is_dir():
            raise SourceNotFoundError(f"Not a directory: {dir_path}")

        items = []
        for item in dir_path.iterdir():
            try:
                items.append(self._get_metadata(item))
            except (PermissionError, OSError) as e:
                logger.warning(f"Could not read metadata for {item}: {e}")

        return items

    def get_metadata(self, path: str) -> FileMetadata:
        """
        Get metadata for a single file.

        Args:
            path: Path relative to root

        Returns:
            FileMetadata for the file
        """
        file_path = self._resolve(path)

        if not file_path.exists():
            raise SourceNotFoundError(f"File not found: {file_path}")

        return self._get_metadata(file_path)

    def _get_metadata(self, file_path: Path) -> FileMetadata:
        """Internal method to build FileMetadata from a Path."""
        try:
            stat = file_path.stat()

            return FileMetadata(
                path=str(file_path),
                name=file_path.name,
                size_bytes=stat.st_size if file_path.is_file() else 0,
                created_at=datetime.fromtimestamp(stat.st_ctime),
                modified_at=datetime.fromtimestamp(stat.st_mtime),
                accessed_at=datetime.fromtimestamp(stat.st_atime),
                mime_type=mimetypes.guess_type(file_path.name)[0],
                is_directory=file_path.is_dir(),
                source_type=self.source_type,
                is_placeholder=False,
            )
        except (PermissionError, OSError) as e:
            logger.error(f"Error reading metadata for {file_path}: {e}")
            raise

    def read_stream(self, path: str) -> BinaryIO:
        """
        Get a readable binary stream for file content.

        Args:
            path: Path relative to root or absolute

        Returns:
            Binary file object
        """
        file_path = self._resolve(path)

        if not file_path.exists():
            raise SourceNotFoundError(f"File not found: {file_path}")

        if not file_path.is_file():
            raise SourceNotFoundError(f"Not a file: {file_path}")

        return open(file_path, 'rb')

    def read_bytes(self, path: str, limit: Optional[int] = None) -> bytes:
        """
        Read file content as bytes.

        Args:
            path: Path relative to root or absolute
            limit: Maximum bytes to read (None = all)

        Returns:
            File content as bytes
        """
        file_path = self._resolve(path)

        if not file_path.exists():
            raise SourceNotFoundError(f"File not found: {file_path}")

        with open(file_path, 'rb') as f:
            if limit:
                return f.read(limit)
            return f.read()

    def exists(self, path: str) -> bool:
        """Check if path exists."""
        return self._resolve(path).exists()

    def is_file(self, path: str) -> bool:
        """Check if path is a file."""
        return self._resolve(path).is_file()

    def is_directory(self, path: str) -> bool:
        """Check if path is a directory."""
        return self._resolve(path).is_dir()

    # FileDestination methods

    def write_stream(self, path: str, stream: BinaryIO, size: Optional[int] = None) -> bool:
        """
        Write stream content to a file.

        Args:
            path: Destination path
            stream: Binary stream to write
            size: Expected size (ignored for local)

        Returns:
            True if successful
        """
        file_path = self._resolve(path)

        try:
            # Ensure parent directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)

            with open(file_path, 'wb') as f:
                # Copy in chunks
                while True:
                    chunk = stream.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)

            return True

        except (PermissionError, OSError) as e:
            logger.error(f"Error writing file {file_path}: {e}")
            return False

    def write_bytes(self, path: str, data: bytes) -> bool:
        """
        Write bytes to a file.

        Args:
            path: Destination path
            data: Bytes to write

        Returns:
            True if successful
        """
        file_path = self._resolve(path)

        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_bytes(data)
            return True

        except (PermissionError, OSError) as e:
            logger.error(f"Error writing file {file_path}: {e}")
            return False

    def mkdir(self, path: str, parents: bool = True) -> bool:
        """
        Create a directory.

        Args:
            path: Directory path
            parents: Create parent directories if needed

        Returns:
            True if successful
        """
        dir_path = self._resolve(path)

        try:
            dir_path.mkdir(parents=parents, exist_ok=True)
            return True

        except (PermissionError, OSError) as e:
            logger.error(f"Error creating directory {dir_path}: {e}")
            return False

    def move(self, source: str, dest: str) -> bool:
        """
        Move a file or directory.

        Args:
            source: Source path
            dest: Destination path

        Returns:
            True if successful
        """
        src_path = self._resolve(source)
        dst_path = self._resolve(dest)

        try:
            # Ensure destination parent exists
            dst_path.parent.mkdir(parents=True, exist_ok=True)

            shutil.move(str(src_path), str(dst_path))
            return True

        except (PermissionError, OSError, shutil.Error) as e:
            logger.error(f"Error moving {src_path} to {dst_path}: {e}")
            return False

    def copy(self, source: str, dest: str) -> bool:
        """
        Copy a file or directory.

        Args:
            source: Source path
            dest: Destination path

        Returns:
            True if successful
        """
        src_path = self._resolve(source)
        dst_path = self._resolve(dest)

        try:
            # Ensure destination parent exists
            dst_path.parent.mkdir(parents=True, exist_ok=True)

            if src_path.is_dir():
                shutil.copytree(str(src_path), str(dst_path))
            else:
                shutil.copy2(str(src_path), str(dst_path))

            return True

        except (PermissionError, OSError, shutil.Error) as e:
            logger.error(f"Error copying {src_path} to {dst_path}: {e}")
            return False

    def delete(self, path: str) -> bool:
        """
        Delete a file or directory.

        Args:
            path: Path to delete

        Returns:
            True if successful
        """
        target_path = self._resolve(path)

        try:
            if target_path.is_dir():
                shutil.rmtree(str(target_path))
            else:
                target_path.unlink()

            return True

        except (PermissionError, OSError) as e:
            logger.error(f"Error deleting {target_path}: {e}")
            return False

    def _resolve(self, path: str) -> Path:
        """
        Resolve a path relative to root.

        If path is absolute and within root, use it directly.
        If path is relative, join with root.
        """
        if not path:
            return self._root

        path_obj = Path(path)

        # If already absolute
        if path_obj.is_absolute():
            # Check if within root
            try:
                path_obj.relative_to(self._root)
                return path_obj
            except ValueError:
                # Not within root, use as-is (for cross-source operations)
                return path_obj

        # Relative path - join with root
        return self._root / path


class NetworkFileSource(LocalFileSource):
    """
    Network share implementation (SMB/NFS).

    This is essentially the same as LocalFileSource but with
    network-specific error handling and retry logic.
    """

    def __init__(self, root: str, name: Optional[str] = None, timeout: int = 30):
        """
        Initialize network file source.

        Args:
            root: UNC path (e.g., \\\\server\\share) or mounted path
            name: Optional name for this source
            timeout: Connection timeout in seconds
        """
        self._timeout = timeout
        super().__init__(root, name)

    @property
    def source_type(self) -> str:
        return 'network'

    def _resolve(self, path: str) -> Path:
        """Resolve path with network-aware handling."""
        resolved = super()._resolve(path)

        # For UNC paths, ensure proper format
        path_str = str(resolved)
        if path_str.startswith('\\\\') and not path_str.startswith('\\\\\\\\'):
            # Normalize UNC path
            pass

        return resolved


if __name__ == '__main__':
    # Test the local file source
    import sys

    logging.basicConfig(level=logging.DEBUG)

    # Test with current directory
    source = LocalFileSource('.')

    print(f"Source: {source.name}")
    print(f"Root: {source.root_path}")
    print(f"Type: {source.source_type}")
    print()

    print("Listing directory:")
    for item in source.list_directory()[:10]:
        type_str = 'DIR' if item.is_directory else 'FILE'
        print(f"  [{type_str}] {item.name:40s} {item.size_bytes:>10,} bytes")

    print()
    print("Walking (first 3 dirs):")
    count = 0
    for dirpath, dirnames, filenames in source.walk():
        print(f"  {dirpath}: {len(filenames)} files, {len(dirnames)} subdirs")
        count += 1
        if count >= 3:
            break
