#!/usr/bin/env python3
"""
Create Versioned Rollback System

Creates flattened backup copies of the file repository with version tracking.
Keeps multiple rollback versions alongside current Organized structure for:
- Backup/disaster recovery
- ML training (historical file state tracking)
- Audit trail (what files were, are, and changes over time)

Author: Claude Code
Date: 2025-11-30
"""

import json
import shutil
from pathlib import Path
from datetime import datetime
import sqlite3


class VersionedRollbackCreator:
    """Create versioned rollback snapshots of file repository"""

    def __init__(self, db_path: str = '.ifmos/file_registry.db'):
        self.db_path = Path(db_path)
        self.rollback_base = Path('.ifmos/rollbacks')
        self.rollback_base.mkdir(parents=True, exist_ok=True)

    def get_latest_version(self) -> int:
        """Get the latest rollback version number"""
        existing = list(self.rollback_base.glob('v*'))
        if not existing:
            return 0

        versions = []
        for p in existing:
            try:
                v = int(p.name[1:])  # Remove 'v' prefix
                versions.append(v)
            except ValueError:
                continue

        return max(versions) if versions else 0

    def create_rollback_snapshot(self, source_dir: str = 'Organized',
                                   flatten: bool = True,
                                   include_metadata: bool = True):
        """
        Create a new rollback snapshot

        Args:
            source_dir: Directory to snapshot (default: Organized)
            flatten: If True, flatten directory structure; if False, preserve hierarchy
            include_metadata: Include JSON metadata about files
        """
        print("\n" + "=" * 80)
        print("CREATING VERSIONED ROLLBACK SNAPSHOT")
        print("=" * 80)

        # Determine next version
        next_version = self.get_latest_version() + 1
        version_dir = self.rollback_base / f'v{next_version:02d}'

        print(f"\nVersion: v{next_version:02d}")
        print(f"Source: {source_dir}")
        print(f"Destination: {version_dir}")
        print(f"Flatten: {flatten}")

        # Create version directory
        version_dir.mkdir(parents=True, exist_ok=True)

        # Create files subdirectory
        if flatten:
            files_dir = version_dir / 'files_flat'
        else:
            files_dir = version_dir / 'files_structured'
        files_dir.mkdir(parents=True, exist_ok=True)

        # Collect files from source
        source_path = Path(source_dir)
        if not source_path.exists():
            print(f"\n[ERROR] Source directory not found: {source_path}")
            return None

        all_files = list(source_path.rglob('*'))
        file_list = [f for f in all_files if f.is_file()]

        print(f"\nFound {len(file_list):,} files to snapshot")

        # Copy files
        copied = 0
        errors = 0
        manifest = []

        for file_path in file_list:
            try:
                # Relative path from source
                rel_path = file_path.relative_to(source_path)

                if flatten:
                    # Flattened: use filename only, add counter if duplicate
                    dest_name = file_path.name
                    dest_path = files_dir / dest_name

                    # Handle duplicates by adding counter
                    counter = 1
                    while dest_path.exists():
                        stem = file_path.stem
                        suffix = file_path.suffix
                        dest_name = f"{stem}_{counter}{suffix}"
                        dest_path = files_dir / dest_name
                        counter += 1
                else:
                    # Structured: preserve directory hierarchy
                    dest_path = files_dir / rel_path
                    dest_path.parent.mkdir(parents=True, exist_ok=True)

                # Copy file
                shutil.copy2(file_path, dest_path)
                copied += 1

                # Track in manifest
                manifest.append({
                    'original_path': str(file_path),
                    'relative_path': str(rel_path),
                    'rollback_path': str(dest_path.relative_to(version_dir)),
                    'size_bytes': file_path.stat().st_size,
                    'modified_time': file_path.stat().st_mtime
                })

                if copied % 1000 == 0:
                    print(f"  Copied {copied:,} files...", end='\r')

            except Exception as e:
                print(f"\n[ERROR] Failed to copy {file_path}: {e}")
                errors += 1

        print(f"\n  Copied {copied:,} files successfully")
        if errors > 0:
            print(f"  Errors: {errors}")

        # Save manifest
        manifest_path = version_dir / 'manifest.json'
        manifest_data = {
            'version': f'v{next_version:02d}',
            'created': datetime.now().isoformat(),
            'source_directory': str(source_path.absolute()),
            'flatten': flatten,
            'total_files': len(manifest),
            'total_size_bytes': sum(f['size_bytes'] for f in manifest),
            'files': manifest
        }

        with open(manifest_path, 'w') as f:
            json.dump(manifest_data, f, indent=2)

        print(f"\n[OK] Manifest saved: {manifest_path}")

        # Load database metadata if requested
        if include_metadata:
            self._add_database_metadata(version_dir, manifest)

        # Create version info
        info_path = version_dir / 'version_info.txt'
        total_size_gb = manifest_data['total_size_bytes'] / (1024**3)

        info_content = f"""IFMOS Rollback Snapshot
Version: v{next_version:02d}
Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Source: {source_path.absolute()}
Layout: {'Flattened' if flatten else 'Structured'}

Statistics:
  Files: {len(manifest):,}
  Total Size: {total_size_gb:.2f} GB

Purpose:
  - Backup/disaster recovery
  - ML training (historical file states)
  - Audit trail (file evolution tracking)

Restore:
  See manifest.json for original file paths
  Use restore_from_rollback.py to restore files
"""

        with open(info_path, 'w') as f:
            f.write(info_content)

        print(f"[OK] Version info saved: {info_path}")

        # Summary
        print("\n" + "=" * 80)
        print("ROLLBACK SNAPSHOT COMPLETE")
        print("=" * 80)
        print(f"\nVersion: v{next_version:02d}")
        print(f"Location: {version_dir}")
        print(f"Files: {len(manifest):,}")
        print(f"Size: {total_size_gb:.2f} GB")
        print(f"\nThis snapshot can be used for:")
        print("  - Restoring files to previous state")
        print("  - ML training on file history")
        print("  - Audit trail analysis")
        print("=" * 80)

        return version_dir

    def _add_database_metadata(self, version_dir: Path, manifest: list):
        """Add database metadata about files to rollback"""
        print("\n[METADATA] Adding database metadata...")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        metadata_records = []

        for file_info in manifest:
            original_path = file_info['original_path']

            # Query database for this file
            cursor.execute('''
                SELECT original_path, canonical_path, canonical_state,
                       document_type, confidence, classification_method,
                       file_size, content_hash, created_at, updated_at
                FROM file_registry
                WHERE canonical_path = ?
            ''', (original_path,))

            row = cursor.fetchone()
            if row:
                metadata_records.append({
                    'file': file_info['rollback_path'],
                    'original_path': row[0],
                    'canonical_path': row[1],
                    'state': row[2],
                    'document_type': row[3],
                    'confidence': row[4],
                    'classification_method': row[5],
                    'size': row[6],
                    'content_hash': row[7],
                    'created_at': row[8],
                    'updated_at': row[9]
                })

        conn.close()

        # Save metadata
        metadata_path = version_dir / 'file_metadata.json'
        with open(metadata_path, 'w') as f:
            json.dump({
                'version': version_dir.name,
                'created': datetime.now().isoformat(),
                'total_records': len(metadata_records),
                'records': metadata_records
            }, f, indent=2)

        print(f"[METADATA] Saved {len(metadata_records):,} metadata records")
        print(f"[METADATA] Location: {metadata_path}")

    def cleanup_old_versions(self, keep_versions: int = 2):
        """Keep only the N most recent versions"""
        print(f"\n[CLEANUP] Keeping only {keep_versions} most recent versions...")

        existing = list(self.rollback_base.glob('v*'))
        if len(existing) <= keep_versions:
            print(f"[CLEANUP] Currently {len(existing)} versions, no cleanup needed")
            return

        # Sort by version number
        versions = []
        for p in existing:
            try:
                v = int(p.name[1:])
                versions.append((v, p))
            except ValueError:
                continue

        versions.sort(reverse=True)  # Newest first

        # Keep top N, delete rest
        to_delete = versions[keep_versions:]

        for version_num, version_path in to_delete:
            print(f"[CLEANUP] Removing old version: {version_path.name}")
            shutil.rmtree(version_path)

        print(f"[CLEANUP] Removed {len(to_delete)} old versions")


def main():
    """Main execution"""
    creator = VersionedRollbackCreator()

    # Create new rollback snapshot (flattened)
    version_dir = creator.create_rollback_snapshot(
        source_dir='Organized',
        flatten=True,  # Flatten directory structure
        include_metadata=True  # Include database metadata
    )

    if version_dir:
        # Cleanup old versions (keep last 2)
        creator.cleanup_old_versions(keep_versions=2)

        print("\n[SUCCESS] Versioned rollback system ready")
        print(f"\nYou now have:")
        print(f"  1. Current files: Organized/")
        print(f"  2. Latest backup: {version_dir}/")

        existing = list(creator.rollback_base.glob('v*'))
        print(f"  3. Total versions: {len(existing)}")


if __name__ == '__main__':
    main()
