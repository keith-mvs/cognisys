"""
File scanning engine for CogniSys.
Traverses directories, extracts metadata, and indexes files with multi-threading support.
"""

import os
import mimetypes
import uuid
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from ..models.database import Database
from ..utils.hashing import calculate_adaptive_hash
from ..utils.categorization import FileCategorizer
from ..utils.logging_config import get_logger

logger = get_logger(__name__)


class FileScanner:
    """
    Multi-threaded file system scanner with metadata extraction.
    """

    def __init__(self, database: Database, config: Dict):
        """
        Initialize scanner with database connection and configuration.

        Args:
            database: Database instance for storing file records
            config: Configuration dictionary with scanning parameters
        """
        self.db = database
        self.config = config
        self.session_id = None
        self.stats = {
            'files_scanned': 0,
            'folders_scanned': 0,
            'errors': 0,
            'total_size': 0
        }
        self.lock = threading.Lock()
        self.db_lock = threading.Lock()  # Separate lock for database writes
        self.categorizer = FileCategorizer()  # File categorization engine

        # Batch processing
        self.batch_size = self.config.get('scanning', {}).get('performance', {}).get('batch_size', 100)
        self.file_batch = []
        self.folder_batch = []

        # Progress tracking
        self.start_time = None
        self.last_progress_time = None
        self.progress_interval = 1000  # Report every N files

    def scan_roots(self, root_paths: List[str]) -> str:
        """
        Scan multiple root directories.

        Args:
            root_paths: List of root directory paths to scan

        Returns:
            Session ID for this scan
        """
        logger.info(f"Starting scan of {len(root_paths)} root path(s)")

        # Create scan session
        self.session_id = self.db.create_session(root_paths, self.config)

        # Start progress tracking
        self.start_time = time.time()
        self.last_progress_time = self.start_time

        try:
            # Scan each root
            for root in root_paths:
                root_path = Path(root)
                if not root_path.exists():
                    logger.warning(f"Root path does not exist: {root}")
                    continue

                logger.info(f"Scanning: {root}")
                self._scan_directory_tree(root_path)

            # Flush any remaining batches
            self._flush_batches()

            # Update session stats
            self.db.update_session(
                self.session_id,
                completed_at=datetime.now(),
                files_scanned=self.stats['files_scanned'],
                status='completed'
            )

            # Calculate final statistics
            elapsed = time.time() - self.start_time
            files_per_sec = self.stats['files_scanned'] / elapsed if elapsed > 0 else 0

            logger.info(f"[OK] Scan completed successfully!")
            logger.info(f"  Files scanned: {self.stats['files_scanned']:,}")
            logger.info(f"  Folders scanned: {self.stats['folders_scanned']:,}")
            logger.info(f"  Total size: {self.stats['total_size'] / 1e9:.2f} GB")
            logger.info(f"  Errors: {self.stats['errors']:,}")
            logger.info(f"  Duration: {elapsed:.1f}s ({files_per_sec:.1f} files/sec)")

            return self.session_id

        except Exception as e:
            logger.error(f"Scan failed: {e}")
            self._flush_batches()  # Try to save what we have
            self.db.update_session(self.session_id, status='failed')
            raise

    def _scan_directory_tree(self, root: Path):
        """
        Recursively scan directory tree with multi-threading for file processing.

        Args:
            root: Root directory path
        """
        exclusion_patterns = self.config.get('scanning', {}).get('exclusions', {}).get('patterns', [])
        exclusion_folders = self.config.get('scanning', {}).get('exclusions', {}).get('folders', [])
        max_threads = self.config.get('scanning', {}).get('performance', {}).get('threads', 4)

        for dirpath, dirnames, filenames in os.walk(root):
            current_path = Path(dirpath)

            # Apply folder exclusions (modify dirnames in-place to prune walk)
            dirnames[:] = [
                d for d in dirnames
                if not self._is_excluded(d, exclusion_folders)
            ]

            # Index this folder
            self._index_folder(current_path)

            # Process files with thread pool
            with ThreadPoolExecutor(max_workers=max_threads) as executor:
                futures = []

                for filename in filenames:
                    if not self._is_excluded(filename, exclusion_patterns):
                        filepath = current_path / filename
                        future = executor.submit(self._index_file, filepath)
                        futures.append(future)

                # Wait for all files in this directory to complete
                for future in as_completed(futures):
                    try:
                        future.result()
                    except Exception as e:
                        logger.error(f"Error processing file: {e}")
                        with self.lock:
                            self.stats['errors'] += 1

    def _is_excluded(self, name: str, exclusion_list: List[str]) -> bool:
        """
        Check if a file/folder name matches exclusion patterns.

        Args:
            name: File or folder name
            exclusion_list: List of exclusion patterns

        Returns:
            True if name should be excluded
        """
        name_lower = name.lower()

        for pattern in exclusion_list:
            pattern_lower = pattern.lower()

            # Exact match
            if name_lower == pattern_lower:
                return True

            # Wildcard pattern
            if '*' in pattern_lower:
                import fnmatch
                if fnmatch.fnmatch(name_lower, pattern_lower):
                    return True

        return False

    def _index_folder(self, folder_path: Path):
        """
        Index a folder and store metadata.

        Args:
            folder_path: Path to the folder
        """
        try:
            stat = folder_path.stat()

            folder_record = {
                'folder_id': str(uuid.uuid4()),
                'path': str(folder_path),
                'parent_id': None,  # TODO: Link to parent folder
                'name': folder_path.name,
                'depth': len(folder_path.parts),
                'created_at': datetime.fromtimestamp(stat.st_ctime),
                'modified_at': datetime.fromtimestamp(stat.st_mtime),
                'scan_session_id': self.session_id
            }

            with self.db_lock:
                self.folder_batch.append(folder_record)
                if len(self.folder_batch) >= self.batch_size:
                    self._flush_folder_batch()

            with self.lock:
                self.stats['folders_scanned'] += 1

        except (PermissionError, OSError) as e:
            logger.debug(f"Cannot access folder {folder_path}: {e}")

    def _index_file(self, file_path: Path):
        """
        Index a single file with full metadata extraction.

        Args:
            file_path: Path to the file
        """
        try:
            stat = file_path.stat()

            # Skip if file is too large (configurable)
            skip_size = self.config.get('scanning', {}).get('hashing', {}).get('skip_files_larger_than', 0)
            if skip_size > 0 and stat.st_size > skip_size:
                logger.debug(f"Skipping large file: {file_path} ({stat.st_size / 1e9:.2f} GB)")
                return

            # Calculate hashes
            quick_hash, full_hash = calculate_adaptive_hash(file_path, stat.st_size)

            # Determine MIME type and category
            mime_type, _ = mimetypes.guess_type(str(file_path))
            file_category, file_subcategory = self.categorizer.categorize(
                file_path.suffix,
                mime_type,
                file_path.name
            )

            file_record = {
                'file_id': str(uuid.uuid4()),
                'path': str(file_path),
                'parent_id': None,  # TODO: Link to parent folder
                'name': file_path.name,
                'extension': file_path.suffix.lower(),
                'size_bytes': stat.st_size,
                'created_at': datetime.fromtimestamp(stat.st_ctime),
                'modified_at': datetime.fromtimestamp(stat.st_mtime),
                'accessed_at': datetime.fromtimestamp(stat.st_atime),
                'mime_type': mime_type,
                'file_category': file_category,
                'file_subcategory': file_subcategory,
                'hash_quick': quick_hash,
                'hash_full': full_hash,
                'access_count': 0,  # TODO: Extract from OS logs
                'scan_session_id': self.session_id
            }

            with self.db_lock:
                self.file_batch.append(file_record)
                if len(self.file_batch) >= self.batch_size:
                    self._flush_file_batch()

            with self.lock:
                self.stats['files_scanned'] += 1
                self.stats['total_size'] += stat.st_size

                # Log progress periodically with enhanced stats
                if self.stats['files_scanned'] % self.progress_interval == 0:
                    current_time = time.time()
                    elapsed = current_time - self.start_time
                    interval_elapsed = current_time - self.last_progress_time

                    # Calculate speeds
                    overall_speed = self.stats['files_scanned'] / elapsed if elapsed > 0 else 0
                    interval_speed = self.progress_interval / interval_elapsed if interval_elapsed > 0 else 0

                    logger.info(
                        f"[PROGRESS] {self.stats['files_scanned']:,} files | "
                        f"{self.stats['total_size'] / 1e9:.2f} GB | "
                        f"{overall_speed:.0f} files/sec | "
                        f"Errors: {self.stats['errors']}"
                    )

                    self.last_progress_time = current_time

        except (PermissionError, OSError, IOError) as e:
            logger.debug(f"Cannot access file {file_path}: {e}")
            with self.lock:
                self.stats['errors'] += 1

    def _flush_batches(self):
        """Flush all pending batches to database."""
        with self.db_lock:
            self._flush_folder_batch()
            self._flush_file_batch()

    def _flush_file_batch(self):
        """Flush pending file records to database."""
        if not self.file_batch:
            return

        try:
            # Batch insert using executemany
            cursor = self.db.conn.cursor()
            cursor.executemany("""
                INSERT INTO files (
                    file_id, path, parent_id, name, extension, size_bytes,
                    created_at, modified_at, accessed_at, mime_type, file_category,
                    file_subcategory, hash_quick, hash_full, access_count, scan_session_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                (
                    f.get('file_id'), f.get('path'), f.get('parent_id'), f.get('name'),
                    f.get('extension'), f.get('size_bytes'), f.get('created_at'),
                    f.get('modified_at'), f.get('accessed_at'), f.get('mime_type'),
                    f.get('file_category'), f.get('file_subcategory'), f.get('hash_quick'),
                    f.get('hash_full'), f.get('access_count', 0), f.get('scan_session_id')
                )
                for f in self.file_batch
            ])
            self.db.conn.commit()
            logger.debug(f"Flushed {len(self.file_batch)} files to database")
            self.file_batch = []
        except Exception as e:
            logger.error(f"Error flushing file batch: {e}")
            self.file_batch = []

    def _flush_folder_batch(self):
        """Flush pending folder records to database."""
        if not self.folder_batch:
            return

        try:
            cursor = self.db.conn.cursor()
            cursor.executemany("""
                INSERT OR REPLACE INTO folders (
                    folder_id, path, parent_id, name, depth, total_size,
                    file_count, subfolder_count, folder_type, created_at,
                    modified_at, scan_session_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                (
                    f.get('folder_id'), f.get('path'), f.get('parent_id'), f.get('name'),
                    f.get('depth'), f.get('total_size', 0), f.get('file_count', 0),
                    f.get('subfolder_count', 0), f.get('folder_type'), f.get('created_at'),
                    f.get('modified_at'), f.get('scan_session_id')
                )
                for f in self.folder_batch
            ])
            self.db.conn.commit()
            logger.debug(f"Flushed {len(self.folder_batch)} folders to database")
            self.folder_batch = []
        except Exception as e:
            logger.error(f"Error flushing folder batch: {e}")
            self.folder_batch = []

    def get_stats(self) -> Dict:
        """Get scan statistics."""
        return self.stats.copy()
