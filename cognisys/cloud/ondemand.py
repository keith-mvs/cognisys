"""
On-Demand File Handler

Handles cloud files that use "Files On-Demand" (OneDrive) or similar
placeholder file technology. These files appear in the filesystem but
may not have their content locally available.

On Windows, this uses the FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS and
FILE_ATTRIBUTE_RECALL_ON_OPEN attributes to detect placeholder files.
"""

import os
import platform
import logging
from enum import Enum
from pathlib import Path
from typing import Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Windows file attributes for cloud files
FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS = 0x00400000
FILE_ATTRIBUTE_RECALL_ON_OPEN = 0x00040000
FILE_ATTRIBUTE_OFFLINE = 0x00001000
FILE_ATTRIBUTE_PINNED = 0x00080000  # "Always available"
FILE_ATTRIBUTE_UNPINNED = 0x00100000  # "Free up space"


class SyncStatus(Enum):
    """Sync status of a cloud file."""

    AVAILABLE = 'available'           # Content is locally available
    ONLINE_ONLY = 'online_only'       # Placeholder, needs download
    SYNCING = 'syncing'               # Currently syncing
    PINNED = 'pinned'                 # Marked as "Always keep on device"
    UNKNOWN = 'unknown'               # Cannot determine status
    ERROR = 'error'                   # Error checking status


@dataclass
class FileStatus:
    """Detailed status of a cloud file."""

    path: Path
    sync_status: SyncStatus
    is_placeholder: bool
    is_pinned: bool
    file_size: int
    local_size: int  # 0 if placeholder
    attributes: int
    error: Optional[str] = None

    @property
    def needs_download(self) -> bool:
        """Check if file needs to be downloaded before reading."""
        return self.is_placeholder and not self.is_pinned

    @property
    def is_available(self) -> bool:
        """Check if file content is locally available."""
        return self.sync_status == SyncStatus.AVAILABLE or self.is_pinned


