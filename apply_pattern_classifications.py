#!/usr/bin/env python3
"""
Apply Pattern-Based Classifications
Implements suggestions from pattern analysis
"""

import sqlite3
from pathlib import Path


def apply_pattern_classifications(db_path: str = '.cognisys/file_registry.db'):
    """Apply all discovered pattern-based classifications"""

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("=" * 80)
    print("APPLYING PATTERN-BASED CLASSIFICATIONS")
    print("=" * 80)

    updates = []
    stats = {}

    # Get all unknown files
    cursor.execute('''
        SELECT file_id, original_path
        FROM file_registry
        WHERE document_type = 'unknown'
    ''')

    unknown_files = cursor.fetchall()
    total = len(unknown_files)

    print(f"\nProcessing {total:,} unknown files...")
    print()

    for file_id, path in unknown_files:
        filepath = Path(path)
        filename = filepath.name.lower()
        ext = filepath.suffix.lower()
        path_str = str(path).lower()

        classified = False

        # Pattern 1: venv/site-packages (44% coverage)
        if 'venv' in path_str and 'site-packages' in path_str:
            updates.append(('dependency_python', 0.95, 'pattern_directory_venv', file_id))
            stats['dependency_python'] = stats.get('dependency_python', 0) + 1
            classified = True

        # Pattern 2: .vcf files (vCard contacts) (6.3%)
        elif ext == '.vcf':
            updates.append(('contact_vcard', 0.95, 'pattern_extension', file_id))
            stats['contact_vcard'] = stats.get('contact_vcard', 0) + 1
            classified = True

        # Pattern 3: .pyi (Python type stubs) (6.2%)
        elif ext == '.pyi':
            updates.append(('source_header', 0.95, 'pattern_extension', file_id))
            stats['source_header'] = stats.get('source_header', 0) + 1
            classified = True

        # Pattern 4: .pyd (Python compiled extensions) (6.0%)
        elif ext == '.pyd':
            updates.append(('compiled_code', 0.95, 'pattern_extension', file_id))
            stats['compiled_code'] = stats.get('compiled_code', 0) + 1
            classified = True

        # Pattern 5: Numbered backups .1, .2, .3, .4, .5 (16.4%)
        elif ext in ['.1', '.2', '.3', '.4', '.5', '.6', '.7', '.8', '.9']:
            updates.append(('backup_versioned', 0.90, 'pattern_extension', file_id))
            stats['backup_versioned'] = stats.get('backup_versioned', 0) + 1
            classified = True

        # Pattern 6: .out, .sum, .wcm (automotive simulation) (8.9%)
        elif ext in ['.out', '.sum', '.wcm']:
            updates.append(('automotive_technical', 0.90, 'pattern_extension', file_id))
            stats['automotive_technical'] = stats.get('automotive_technical', 0) + 1
            classified = True

        # Pattern 7: .m (MATLAB scripts) (3%)
        elif ext == '.m':
            updates.append(('technical_script', 0.85, 'pattern_extension', file_id))
            stats['technical_script'] = stats.get('technical_script', 0) + 1
            classified = True

        # Pattern 8: .lib (library files) (2.8%)
        elif ext == '.lib':
            updates.append(('compiled_code', 0.90, 'pattern_extension', file_id))
            stats['compiled_code'] = stats.get('compiled_code', 0) + 1
            classified = True

        # Pattern 9: .itc2 (specialized format) (1.7%)
        elif ext == '.itc2':
            updates.append(('technical_dataset', 0.75, 'pattern_extension', file_id))
            stats['technical_dataset'] = stats.get('technical_dataset', 0) + 1
            classified = True

        # Pattern 10: .xsd (XML Schema)
        elif ext == '.xsd':
            updates.append(('technical_config', 0.90, 'pattern_extension', file_id))
            stats['technical_config'] = stats.get('technical_config', 0) + 1
            classified = True

        # Pattern 11: .chm (Compiled HTML Help)
        elif ext == '.chm':
            updates.append(('technical_documentation', 0.90, 'pattern_extension', file_id))
            stats['technical_documentation'] = stats.get('technical_documentation', 0) + 1
            classified = True

        # Pattern 12: .pth (Python path configuration)
        elif ext == '.pth':
            updates.append(('technical_config', 0.95, 'pattern_extension', file_id))
            stats['technical_config'] = stats.get('technical_config', 0) + 1
            classified = True

    # Apply all updates
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

    # Final statistics
    cursor.execute('SELECT COUNT(*) FROM file_registry')
    total_files = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM file_registry WHERE document_type = "unknown"')
    final_unknown = cursor.fetchone()[0]

    final_rate = (final_unknown / total_files * 100) if total_files > 0 else 0

    # Print results
    print("=" * 80)
    print("CLASSIFICATION RESULTS")
    print("=" * 80)
    print(f"Files classified: {len(updates):,}")
    print()
    print("Breakdown by type:")
    for doc_type, count in sorted(stats.items(), key=lambda x: x[1], reverse=True):
        pct = (count / len(updates) * 100) if updates else 0
        print(f"  {doc_type:35} {count:6,} ({pct:5.1f}%)")

    print()
    print("=" * 80)
    print("FINAL STATUS")
    print("=" * 80)
    print(f"Initial unknown: {total:,} (7.39%)")
    print(f"Classified: {len(updates):,}")
    print(f"Remaining unknown: {final_unknown:,} ({final_rate:.2f}%)")
    print()

    if final_rate <= 5.0:
        improvement = 7.39 - final_rate
        print(f"[SUCCESS] TARGET ACHIEVED!")
        print(f"  Final unknown rate: {final_rate:.2f}%")
        print(f"  Target: 5.00%")
        print(f"  Improvement: -{improvement:.2f} points")
        print(f"  Exceeded target by: {5.0 - final_rate:.2f} points")
    else:
        gap = final_rate - 5.0
        print(f"[PROGRESS] Getting closer to target")
        print(f"  Current: {final_rate:.2f}%")
        print(f"  Target: 5.00%")
        print(f"  Remaining gap: {gap:.2f} points ({int(gap * total_files / 100):,} files)")

    print("=" * 80)

    conn.close()

    return {
        'classified': len(updates),
        'final_unknown': final_unknown,
        'final_rate': final_rate,
        'stats': stats
    }


if __name__ == '__main__':
    results = apply_pattern_classifications()
