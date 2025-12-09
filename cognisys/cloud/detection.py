"""
Cloud Folder Detection Module

Auto-detects mounted cloud storage folders for:
- OneDrive (Personal and Business)
- Google Drive (Drive for Desktop)
- iCloud Drive
- Proton Drive

Works on Windows, macOS, and Linux where applicable.
"""

import os
import platform
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any

try:
    import winreg
    HAS_WINREG = True
except ImportError:
    HAS_WINREG = False

logger = logging.getLogger(__name__)


@dataclass
class CloudFolder:
    """Represents a detected cloud storage folder."""

    provider: str  # 'onedrive', 'onedrive_business', 'googledrive', 'icloud', 'proton'
    local_path: Path
    account_name: Optional[str] = None
    account_email: Optional[str] = None
    sync_state: str = 'unknown'  # 'synced', 'syncing', 'paused', 'offline', 'unknown'
    on_demand_enabled: bool = False
    is_business: bool = False
    subfolders: List[str] = field(default_factory=list)

    def __post_init__(self):
        if isinstance(self.local_path, str):
            self.local_path = Path(self.local_path)

    @property
    def exists(self) -> bool:
        """Check if the folder exists and is accessible."""
        return self.local_path.exists() and self.local_path.is_dir()

    @property
    def display_name(self) -> str:
        """Human-readable name for this cloud folder."""
        name = self.provider.replace('_', ' ').title()
        if self.account_name:
            name += f" ({self.account_name})"
        elif self.account_email:
            name += f" ({self.account_email})"
        return name

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'provider': self.provider,
            'local_path': str(self.local_path),
            'account_name': self.account_name,
            'account_email': self.account_email,
            'sync_state': self.sync_state,
            'on_demand_enabled': self.on_demand_enabled,
            'is_business': self.is_business,
            'subfolders': self.subfolders,
            'exists': self.exists,
        }


