#!/usr/bin/env python3
"""
Classify Package Manager Cache Files
Final push to achieve <5% unknown rate
"""

import sqlite3
from pathlib import Path
import re


def classify_cache_files(db_path: str = '.cognisys/file_registry.db'):
    """Classify NPM/Yarn/package manager cache files"""

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("=" * 80)
    print("PACKAGE MANAGER CACHE CLASSIFICATION")
    print("=" * 80)

    # Get unknown files
    cursor.execute('''
        SELECT file_id, original_path
        FROM file_registry
        WHERE document_type = 'unknown'
    ''')

    unknown_files = cursor.fetchall()
    total = len(unknown_files)

    print(f"\nAnalyzing {total:,} unknown files...")
    print()

    # Classify cache patterns
    updates = []

    for file_id, path in unknown_files:
        filepath = Path(path)
        filename = filepath.name

        # NPM/Yarn cache: 16-char hex + @v{N}
        if re.match(r'^[a-f0-9]{16}@v\d+$', filename):
            updates.append(('cache_package_manager', 0.95, 'pattern_cache_npm', file_id))

        # NPM cache: hex hash (40 chars, no extension)
        elif len(filename) == 40 and re.match(r'^[a-f0-9]{40}$', filename) and 'npm' in str(path).lower():
            updates.append(('cache_package_manager', 0.90, 'pattern_cache_npm', file_id))

        # Generic cache patterns (no extension, cache in path)
        elif not filepath.suffix and 'cache' in str(path).lower():
            if re.match(r'^[a-f0-9-]{8,}', filename):  # Looks like hash
                updates.append(('cache_temporary', 0.85, 'pattern_cache_generic', file_id))

        # Browser cache (numbered files)
        elif not filepath.suffix and re.match(r'^\d{5,}$', filename):
            updates.append(('cache_temporary', 0.75, 'pattern_cache_numbered', file_id))

    # Apply updates
    if updates:
        cursor.executemany('''
            UPDATE file_registry
            SET document_type = ?,
                confidence = ?,
                classification_method = ?,
                updated_at = datetime('now')
            WHERE file_id = ?
        ''', updates)

        conn.commit()

    # Final stats
    cursor.execute('SELECT COUNT(*) FROM file_registry')
    total_files = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM file_registry WHERE document_type = \"unknown\"')
    final_unknown = cursor.fetchone()[0]

    final_rate = (final_unknown / total_files * 100) if total_files > 0 else 0

    print("=" * 80)
    print("CLASSIFICATION COMPLETE")
    print("=" * 80)
    print(f"Cache files classified: {len(updates):,}")
    print(f"Remaining unknown: {final_unknown:,}")
    print(f"Unknown rate: {final_rate:.2f}%")
    print()

    if final_rate <= 5.0:
        print(f"[SUCCESS] Target achieved! ({final_rate:.2f}% <= 5.00%)")
        print(f"  Improvement: {7.58 - final_rate:.2f} points")
    else:
        print(f"[PROGRESS] Current: {final_rate:.2f}%")
        print(f"  Gap to target: {final_rate - 5.0:.2f} points")

    print("=" * 80)

    conn.close()

    return {
        'classified': len(updates),
        'final_unknown': final_unknown,
        'final_rate': final_rate
    }


if __name__ == '__main__':
    results = classify_cache_files()
