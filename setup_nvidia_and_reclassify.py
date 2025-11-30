#!/usr/bin/env python3
"""
Setup NVIDIA API Key and Reclassify Pending Files
Fixes classification issues and adds missing rules
"""

import os
import sqlite3
from pathlib import Path
import sys

# Set NVIDIA API key
NVIDIA_API_KEY = "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"

def set_environment_variable():
    """Set NVIDIA API key as Windows user environment variable"""
    try:
        if sys.platform == 'win32':
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                'Environment',
                0,
                winreg.KEY_SET_VALUE
            )
            winreg.SetValueEx(key, 'NVIDIA_API_KEY', 0, winreg.REG_SZ, NVIDIA_API_KEY)
            winreg.CloseKey(key)
            print("[OK] NVIDIA_API_KEY set as user environment variable")
            print("  (Restart terminal/Claude Code for it to take effect)")

            # Also set for current process
            os.environ['NVIDIA_API_KEY'] = NVIDIA_API_KEY
            print("[OK] NVIDIA_API_KEY set for current session")
        else:
            # Unix-like systems
            os.environ['NVIDIA_API_KEY'] = NVIDIA_API_KEY
            print("[OK] NVIDIA_API_KEY set for current session")
            print("  Add to ~/.bashrc or ~/.zshrc for persistence:")
            print(f"  export NVIDIA_API_KEY='{NVIDIA_API_KEY}'")
    except Exception as e:
        print(f"Warning: Could not set system environment variable: {e}")
        # Still set for current process
        os.environ['NVIDIA_API_KEY'] = NVIDIA_API_KEY
        print("[OK] NVIDIA_API_KEY set for current session only")


def classify_file_by_extension(filepath: Path) -> tuple:
    """
    Enhanced pattern-based classification
    Returns: (document_type, confidence, method)
    """
    filename = filepath.name.lower()
    ext = filepath.suffix.lower()

    # Python files
    if ext in ['.py', '.pyw']:
        return ('technical_script', 1.0, 'pattern_extension')

    # Python compiled
    if ext in ['.pyc', '.pyo', '.pyd']:
        return ('compiled_code', 1.0, 'pattern_extension')

    # Python type stubs
    if ext in ['.pyi', '.typed']:
        return ('source_header', 1.0, 'pattern_extension')

    # Cython
    if ext in ['.pyx', '.pxd', '.pxi']:
        return ('technical_script', 1.0, 'pattern_extension')

    # C/C++ headers
    if ext in ['.h', '.hpp', '.hh', '.hxx', '.h++']:
        return ('source_header', 1.0, 'pattern_extension')

    # C/C++ source
    if ext in ['.c', '.cpp', '.cc', '.cxx', '.c++']:
        return ('technical_script', 1.0, 'pattern_extension')

    # Compiled libraries
    if ext in ['.dll', '.so', '.dylib', '.a', '.lib']:
        return ('compiled_code', 1.0, 'pattern_extension')

    # Archives
    if ext in ['.gz', '.bz2', '.xz', '.lzma', '.z', '.gzip']:
        return ('archive', 1.0, 'pattern_extension')

    # Data files
    if ext in ['.mat', '.npy', '.npz', '.pkl', '.arff']:
        return ('technical_dataset', 1.0, 'pattern_extension')

    # Config files
    if ext in ['.yaml', '.yml', '.json', '.toml', '.cfg', '.ini']:
        return ('technical_config', 1.0, 'pattern_extension')

    # Build files
    if ext in ['.cmake']:
        return ('technical_script', 1.0, 'pattern_extension')

    # Automotive simulation outputs (based on filenames seen)
    if ext in ['.out', '.sum', '.wcm'] and ('speed' in filename or 'run' in filename or 'centerpoint' in filename):
        return ('automotive_technical', 0.90, 'pattern_context')

    # Generic .out files (compiler/test output)
    if ext == '.out':
        return ('technical_log', 0.70, 'pattern_extension')

    # Data tables
    if ext == '.tab':
        return ('technical_dataset', 0.80, 'pattern_extension')

    # Web files
    if ext in ['.html', '.htm', '.css', '.js']:
        return ('technical_documentation', 0.70, 'pattern_extension')

    # Images
    if ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp']:
        return ('media_image', 0.80, 'pattern_extension')

    # Notebooks
    if ext == '.ipynb':
        return ('technical_documentation', 0.90, 'pattern_extension')

    # Markdown
    if ext in ['.md', '.markdown']:
        return ('technical_documentation', 0.85, 'pattern_extension')

    # Scripts
    if ext in ['.vbs', '.bat', '.cmd']:
        return ('technical_script', 0.90, 'pattern_extension')

    # Templates
    if ext in ['.jinja', '.jinja2']:
        return ('technical_config', 0.85, 'pattern_extension')

    # Other
    if ext in ['.xsl']:
        return ('technical_config', 0.75, 'pattern_extension')

    return (None, 0.0, None)


