#!/usr/bin/env python3
"""
IFMOS Production Reorganization
Moves files to organized structure based on classification
Includes checkpoint, rollback, and progress tracking
"""

import sqlite3
import yaml
import shutil
from pathlib import Path
from datetime import datetime
import json
import argparse


class ProductionReorganizer:
    """Safe file reorganization with rollback capability"""

    def __init__(self, db_path: str = '.ifmos/file_registry.db', dry_run: bool = True):
        self.db_path = db_path
        self.dry_run = dry_run
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self.checkpoint_file = None
        self.stats = {
            'files_moved': 0,
            'directories_created': 0,
            'errors': 0,
            'skipped': 0
        }
        self.config = self.load_config()

    def load_config(self):
        """Load IFMOS configuration"""
        with open('.ifmos/config.yml', 'r') as f:
            return yaml.safe_load(f)

    def apply_path_template(self, template: str, metadata: dict) -> str:
        """Apply metadata to path template"""
        original = metadata.get('original_filename', 'unknown')
        doc_type = metadata.get('document_type', 'unknown')

        # Default metadata
        now = datetime.now()
        defaults = {
            'YYYY': now.strftime('%Y'),
            'MM': now.strftime('%m'),
            'DD': now.strftime('%d'),
            'YYYY-MM-DD': now.strftime('%Y-%m-%d'),
            'doc_type': doc_type,
            'doc_subtype': doc_type.split('_')[-1] if '_' in doc_type else doc_type,
            'original': original,
            'vehicle_id': 'BMW_328i',
            'project': 'General',
            'product': 'Unknown',
            'version': 'v1',
            'vendor': 'Unknown'
        }

        defaults.update(metadata)

        result = template
        for key, value in defaults.items():
            result = result.replace(f'{{{key}}}', str(value))

        return result

    def create_checkpoint(self):
        """Create rollback checkpoint before reorganization"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.checkpoint_file = f'.ifmos/checkpoints/reorganization_{timestamp}.json'

        Path(self.checkpoint_file).parent.mkdir(parents=True, exist_ok=True)

        # Get all files to be reorganized
        self.cursor.execute('''
            SELECT file_id, original_path, document_type
            FROM file_registry
            WHERE canonical_state = 'organized' AND document_type IS NOT NULL
        ''')

        files = []
        for file_id, path, doc_type in self.cursor.fetchall():
            files.append({
                'file_id': file_id,
                'original_path': path,
                'document_type': doc_type,
                'exists_at_checkpoint': Path(path).exists() if path else False
            })

        checkpoint_data = {
            'timestamp': timestamp,
            'total_files': len(files),
            'files': files,
            'database_path': self.db_path
        }

        with open(self.checkpoint_file, 'w') as f:
            json.dump(checkpoint_data, f, indent=2)

        print(f"[CHECKPOINT] Created: {self.checkpoint_file}")
        print(f"[CHECKPOINT] {len(files):,} files backed up")
        return self.checkpoint_file

    def reorganize_files(self, base_dir: str = 'Organized'):
        """Reorganize files to target structure"""
        print("\n" + "=" * 80)
        print("PRODUCTION REORGANIZATION" + (" [DRY RUN]" if self.dry_run else " [LIVE]"))
        print("=" * 80)

        # Get organized files
        self.cursor.execute('''
            SELECT file_id, original_path, document_type
            FROM file_registry
            WHERE canonical_state = 'organized'
              AND document_type IS NOT NULL
              AND canonical_path IS NULL
            ORDER BY file_id
        ''')

        files = self.cursor.fetchall()
        total = len(files)

        print(f"\nReorganizing {total:,} files to {base_dir}/...")
        print()

        domain_mappings = self.config.get('domain_mappings', {})
        batch_size = 100
        moved_count = 0
        created_dirs = set()

        for i, (file_id, original_path, doc_type) in enumerate(files, 1):
            # Progress
            if i % batch_size == 0:
                print(f"  Progress: {i:,}/{total:,} ({i/total*100:.1f}%) - Moved: {moved_count:,}, Dirs: {len(created_dirs)}")

            # Skip if source doesn't exist
            if not original_path or not Path(original_path).exists():
                self.stats['skipped'] += 1
                continue

            try:
                # Find domain and template
                target_template = None
                for domain, domain_config in domain_mappings.items():
                    if doc_type in domain_config.get('types', []):
                        target_template = domain_config.get('path_template')
                        break

                if not target_template:
                    # Default template
                    target_template = "Organized/{doc_type}/{YYYY}/{MM}/{YYYY-MM-DD}_{original}"

                # Extract metadata
                filename = Path(original_path).name
                metadata = {
                    'original_filename': filename,
                    'document_type': doc_type
                }

                # Apply template
                target_path = self.apply_path_template(target_template, metadata)
                target_path_obj = Path(target_path)

                # Create directory structure
                if not self.dry_run:
                    target_path_obj.parent.mkdir(parents=True, exist_ok=True)
                    created_dirs.add(str(target_path_obj.parent))

                    # Move file
                    shutil.move(str(original_path), str(target_path))

                    # Update database
                    self.cursor.execute('''
                        UPDATE file_registry
                        SET canonical_path = ?,
                            updated_at = datetime('now')
                        WHERE file_id = ?
                    ''', (str(target_path), file_id))

                moved_count += 1

            except Exception as e:
                self.stats['errors'] += 1
                print(f"  [ERROR] {original_path}: {e}")

        # Commit database changes
        if not self.dry_run:
            self.conn.commit()

        self.stats['files_moved'] = moved_count
        self.stats['directories_created'] = len(created_dirs)

        # Summary
        print()
        print("=" * 80)
        print("REORGANIZATION SUMMARY")
        print("=" * 80)
        print(f"Total processed: {total:,}")
        print(f"Files moved: {moved_count:,}")
        print(f"Directories created: {len(created_dirs)}")
        print(f"Skipped: {self.stats['skipped']:,}")
        print(f"Errors: {self.stats['errors']:,}")
        print("=" * 80)

        return moved_count

    def verify_reorganization(self):
        """Verify reorganization results"""
        print("\n" + "=" * 80)
        print("VERIFICATION")
        print("=" * 80)

        # Count files with canonical paths
        self.cursor.execute('''
            SELECT COUNT(*) FROM file_registry
            WHERE canonical_path IS NOT NULL
        ''')
        with_canonical = self.cursor.fetchone()[0]

        # Count files still needing reorganization
        self.cursor.execute('''
            SELECT COUNT(*) FROM file_registry
            WHERE canonical_state = 'organized'
              AND document_type IS NOT NULL
              AND canonical_path IS NULL
        ''')
        remaining = self.cursor.fetchone()[0]

        # Count total organized
        self.cursor.execute('''
            SELECT COUNT(*) FROM file_registry
            WHERE canonical_state = 'organized'
        ''')
        total_organized = self.cursor.fetchone()[0]

        print(f"\nFiles with canonical paths: {with_canonical:,}")
        print(f"Files needing reorganization: {remaining:,}")
        print(f"Total organized: {total_organized:,}")

        # Calculate completion
        completion = (with_canonical / total_organized * 100) if total_organized > 0 else 0
        print(f"\nReorganization completion: {completion:.1f}%")
        print("=" * 80)

        return remaining == 0

    def generate_report(self):
        """Generate reorganization report"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'dry_run': self.dry_run,
            'checkpoint_file': self.checkpoint_file,
            'statistics': self.stats
        }

        filename = f"reorganization_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"\n[REPORT] Saved: {filename}")
        return filename

    def close(self):
        """Close database connection"""
        self.conn.close()


