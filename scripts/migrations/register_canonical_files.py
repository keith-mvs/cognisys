#!/usr/bin/env python3
"""
Register all files in Organized_Canonical into file_registry database.
This is needed after the partial consolidation migration.
"""

import sqlite3
import hashlib
from pathlib import Path
from datetime import datetime
import yaml
import sys

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Load config
CONFIG_PATH = PROJECT_ROOT / ".ifmos" / "config.yml"
with open(CONFIG_PATH) as f:
    config = yaml.safe_load(f)

DB_PATH = PROJECT_ROOT / config['ifmos']['database']
CANONICAL_ROOT = Path(config['ifmos']['canonical_root'])


def compute_hash(filepath):
    """Compute SHA-256 hash of file"""
    sha256 = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()


def register_all_canonical_files():
    """Register all files in Organized_Canonical into database"""
    print("="*80)
    print("REGISTERING CANONICAL FILES")
    print("="*80)
    print(f"Canonical root: {CANONICAL_ROOT}")
    print()

    if not CANONICAL_ROOT.exists():
        print(f"ERROR: Canonical root does not exist: {CANONICAL_ROOT}")
        return 1

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    stats = {
        'scanned': 0,
        'already_registered': 0,
        'newly_registered': 0,
        'errors': 0
    }

    print("Scanning canonical directory...")

    for filepath in CANONICAL_ROOT.rglob('*'):
        if not filepath.is_file():
            continue

        stats['scanned'] += 1

        # Skip excluded files
        if 'exclusions' in config and 'exclude_files' in config['exclusions']:
            if any(filepath.match(pattern) for pattern in config['exclusions']['exclude_files']):
                continue

        try:
            file_hash = compute_hash(filepath)
            file_size = filepath.stat().st_size

            # Check if already registered by hash
            cursor.execute("""
                SELECT file_id, canonical_path FROM file_registry
                WHERE content_hash = ?
            """, (file_hash,))

            existing = cursor.fetchone()

            if existing:
                stats['already_registered'] += 1
                if stats['already_registered'] % 100 == 0:
                    print(f"  Progress: {stats['scanned']} scanned, {stats['already_registered']} already registered")
            else:
                # Register as new file
                cursor.execute("""
                    INSERT INTO file_registry
                    (original_path, canonical_path, drop_timestamp, content_hash, file_size,
                     canonical_state, is_duplicate, move_count)
                    VALUES (?, ?, datetime('now'), ?, ?, 'organized', 0, 0)
                """, (
                    str(filepath),  # original_path = canonical_path for migrated files
                    str(filepath),
                    file_hash,
                    file_size
                ))
                stats['newly_registered'] += 1

                if stats['newly_registered'] % 100 == 0:
                    print(f"  Progress: {stats['scanned']} scanned, {stats['newly_registered']} newly registered")

        except (OSError, PermissionError) as e:
            print(f"  ERROR: {filepath} - {e}")
            stats['errors'] += 1
            continue

    conn.commit()
    conn.close()

    # Print summary
    print()
    print("="*80)
    print("REGISTRATION SUMMARY")
    print("="*80)
    print(f"  Files scanned: {stats['scanned']}")
    print(f"  Already registered: {stats['already_registered']}")
    print(f"  Newly registered: {stats['newly_registered']}")
    print(f"  Errors: {stats['errors']}")
    print()
    print("Registration complete!")

    return 0


if __name__ == '__main__':
    sys.exit(register_all_canonical_files())
