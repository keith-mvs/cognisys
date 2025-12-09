#!/usr/bin/env python3
"""
Classify Pending Files - Simple, robust classification
Classifies files in 'pending' state using hybrid pattern+ML system
"""

import sys
import sqlite3
from pathlib import Path
import logging

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from reclassify_null_files import classify_with_patterns, load_ml_model

logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)


def classify_pending_files(db_path, batch_size=1000):
    """Classify all pending files with progress tracking"""

    logger.info("=" * 80)
    logger.info("CLASSIFYING PENDING FILES")
    logger.info("=" * 80)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Load ML model
    logger.info("\nLoading ML model...")
    ml_classifier, ml_vectorizer, ml_label_mappings = load_ml_model()

    if ml_classifier:
        logger.info("✓ ML model loaded (99.21% accuracy)")
    else:
        logger.warning("⚠ ML model not available - using patterns only")

    # Get count of pending files
    cursor.execute("SELECT COUNT(*) FROM file_registry WHERE canonical_state = 'pending'")
    total = cursor.fetchone()[0]

    if total == 0:
        logger.info("\nNo pending files to classify")
        conn.close()
        return

    logger.info(f"\nFiles to classify: {total:,}")
    logger.info("Starting classification...\n")

    stats = {
        'pattern': 0,
        'ml': 0,
        'unknown': 0,
        'total': 0,
        'processed': 0
    }

    # Process in batches
    offset = 0

    while offset < total:
        # Get batch of pending files
        cursor.execute("""
            SELECT file_id, original_path
            FROM file_registry
            WHERE canonical_state = 'pending'
            LIMIT ? OFFSET ?
        """, (batch_size, offset))

        batch = cursor.fetchall()

        if not batch:
            break

        updates = []

        for file_id, original_path in batch:
            try:
                filename = Path(original_path).name

                # Try pattern-based first
                doc_type, confidence, method = classify_with_patterns(filename)

                # Fall back to ML if no pattern match
                if not doc_type and ml_classifier:
                    try:
                        features = ml_vectorizer.transform([filename])
                        prediction = ml_classifier.predict(features)[0]
                        proba = ml_classifier.predict_proba(features)[0]
                        conf = max(proba)

                        if conf >= 0.70:
                            doc_type = prediction
                            confidence = conf
                            method = 'ml_model'
                    except Exception as e:
                        pass  # Silently fail ML, will be marked unknown

                # Default to unknown if still no match
                if not doc_type:
                    doc_type = 'unknown'
                    confidence = 0.0
                    method = 'default'

                # Track stats
                if method == 'pattern_override':
                    stats['pattern'] += 1
                elif method == 'ml_model':
                    stats['ml'] += 1
                else:
                    stats['unknown'] += 1

                stats['total'] += 1
                updates.append((doc_type, confidence, method, file_id))

            except Exception as e:
                logger.warning(f"Error processing file_id {file_id}: {e}")
                stats['total'] += 1

        # Batch update
        if updates:
            cursor.executemany("""
                UPDATE file_registry
                SET document_type = ?,
                    confidence = ?,
                    classification_method = ?,
                    canonical_state = 'organized',
                    updated_at = datetime('now')
                WHERE file_id = ?
            """, updates)
            conn.commit()

        offset += batch_size
        stats['processed'] = min(offset, total)

        # Progress
        pct = (stats['processed'] / total) * 100
        logger.info(f"  Progress: {stats['processed']:,}/{total:,} ({pct:.1f}%)")

    conn.close()

    # Summary
    logger.info("")
    logger.info("=" * 80)
    logger.info("CLASSIFICATION COMPLETE")
    logger.info("=" * 80)
    logger.info(f"Total classified: {stats['total']:,}")
    logger.info(f"  Pattern-based: {stats['pattern']:,} ({stats['pattern']/stats['total']*100:.1f}%)")
    logger.info(f"  ML-based: {stats['ml']:,} ({stats['ml']/stats['total']*100:.1f}%)")
    logger.info(f"  Unknown: {stats['unknown']:,} ({stats['unknown']/stats['total']*100:.1f}%)")
    logger.info("=" * 80)

    return stats


def main():
    print("=" * 80)
    print("CLASSIFY PENDING FILES")
    print("=" * 80)
    print()

    db_path = Path(".cognisys/file_registry.db")

    if not db_path.exists():
        logger.error(f"Database not found: {db_path}")
        return

    stats = classify_pending_files(db_path, batch_size=1000)

    print()
    print("✓ Classification complete!")
    print()
    print("Next steps:")
    print("  1. Run check_db_status.py to see results")
    print("  2. Generate metrics snapshot")
    print("=" * 80)


if __name__ == '__main__':
    main()
