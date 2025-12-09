"""
Two-Way Sync Manager

Manages bidirectional synchronization between local and cloud sources:
- Pull: Download new/changed files from cloud for classification
- Push: Upload organized files back to cloud storage
- Delta tracking: Use cloud provider change APIs for efficient sync
"""

import logging
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, Tuple

from cognisys.storage.interfaces import (
    SyncableSource,
    FileSource,
    FileDestination,
    ChangeRecord,
    ChangeType,
    FileMetadata,
)

logger = logging.getLogger(__name__)


class SyncDirection(Enum):
    """Direction of sync operation."""
    PULL = "pull"       # Cloud -> Local
    PUSH = "push"       # Local -> Cloud
    BIDIRECTIONAL = "bidirectional"  # Both directions


class ConflictResolution(Enum):
    """How to resolve sync conflicts."""
    LOCAL_WINS = "local_wins"       # Keep local version
    REMOTE_WINS = "remote_wins"     # Keep remote version
    NEWER_WINS = "newer_wins"       # Keep newer modification
    KEEP_BOTH = "keep_both"         # Rename and keep both
    ASK = "ask"                     # Prompt user (callback)


@dataclass
class SyncItem:
    """Represents a file to be synced."""
    source_path: str
    dest_path: str
    change_type: ChangeType
    source_modified: Optional[datetime] = None
    dest_modified: Optional[datetime] = None
    source_size: int = 0
    dest_size: int = 0
    conflict: bool = False
    resolution: Optional[str] = None


@dataclass
class SyncStats:
    """Statistics from a sync operation."""
    direction: SyncDirection
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    files_scanned: int = 0
    files_downloaded: int = 0
    files_uploaded: int = 0
    files_skipped: int = 0
    files_conflicted: int = 0
    bytes_transferred: int = 0
    errors: List[str] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0

    @property
    def success(self) -> bool:
        return len(self.errors) == 0


@dataclass
class SyncConfig:
    """Configuration for sync operations."""
    direction: SyncDirection = SyncDirection.BIDIRECTIONAL
    conflict_resolution: ConflictResolution = ConflictResolution.NEWER_WINS

    # Filters
    include_patterns: List[str] = field(default_factory=list)
    exclude_patterns: List[str] = field(default_factory=list)
    max_file_size: Optional[int] = None  # Bytes

    # Behavior
    dry_run: bool = False
    delete_orphans: bool = False  # Delete files that no longer exist at source
    preserve_timestamps: bool = True

    # Local staging
    staging_dir: Optional[str] = None

    # Callbacks
    on_conflict: Optional[Callable[[SyncItem], ConflictResolution]] = None
    on_progress: Optional[Callable[[str, int, int], None]] = None


