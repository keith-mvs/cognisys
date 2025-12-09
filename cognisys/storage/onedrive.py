"""
OneDrive Storage Source

Implements FileSource and FileDestination for OneDrive via Microsoft Graph API.
Supports:
- File listing and metadata
- File download (streaming)
- File upload
- Delta sync for change detection
"""

import logging
import mimetypes
from datetime import datetime
from io import BytesIO
from pathlib import PurePosixPath
from typing import Any, BinaryIO, Dict, Iterator, List, Optional, Tuple

import requests

from .interfaces import (
    ChangeRecord,
    FileDestination,
    FileMetadata,
    FileNotAvailableError,
    FileSource,
    FolderMetadata,
    SourceNotFoundError,
    SyncableSource,
)

logger = logging.getLogger(__name__)

# Microsoft Graph API base URL
GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"


class OneDriveSource(SyncableSource):
    """
    OneDrive implementation using Microsoft Graph API.

    Provides full FileSource, FileDestination, and SyncableSource functionality
    for OneDrive storage.
    """

    def __init__(
        self,
        access_token: str,
        root_path: str = '/',
        drive_id: Optional[str] = None,
    ):
        """
        Initialize OneDrive source.

        Args:
            access_token: Valid OAuth access token
            root_path: Root path in OneDrive (e.g., '/' or '/Documents')
            drive_id: Specific drive ID (default: user's default drive)
        """
        self._access_token = access_token
        self._root_path = root_path.rstrip('/') or '/'
        self._drive_id = drive_id
        self._session = requests.Session()
        self._delta_token: Optional[str] = None

    @property
    def source_type(self) -> str:
        return 'onedrive'

    @property
    def root_path(self) -> str:
        return self._root_path

    @property
    def _headers(self) -> Dict[str, str]:
        """Get authorization headers."""
        return {
            'Authorization': f'Bearer {self._access_token}',
            'Content-Type': 'application/json',
        }

    def _build_path_url(self, path: str) -> str:
        """Build Graph API URL for a path."""
        # Normalize path
        if not path or path == '/':
            if self._root_path == '/':
                return f"{GRAPH_API_BASE}/me/drive/root"
            else:
                return f"{GRAPH_API_BASE}/me/drive/root:{self._root_path}"

        # Combine root with relative path
        if self._root_path == '/':
            full_path = path
        else:
            full_path = f"{self._root_path}/{path.lstrip('/')}"

        return f"{GRAPH_API_BASE}/me/drive/root:{full_path}"

    def _parse_item(self, item: Dict[str, Any]) -> FileMetadata:
        """Parse Graph API item to FileMetadata."""
        is_folder = 'folder' in item

        # Parse dates
        created_at = None
        modified_at = None
        if 'createdDateTime' in item:
            created_at = datetime.fromisoformat(item['createdDateTime'].rstrip('Z'))
        if 'lastModifiedDateTime' in item:
            modified_at = datetime.fromisoformat(item['lastModifiedDateTime'].rstrip('Z'))

        # Get MIME type
        mime_type = None
        if 'file' in item and 'mimeType' in item['file']:
            mime_type = item['file']['mimeType']
        elif not is_folder:
            mime_type = mimetypes.guess_type(item['name'])[0]

        # Build path from parentReference
        path = item['name']
        if 'parentReference' in item and 'path' in item['parentReference']:
            parent_path = item['parentReference']['path']
            # Remove /drive/root: prefix
            if '/root:' in parent_path:
                parent_path = parent_path.split('/root:')[-1]
            if parent_path:
                path = f"{parent_path}/{item['name']}"

        return FileMetadata(
            path=path,
            name=item['name'],
            size_bytes=item.get('size', 0),
            created_at=created_at,
            modified_at=modified_at,
            accessed_at=None,  # Not available via Graph API
            mime_type=mime_type,
            is_directory=is_folder,
            source_type='onedrive',
            source_id=item.get('id'),
            etag=item.get('eTag'),
            content_hash=item.get('file', {}).get('hashes', {}).get('sha256Hash'),
            extra={
                'webUrl': item.get('webUrl'),
                'downloadUrl': item.get('@microsoft.graph.downloadUrl'),
            },
        )

    def walk(self, path: str = '') -> Iterator[Tuple[str, List[str], List[str]]]:
        """
        Walk directory tree.

        Args:
            path: Starting path relative to root

        Yields:
            Tuples of (dirpath, dirnames, filenames)
        """
        # Get items in current directory
        items = self.list_directory(path)

        dirs = []
        files = []

        for item in items:
            if item.is_directory:
                dirs.append(item.name)
            else:
                files.append(item.name)

        # Yield current directory
        current_path = path or self._root_path
        yield current_path, dirs, files

        # Recursively walk subdirectories
        for dirname in dirs:
            subpath = f"{path}/{dirname}" if path else dirname
            yield from self.walk(subpath)

    def list_directory(self, path: str = '') -> List[FileMetadata]:
        """
        List files and folders in a directory.

        Args:
            path: Path relative to root

        Returns:
            List of FileMetadata
        """
        url = self._build_path_url(path)
        if not url.endswith('/children'):
            url += '/children'

        items = []

        try:
            # Handle pagination
            while url:
                response = self._session.get(url, headers=self._headers)
                response.raise_for_status()
                data = response.json()

                for item in data.get('value', []):
                    items.append(self._parse_item(item))

                # Check for next page
                url = data.get('@odata.nextLink')

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise SourceNotFoundError(f"Path not found: {path}")
            raise

        return items

    def get_metadata(self, path: str) -> FileMetadata:
        """
        Get metadata for a single file.

        Args:
            path: Path relative to root

        Returns:
            FileMetadata
        """
        url = self._build_path_url(path)

        try:
            response = self._session.get(url, headers=self._headers)
            response.raise_for_status()
            return self._parse_item(response.json())

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise SourceNotFoundError(f"File not found: {path}")
            raise

    def read_stream(self, path: str) -> BinaryIO:
        """
        Get a readable stream for file content.

        Args:
            path: Path relative to root

        Returns:
            Binary stream
        """
        # Get download URL
        url = self._build_path_url(path) + '/content'

        try:
            response = self._session.get(
                url,
                headers=self._headers,
                stream=True,
                allow_redirects=True,
            )
            response.raise_for_status()

            # Return content as BytesIO
            return BytesIO(response.content)

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise SourceNotFoundError(f"File not found: {path}")
            raise

    def read_bytes(self, path: str, limit: Optional[int] = None) -> bytes:
        """
        Read file content as bytes.

        Args:
            path: Path relative to root
            limit: Maximum bytes to read

        Returns:
            File content
        """
        url = self._build_path_url(path) + '/content'

        headers = self._headers.copy()
        if limit:
            headers['Range'] = f'bytes=0-{limit - 1}'

        try:
            response = self._session.get(
                url,
                headers=headers,
                allow_redirects=True,
            )
            response.raise_for_status()
            return response.content

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise SourceNotFoundError(f"File not found: {path}")
            raise

    def exists(self, path: str) -> bool:
        """Check if path exists."""
        try:
            self.get_metadata(path)
            return True
        except SourceNotFoundError:
            return False

    def is_file(self, path: str) -> bool:
        """Check if path is a file."""
        try:
            meta = self.get_metadata(path)
            return not meta.is_directory
        except SourceNotFoundError:
            return False

    def is_directory(self, path: str) -> bool:
        """Check if path is a directory."""
        try:
            meta = self.get_metadata(path)
            return meta.is_directory
        except SourceNotFoundError:
            return False

    # FileDestination methods

    def write_stream(self, path: str, stream: BinaryIO, size: Optional[int] = None) -> bool:
        """
        Write stream content to a file.

        For files > 4MB, uses resumable upload.
        """
        content = stream.read()
        return self.write_bytes(path, content)

    def write_bytes(self, path: str, data: bytes) -> bool:
        """
        Write bytes to a file.

        For files > 4MB, uses resumable upload session.
        """
        url = self._build_path_url(path) + '/content'

        # For small files (< 4MB), use simple upload
        if len(data) < 4 * 1024 * 1024:
            try:
                response = self._session.put(
                    url,
                    headers={
                        'Authorization': f'Bearer {self._access_token}',
                        'Content-Type': 'application/octet-stream',
                    },
                    data=data,
                )
                return response.status_code in (200, 201)

            except Exception as e:
                logger.error(f"Upload failed: {e}")
                return False

        # For large files, use upload session
        return self._upload_large_file(path, data)

    def _upload_large_file(self, path: str, data: bytes) -> bool:
        """Upload large file using resumable upload session."""
        # Create upload session
        session_url = self._build_path_url(path) + '/createUploadSession'

        try:
            response = self._session.post(
                session_url,
                headers=self._headers,
                json={
                    'item': {
                        '@microsoft.graph.conflictBehavior': 'replace',
                    }
                },
            )
            response.raise_for_status()
            upload_url = response.json()['uploadUrl']

            # Upload in chunks
            chunk_size = 10 * 1024 * 1024  # 10MB chunks
            total_size = len(data)

            for offset in range(0, total_size, chunk_size):
                chunk = data[offset:offset + chunk_size]
                end = offset + len(chunk) - 1

                response = self._session.put(
                    upload_url,
                    headers={
                        'Content-Length': str(len(chunk)),
                        'Content-Range': f'bytes {offset}-{end}/{total_size}',
                    },
                    data=chunk,
                )

                if response.status_code not in (200, 201, 202):
                    logger.error(f"Chunk upload failed: {response.status_code}")
                    return False

            return True

        except Exception as e:
            logger.error(f"Large file upload failed: {e}")
            return False

    def mkdir(self, path: str, parents: bool = True) -> bool:
        """Create a folder."""
        # Get parent path and folder name
        path_obj = PurePosixPath(path)
        parent_path = str(path_obj.parent) if str(path_obj.parent) != '.' else ''
        folder_name = path_obj.name

        # Create parent if needed
        if parents and parent_path:
            self.mkdir(parent_path, parents=True)

        # Create folder
        url = self._build_path_url(parent_path) + '/children'

        try:
            response = self._session.post(
                url,
                headers=self._headers,
                json={
                    'name': folder_name,
                    'folder': {},
                    '@microsoft.graph.conflictBehavior': 'fail',
                },
            )

            if response.status_code == 409:  # Conflict - already exists
                return True

            return response.status_code in (200, 201)

        except Exception as e:
            logger.error(f"mkdir failed: {e}")
            return False

    def move(self, source: str, dest: str) -> bool:
        """Move a file or folder."""
        # Get parent path and new name
        dest_obj = PurePosixPath(dest)
        new_parent = str(dest_obj.parent) if str(dest_obj.parent) != '.' else ''
        new_name = dest_obj.name

        # Get source item ID
        try:
            source_meta = self.get_metadata(source)
        except SourceNotFoundError:
            return False

        # Get destination parent ID
        try:
            parent_meta = self.get_metadata(new_parent) if new_parent else None
            parent_id = parent_meta.source_id if parent_meta else 'root'
        except SourceNotFoundError:
            return False

        # Move item
        url = f"{GRAPH_API_BASE}/me/drive/items/{source_meta.source_id}"

        try:
            response = self._session.patch(
                url,
                headers=self._headers,
                json={
                    'parentReference': {'id': parent_id},
                    'name': new_name,
                },
            )
            return response.status_code == 200

        except Exception as e:
            logger.error(f"Move failed: {e}")
            return False

    def copy(self, source: str, dest: str) -> bool:
        """Copy a file or folder."""
        # Get destination parent
        dest_obj = PurePosixPath(dest)
        new_parent = str(dest_obj.parent) if str(dest_obj.parent) != '.' else ''
        new_name = dest_obj.name

        try:
            source_meta = self.get_metadata(source)
            parent_meta = self.get_metadata(new_parent) if new_parent else None
        except SourceNotFoundError:
            return False

        # Copy item
        url = f"{GRAPH_API_BASE}/me/drive/items/{source_meta.source_id}/copy"

        try:
            response = self._session.post(
                url,
                headers=self._headers,
                json={
                    'parentReference': {
                        'id': parent_meta.source_id if parent_meta else 'root',
                    },
                    'name': new_name,
                },
            )
            # Copy returns 202 Accepted (async operation)
            return response.status_code == 202

        except Exception as e:
            logger.error(f"Copy failed: {e}")
            return False

    def delete(self, path: str) -> bool:
        """Delete a file or folder."""
        try:
            meta = self.get_metadata(path)
        except SourceNotFoundError:
            return True  # Already doesn't exist

        url = f"{GRAPH_API_BASE}/me/drive/items/{meta.source_id}"

        try:
            response = self._session.delete(url, headers=self._headers)
            return response.status_code == 204

        except Exception as e:
            logger.error(f"Delete failed: {e}")
            return False

    # SyncableSource methods

    def get_changes_since(
        self,
        timestamp: Optional[datetime] = None,
        token: Optional[str] = None,
    ) -> Tuple[List[ChangeRecord], Optional[str]]:
        """
        Get changes using delta API.

        Args:
            timestamp: Not used (delta API uses tokens)
            token: Delta token from previous call

        Returns:
            Tuple of (changes, new_token)
        """
        url = f"{GRAPH_API_BASE}/me/drive/root/delta"
        if token:
            url = token  # Use delta link from previous call

        changes = []

        try:
            while url:
                response = self._session.get(url, headers=self._headers)
                response.raise_for_status()
                data = response.json()

                for item in data.get('value', []):
                    change_type = 'deleted' if 'deleted' in item else 'modified'

                    if change_type == 'deleted':
                        changes.append(ChangeRecord(
                            path=item.get('name', ''),
                            change_type='deleted',
                            timestamp=datetime.now(),
                        ))
                    else:
                        meta = self._parse_item(item)
                        changes.append(ChangeRecord(
                            path=meta.path,
                            change_type='modified',
                            timestamp=meta.modified_at or datetime.now(),
                            metadata=meta,
                        ))

                # Get next page or delta link
                url = data.get('@odata.nextLink')
                if not url:
                    new_token = data.get('@odata.deltaLink')
                    return changes, new_token

        except Exception as e:
            logger.error(f"Delta query failed: {e}")
            return [], None

        return changes, None

    def upload(self, local_path: str, remote_path: str) -> bool:
        """Upload a local file to OneDrive."""
        try:
            with open(local_path, 'rb') as f:
                data = f.read()
            return self.write_bytes(remote_path, data)
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            return False

    def download(self, remote_path: str, local_path: str) -> bool:
        """Download a file from OneDrive to local path."""
        try:
            from pathlib import Path

            content = self.read_bytes(remote_path)

            local = Path(local_path)
            local.parent.mkdir(parents=True, exist_ok=True)
            local.write_bytes(content)

            return True

        except Exception as e:
            logger.error(f"Download failed: {e}")
            return False

    def get_sync_token(self) -> Optional[str]:
        """Get current delta sync token."""
        return self._delta_token


def create_onedrive_source(
    access_token: str,
    root_path: str = '/',
) -> OneDriveSource:
    """
    Create an OneDrive source.

    Args:
        access_token: Valid OAuth access token
        root_path: Root path in OneDrive

    Returns:
        OneDriveSource instance
    """
    return OneDriveSource(
        access_token=access_token,
        root_path=root_path,
    )
