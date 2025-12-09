"""
Analysis engine for CogniSys.
Implements multi-stage deduplication pipeline and pattern detection.
"""

from pathlib import Path
from typing import List, Dict, Optional
from difflib import SequenceMatcher

from ..models.database import Database
from ..utils.hashing import calculate_full_hash
from ..utils.naming import normalize_filename
from ..utils.logging_config import get_logger

logger = get_logger(__name__)


class Analyzer:
    """
    Intelligent file analyzer with deduplication and pattern detection.
    """

    def __init__(self, database: Database, config: Dict):
        """
        Initialize analyzer with database and configuration.

        Args:
            database: Database instance
            config: Configuration dictionary with analysis rules
        """
        self.db = database
        self.config = config
        self.stats = {
            'duplicate_groups': 0,
            'duplicate_files': 0,
            'space_wasted': 0
        }

    def analyze_session(self, session_id: str) -> Dict:
        """
        Run full analysis pipeline on a scan session.

        Args:
            session_id: Scan session to analyze

        Returns:
            Analysis results and statistics
        """
        logger.info(f"=== Starting Analysis Pipeline ===")
        logger.info(f"Session ID: {session_id}")

        # Stage 1: Find exact duplicates
        if self.config.get('deduplication', {}).get('exact_match', {}).get('enabled', True):
            logger.info(f"\n[1/4] Finding exact duplicates...")
            self._find_exact_duplicates(session_id)
            logger.info(f"  [OK] Found {self.stats['duplicate_groups']} duplicate groups "
                       f"({self.stats['space_wasted'] / 1e9:.3f} GB wasted)")

        # Stage 2: Find fuzzy filename matches
        if self.config.get('deduplication', {}).get('fuzzy_filename', {}).get('enabled', True):
            logger.info(f"\n[2/4] Finding similar filenames...")
            groups_before = self.stats['duplicate_groups']
            self._find_fuzzy_duplicates(session_id)
            fuzzy_groups = self.stats['duplicate_groups'] - groups_before
            logger.info(f"  [OK] Found {fuzzy_groups} fuzzy duplicate groups")

        # Stage 3: Identify orphaned files
        logger.info(f"\n[3/4] Identifying orphaned files...")
        self._identify_orphaned_files(session_id)

        # Stage 4: Mark temporary/low-value files
        logger.info(f"\n[4/4] Marking low-value files...")
        self._mark_temp_files(session_id)

        logger.info(f"\n=== Analysis Complete ===")
        logger.info(f"  Duplicate groups: {self.stats['duplicate_groups']}")
        logger.info(f"  Duplicate files: {self.stats['duplicate_files']}")
        logger.info(f"  Wasted space: {self.stats['space_wasted'] / 1e9:.2f} GB")

        return self.stats

    def _find_exact_duplicates(self, session_id: str):
        """
        Stage 1-3: Find exact duplicate files using progressive hashing.
        """
        min_size = self.config.get('deduplication', {}).get('exact_match', {}).get('min_file_size', 1024)

        # Stage 1: Pre-filter by size + extension
        candidates = self.db.get_duplicate_candidates(session_id)
        logger.info(f"  -> Examining {len(candidates)} candidate groups...")

        # Stage 2: Group by quick hash
        processed = 0
        for candidate_group in candidates:
            processed += 1
            if processed % 100 == 0:
                logger.info(f"  -> Processing candidate group {processed}/{len(candidates)}")
            file_ids = candidate_group['file_ids'].split(',')

            if candidate_group['size_bytes'] < min_size:
                continue

            # Get files
            files = [self.db.get_files_by_hash(fid)[0] if self.db.get_files_by_hash(fid)
                     else None for fid in file_ids]
            files = [f for f in files if f]

            # Group by quick hash
            hash_groups = {}
            for file in files:
                if file['hash_quick']:
                    if file['hash_quick'] not in hash_groups:
                        hash_groups[file['hash_quick']] = []
                    hash_groups[file['hash_quick']].append(file)

            # Stage 3: Verify with full hash
            for quick_hash, file_group in hash_groups.items():
                if len(file_group) < 2:
                    continue

                # Calculate full hashes if not already present
                for file in file_group:
                    if not file['hash_full']:
                        full_hash = calculate_full_hash(Path(file['path']))
                        if full_hash:
                            self.db.update_file_hash(file['file_id'], 'full', full_hash)
                            file['hash_full'] = full_hash

                # Group by full hash
                full_hash_groups = {}
                for file in file_group:
                    if file['hash_full']:
                        if file['hash_full'] not in full_hash_groups:
                            full_hash_groups[file['hash_full']] = []
                        full_hash_groups[file['hash_full']].append(file)

                # Create duplicate groups
                for full_hash, duplicates in full_hash_groups.items():
                    if len(duplicates) >= 2:
                        self._create_duplicate_group(duplicates, 'exact')

    def _find_fuzzy_duplicates(self, session_id: str):
        """
        Stage 4: Find files with similar names (likely copies).
        Optimized with pre-filtering and grouping.
        """
        threshold = self.config.get('deduplication', {}).get('fuzzy_filename', {}).get('similarity_threshold', 0.85)
        same_folder_only = self.config.get('deduplication', {}).get('fuzzy_filename', {}).get('same_folder_only', True)
        max_folder_files = self.config.get('deduplication', {}).get('fuzzy_filename', {}).get('max_folder_files', 1000)
        min_file_size = self.config.get('deduplication', {}).get('fuzzy_filename', {}).get('min_file_size', 1024)  # 1KB

        files = self.db.get_files_by_session(session_id)

        # Pre-filter: skip small files and already marked duplicates
        files = [f for f in files
                 if not f['is_duplicate'] and f['size_bytes'] >= min_file_size]
        logger.info(f"  -> Analyzing {len(files)} files after pre-filtering...")

        # Group by folder if required
        if same_folder_only:
            folder_groups = {}
            for file in files:
                folder = str(Path(file['path']).parent)
                if folder not in folder_groups:
                    folder_groups[folder] = []
                folder_groups[folder].append(file)

            logger.info(f"  -> Comparing files in {len(folder_groups)} folders...")

            # Compare within each folder (skip folders with too many files)
            processed_folders = 0
            skipped_folders = 0
            for folder, folder_files in folder_groups.items():
                processed_folders += 1
                if processed_folders % 50 == 0:
                    logger.info(f"  -> Progress: {processed_folders}/{len(folder_groups)} folders processed")

                if len(folder_files) <= max_folder_files:
                    self._compare_filenames_optimized(folder_files, threshold)
                else:
                    skipped_folders += 1
                    logger.debug(f"Skipping fuzzy match for {folder}: {len(folder_files)} files (threshold: {max_folder_files})")

            if skipped_folders > 0:
                logger.info(f"  -> Skipped {skipped_folders} folders with > {max_folder_files} files")
        else:
            # Compare all files (expensive!)
            self._compare_filenames_optimized(files, threshold)

    def _compare_filenames_optimized(self, files: List[Dict], threshold: float):
        """
        Optimized filename comparison with extension grouping and early filtering.

        Args:
            files: List of file records
            threshold: Similarity threshold (0.0 to 1.0)
        """
        # Group by extension first to reduce comparisons
        ext_groups = {}
        for file in files:
            ext = file.get('extension', '').lower()
            if ext not in ext_groups:
                ext_groups[ext] = []
            ext_groups[ext].append(file)

        # Compare only within same extension groups
        for ext, ext_files in ext_groups.items():
            # Further group by file size (within 10% tolerance) for efficiency
            size_groups = {}
            for file in ext_files:
                size_key = file['size_bytes'] // 1024  # Group by KB
                if size_key not in size_groups:
                    size_groups[size_key] = []
                size_groups[size_key].append(file)

            # Compare within size groups
            for size_key, size_files in size_groups.items():
                if len(size_files) < 2:
                    continue

                for i, file_a in enumerate(size_files):
                    for file_b in size_files[i + 1:]:
                        # Early exit if sizes are too different (> 10%)
                        size_diff = abs(file_a['size_bytes'] - file_b['size_bytes'])
                        if size_diff > file_a['size_bytes'] * 0.1:
                            continue

                        # Normalize names
                        norm_a = normalize_filename(file_a['name'])
                        norm_b = normalize_filename(file_b['name'])

                        # Quick length check before expensive similarity calculation
                        len_diff = abs(len(norm_a) - len(norm_b))
                        if len_diff > max(len(norm_a), len(norm_b)) * (1 - threshold):
                            continue

                        # Calculate similarity
                        similarity = SequenceMatcher(None, norm_a, norm_b).ratio()

                        if similarity >= threshold:
                            self._create_duplicate_group(
                                [file_a, file_b],
                                'fuzzy-name',
                                f"Name similarity: {similarity:.2f}, size: {file_a['size_bytes']}"
                            )

    def _compare_filenames(self, files: List[Dict], threshold: float):
        """
        DEPRECATED: Use _compare_filenames_optimized instead.
        Kept for backwards compatibility.
        """
        self._compare_filenames_optimized(files, threshold)

    def _create_duplicate_group(
        self,
        files: List[Dict],
        similarity_type: str,
        detection_rule: Optional[str] = None
    ):
        """
        Create a duplicate group and select canonical file.

        Args:
            files: List of duplicate file records
            similarity_type: Type of duplicate (exact, fuzzy-name, etc.)
            detection_rule: Rule used to detect duplicates
        """
        # Select canonical file
        canonical = self._select_canonical(files)

        # Build member list
        members = []
        for file in files:
            is_canonical = (file['file_id'] == canonical['file_id'])
            members.append({
                'file_id': file['file_id'],
                'priority_score': file.get('_priority_score', 0),
                'reason': 'Canonical copy' if is_canonical else 'Duplicate'
            })

        # Calculate space wasted (all copies except canonical)
        space_wasted = sum(f['size_bytes'] for f in files if f['file_id'] != canonical['file_id'])

        group_data = {
            'canonical_file': canonical['file_id'],
            'member_count': len(files),
            'total_size': files[0]['size_bytes'],
            'similarity_type': similarity_type,
            'detection_rule': detection_rule or similarity_type,
            'members': members
        }

        group_id = self.db.create_duplicate_group(group_data)

        self.stats['duplicate_groups'] += 1
        self.stats['duplicate_files'] += len(files) - 1
        self.stats['space_wasted'] += space_wasted

        logger.debug(f"Created duplicate group {group_id} with {len(files)} members")

    def _select_canonical(self, files: List[Dict]) -> Dict:
        """
        Select canonical file from duplicates using priority scoring.

        Args:
            files: List of duplicate file records

        Returns:
            Canonical file record
        """
        priorities = self.config.get('deduplication', {}).get('canonical_selection', {}).get('priorities', [])
        preferred_paths = self.config.get('deduplication', {}).get('canonical_selection', {}).get('preferred_paths', [])

        for file in files:
            score = 0

            # Priority 1: Newest modified
            newest = max(files, key=lambda f: f['modified_at'])
            if file['file_id'] == newest['file_id']:
                score += 10

            # Priority 2: Preferred path
            for preferred_path in preferred_paths:
                if preferred_path in file['path']:
                    score += 20
                    break

            # Priority 3: Shorter path (closer to root)
            depth = file['path'].count(os.sep)
            score += max(0, 10 - depth)

            # Priority 4: Descriptive name (not generic)
            import re
            if not re.search(r'(copy|backup|\(\d+\)|untitled)', file['name'], re.I):
                score += 5

            # Priority 5: Access frequency
            if file['access_count'] > 0:
                score += min(15, file['access_count'])

            file['_priority_score'] = score

        # Return highest scoring file
        return max(files, key=lambda f: f['_priority_score'])

    def _identify_orphaned_files(self, session_id: str):
        """
        Identify orphaned or stale files based on access patterns.
        """
        criteria = self.config.get('orphaned_files', {}).get('criteria', [])

        # Build query based on criteria
        # For now, mark files not accessed in 365+ days
        cursor = self.db.conn.cursor()
        cursor.execute("""
            UPDATE files
            SET is_orphaned = 1
            WHERE scan_session_id = ?
              AND accessed_at < datetime('now', '-365 days')
        """, (session_id,))
        self.db.conn.commit()

        count = cursor.rowcount
        logger.info(f"Marked {count} files as orphaned")

    def _mark_temp_files(self, session_id: str):
        """
        Mark temporary and low-value files.
        """
        temp_patterns = ['.tmp', '.bak', '.old', '.temp', '.cache']

        cursor = self.db.conn.cursor()

        for pattern in temp_patterns:
            cursor.execute("""
                UPDATE files
                SET is_temp = 1
                WHERE scan_session_id = ?
                  AND (extension = ? OR name LIKE ?)
            """, (session_id, pattern, f'%{pattern}'))

        self.db.conn.commit()

        count = cursor.rowcount
        logger.info(f"Marked {count} files as temporary")

    def get_stats(self) -> Dict:
        """Get analysis statistics."""
        return self.stats.copy()


import os
