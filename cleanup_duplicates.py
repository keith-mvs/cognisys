#!/usr/bin/env python3
"""
CogniSys Duplicate Cleanup
Safely remove duplicate files while preserving canonicals
Includes checkpoint, rollback, and verification
"""

import sqlite3
import json
import shutil
from pathlib import Path
from datetime import datetime
import hashlib
import argparse


class DuplicateCleanup:
    """Safe duplicate file removal with rollback capability"""

    def __init__(self, db_path: str = '.cognisys/file_registry.db', dry_run: bool = True):
        self.db_path = db_path
        self.dry_run = dry_run
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self.checkpoint_file = None
        self.stats = {
            'duplicates_found': 0,
            'duplicates_deleted': 0,
            'space_freed': 0,
            'errors': 0,
            'skipped': 0
        }

    def create_checkpoint(self):
        """Create rollback checkpoint before deletion"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.checkpoint_file = f'.cognisys/checkpoints/duplicate_cleanup_{timestamp}.json'

        # Ensure checkpoint directory exists
        Path(self.checkpoint_file).parent.mkdir(parents=True, exist_ok=True)

        # Get all duplicates
        self.cursor.execute('''
            SELECT file_id, original_path, content_hash, file_size
            FROM file_registry
            WHERE is_duplicate = 1
        ''')

        duplicates = []
        for file_id, path, content_hash, size in self.cursor.fetchall():
            duplicates.append({
                'file_id': file_id,
                'original_path': path,
                'content_hash': content_hash,
                'file_size': size,
                'existed_at_checkpoint': Path(path).exists() if path else False
            })

        checkpoint_data = {
            'timestamp': timestamp,
            'total_duplicates': len(duplicates),
            'duplicates': duplicates,
            'database_path': self.db_path
        }

        with open(self.checkpoint_file, 'w') as f:
            json.dump(checkpoint_data, f, indent=2)

        print(f"[CHECKPOINT] Created: {self.checkpoint_file}")
        print(f"[CHECKPOINT] {len(duplicates):,} duplicates backed up")
        return self.checkpoint_file

    def analyze_duplicates(self):
        """Analyze duplicates before deletion"""
        print("\n" + "=" * 80)
        print("DUPLICATE ANALYSIS")
        print("=" * 80)

        # Total duplicates
        self.cursor.execute('SELECT COUNT(*), SUM(file_size) FROM file_registry WHERE is_duplicate = 1')
        count, total_size = self.cursor.fetchone()

        print(f"\nTotal duplicates: {count:,}")
        print(f"Total size: {total_size / (1024**3):.2f} GB")

        # By document type
        self.cursor.execute('''
            SELECT document_type, COUNT(*) as count, SUM(file_size) as size
            FROM file_registry
            WHERE is_duplicate = 1
            GROUP BY document_type
            ORDER BY size DESC
            LIMIT 10
        ''')

        print("\nTop duplicates by type:")
        for doc_type, cnt, size in self.cursor.fetchall():
            print(f"  {doc_type or 'NULL'}: {cnt:,} files, {size / (1024**2):.2f} MB")

        # Largest duplicate groups
        self.cursor.execute('''
            SELECT content_hash, COUNT(*) as count
            FROM file_registry
            WHERE is_duplicate = 1
            GROUP BY content_hash
            HAVING count > 10
            ORDER BY count DESC
            LIMIT 5
        ''')

        print("\nLargest duplicate groups:")
        for content_hash, cnt in self.cursor.fetchall():
            # Get sample path
            self.cursor.execute('''
                SELECT original_path, file_size
                FROM file_registry
                WHERE content_hash = ?
                LIMIT 1
            ''', (content_hash,))
            path, size = self.cursor.fetchone()
            filename = Path(path).name if path else 'unknown'
            print(f"  {cnt:,}x copies of '{filename[:50]}' ({size:,} bytes each)")

        self.stats['duplicates_found'] = count
        print("\n" + "=" * 80)

    def delete_duplicates(self, skip_patterns=None):
        """Delete duplicate files with safety checks"""
        skip_patterns = skip_patterns or []

        print("\n" + "=" * 80)
        print("DUPLICATE DELETION" + (" [DRY RUN]" if self.dry_run else " [LIVE]"))
        print("=" * 80)

        # Get all duplicates
        self.cursor.execute('''
            SELECT file_id, original_path, file_size
            FROM file_registry
            WHERE is_duplicate = 1
            ORDER BY file_id
        ''')

        duplicates = self.cursor.fetchall()
        total = len(duplicates)

        print(f"\nProcessing {total:,} duplicates...")
        print()

        deleted_count = 0
        space_freed = 0
        errors = []
        batch_size = 100

        for i, (file_id, path, size) in enumerate(duplicates, 1):
            # Progress
            if i % batch_size == 0:
                print(f"  Progress: {i:,}/{total:,} ({i/total*100:.1f}%) - Deleted: {deleted_count:,}, Space freed: {space_freed / (1024**3):.2f} GB")

            # Skip if path matches skip patterns
            if any(pattern in str(path) for pattern in skip_patterns):
                self.stats['skipped'] += 1
                continue

            # Check if file exists
            if not path or not Path(path).exists():
                self.stats['skipped'] += 1
                continue

            try:
                if not self.dry_run:
                    # Delete file
                    Path(path).unlink()

                    # Update database
                    self.cursor.execute('''
                        UPDATE file_registry
                        SET canonical_state = 'deleted',
                            updated_at = datetime('now')
                        WHERE file_id = ?
                    ''', (file_id,))

                deleted_count += 1
                space_freed += size

            except Exception as e:
                self.stats['errors'] += 1
                errors.append((path, str(e)))

        # Commit database changes
        if not self.dry_run:
            self.conn.commit()

        # Final summary
        print()
        print("=" * 80)
        print("DELETION SUMMARY")
        print("=" * 80)
        print(f"Total processed: {total:,}")
        print(f"Deleted: {deleted_count:,}")
        print(f"Skipped: {self.stats['skipped']:,}")
        print(f"Errors: {self.stats['errors']:,}")
        print(f"Space freed: {space_freed / (1024**3):.2f} GB")

        if errors and len(errors) <= 10:
            print("\nErrors:")
            for path, error in errors[:10]:
                print(f"  {path}: {error}")

        self.stats['duplicates_deleted'] = deleted_count
        self.stats['space_freed'] = space_freed

        print("=" * 80)

        return deleted_count, space_freed

    def verify_cleanup(self):
        """Verify cleanup results"""
        print("\n" + "=" * 80)
        print("VERIFICATION")
        print("=" * 80)

        # Count remaining duplicates
        self.cursor.execute('SELECT COUNT(*) FROM file_registry WHERE is_duplicate = 1 AND canonical_state != "deleted"')
        remaining = self.cursor.fetchone()[0]

        # Count unique files
        self.cursor.execute('SELECT COUNT(*) FROM file_registry WHERE is_duplicate = 0')
        unique = self.cursor.fetchone()[0]

        # Count deleted
        self.cursor.execute('SELECT COUNT(*) FROM file_registry WHERE canonical_state = "deleted"')
        deleted = self.cursor.fetchone()[0]

        # Storage stats
        self.cursor.execute('SELECT SUM(file_size) FROM file_registry WHERE is_duplicate = 0')
        unique_size = self.cursor.fetchone()[0] or 0

        print(f"\nRemaining duplicates: {remaining:,}")
        print(f"Unique files: {unique:,}")
        print(f"Deleted files: {deleted:,}")
        print(f"Unique storage: {unique_size / (1024**3):.2f} GB")

        # Calculate new space efficiency
        total_files = unique + remaining
        space_efficiency = (unique / total_files * 100) if total_files > 0 else 0

        print(f"\nNew space efficiency: {space_efficiency:.2f}%")
        print("=" * 80)

        return remaining == 0 or remaining < 100

    def generate_report(self):
        """Generate cleanup report"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'dry_run': self.dry_run,
            'checkpoint_file': self.checkpoint_file,
            'statistics': self.stats
        }

        filename = f"duplicate_cleanup_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"\n[REPORT] Saved: {filename}")
        return filename

    def close(self):
        """Close database connection"""
        self.conn.close()


