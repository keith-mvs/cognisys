#!/usr/bin/env python3
"""
IFMOS Consolidation Migration
Consolidates Organized/ and Organized_V2/ into Organized_Canonical/

Features:
- Detects duplicates by content hash
- Preserves higher-priority source files
- Tracks all files in file_registry.db
- Creates archive of old trees (doesn't delete)
- Dry-run mode to preview changes
"""

import sqlite3
import hashlib
import shutil
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict
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


def scan_directory(directory, source_priority=50):
    """
    Scan directory and return all files with metadata.

    Returns: List of dicts with {path, hash, size, source, priority}
    """
    files = []

    for filepath in Path(directory).rglob('*'):
        if not filepath.is_file():
            continue

        # Skip excluded files
        if 'exclusions' in config and 'exclude_files' in config['exclusions']:
            if any(filepath.match(pattern) for pattern in config['exclusions']['exclude_files']):
                continue

        # Skip excluded directories
        if 'exclusions' in config and 'exclude_dirs' in config['exclusions']:
            if any(part.startswith('.') or part in config['exclusions']['exclude_dirs']
                   for part in filepath.parts):
                continue

        try:
            file_hash = compute_hash(filepath)
            file_size = filepath.stat().st_size

            files.append({
                'path': filepath,
                'hash': file_hash,
                'size': file_size,
                'source': directory,
                'priority': source_priority
            })

        except (OSError, PermissionError) as e:
            print(f"SKIP (error): {filepath} - {e}")
            continue

    return files


def detect_duplicates(all_files):
    """
    Detect duplicates by content hash.

    Returns:
        {
            'unique': [...],      # Files to keep (one per hash)
            'duplicates': [...]   # Files that are duplicates
        }
    """
    # Group by hash
    by_hash = defaultdict(list)
    for file in all_files:
        by_hash[file['hash']].append(file)

    unique = []
    duplicates = []

    for file_hash, file_list in by_hash.items():
        if len(file_list) == 1:
            # Only one file with this hash
            unique.append(file_list[0])
        else:
            # Multiple files with same hash - pick highest priority
            file_list_sorted = sorted(file_list, key=lambda x: x['priority'], reverse=True)

            # First is the keeper
            keeper = file_list_sorted[0]
            keeper['is_original'] = True
            unique.append(keeper)

            # Rest are duplicates
            for dup in file_list_sorted[1:]:
                dup['is_original'] = False
                dup['duplicate_of'] = keeper['path']
                duplicates.append(dup)

    return {
        'unique': unique,
        'duplicates': duplicates
    }


def register_file_in_database(conn, file_info, is_duplicate=False, duplicate_of_id=None):
    """Register file in file_registry table"""
    cursor = conn.cursor()

    canonical_path = file_info.get('canonical_path', None)

    cursor.execute("""
        INSERT INTO file_registry
        (original_path, canonical_path, drop_timestamp, content_hash, file_size,
         canonical_state, is_duplicate, duplicate_of)
        VALUES (?, ?, datetime('now'), ?, ?, ?, ?, ?)
    """, (
        str(file_info['path']),
        str(canonical_path) if canonical_path else None,
        file_info['hash'],
        file_info['size'],
        'organized' if canonical_path else 'pending',
        1 if is_duplicate else 0,
        duplicate_of_id
    ))

    return cursor.lastrowid