class OnDemandHandler:
    """
    Handler for cloud files with on-demand/placeholder functionality.

    Supports:
    - OneDrive Files On-Demand (Windows 10 1709+)
    - Google Drive streaming (limited detection)
    - iCloud Drive (limited detection)
    """

    def __init__(self, on_demand_behavior: str = 'skip'):
        """
        Initialize handler.

        Args:
            on_demand_behavior: How to handle online-only files
                - 'skip': Skip online-only files (don't process)
                - 'download': Request download before processing
                - 'warn': Log warning but attempt to process
        """
        self.behavior = on_demand_behavior
        self.system = platform.system()
        self._ctypes_available = False
        self._setup_ctypes()

    def _setup_ctypes(self):
        """Setup ctypes for Windows API access."""
        if self.system != 'Windows':
            return

        try:
            import ctypes
            self._kernel32 = ctypes.windll.kernel32
            self._ctypes_available = True
        except Exception as e:
            logger.warning(f"Could not setup ctypes for on-demand detection: {e}")

    def get_file_status(self, path: Path) -> FileStatus:
        """
        Get detailed status of a file.

        Args:
            path: Path to the file

        Returns:
            FileStatus with sync status and details
        """
        if not path.exists():
            return FileStatus(
                path=path,
                sync_status=SyncStatus.ERROR,
                is_placeholder=False,
                is_pinned=False,
                file_size=0,
                local_size=0,
                attributes=0,
                error="File does not exist",
            )

        if self.system == 'Windows':
            return self._get_file_status_windows(path)
        else:
            return self._get_file_status_generic(path)

    def _get_file_status_windows(self, path: Path) -> FileStatus:
        """Get file status on Windows using file attributes."""
        try:
            import ctypes

            # Get file attributes
            attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))

            if attrs == -1:  # INVALID_FILE_ATTRIBUTES
                return FileStatus(
                    path=path,
                    sync_status=SyncStatus.ERROR,
                    is_placeholder=False,
                    is_pinned=False,
                    file_size=0,
                    local_size=0,
                    attributes=0,
                    error="Could not get file attributes",
                )

            # Check for placeholder indicators
            is_recall_on_access = bool(attrs & FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS)
            is_recall_on_open = bool(attrs & FILE_ATTRIBUTE_RECALL_ON_OPEN)
            is_offline = bool(attrs & FILE_ATTRIBUTE_OFFLINE)
            is_pinned = bool(attrs & FILE_ATTRIBUTE_PINNED)
            is_unpinned = bool(attrs & FILE_ATTRIBUTE_UNPINNED)

            is_placeholder = is_recall_on_access or is_recall_on_open or is_offline

            # Determine sync status
            if is_pinned:
                sync_status = SyncStatus.PINNED
            elif is_placeholder:
                sync_status = SyncStatus.ONLINE_ONLY
            else:
                sync_status = SyncStatus.AVAILABLE

            # Get file sizes
            try:
                stat = path.stat()
                file_size = stat.st_size
                # For placeholders, local size is effectively 0 until downloaded
                local_size = 0 if is_placeholder else file_size
            except OSError:
                file_size = 0
                local_size = 0

            return FileStatus(
                path=path,
                sync_status=sync_status,
                is_placeholder=is_placeholder,
                is_pinned=is_pinned,
                file_size=file_size,
                local_size=local_size,
                attributes=attrs,
            )

        except Exception as e:
            logger.error(f"Error getting file status for {path}: {e}")
            return FileStatus(
                path=path,
                sync_status=SyncStatus.ERROR,
                is_placeholder=False,
                is_pinned=False,
                file_size=0,
                local_size=0,
                attributes=0,
                error=str(e),
            )

    def _get_file_status_generic(self, path: Path) -> FileStatus:
        """Get file status on non-Windows platforms."""
        try:
            stat = path.stat()
            return FileStatus(
                path=path,
                sync_status=SyncStatus.AVAILABLE,
                is_placeholder=False,
                is_pinned=False,
                file_size=stat.st_size,
                local_size=stat.st_size,
                attributes=0,
            )
        except OSError as e:
            return FileStatus(
                path=path,
                sync_status=SyncStatus.ERROR,
                is_placeholder=False,
                is_pinned=False,
                file_size=0,
                local_size=0,
                attributes=0,
                error=str(e),
            )

    def is_placeholder(self, path: Path) -> bool:
        """
        Check if a file is a cloud placeholder (not locally available).

        Args:
            path: Path to the file

        Returns:
            True if file is a placeholder that needs download
        """
        status = self.get_file_status(path)
        return status.is_placeholder

    def is_available(self, path: Path) -> bool:
        """
        Check if file content is locally available.

        Args:
            path: Path to the file

        Returns:
            True if file can be read without download
        """
        status = self.get_file_status(path)
        return status.is_available

    def should_process(self, path: Path) -> Tuple[bool, str]:
        """
        Determine if a file should be processed based on behavior setting.

        Args:
            path: Path to the file

        Returns:
            Tuple of (should_process, reason)
        """
        status = self.get_file_status(path)

        if status.sync_status == SyncStatus.ERROR:
            return False, f"Error: {status.error}"

        if status.is_available:
            return True, "File is available"

        # File is online-only
        if self.behavior == 'skip':
            return False, "Skipping online-only file"
        elif self.behavior == 'download':
            # Request download and return True (caller should wait)
            self.request_download(path)
            return True, "Download requested"
        elif self.behavior == 'warn':
            logger.warning(f"Processing online-only file: {path}")
            return True, "Processing with warning"

        return False, "Unknown behavior"

    def request_download(self, path: Path, timeout: int = 60) -> bool:
        """
        Request download of an online-only file.

        On Windows, this triggers the cloud provider to download the file.

        Args:
            path: Path to the file
            timeout: Maximum seconds to wait for download

        Returns:
            True if file is now available
        """
        if self.system != 'Windows':
            logger.warning("Download request only supported on Windows")
            return False

        try:
            # On Windows, simply opening the file triggers download
            # We can also use the SetFileAttributesW to clear the recall flag

            # Method 1: Try to read the file (triggers download)
            logger.info(f"Requesting download for: {path}")

            import time
            start = time.time()

            while time.time() - start < timeout:
                # Try to open the file
                try:
                    with open(path, 'rb') as f:
                        # Read a small chunk to trigger download
                        f.read(1)

                    # Check if still placeholder
                    if not self.is_placeholder(path):
                        logger.info(f"Download complete for: {path}")
                        return True

                except PermissionError:
                    # File might be syncing
                    pass
                except Exception as e:
                    logger.debug(f"Download attempt error: {e}")

                time.sleep(1)

            logger.warning(f"Download timeout for: {path}")
            return False

        except Exception as e:
            logger.error(f"Error requesting download for {path}: {e}")
            return False

    def pin_file(self, path: Path) -> bool:
        """
        Pin a file to always keep locally (OneDrive "Always keep on this device").

        Args:
            path: Path to the file

        Returns:
            True if successful
        """
        if self.system != 'Windows':
            logger.warning("Pin operation only supported on Windows")
            return False

        try:
            import ctypes

            # Get current attributes
            attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))
            if attrs == -1:
                return False

            # Add PINNED, remove UNPINNED
            new_attrs = (attrs | FILE_ATTRIBUTE_PINNED) & ~FILE_ATTRIBUTE_UNPINNED

            result = ctypes.windll.kernel32.SetFileAttributesW(str(path), new_attrs)
            return bool(result)

        except Exception as e:
            logger.error(f"Error pinning file {path}: {e}")
            return False

    def unpin_file(self, path: Path) -> bool:
        """
        Unpin a file to allow freeing up space (OneDrive "Free up space").

        Args:
            path: Path to the file

        Returns:
            True if successful
        """
        if self.system != 'Windows':
            logger.warning("Unpin operation only supported on Windows")
            return False

        try:
            import ctypes

            # Get current attributes
            attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))
            if attrs == -1:
                return False

            # Add UNPINNED, remove PINNED
            new_attrs = (attrs | FILE_ATTRIBUTE_UNPINNED) & ~FILE_ATTRIBUTE_PINNED

            result = ctypes.windll.kernel32.SetFileAttributesW(str(path), new_attrs)
            return bool(result)

        except Exception as e:
            logger.error(f"Error unpinning file {path}: {e}")
            return False


