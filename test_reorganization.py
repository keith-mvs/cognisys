#!/usr/bin/env python3
"""
Test Reorganization - Dry Run
Simulates file reorganization without moving files
Validates path templates and target structure
"""

import sqlite3
import yaml
from pathlib import Path
from collections import Counter
import re
from datetime import datetime

def load_config():
    """Load IFMOS configuration"""
    with open('.ifmos/config.yml', 'r') as f:
        return yaml.safe_load(f)

def apply_path_template(template: str, metadata: dict) -> str:
    """
    Apply metadata to path template

    Args:
        template: Path template with {placeholders}
        metadata: Dictionary of metadata values

    Returns:
        Resolved path string
    """
    # Extract filename metadata
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
        'vehicle_id': 'BMW_328i',  # Default
        'project': 'General',
        'product': 'Unknown',
        'version': 'v1',
        'vendor': 'Unknown'
    }

    # Merge with provided metadata
    defaults.update(metadata)

    # Replace placeholders
    result = template
    for key, value in defaults.items():
        result = result.replace(f'{{{key}}}', str(value))

    return result

def test_reorganization(db_path: str, config: dict, limit: int = 100):
    """
    Test reorganization in dry-run mode

    Args:
        db_path: Path to database
        config: IFMOS configuration
        limit: Number of files to test
    """
    print("=" * 80)
    print("REORGANIZATION DRY RUN TEST")
    print("=" * 80)
    print()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get sample of organized files
    cursor.execute("""
        SELECT file_id, original_path, document_type, confidence, classification_method
        FROM file_registry
        WHERE canonical_state = 'organized' AND document_type IS NOT NULL
        ORDER BY RANDOM()
        LIMIT ?
    """, (limit,))

    files = cursor.fetchall()

    print(f"Testing reorganization for {len(files)} sample files...\n")

    # Get path templates from config
    domain_mappings = config.get('domain_mappings', {})

    # Results tracking
    successful = 0
    failed = 0
    warnings = []
    target_paths = {}

    for file_id, original_path, doc_type, confidence, method in files:
        try:
            # Find domain and path template for this document type
            target_template = None
            domain_name = None

            for domain, domain_config in domain_mappings.items():
                if doc_type in domain_config.get('types', []):
                    target_template = domain_config.get('path_template')
                    domain_name = domain
                    break

            if not target_template:
                # Default template
                target_template = "Organized/{doc_type}/{YYYY}/{MM}/{YYYY-MM-DD}_{original}"
                domain_name = "default"

            # Extract metadata
            filename = Path(original_path).name
            metadata = {
                'original_filename': filename,
                'document_type': doc_type
            }

            # Apply template
            target_path = apply_path_template(target_template, metadata)

            # Track results
            target_paths[original_path] = target_path
            successful += 1

            # Show first 5 examples
            if successful <= 5:
                print(f"Example {successful}:")
                print(f"  Original: {original_path}")
                print(f"  Type: {doc_type} (domain: {domain_name})")
                print(f"  Target: {target_path}")
                print()

        except Exception as e:
            failed += 1
            warnings.append(f"Failed for {original_path}: {e}")

    conn.close()

    # Summary
    print("=" * 80)
    print("DRY RUN SUMMARY")
    print("=" * 80)
    print(f"Files tested: {len(files)}")
    print(f"Successful mappings: {successful}")
    print(f"Failed mappings: {failed}")
    print()

    # Analyze target paths
    target_dirs = Counter()
    for target in target_paths.values():
        target_dir = str(Path(target).parent)
        target_dirs[target_dir] += 1

    print("Top 10 target directories:")
    for dir_path, count in target_dirs.most_common(10):
        print(f"  {dir_path}: {count} files")
    print()

    # Show warnings
    if warnings:
        print("Warnings:")
        for warning in warnings[:10]:
            print(f"  - {warning}")
        if len(warnings) > 10:
            print(f"  ... and {len(warnings) - 10} more")
        print()

    print("=" * 80)
    print("DRY RUN COMPLETE")
    print("=" * 80)
    print()
    print("Next steps:")
    print("  1. Review target paths above")
    print("  2. Adjust path templates in .ifmos/config.yml if needed")
    print("  3. Run full reorganization with execute flag")
    print()
    print("To execute reorganization:")
    print("  python reorganize_files.py --execute")
    print("=" * 80)


def main():
    db_path = Path('.ifmos/file_registry.db')
    config_path = Path('.ifmos/config.yml')

    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        return

    if not config_path.exists():
        print(f"Error: Config not found at {config_path}")
        return

    config = load_config()
    test_reorganization(str(db_path), config, limit=100)


if __name__ == '__main__':
    main()