def reclassify_pending_files(db_path: str = '.ifmos/file_registry.db'):
    """Reclassify all pending files using enhanced rules"""

    print("\n" + "=" * 80)
    print("RECLASSIFYING PENDING FILES")
    print("=" * 80)
    print()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all pending files
    cursor.execute('''
        SELECT file_id, original_path
        FROM file_registry
        WHERE canonical_state = "pending"
    ''')

    pending_files = cursor.fetchall()
    total = len(pending_files)

    print(f"Found {total:,} pending files to reclassify")
    print()

    # Reclassify
    classified = 0
    still_unknown = 0
    updates = []

    for file_id, original_path in pending_files:
        filepath = Path(original_path)
        doc_type, confidence, method = classify_file_by_extension(filepath)

        if doc_type:
            updates.append((
                doc_type,
                confidence,
                method,
                'organized',
                file_id
            ))
            classified += 1
        else:
            still_unknown += 1

    # Batch update
    if updates:
        cursor.executemany('''
            UPDATE file_registry
            SET document_type = ?,
                confidence = ?,
                classification_method = ?,
                canonical_state = ?,
                updated_at = datetime('now')
            WHERE file_id = ?
        ''', updates)

        conn.commit()

    conn.close()

    # Summary
    print("=" * 80)
    print("RECLASSIFICATION COMPLETE")
    print("=" * 80)
    print(f"Total processed: {total:,}")
    print(f"Successfully classified: {classified:,} ({classified/total*100:.1f}%)")
    print(f"Still unknown: {still_unknown:,} ({still_unknown/total*100:.1f}%)")
    print()

    return classified, still_unknown


def main():
    print("=" * 80)
    print("NVIDIA API SETUP & PENDING FILE RECLASSIFICATION")
    print("=" * 80)
    print()

    # Step 1: Set API key
    print("Step 1: Setting NVIDIA API Key...")
    set_environment_variable()
    print()

    # Step 2: Reclassify
    print("Step 2: Reclassifying pending files with enhanced rules...")
    classified, unknown = reclassify_pending_files()

    # Final stats
    conn = sqlite3.connect('.ifmos/file_registry.db')
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM file_registry')
    total = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM file_registry WHERE canonical_state = "organized"')
    organized = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM file_registry WHERE canonical_state = "pending"')
    pending = cursor.fetchone()[0]

    conn.close()

    print("=" * 80)
    print("FINAL DATABASE STATUS")
    print("=" * 80)
    print(f"Total files: {total:,}")
    print(f"Organized: {organized:,} ({organized/total*100:.1f}%)")
    print(f"Pending: {pending:,} ({pending/total*100:.1f}%)")
    print()
    print("[COMPLETE] Setup finished!")
    print("  - NVIDIA API key configured")
    print(f"  - {classified:,} files reclassified")
    print("=" * 80)


if __name__ == '__main__':
    main()