class CloudFolderDetector:
    """Detects cloud storage folders across different providers and platforms."""

    def __init__(self):
        self.system = platform.system()  # 'Windows', 'Darwin', 'Linux'
        self._detected: List[CloudFolder] = []

    def detect_all(self) -> List[CloudFolder]:
        """Detect all available cloud folders."""
        self._detected = []

        # OneDrive
        onedrive = self.detect_onedrive()
        if onedrive:
            self._detected.extend(onedrive if isinstance(onedrive, list) else [onedrive])

        # Google Drive
        gdrive = self.detect_google_drive()
        if gdrive:
            self._detected.extend(gdrive if isinstance(gdrive, list) else [gdrive])

        # iCloud
        icloud = self.detect_icloud()
        if icloud:
            self._detected.append(icloud)

        # Proton Drive
        proton = self.detect_proton_drive()
        if proton:
            self._detected.append(proton)

        return self._detected

    def detect_onedrive(self) -> Optional[List[CloudFolder]]:
        """Detect OneDrive folders (Personal and Business)."""
        folders = []

        if self.system == 'Windows':
            folders.extend(self._detect_onedrive_windows())
        elif self.system == 'Darwin':
            folders.extend(self._detect_onedrive_macos())
        elif self.system == 'Linux':
            folders.extend(self._detect_onedrive_linux())

        return folders if folders else None

    def _detect_onedrive_windows(self) -> List[CloudFolder]:
        """Detect OneDrive on Windows using registry and environment variables."""
        folders = []

        # Method 1: Environment variables
        env_paths = {
            'OneDrive': ('onedrive', False),
            'OneDriveConsumer': ('onedrive', False),
            'OneDriveCommercial': ('onedrive_business', True),
        }

        for env_var, (provider, is_business) in env_paths.items():
            path = os.environ.get(env_var)
            if path and Path(path).exists():
                folder = CloudFolder(
                    provider=provider,
                    local_path=Path(path),
                    is_business=is_business,
                    on_demand_enabled=self._check_onedrive_on_demand(Path(path)),
                )
                folders.append(folder)
                logger.debug(f"Found OneDrive via env {env_var}: {path}")

        # Method 2: Registry (more detailed info)
        if HAS_WINREG:
            folders.extend(self._detect_onedrive_from_registry())

        # Deduplicate by path
        seen_paths = set()
        unique_folders = []
        for folder in folders:
            if str(folder.local_path) not in seen_paths:
                seen_paths.add(str(folder.local_path))
                unique_folders.append(folder)

        return unique_folders

    def _detect_onedrive_from_registry(self) -> List[CloudFolder]:
        """Read OneDrive configuration from Windows registry."""
        folders = []

        if not HAS_WINREG:
            return folders

        # Check both Personal and Business accounts
        registry_paths = [
            (r'Software\Microsoft\OneDrive\Accounts\Personal', 'onedrive', False),
            (r'Software\Microsoft\OneDrive\Accounts\Business1', 'onedrive_business', True),
            (r'Software\Microsoft\OneDrive\Accounts\Business2', 'onedrive_business', True),
        ]

        for reg_path, provider, is_business in registry_paths:
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path) as key:
                    try:
                        user_folder = winreg.QueryValueEx(key, 'UserFolder')[0]
                        if user_folder and Path(user_folder).exists():
                            # Try to get account email
                            email = None
                            try:
                                email = winreg.QueryValueEx(key, 'UserEmail')[0]
                            except (FileNotFoundError, OSError):
                                pass

                            folder = CloudFolder(
                                provider=provider,
                                local_path=Path(user_folder),
                                account_email=email,
                                is_business=is_business,
                                on_demand_enabled=self._check_onedrive_on_demand(Path(user_folder)),
                            )
                            folders.append(folder)
                            logger.debug(f"Found OneDrive via registry: {user_folder}")
                    except (FileNotFoundError, OSError):
                        pass
            except (FileNotFoundError, OSError):
                pass

        return folders

    def _check_onedrive_on_demand(self, path: Path) -> bool:
        """Check if OneDrive Files On-Demand is enabled."""
        # On Windows, check for placeholder files (.cloud extension or FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS)
        # For now, assume on-demand is enabled if OneDrive is detected on Windows 10+
        if self.system == 'Windows':
            # Check Windows version - Files On-Demand requires Windows 10 1709+
            try:
                import sys
                if sys.getwindowsversion().build >= 16299:  # Windows 10 1709
                    return True
            except Exception:
                pass
        return False

    def _detect_onedrive_macos(self) -> List[CloudFolder]:
        """Detect OneDrive on macOS."""
        folders = []

        # Standard OneDrive locations on macOS
        home = Path.home()
        locations = [
            home / 'OneDrive',
            home / 'OneDrive - Personal',
            home / 'Library' / 'CloudStorage',
        ]

        for loc in locations:
            if loc.exists():
                if loc.name == 'CloudStorage':
                    # Check for OneDrive folders in CloudStorage
                    for item in loc.iterdir():
                        if item.is_dir() and 'OneDrive' in item.name:
                            is_business = 'Business' in item.name or 'Personal' not in item.name
                            folders.append(CloudFolder(
                                provider='onedrive_business' if is_business else 'onedrive',
                                local_path=item,
                                is_business=is_business,
                            ))
                else:
                    is_business = 'Business' in loc.name
                    folders.append(CloudFolder(
                        provider='onedrive_business' if is_business else 'onedrive',
                        local_path=loc,
                        is_business=is_business,
                    ))

        return folders

    def _detect_onedrive_linux(self) -> List[CloudFolder]:
        """Detect OneDrive on Linux (using third-party clients like rclone)."""
        folders = []

        # Common OneDrive mount locations on Linux
        home = Path.home()
        locations = [
            home / 'OneDrive',
            home / 'onedrive',
            Path('/mnt/onedrive'),
        ]

        for loc in locations:
            if loc.exists() and loc.is_dir():
                folders.append(CloudFolder(
                    provider='onedrive',
                    local_path=loc,
                ))

        return folders

    def detect_google_drive(self) -> Optional[List[CloudFolder]]:
        """Detect Google Drive folders."""
        folders = []

        if self.system == 'Windows':
            folders.extend(self._detect_google_drive_windows())
        elif self.system == 'Darwin':
            folders.extend(self._detect_google_drive_macos())
        elif self.system == 'Linux':
            folders.extend(self._detect_google_drive_linux())

        return folders if folders else None

    def _detect_google_drive_windows(self) -> List[CloudFolder]:
        """Detect Google Drive on Windows."""
        folders = []

        # Google Drive for Desktop creates a virtual drive (G:) or folder
        # Check common locations

        # Method 1: Check for mounted drive letters
        for drive_letter in 'GHIJKLMNOPQRSTUVWXYZ':
            drive_path = Path(f'{drive_letter}:/')
            if drive_path.exists():
                # Check if it looks like Google Drive (has "My Drive" folder)
                my_drive = drive_path / 'My Drive'
                if my_drive.exists():
                    folders.append(CloudFolder(
                        provider='googledrive',
                        local_path=drive_path,
                        subfolders=['My Drive', 'Shared drives'] if (drive_path / 'Shared drives').exists() else ['My Drive'],
                    ))
                    logger.debug(f"Found Google Drive at {drive_path}")
                    break

        # Method 2: Check local app data for Google Drive config
        local_appdata = os.environ.get('LOCALAPPDATA', '')
        if local_appdata:
            gdrive_path = Path(local_appdata) / 'Google' / 'DriveFS'
            if gdrive_path.exists():
                # Google Drive for Desktop is installed
                logger.debug(f"Google Drive for Desktop detected at {gdrive_path}")

        # Method 3: Check user profile for Google Drive folder (older Backup and Sync)
        user_profile = os.environ.get('USERPROFILE', '')
        if user_profile:
            gdrive_folder = Path(user_profile) / 'Google Drive'
            if gdrive_folder.exists():
                folders.append(CloudFolder(
                    provider='googledrive',
                    local_path=gdrive_folder,
                ))

        return folders

    def _detect_google_drive_macos(self) -> List[CloudFolder]:
        """Detect Google Drive on macOS."""
        folders = []
        home = Path.home()

        # CloudStorage location (modern Google Drive)
        cloud_storage = home / 'Library' / 'CloudStorage'
        if cloud_storage.exists():
            for item in cloud_storage.iterdir():
                if item.is_dir() and 'GoogleDrive' in item.name:
                    folders.append(CloudFolder(
                        provider='googledrive',
                        local_path=item,
                    ))

        # Legacy Google Drive folder
        legacy_path = home / 'Google Drive'
        if legacy_path.exists():
            folders.append(CloudFolder(
                provider='googledrive',
                local_path=legacy_path,
            ))

        return folders

    def _detect_google_drive_linux(self) -> List[CloudFolder]:
        """Detect Google Drive on Linux (using rclone or other clients)."""
        folders = []
        home = Path.home()

        locations = [
            home / 'Google Drive',
            home / 'google-drive',
            home / 'gdrive',
            Path('/mnt/gdrive'),
        ]

        for loc in locations:
            if loc.exists() and loc.is_dir():
                folders.append(CloudFolder(
                    provider='googledrive',
                    local_path=loc,
                ))

        return folders

    def detect_icloud(self) -> Optional[CloudFolder]:
        """Detect iCloud Drive folder."""
        if self.system == 'Windows':
            return self._detect_icloud_windows()
        elif self.system == 'Darwin':
            return self._detect_icloud_macos()
        return None

    def _detect_icloud_windows(self) -> Optional[CloudFolder]:
        """Detect iCloud on Windows."""
        # iCloud Drive location on Windows
        user_profile = os.environ.get('USERPROFILE', '')
        if user_profile:
            icloud_path = Path(user_profile) / 'iCloudDrive'
            if icloud_path.exists():
                return CloudFolder(
                    provider='icloud',
                    local_path=icloud_path,
                )
        return None

    def _detect_icloud_macos(self) -> Optional[CloudFolder]:
        """Detect iCloud on macOS."""
        home = Path.home()

        # iCloud Drive location on macOS
        icloud_path = home / 'Library' / 'Mobile Documents' / 'com~apple~CloudDocs'
        if icloud_path.exists():
            return CloudFolder(
                provider='icloud',
                local_path=icloud_path,
            )

        # Alternative: CloudStorage location
        cloud_storage = home / 'Library' / 'CloudStorage' / 'iCloud Drive'
        if cloud_storage.exists():
            return CloudFolder(
                provider='icloud',
                local_path=cloud_storage,
            )

        return None

    def detect_proton_drive(self) -> Optional[CloudFolder]:
        """Detect Proton Drive folder (if sync client is available)."""
        # Proton Drive desktop client is relatively new
        # Check common locations

        home = Path.home()
        locations = [
            home / 'Proton Drive',
            home / 'ProtonDrive',
        ]

        if self.system == 'Windows':
            user_profile = os.environ.get('USERPROFILE', '')
            if user_profile:
                locations.append(Path(user_profile) / 'Proton Drive')

        for loc in locations:
            if loc.exists() and loc.is_dir():
                return CloudFolder(
                    provider='proton',
                    local_path=loc,
                )

        return None

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all detected cloud folders."""
        if not self._detected:
            self.detect_all()

        return {
            'total_detected': len(self._detected),
            'providers': list(set(f.provider for f in self._detected)),
            'folders': [f.to_dict() for f in self._detected],
        }


def detect_cloud_folders() -> List[CloudFolder]:
    """Convenience function to detect all cloud folders."""
    detector = CloudFolderDetector()
    return detector.detect_all()


if __name__ == '__main__':
    # Test detection
    logging.basicConfig(level=logging.DEBUG)

    detector = CloudFolderDetector()
    folders = detector.detect_all()

    print(f"\nDetected {len(folders)} cloud folder(s):\n")

    for folder in folders:
        print(f"  Provider: {folder.provider}")
        print(f"  Path: {folder.local_path}")
        print(f"  Exists: {folder.exists}")
        print(f"  On-Demand: {folder.on_demand_enabled}")
        if folder.account_email:
            print(f"  Account: {folder.account_email}")
        print()