class SyncManager:
    """
    Manages two-way synchronization between sources.

    Supports:
    - Pull: Download new/changed files from cloud
    - Push: Upload organized files to cloud
    - Delta sync: Efficient change detection using provider APIs
    - Conflict resolution: Multiple strategies for handling conflicts

    Usage:
        # Pull from OneDrive
        manager = SyncManager(onedrive_source, local_dest)
        stats = manager.pull()

        # Push organized files back
        stats = manager.push(organized_dir, remote_organized_dir)

        # Bidirectional sync
        stats = manager.sync(SyncDirection.BIDIRECTIONAL)
    """

    def __init__(
        self,
        source: SyncableSource,
        destination: FileDestination,
        config: Optional[SyncConfig] = None,
        delta_token_storage: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize sync manager.

        Args:
            source: Source to sync from (typically cloud)
            destination: Destination to sync to (typically local)
            config: Sync configuration
            delta_token_storage: Dict to store delta tokens (persisted externally)
        """
        self.source = source
        self.destination = destination
        self.config = config or SyncConfig()
        self._delta_tokens = delta_token_storage or {}

        # Create staging directory if needed
        if self.config.staging_dir:
            Path(self.config.staging_dir).mkdir(parents=True, exist_ok=True)

    def pull(
        self,
        remote_path: str = '',
        local_path: Optional[str] = None,
    ) -> SyncStats:
        """
        Pull changes from source to destination.

        Args:
            remote_path: Path in source to pull from
            local_path: Local path to pull to (uses destination root if None)

        Returns:
            Sync statistics
        """
        stats = SyncStats(direction=SyncDirection.PULL)

        try:
            logger.info(f"Starting pull from {remote_path or '/'}")

            # Get changes since last sync
            delta_key = f"pull:{remote_path}"
            delta_token = self._delta_tokens.get(delta_key)

            if isinstance(self.source, SyncableSource):
                changes, new_token = self.source.get_changes_since(
                    path=remote_path,
                    delta_token=delta_token,
                )

                if new_token:
                    self._delta_tokens[delta_key] = new_token
            else:
                # Full scan fallback
                changes = self._scan_for_changes(remote_path)

            stats.files_scanned = len(changes)
            logger.info(f"Found {len(changes)} changes to process")

            # Process changes
            for i, change in enumerate(changes):
                try:
                    self._process_pull_change(change, local_path, stats)

                    if self.config.on_progress:
                        self.config.on_progress(change.path, i + 1, len(changes))

                except Exception as e:
                    error_msg = f"Error pulling {change.path}: {e}"
                    logger.error(error_msg)
                    stats.errors.append(error_msg)

        except Exception as e:
            error_msg = f"Pull operation failed: {e}"
            logger.error(error_msg)
            stats.errors.append(error_msg)

        stats.completed_at = datetime.now()
        logger.info(
            f"Pull complete: {stats.files_downloaded} downloaded, "
            f"{stats.files_skipped} skipped, {len(stats.errors)} errors"
        )

        return stats

    def push(
        self,
        local_path: str,
        remote_path: str = '',
    ) -> SyncStats:
        """
        Push changes from local to source.

        Args:
            local_path: Local path to push from
            remote_path: Remote path to push to

        Returns:
            Sync statistics
        """
        stats = SyncStats(direction=SyncDirection.PUSH)

        try:
            logger.info(f"Starting push from {local_path} to {remote_path or '/'}")

            # Scan local directory for files to upload
            local_root = Path(local_path)
            if not local_root.exists():
                raise FileNotFoundError(f"Local path not found: {local_path}")

            files_to_push: List[Tuple[Path, str]] = []

            for root, dirs, files in os.walk(local_root):
                root_path = Path(root)
                rel_root = root_path.relative_to(local_root)

                for filename in files:
                    local_file = root_path / filename
                    remote_file = str(Path(remote_path) / rel_root / filename).replace('\\', '/')

                    if self._should_sync(str(local_file), local_file.stat().st_size):
                        files_to_push.append((local_file, remote_file))

            stats.files_scanned = len(files_to_push)
            logger.info(f"Found {len(files_to_push)} files to push")

            # Upload files
            for i, (local_file, remote_file) in enumerate(files_to_push):
                try:
                    self._process_push_file(local_file, remote_file, stats)

                    if self.config.on_progress:
                        self.config.on_progress(str(local_file), i + 1, len(files_to_push))

                except Exception as e:
                    error_msg = f"Error pushing {local_file}: {e}"
                    logger.error(error_msg)
                    stats.errors.append(error_msg)

        except Exception as e:
            error_msg = f"Push operation failed: {e}"
            logger.error(error_msg)
            stats.errors.append(error_msg)

        stats.completed_at = datetime.now()
        logger.info(
            f"Push complete: {stats.files_uploaded} uploaded, "
            f"{stats.files_skipped} skipped, {len(stats.errors)} errors"
        )

        return stats

    def sync(
        self,
        remote_path: str = '',
        local_path: Optional[str] = None,
    ) -> SyncStats:
        """
        Perform bidirectional sync.

        Args:
            remote_path: Remote path to sync
            local_path: Local path to sync

        Returns:
            Combined sync statistics
        """
        stats = SyncStats(direction=SyncDirection.BIDIRECTIONAL)

        # Pull first, then push
        pull_stats = self.pull(remote_path, local_path)
        push_stats = self.push(local_path or '', remote_path)

        # Combine stats
        stats.files_scanned = pull_stats.files_scanned + push_stats.files_scanned
        stats.files_downloaded = pull_stats.files_downloaded
        stats.files_uploaded = push_stats.files_uploaded
        stats.files_skipped = pull_stats.files_skipped + push_stats.files_skipped
        stats.files_conflicted = pull_stats.files_conflicted + push_stats.files_conflicted
        stats.bytes_transferred = pull_stats.bytes_transferred + push_stats.bytes_transferred
        stats.errors = pull_stats.errors + push_stats.errors
        stats.completed_at = datetime.now()

        return stats

    def _process_pull_change(
        self,
        change: ChangeRecord,
        local_base: Optional[str],
        stats: SyncStats,
    ) -> None:
        """Process a single change during pull."""
        # Determine local path
        if local_base:
            local_path = Path(local_base) / change.path.lstrip('/')
        else:
            local_path = Path(change.path.lstrip('/'))

        # Skip if filtered
        if not self._should_sync(change.path, change.size or 0):
            stats.files_skipped += 1
            logger.debug(f"Skipping filtered file: {change.path}")
            return

        if self.config.dry_run:
            logger.info(f"[DRY RUN] Would download: {change.path}")
            stats.files_skipped += 1
            return

        if change.change_type == ChangeType.DELETED:
            if self.config.delete_orphans and local_path.exists():
                local_path.unlink()
                logger.info(f"Deleted local file: {local_path}")
            return

        # Check for conflicts
        if local_path.exists():
            local_mtime = datetime.fromtimestamp(local_path.stat().st_mtime)
            remote_mtime = change.modified_at

            if remote_mtime and local_mtime > remote_mtime:
                # Local is newer - potential conflict
                resolution = self._resolve_conflict(
                    SyncItem(
                        source_path=change.path,
                        dest_path=str(local_path),
                        change_type=change.change_type,
                        source_modified=remote_mtime,
                        dest_modified=local_mtime,
                        conflict=True,
                    )
                )

                if resolution == ConflictResolution.LOCAL_WINS:
                    stats.files_skipped += 1
                    stats.files_conflicted += 1
                    return
                elif resolution == ConflictResolution.KEEP_BOTH:
                    # Rename local file
                    backup_path = local_path.with_suffix(f'.local{local_path.suffix}')
                    shutil.move(str(local_path), str(backup_path))
                    stats.files_conflicted += 1

        # Download file
        try:
            if isinstance(self.source, SyncableSource):
                local_path.parent.mkdir(parents=True, exist_ok=True)
                self.source.download(change.path, str(local_path))
                stats.files_downloaded += 1
                stats.bytes_transferred += change.size or 0
                logger.info(f"Downloaded: {change.path}")
            else:
                # Use read_stream fallback
                local_path.parent.mkdir(parents=True, exist_ok=True)
                with self.source.read_stream(change.path) as stream:
                    with open(local_path, 'wb') as f:
                        shutil.copyfileobj(stream, f)
                stats.files_downloaded += 1

        except Exception as e:
            raise RuntimeError(f"Download failed: {e}")

    def _process_push_file(
        self,
        local_path: Path,
        remote_path: str,
        stats: SyncStats,
    ) -> None:
        """Process a single file during push."""
        if self.config.dry_run:
            logger.info(f"[DRY RUN] Would upload: {local_path} -> {remote_path}")
            stats.files_skipped += 1
            return

        # Check if remote exists and handle conflicts
        try:
            remote_meta = self.source.get_metadata(remote_path)
            if remote_meta:
                local_mtime = datetime.fromtimestamp(local_path.stat().st_mtime)

                if remote_meta.modified_at and remote_meta.modified_at > local_mtime:
                    # Remote is newer - potential conflict
                    resolution = self._resolve_conflict(
                        SyncItem(
                            source_path=str(local_path),
                            dest_path=remote_path,
                            change_type=ChangeType.MODIFIED,
                            source_modified=local_mtime,
                            dest_modified=remote_meta.modified_at,
                            conflict=True,
                        )
                    )

                    if resolution == ConflictResolution.REMOTE_WINS:
                        stats.files_skipped += 1
                        stats.files_conflicted += 1
                        return
                    elif resolution == ConflictResolution.KEEP_BOTH:
                        # Append timestamp to remote filename
                        base, ext = os.path.splitext(remote_path)
                        remote_path = f"{base}.{datetime.now().strftime('%Y%m%d%H%M%S')}{ext}"
                        stats.files_conflicted += 1

        except Exception:
            # Remote doesn't exist - OK to upload
            pass

        # Upload file
        try:
            if isinstance(self.source, SyncableSource):
                self.source.upload(str(local_path), remote_path)
                stats.files_uploaded += 1
                stats.bytes_transferred += local_path.stat().st_size
                logger.info(f"Uploaded: {local_path} -> {remote_path}")
            else:
                raise RuntimeError("Source does not support uploads")

        except Exception as e:
            raise RuntimeError(f"Upload failed: {e}")

    def _should_sync(self, path: str, size: int) -> bool:
        """Check if file should be synced based on filters."""
        import fnmatch

        # Check size limit
        if self.config.max_file_size and size > self.config.max_file_size:
            return False

        # Check exclude patterns
        filename = os.path.basename(path)
        for pattern in self.config.exclude_patterns:
            if fnmatch.fnmatch(filename, pattern) or fnmatch.fnmatch(path, pattern):
                return False

        # Check include patterns (if specified, file must match one)
        if self.config.include_patterns:
            for pattern in self.config.include_patterns:
                if fnmatch.fnmatch(filename, pattern) or fnmatch.fnmatch(path, pattern):
                    return True
            return False

        return True

    def _resolve_conflict(self, item: SyncItem) -> ConflictResolution:
        """Resolve a sync conflict."""
        # Use callback if provided
        if self.config.on_conflict:
            return self.config.on_conflict(item)

        # Apply default resolution strategy
        resolution = self.config.conflict_resolution

        if resolution == ConflictResolution.NEWER_WINS:
            if item.source_modified and item.dest_modified:
                if item.source_modified > item.dest_modified:
                    return ConflictResolution.REMOTE_WINS
                else:
                    return ConflictResolution.LOCAL_WINS

        return resolution

    def _scan_for_changes(self, path: str) -> List[ChangeRecord]:
        """Fallback: scan source for all files (no delta support)."""
        changes = []

        for root, dirs, files in self.source.walk(path):
            for filename in files:
                file_path = f"{root}/{filename}".replace('//', '/')
                try:
                    meta = self.source.get_metadata(file_path)
                    if meta:
                        changes.append(ChangeRecord(
                            path=file_path,
                            change_type=ChangeType.MODIFIED,  # Treat all as modified
                            modified_at=meta.modified_at,
                            size=meta.size,
                        ))
                except Exception as e:
                    logger.warning(f"Error scanning {file_path}: {e}")

        return changes

    def get_delta_token(self, key: str) -> Optional[str]:
        """Get stored delta token for a sync path."""
        return self._delta_tokens.get(key)

    def set_delta_token(self, key: str, token: str) -> None:
        """Store delta token for a sync path."""
        self._delta_tokens[key] = token

    def clear_delta_tokens(self) -> None:
        """Clear all delta tokens (forces full resync)."""
        self._delta_tokens.clear()


def create_sync_manager(
    source_type: str,
    source_config: Dict[str, Any],
    destination_path: str,
    sync_config: Optional[SyncConfig] = None,
) -> SyncManager:
    """
    Factory function to create a sync manager.

    Args:
        source_type: Type of source ('onedrive', 'googledrive', 'local')
        source_config: Source-specific configuration
        destination_path: Local destination path
        sync_config: Sync configuration

    Returns:
        Configured SyncManager instance
    """
    from cognisys.storage.local import LocalFileSource

    # Create source based on type
    if source_type == 'onedrive':
        from cognisys.storage.onedrive import OneDriveSource
        source = OneDriveSource(
            client_id=source_config['client_id'],
            root_path=source_config.get('root_path', ''),
        )
    elif source_type == 'local':
        source = LocalFileSource(source_config.get('path', ''))
    else:
        raise ValueError(f"Unknown source type: {source_type}")

    # Create local destination
    destination = LocalFileSource(destination_path)

    return SyncManager(
        source=source,
        destination=destination,
        config=sync_config,
    )


if __name__ == '__main__':
    # Example usage
    import sys
    logging.basicConfig(level=logging.INFO)

    print("SyncManager module loaded successfully")
    print("\nUsage example:")
    print("  from cognisys.cloud.sync import SyncManager, SyncConfig")
    print("  from cognisys.storage.onedrive import OneDriveSource")
    print("  from cognisys.storage.local import LocalFileSource")
    print()
    print("  # Create sources")
    print("  cloud = OneDriveSource(client_id='...')")
    print("  local = LocalFileSource('/path/to/local')")
    print()
    print("  # Create sync manager")
    print("  manager = SyncManager(cloud, local)")
    print()
    print("  # Pull from cloud")
    print("  stats = manager.pull('/Documents')")
    print("  print(f'Downloaded {stats.files_downloaded} files')")
