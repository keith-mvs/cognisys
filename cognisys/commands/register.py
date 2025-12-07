"""
CogniSys Register Command
Registers files from drop directory into file_registry database
"""

import sqlite3
import hashlib
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def compute_hash(filepath):
    """Compute SHA-256 hash of file"""
    sha256 = hashlib.sha256()

    try:
        with open(filepath, 'rb') as f:
            while chunk := f.read(8192):
                sha256.update(chunk)
        return sha256.hexdigest()
    except (OSError, PermissionError) as e:
        logger.warning(f"Cannot hash {filepath}: {e}")
        return None


def register_files_from_drop(drop_dir, db_path, dry_run=False):
    """
    Scan drop directory and register files in database.

    Args:
        drop_dir: Path to drop/inbox directory
        db_path: Path to SQLite database
        dry_run: If True, don't actually register files

    Returns:
        dict with statistics
    """
    drop_dir = Path(drop_dir)

    if not drop_dir.exists():
        raise FileNotFoundError(f"Drop directory not found: {drop_dir}")

    logger.info(f"Scanning drop directory: {drop_dir}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    stats = {
        'scanned': 0,
        'registered': 0,
        'duplicates': 0,
        'errors': 0
    }

    # Scan all files in drop directory
    for filepath in drop_dir.rglob('*'):
        if not filepath.is_file():
            continue

        stats['scanned'] += 1

        # Skip system files
        if filepath.name.startswith('.') or filepath.name in ['Thumbs.db', 'desktop.ini']:
            continue

        # Compute hash
        content_hash = compute_hash(filepath)
        if not content_hash:
            stats['errors'] += 1
            continue

        # Check if already registered
        cursor.execute("""
            SELECT file_id, canonical_path, is_duplicate
            FROM file_registry
            WHERE content_hash = ?
        """, (content_hash,))

        existing = cursor.fetchone()

        if existing:
            # Duplicate
            file_id, canonical_path, is_dup = existing
            logger.info(f"SKIP (duplicate): {filepath}")
            logger.info(f"  Original: {canonical_path}")
            stats['duplicates'] += 1

            if not dry_run:
                # Register as duplicate
                cursor.execute("""
                    INSERT INTO file_registry
                    (original_path, drop_timestamp, content_hash, file_size,
                     canonical_state, is_duplicate, duplicate_of)
                    VALUES (?, datetime('now'), ?, ?, 'duplicate', 1, ?)
                """, (str(filepath), content_hash, filepath.stat().st_size, file_id))
        else:
            # New file
            logger.info(f"REGISTER: {filepath}")
            stats['registered'] += 1

            if not dry_run:
                cursor.execute("""
                    INSERT INTO file_registry
                    (original_path, drop_timestamp, content_hash, file_size, canonical_state)
                    VALUES (?, datetime('now'), ?, ?, 'pending')
                """, (str(filepath), content_hash, filepath.stat().st_size))

    if not dry_run:
        conn.commit()

    conn.close()

    # Print summary
    logger.info("")
    logger.info("="*80)
    logger.info("REGISTRATION SUMMARY")
    logger.info("="*80)
    logger.info(f"  Files scanned: {stats['scanned']}")
    logger.info(f"  New files registered: {stats['registered']}")
    logger.info(f"  Duplicates detected: {stats['duplicates']}")
    logger.info(f"  Errors: {stats['errors']}")

    if dry_run:
        logger.info("\nDRY RUN - No files were registered")

    return stats