def check_file_availability(path: Path) -> Tuple[bool, str]:
    """
    Convenience function to check if a file is available for reading.

    Args:
        path: Path to the file

    Returns:
        Tuple of (is_available, reason)
    """
    handler = OnDemandHandler()
    status = handler.get_file_status(path)

    if status.sync_status == SyncStatus.ERROR:
        return False, f"Error: {status.error}"
    elif status.is_available:
        return True, "Available"
    else:
        return False, "Online-only (not downloaded)"


if __name__ == '__main__':
    # Test the handler
    import sys

    logging.basicConfig(level=logging.DEBUG)

    handler = OnDemandHandler()

    # Test with OneDrive folder
    onedrive_path = Path(os.environ.get('OneDrive', ''))

    if onedrive_path.exists():
        print(f"\nScanning OneDrive: {onedrive_path}\n")

        count = 0
        placeholders = 0

        for item in onedrive_path.rglob('*'):
            if item.is_file() and count < 20:
                status = handler.get_file_status(item)

                status_icon = {
                    SyncStatus.AVAILABLE: '+',
                    SyncStatus.ONLINE_ONLY: 'O',
                    SyncStatus.PINNED: 'P',
                    SyncStatus.SYNCING: 'S',
                    SyncStatus.UNKNOWN: '?',
                    SyncStatus.ERROR: 'X',
                }[status.sync_status]

                if status.is_placeholder:
                    placeholders += 1

                print(f"  [{status_icon}] {item.name[:50]:50s}  {status.file_size:>10,} bytes")
                count += 1

        print(f"\nScanned {count} files, {placeholders} are placeholders")
    else:
        print("OneDrive not found. Testing with current directory.")

        for item in Path('.').iterdir():
            if item.is_file():
                status = handler.get_file_status(item)
                print(f"  {item.name}: {status.sync_status.value}")