def consolidate_to_canonical(dry_run=True):
    """
    Main consolidation logic.

    1. Scan all source directories
    2. Detect duplicates
    3. Move unique files to canonical
    4. Register all files in database
    """
    print("="*80)
    print("IFMOS CONSOLIDATION MIGRATION")
    print("="*80)
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE EXECUTION'}")
    print(f"Target: {CANONICAL_ROOT}")
    print()

    # Ensure canonical root exists
    if not dry_run:
        CANONICAL_ROOT.mkdir(parents=True, exist_ok=True)

    # Connect to database
    conn = sqlite3.connect(DB_PATH)

    # Step 1: Scan all source directories
    print("Step 1: Scanning source directories...")
    all_files = []

    # First, scan canonical directory if it exists (highest priority to prevent duplicates)
    if CANONICAL_ROOT.exists():
        print(f"  Scanning: {CANONICAL_ROOT} (priority=1000 - already canonical)")
        canonical_files = scan_directory(CANONICAL_ROOT, source_priority=1000)
        all_files.extend(canonical_files)
        print(f"    Found: {len(canonical_files)} files (already in canonical location)")

    for source_config in config['consolidation']['sources']:
        source_path = Path(source_config['path'])
        priority = source_config['priority']

        if not source_path.exists():
            print(f"  SKIP (not found): {source_path}")
            continue

        print(f"  Scanning: {source_path} (priority={priority})")
        files = scan_directory(source_path, priority)
        all_files.extend(files)
        print(f"    Found: {len(files)} files")

    print(f"\nTotal files scanned: {len(all_files)}")

    # Step 2: Detect duplicates
    print("\nStep 2: Detecting duplicates...")
    result = detect_duplicates(all_files)

    unique_files = result['unique']
    duplicate_files = result['duplicates']

    print(f"  Unique files: {len(unique_files)}")
    print(f"  Duplicate files: {len(duplicate_files)}")

    # Step 3: Move unique files to canonical
    print("\nStep 3: Moving files to canonical tree...")

    moved_count = 0
    skipped_count = 0

    # Create hash-to-id mapping for duplicates
    hash_to_id = {}

    for file_info in unique_files:
        # Compute target path in canonical tree
        # For now, maintain relative structure from source
        source_root = Path(file_info['source'])
        relative_path = file_info['path'].relative_to(source_root)
        target_path = CANONICAL_ROOT / relative_path

        if file_info['path'] == target_path:
            # Already in canonical location
            skipped_count += 1
            continue

        try:
            print(f"  MOVE: {file_info['path']}")
            print(f"    --> {target_path}")
        except UnicodeEncodeError:
            print(f"  MOVE: [file with special chars]")
            print(f"    --> [target with special chars]")

        if not dry_run:
            # Create target directory
            target_path.parent.mkdir(parents=True, exist_ok=True)

            # Move file (or copy if cross-device)
            try:
                shutil.move(str(file_info['path']), str(target_path))
            except OSError:
                # Cross-device move - copy then delete
                shutil.copy2(str(file_info['path']), str(target_path))
                file_info['path'].unlink()

            # Register in database
            file_info['canonical_path'] = target_path
            file_id = register_file_in_database(conn, file_info, is_duplicate=False)
            hash_to_id[file_info['hash']] = file_id

            moved_count += 1
        else:
            moved_count += 1

    # Step 4: Register duplicates
    print("\nStep 4: Registering duplicates...")

    for dup_info in duplicate_files:
        original_hash = dup_info['hash']
        original_id = hash_to_id.get(original_hash)

        try:
            print(f"  DUPLICATE: {dup_info['path']}")
            print(f"    Original: {dup_info['duplicate_of']}")
        except UnicodeEncodeError:
            print(f"  DUPLICATE: [file with special chars]")

        if not dry_run and original_id:
            register_file_in_database(conn, dup_info, is_duplicate=True, duplicate_of_id=original_id)

    # Commit database changes
    if not dry_run:
        conn.commit()

    conn.close()

    # Step 5: Summary
    print("\n" + "="*80)
    print("CONSOLIDATION SUMMARY")
    print("="*80)
    print(f"  Total files scanned: {len(all_files)}")
    print(f"  Unique files: {len(unique_files)}")
    print(f"  Moved to canonical: {moved_count}")
    print(f"  Skipped (already in place): {skipped_count}")
    print(f"  Duplicates detected: {len(duplicate_files)}")
    print()

    if dry_run:
        print("This was a DRY RUN. No files were moved.")
        print("Run with --execute to perform the consolidation.")
    else:
        print(f"Consolidation complete! Files are now in: {CANONICAL_ROOT}")
        print("\nNext steps:")
        print("  1. Verify files: ls -R", str(CANONICAL_ROOT))
        print("  2. Check database: ifmos status")
        print("  3. Archive old directories (manual)")
        print(f"     mv {config['consolidation']['sources'][0]['path']} {config['consolidation']['archive_path']}/")

    return {
        'total_scanned': len(all_files),
        'unique': len(unique_files),
        'moved': moved_count,
        'skipped': skipped_count,
        'duplicates': len(duplicate_files)
    }


def create_consolidation_report(stats, output_path):
    """Create JSON report of consolidation"""
    report = {
        'timestamp': datetime.now().isoformat(),
        'mode': 'consolidation',
        'statistics': stats,
        'config': {
            'canonical_root': str(CANONICAL_ROOT),
            'sources': config['consolidation']['sources']
        }
    }

    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2)

    print(f"\nReport saved to: {output_path}")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Consolidate IFMOS file trees')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without moving files')
    parser.add_argument('--execute', action='store_true', help='Actually perform consolidation')
    parser.add_argument('--report', type=str, help='Save JSON report to file')

    args = parser.parse_args()

    # Default to dry-run if neither specified
    if not args.dry_run and not args.execute:
        args.dry_run = True
        print("No mode specified, defaulting to --dry-run")
        print()

    dry_run = args.dry_run

    try:
        stats = consolidate_to_canonical(dry_run=dry_run)

        if args.report:
            create_consolidation_report(stats, args.report)

        return 0

    except Exception as e:
        print(f"\n[ERROR] Consolidation failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