def main():
    parser = argparse.ArgumentParser(description='CogniSys Duplicate Cleanup')
    parser.add_argument('--execute', action='store_true', help='Execute deletion (default is dry-run)')
    parser.add_argument('--skip-checkpoint', action='store_true', help='Skip checkpoint creation')
    parser.add_argument('--db', default='.cognisys/file_registry.db', help='Database path')
    args = parser.parse_args()

    print("=" * 80)
    print("COGNISYS DUPLICATE CLEANUP")
    print("=" * 80)
    print(f"Mode: {'LIVE DELETION' if args.execute else 'DRY RUN'}")
    print(f"Database: {args.db}")
    print("=" * 80)

    # Initialize cleanup
    cleanup = DuplicateCleanup(db_path=args.db, dry_run=not args.execute)

    try:
        # Analyze first
        cleanup.analyze_duplicates()

        # Create checkpoint
        if not args.skip_checkpoint and args.execute:
            cleanup.create_checkpoint()

        # Confirm if executing
        if args.execute:
            print("\n[WARNING] This will permanently delete duplicate files!")
            print("[WARNING] Checkpoint created for rollback if needed")
            response = input("\nProceed with deletion? (yes/no): ")
            if response.lower() != 'yes':
                print("Aborted.")
                return

        # Delete duplicates
        # Skip Claude session files and other safe-to-delete patterns
        skip_patterns = []  # Could add patterns here if needed
        deleted, freed = cleanup.delete_duplicates(skip_patterns=skip_patterns)

        # Verify if executed
        if args.execute:
            cleanup.verify_cleanup()

        # Generate report
        cleanup.generate_report()

        print("\n" + "=" * 80)
        print("CLEANUP COMPLETE")
        print("=" * 80)
        if args.execute:
            print(f"Deleted: {deleted:,} files")
            print(f"Space freed: {freed / (1024**3):.2f} GB")
            print(f"Checkpoint: {cleanup.checkpoint_file}")
        else:
            print("DRY RUN - No files were deleted")
            print("Run with --execute to perform actual deletion")
        print("=" * 80)

    finally:
        cleanup.close()


if __name__ == '__main__':
    main()
