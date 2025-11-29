#!/usr/bin/env python3
"""
IFMOS Organization Validation Script
Validates that all files exist at their new paths and provides statistics
"""

import sqlite3
import os
from collections import defaultdict
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def validate_reorganization(db_path: str):
    """Validate all files exist at new paths"""

    logger.info("=" * 80)
    logger.info("REORGANIZATION VALIDATION")
    logger.info("=" * 80)
    logger.info("")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all files in Organized_V2
    cursor.execute('''
        SELECT id, file_name, file_path, document_type, confidence
        FROM documents
        WHERE file_path LIKE '%Organized_V2%'
        ORDER BY document_type, file_name
    ''')

    files = cursor.fetchall()

    logger.info(f"Total files in database: {len(files)}")
    logger.info("")

    # Validation
    missing = []
    existing = 0
    by_domain = defaultdict(int)
    by_type = defaultdict(int)
    low_confidence = []

    for doc_id, filename, path, doc_type, confidence in files:
        if os.path.exists(path):
            existing += 1

            # Extract domain from path
            parts = Path(path).parts
            if 'Organized_V2' in parts:
                idx = parts.index('Organized_V2')
                if idx + 1 < len(parts):
                    domain = parts[idx + 1]
                    by_domain[domain] += 1

            by_type[doc_type] += 1

            # Track low confidence
            if confidence and confidence < 0.75:
                low_confidence.append({
                    'id': doc_id,
                    'filename': filename,
                    'type': doc_type,
                    'confidence': confidence,
                    'path': path
                })
        else:
            missing.append({
                'id': doc_id,
                'filename': filename,
                'expected_path': path
            })

    # Print results
    logger.info("VALIDATION RESULTS:")
    logger.info(f"  ✓ Files existing: {existing}")
    logger.info(f"  ✗ Files missing: {len(missing)}")
    logger.info(f"  ⚠ Low confidence (<0.75): {len(low_confidence)}")
    logger.info("")

    if missing:
        logger.warning("MISSING FILES:")
        for item in missing[:10]:
            logger.warning(f"  {item['filename']}")
        if len(missing) > 10:
            logger.warning(f"  ... and {len(missing) - 10} more")
        logger.info("")

    logger.info("FILES PER DOMAIN:")
    for domain, count in sorted(by_domain.items(), key=lambda x: x[1], reverse=True):
        logger.info(f"  {domain:30} {count:5} files")
    logger.info("")

    logger.info("FILES PER TYPE (Top 15):")
    for doc_type, count in sorted(by_type.items(), key=lambda x: x[1], reverse=True)[:15]:
        logger.info(f"  {doc_type:30} {count:5} files")
    logger.info("")

    logger.info("LOW CONFIDENCE FILES (Sample):")
    for item in low_confidence[:10]:
        logger.info(f"  {item['type']:25} {item['confidence']:.2f} | {item['filename'][:50]}")
    if len(low_confidence) > 10:
        logger.info(f"  ... and {len(low_confidence) - 10} more")
    logger.info("")

    # Summary
    if len(missing) == 0:
        logger.info("✓ VALIDATION PASSED - All files exist at expected locations")
    else:
        logger.error(f"✗ VALIDATION FAILED - {len(missing)} files missing")

    conn.close()

    return {
        'total': len(files),
        'existing': existing,
        'missing': len(missing),
        'low_confidence': len(low_confidence),
        'by_domain': dict(by_domain),
        'by_type': dict(by_type)
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Validate IFMOS reorganization")
    parser.add_argument('--db', type=str, default='ifmos/data/training/ifmos_ml.db')

    args = parser.parse_args()

    stats = validate_reorganization(args.db)
