#!/usr/bin/env python3
"""
Final Unknown File Cleanup
Handles edge cases: Git files, PowerShell modules, specialized formats
"""

import sqlite3
from pathlib import Path
import re


class FinalUnknownCleanup:
    """Final pass to classify remaining edge case files"""

    def __init__(self, db_path: str = '.cognisys/file_registry.db'):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()

    def classify_edge_cases(self, filepath: Path) -> tuple:
        """
        Classify edge case files
        Returns: (document_type, confidence, method)
        """
        filename = filepath.name
        stem = filepath.stem.lower()
        ext = filepath.suffix.lower()
        path_str = str(filepath).lower()

        # Git internal files (no extension)
        if '.git' in path_str:
            # Git objects (40-char hex)
            if len(filename) == 40 and re.match(r'^[a-f0-9]{40}$', filename):
                return ('git_object', 0.99, 'pattern_git_object')

            # Git special files
            if filename in ['HEAD', 'index', 'COMMIT_EDITMSG', 'FETCH_HEAD', 'ORIG_HEAD', 'config', 'description']:
                return ('git_metadata', 0.99, 'pattern_git_metadata')

            # Git refs
            if 'refs/' in path_str or 'objects/' in path_str or 'hooks/' in path_str:
                return ('git_internal', 0.95, 'pattern_git_path')

        # PowerShell modules
        if ext == '.psm1':
            return ('technical_script', 0.95, 'pattern_extension')
        if ext == '.psd1':
            return ('technical_config', 0.95, 'pattern_extension')

        # Excel with macros
        if ext == '.xlsm':
            if 'portfolio' in stem or 'financial' in stem or 'budget' in stem:
                return ('financial_spreadsheet', 0.90, 'context_filename')
            else:
                return ('business_spreadsheet', 0.85, 'pattern_extension')

        # Adobe swatch files
        if ext == '.ase':
            return ('design_swatch', 0.95, 'pattern_extension')

        # Web templates
        if ext == '.haml':
            return ('web_template', 0.95, 'pattern_extension')
        if ext == '.scss' or ext == '.sass':
            return ('web_stylesheet', 0.95, 'pattern_extension')
        if ext == '.less':
            return ('web_stylesheet', 0.95, 'pattern_extension')

        # Video formats
        if ext == '.3gp':
            return ('media_video', 0.90, 'pattern_extension')

        # JSON Lines
        if ext == '.jsonl' or ext == '.ndjson':
            return ('technical_dataset', 0.90, 'pattern_extension')

        # VS Code workspace
        if ext == '.code-workspace':
            return ('technical_config', 0.95, 'pattern_extension')

        # VS Code index files
        if ext == '.vsidx':
            return ('technical_index', 0.90, 'pattern_extension')

        # Backup files
        if ext.startswith('.backup') or '.backup' in filename:
            return ('backup_file', 0.85, 'pattern_extension')

        # Shell scripts (no extension)
        if not ext and filename in ['install', 'configure', 'setup', 'build', 'deploy']:
            return ('technical_script', 0.75, 'pattern_filename')

        # Binary executables (no extension)
        if not ext and filename in ['a.out', 'core']:
            return ('compiled_code', 0.80, 'pattern_filename')

        # Build artifacts
        if filename in ['Makefile', 'makefile', 'CMakeLists.txt', 'BUILD', 'build.gradle']:
            return ('technical_config', 0.90, 'pattern_filename')

        return (None, 0.0, None)

    def cleanup_remaining_unknown(self):
        """Final cleanup pass"""
        print("\n" + "=" * 80)
        print("FINAL UNKNOWN FILE CLEANUP")
        print("=" * 80)

        # Get remaining unknown
        self.cursor.execute('''
            SELECT file_id, original_path
            FROM file_registry
            WHERE document_type = 'unknown'
        ''')

        unknown_files = self.cursor.fetchall()
        total = len(unknown_files)

        print(f"\nRemaining unknown files: {total:,}")
        print()

        # Classify
        updates = []
        reclassified = 0

        for file_id, path in unknown_files:
            filepath = Path(path)
            doc_type, confidence, method = self.classify_edge_cases(filepath)

            if doc_type:
                updates.append((
                    doc_type,
                    confidence,
                    method,
                    file_id
                ))
                reclassified += 1

        # Batch update
        if updates:
            self.cursor.executemany('''
                UPDATE file_registry
                SET document_type = ?,
                    confidence = ?,
                    classification_method = ?,
                    updated_at = datetime('now')
                WHERE file_id = ?
            ''', updates)

            self.conn.commit()

        # Final stats
        self.cursor.execute('SELECT COUNT(*) FROM file_registry')
        total_files = self.cursor.fetchone()[0]

        self.cursor.execute('SELECT COUNT(*) FROM file_registry WHERE document_type = "unknown"')
        final_unknown = self.cursor.fetchone()[0]

        final_unknown_rate = (final_unknown / total_files * 100) if total_files > 0 else 0

        print("=" * 80)
        print("FINAL CLEANUP COMPLETE")
        print("=" * 80)
        print(f"Initial unknown: {total:,}")
        print(f"Reclassified: {reclassified:,} ({reclassified/total*100:.1f}%)")
        print(f"Final unknown: {final_unknown:,}")
        print(f"\nFinal unknown rate: {final_unknown_rate:.2f}%")
        print(f"Target: 5.00%")

        if final_unknown_rate <= 5.0:
            print(f"\n✓ TARGET ACHIEVED! ({final_unknown_rate:.2f}% <= 5.00%)")
        else:
            print(f"\n✗ Target not met ({final_unknown_rate:.2f}% > 5.00%)")
            print(f"  Remaining gap: {final_unknown_rate - 5.0:.2f} points")

        print("=" * 80)

        # Show breakdown
        if reclassified > 0:
            print("\nReclassification breakdown:")
            self.cursor.execute('''
                SELECT classification_method, COUNT(*) as count
                FROM file_registry
                WHERE classification_method LIKE 'pattern_git%'
                   OR classification_method IN ('pattern_extension', 'context_filename')
                   AND updated_at > datetime('now', '-1 hour')
                GROUP BY classification_method
                ORDER BY count DESC
            ''')

            for method, count in self.cursor.fetchall():
                print(f"  {method}: {count:,}")

        self.conn.close()

        return {
            'total': total,
            'reclassified': reclassified,
            'final_unknown': final_unknown,
            'final_rate': final_unknown_rate
        }


def main():
    print("=" * 80)
    print("FINAL UNKNOWN FILE CLEANUP")
    print("=" * 80)

    cleanup = FinalUnknownCleanup()
    results = cleanup.cleanup_remaining_unknown()

    print("\n" + "=" * 80)
    print("SESSION COMPLETE")
    print("=" * 80)
    print(f"Unknown rate: 11.19% -> {results['final_rate']:.2f}%")
    print(f"Improvement: {11.19 - results['final_rate']:.2f} points")
    print("=" * 80)


if __name__ == '__main__':
    main()
