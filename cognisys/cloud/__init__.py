"""
CogniSys Cloud Integration Module

Provides cloud storage detection, sync, and API integration for:
- OneDrive (Microsoft Graph API)
- Google Drive (Google Drive API)
- iCloud (mounted folder only)
- Proton Drive (mounted folder only)
"""

from .detection import CloudFolderDetector, CloudFolder
from .sync import SyncManager, SyncConfig, SyncDirection, ConflictResolution, SyncStats

__all__ = [
    'CloudFolderDetector',
    'CloudFolder',
    'SyncManager',
    'SyncConfig',
    'SyncDirection',
    'ConflictResolution',
    'SyncStats',
]