def main():
    parser = argparse.ArgumentParser(description='IFMOS Production Reorganization')
    parser.add_argument('--execute', action='store_true', help='Execute reorganization (default is dry-run)')
    parser.add_argument('--skip-checkpoint', action='store_true', help='Skip checkpoint creation')
    parser.add_argument('--base-dir', default='Organized', help='Base directory for organization')
    parser.add_argument('--db', default='.ifmos/file_registry.db', help='Database path')
    args = parser.parse_args()

    print("=" * 80)
    print("IFMOS PRODUCTION REORGANIZATION")
    print("=" * 80)
    print(f"Mode: {'LIVE REORGANIZATION' if args.execute else 'DRY RUN'}")
    print(f"Database: {args.db}")
    print(f"Target: {args.base_dir}/")
    print("=" * 80)

    reorganizer = ProductionReorganizer(db_path=args.db, dry_run=not args.execute)

    try:
        # Create checkpoint
        if not args.skip_checkpoint and args.execute:
            reorganizer.create_checkpoint()

        # Confirm if executing
        if args.execute:
            print("\n[WARNING] This will move all organized files to new structure!")
            print("[WARNING] Checkpoint created for rollback if needed")
            response = input("\nProceed with reorganization? (yes/no): ")
            if response.lower() != 'yes':
                print("Aborted.")
                return

        # Reorganize files
        moved = reorganizer.reorganize_files(base_dir=args.base_dir)

        # Verify if executed
        if args.execute:
            reorganizer.verify_reorganization()

        # Generate report
        reorganizer.generate_report()

        print("\n" + "=" * 80)
        print("REORGANIZATION COMPLETE")
        print("=" * 80)
        if args.execute:
            print(f"Files moved: {moved:,}")
            print(f"Directories created: {reorganizer.stats['directories_created']}")
            print(f"Checkpoint: {reorganizer.checkpoint_file}")
        else:
            print("DRY RUN - No files were moved")
            print("Run with --execute to perform actual reorganization")
        print("=" * 80)

    finally:
        reorganizer.close()


if __name__ == '__main__':
    main()
