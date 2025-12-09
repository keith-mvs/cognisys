"""
CogniSys Storage Abstraction Layer

Provides abstract interfaces for file operations across different backends:
- Local filesystem
- Network shares (SMB/NFS)
- Cloud storage (OneDrive, Google Drive, iCloud)

This abstraction allows the scanner, organizer, and migrator to work
with any storage backend without code changes.
"""

from .interfaces import (
    FileSource,
    FileDestination,
    SyncableSource,
    FileMetadata,
    FolderMetadata,
    ChangeRecord,
    ChangeType,
    FileNotAvailableError,
    SourceNotFoundError,
)

__all__ = [
    'FileSource',
    'FileDestination',
    'SyncableSource',
    'FileMetadata',
    'FolderMetadata',
    'ChangeRecord',
    'ChangeType',
    'FileNotAvailableError',
    'SourceNotFoundError',
]
