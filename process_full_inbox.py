#!/usr/bin/env python3
"""
Process Full Inbox - Register and Classify 102k+ Files
Combines registration + hybrid pattern+ML classification
"""

import sys
import sqlite3
from pathlib import Path
from datetime import datetime
import logging

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from cognisys.commands.register import register_files_from_drop
from reclassify_null_files import classify_with_patterns, load_ml_model

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def classify_pending_files(db_path):
    """
    Classify all files with canonical_state='pending' using hybrid system
    """
    logger.info("=" * 80)
    logger.info("CLASSIFYING PENDING FILES")
    logger.info("=" * 80)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Load ML model
    ml_classifier, ml_vectorizer = load_ml_model()
    if not ml_classifier:
        logger.warning("ML model not available - using patterns only")

    # Get all pending files
    cursor.execute("""
        SELECT file_id, original_path
        FROM file_registry
        WHERE canonical_state = 'pending'
    """)

    pending = cursor.fetchall()
    total = len(pending)

    if total == 0:
        logger.info("No pending files to classify")
        conn.close()
        return

    logger.info(f"Found {total:,} pending files to classify\n")

    stats = {
        'pattern': 0,
        'ml': 0,
        'total': 0
    }

    # Classify in batches
    batch_size = 100
    batch = []

    for i, (file_id, original_path) in enumerate(pending):
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
                logger.warning(f"ML classification failed for {filename}: {e}")

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
        stats['total'] += 1

        # Add to batch
        batch.append((doc_type, confidence, method, file_id))

        # Execute batch update
        if len(batch) >= batch_size:
            cursor.executemany("""
                UPDATE file_registry
                SET document_type = ?,
                    confidence = ?,
                    classification_method = ?,
                    canonical_state = 'organized',
                    updated_at = datetime('now')
                WHERE file_id = ?
            """, batch)
            conn.commit()
            batch = []

            # Progress update
            pct = (i + 1) / total * 100
            logger.info(f"  Progress: {i+1:,}/{total:,} ({pct:.1f}%)")

    # Execute remaining batch
    if batch:
        cursor.executemany("""
            UPDATE file_registry
            SET document_type = ?,
                confidence = ?,
                classification_method = ?,
                canonical_state = 'organized',
                updated_at = datetime('now')
            WHERE file_id = ?
        """, batch)
        conn.commit()

    conn.close()

    # Print summary
    logger.info("")
    logger.info("=" * 80)
    logger.info("CLASSIFICATION SUMMARY")
    logger.info("=" * 80)
    logger.info(f"  Total classified: {stats['total']:,}")
    logger.info(f"  Pattern-based: {stats['pattern']:,} ({stats['pattern']/stats['total']*100:.1f}%)")
    logger.info(f"  ML-based: {stats['ml']:,} ({stats['ml']/stats['total']*100:.1f}%)")
    logger.info("=" * 80)

    return stats


def main():
    print("=" * 80)
    print("PROCESS FULL INBOX")
    print("=" * 80)
    print()

    inbox_dir = Path(r"C:\Users\kjfle\00_Inbox")
    db_path = Path(".ifmos/file_registry.db")

    if not inbox_dir.exists():
        logger.error(f"Inbox directory not found: {inbox_dir}")
        return

    if not db_path.exists():
        logger.error(f"Database not found: {db_path}")
        return

    # Step 1: Register files
    logger.info("STEP 1: Registering inbox files...")
    logger.info("")

    try:
        reg_stats = register_files_from_drop(inbox_dir, db_path, dry_run=False)

        logger.info("")
        logger.info(f"✓ Registered {reg_stats['registered']:,} new files")
        logger.info(f"✓ Detected {reg_stats['duplicates']:,} duplicates")
        logger.info("")

    except Exception as e:
        logger.error(f"Registration failed: {e}")
        raise

    # Step 2: Classify pending files
    logger.info("STEP 2: Classifying pending files with hybrid system...")
    logger.info("")

    try:
        class_stats = classify_pending_files(db_path)

        logger.info("")
        logger.info("✓ Classification complete")
        logger.info("")

    except Exception as e:
        logger.error(f"Classification failed: {e}")
        raise

    # Step 3: Summary
    print()
    print("=" * 80)
    print("INBOX PROCESSING COMPLETE")
    print("=" * 80)
    print(f"New files registered: {reg_stats['registered']:,}")
    print(f"Duplicates detected: {reg_stats['duplicates']:,}")
    print(f"Files classified: {class_stats['total']:,}")
    print(f"  - Pattern-based: {class_stats['pattern']:,} ({class_stats['pattern']/class_stats['total']*100:.1f}%)")
    print(f"  - ML-based: {class_stats['ml']:,} ({class_stats['ml']/class_stats['total']*100:.1f}%)")
    print()
    print("Next steps:")
    print("  1. Run check_db_status.py to see updated database")
    print("  2. Generate metrics snapshot")
    print("  3. Review classification quality")
    print("=" * 80)


if __name__ == '__main__':
    main()
