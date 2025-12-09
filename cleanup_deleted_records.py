#!/usr/bin/env python3
"""
Database Cleanup - Remove Deleted File Records

This script removes file records marked as 'deleted' from the database.
These records are from the duplicate cleanup process and are no longer needed.

Safety:
- Creates backup of database before cleanup
- Reports detailed statistics
- Non-destructive (deleted files already removed from filesystem)

Author: Claude Code
Date: 2025-11-30
"""

import sqlite3
import shutil
from pathlib import Path
from datetime import datetime
import json


class DatabaseCleanup:
    """Clean up deleted records from CogniSys database"""

    def __init__(self, db_path: str = '.cognisys/file_registry.db'):
        self.db_path = Path(db_path)
        self.backup_path = None
        self.stats = {
            'timestamp': datetime.now().isoformat(),
            'before': {},
            'after': {},
            'removed': {}
        }

    def create_backup(self):
        """Create database backup before cleanup"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_dir = Path('.cognisys/backups')
        backup_dir.mkdir(parents=True, exist_ok=True)

        self.backup_path = backup_dir / f'file_registry_before_cleanup_{timestamp}.db'
        shutil.copy2(self.db_path, self.backup_path)

        print(f"\n[BACKUP] Created: {self.backup_path}")
        print(f"[BACKUP] Size: {self.backup_path.stat().st_size / 1024 / 1024:.2f} MB")
        return self.backup_path

    def get_statistics(self, conn) -> dict:
        """Get current database statistics"""
        cursor = conn.cursor()

        # Overall counts
        cursor.execute('SELECT COUNT(*), SUM(file_size) FROM file_registry')
        total_count, total_size = cursor.fetchone()

        # By canonical state
        cursor.execute('''
            SELECT canonical_state, COUNT(*), SUM(file_size)
            FROM file_registry
            GROUP BY canonical_state
        ''')
        by_state = {}
        for state, count, size in cursor.fetchall():
            state_name = state if state else 'NULL'
            by_state[state_name] = {
                'count': count,
                'size_bytes': size if size else 0,
                'size_gb': (size / 1024 / 1024 / 1024) if size else 0
            }

        # Database file size
        db_size_mb = self.db_path.stat().st_size / 1024 / 1024

        return {
            'total_records': total_count,
            'total_size_gb': (total_size / 1024 / 1024 / 1024) if total_size else 0,
            'db_size_mb': db_size_mb,
            'by_state': by_state
        }

    def cleanup_deleted_records(self):
        """Remove all deleted file records"""
        print("\n" + "=" * 80)
        print("DATABASE CLEANUP - REMOVE DELETED RECORDS")
        print("=" * 80)

        # Create backup first
        self.create_backup()

        # Connect and get before stats
        conn = sqlite3.connect(self.db_path)

        print("\n[BEFORE CLEANUP]")
        self.stats['before'] = self.get_statistics(conn)
        self._print_stats(self.stats['before'])

        # Delete records with canonical_state = 'deleted'
        cursor = conn.cursor()

        print("\n[CLEANUP] Removing deleted records...")
        cursor.execute('SELECT COUNT(*) FROM file_registry WHERE canonical_state = ?', ('deleted',))
        deleted_count = cursor.fetchone()[0]

        cursor.execute('''
            SELECT SUM(file_size)
            FROM file_registry
            WHERE canonical_state = ?
        ''', ('deleted',))
        deleted_size = cursor.fetchone()[0] or 0

        self.stats['removed'] = {
            'count': deleted_count,
            'size_bytes': deleted_size,
            'size_gb': deleted_size / 1024 / 1024 / 1024
        }

        # Execute deletion
        cursor.execute('DELETE FROM file_registry WHERE canonical_state = ?', ('deleted',))
        conn.commit()

        print(f"[CLEANUP] Removed {deleted_count:,} deleted records")
        print(f"[CLEANUP] Freed {self.stats['removed']['size_gb']:.2f} GB from database tracking")

        # Vacuum database to reclaim space
        print("\n[VACUUM] Reclaiming database space...")
        cursor.execute('VACUUM')
        conn.commit()

        # Get after stats
        print("\n[AFTER CLEANUP]")
        self.stats['after'] = self.get_statistics(conn)
        self._print_stats(self.stats['after'])

        conn.close()

        # Calculate improvements
        self._print_improvements()

        # Save report
        self._save_report()

        return self.stats

    def _print_stats(self, stats: dict):
        """Print statistics in readable format"""
        print(f"  Total Records: {stats['total_records']:,}")
        print(f"  Total Size: {stats['total_size_gb']:.2f} GB")
        print(f"  Database Size: {stats['db_size_mb']:.2f} MB")
        print(f"\n  By State:")
        for state, data in stats['by_state'].items():
            print(f"    {state:15} : {data['count']:8,} records | {data['size_gb']:8.2f} GB")

    def _print_improvements(self):
        """Print improvement summary"""
        print("\n" + "=" * 80)
        print("CLEANUP SUMMARY")
        print("=" * 80)

        records_removed = self.stats['before']['total_records'] - self.stats['after']['total_records']
        size_freed = self.stats['removed']['size_gb']
        db_size_reduction = self.stats['before']['db_size_mb'] - self.stats['after']['db_size_mb']
        db_size_pct = (db_size_reduction / self.stats['before']['db_size_mb']) * 100

        print(f"\n[SUCCESS] Database Cleanup Complete!")
        print(f"\n  Records Removed: {records_removed:,}")
        print(f"  Space Freed from Tracking: {size_freed:.2f} GB")
        print(f"  Database Size Reduction: {db_size_reduction:.2f} MB ({db_size_pct:.1f}%)")
        print(f"\n  Database Size: {self.stats['before']['db_size_mb']:.2f} MB → {self.stats['after']['db_size_mb']:.2f} MB")
        print(f"  Active Records: {self.stats['after']['total_records']:,}")

        # Calculate new space efficiency
        if 'organized' in self.stats['after']['by_state']:
            organized_size = self.stats['after']['by_state']['organized']['size_gb']
            total_original = self.stats['before']['total_size_gb']
            efficiency = (organized_size / total_original) * 100
            print(f"\n  Space Efficiency: {efficiency:.2f}%")

        print("\n" + "=" * 80)

    def _save_report(self):
        """Save cleanup report to JSON"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_path = Path(f'database_cleanup_report_{timestamp}.json')

        with open(report_path, 'w') as f:
            json.dump(self.stats, f, indent=2)

        print(f"\n[REPORT] Saved to: {report_path}")


def main():
    """Main execution"""
    cleanup = DatabaseCleanup()

    try:
        stats = cleanup.cleanup_deleted_records()

        print("\n[OK] Database cleanup completed successfully")
        print(f"[OK] Backup available at: {cleanup.backup_path}")

        return 0

    except Exception as e:
        print(f"\n[ERROR] Cleanup failed: {e}")
        if cleanup.backup_path and cleanup.backup_path.exists():
            print(f"[ERROR] Database backup available at: {cleanup.backup_path}")
            print(f"[ERROR] To restore: cp {cleanup.backup_path} {cleanup.db_path}")
        return 1


if __name__ == '__main__':
    exit(main())
