#!/usr/bin/env python3
"""
IFMOS: Classify and Organize Inbox Files
Complete workflow for unclassified files
"""

import sys
import sqlite3
import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.ml.comprehensive_reclassify import ComprehensiveReclassifier
from cognisys.core.file_organizer import FileOrganizer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def classify_unclassified_files(db_path: str, dry_run: bool = False) -> int:
    """
    Classify files that don't have a document_type yet
    Uses pattern matching from ComprehensiveReclassifier
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get unclassified files
    cursor.execute("""
        SELECT id, file_name
        FROM documents
        WHERE document_type IS NULL
        ORDER BY id
    """)

    unclassified = cursor.fetchall()
    logger.info(f"Found {len(unclassified)} unclassified files")

    if not unclassified:
        return 0

    # Use the comprehensive reclassifier's pattern matching
    reclassifier = ComprehensiveReclassifier(db_path)
    classified = 0

    for doc_id, filename in unclassified:
        result = reclassifier.analyze_filename(filename)

        if result:
            new_type, confidence, reason = result

            if not dry_run:
                cursor.execute("""
                    UPDATE documents
                    SET document_type = ?, confidence = ?
                    WHERE id = ?
                """, (new_type, confidence, doc_id))

            classified += 1

        else:
            # Give it a generic classification
            if not dry_run:
                cursor.execute("""
                    UPDATE documents
                    SET document_type = 'general_document', confidence = 0.50
                    WHERE id = ?
                """, (doc_id,))

    if not dry_run:
        conn.commit()

    reclassifier.close()
    conn.close()

    logger.info(f"Classified {classified} files")
    return classified


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--inbox', default='C:\\Users\\kjfle\\00_Inbox')
    parser.add_argument('--db', default=None)
    parser.add_argument('--dry-run', action='store_true')

    args = parser.parse_args()

    if args.db is None:
        args.db = PROJECT_ROOT / "ifmos" / "data" / "training" / "ifmos_ml.db"

    logger.info("=" * 80)
    logger.info("IFMOS CLASSIFY AND ORGANIZE INBOX")
    logger.info("=" * 80)
    logger.info(f"Database: {args.db}")
    logger.info(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    logger.info("=" * 80)

    # Step 1: Classify unclassified files
    logger.info("\n[STEP 1] CLASSIFYING UNCLASSIFIED FILES")
    logger.info("-" * 80)
    classified = classify_unclassified_files(str(args.db), args.dry_run)

    # Step 2: Run comprehensive reclassifier on all files
    logger.info("\n[STEP 2] IMPROVING CLASSIFICATIONS")
    logger.info("-" * 80)
    reclassifier = ComprehensiveReclassifier(str(args.db))
    try:
        stats, reclassifications = reclassifier.reclassify_all(dry_run=args.dry_run)
    finally:
        reclassifier.close()

    # Step 3: Organize inbox files
    logger.info("\n[STEP 3] ORGANIZING INBOX FILES")
    logger.info("-" * 80)

    conn = sqlite3.connect(str(args.db))
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, document_type, COUNT(*) as count
        FROM documents
        WHERE file_path LIKE ?
        AND document_type IS NOT NULL
        GROUP BY document_type
        ORDER BY count DESC
    """, (f"%{args.inbox}%",))

    logger.info("Classification breakdown:")
    total_docs = 0
    for row in cursor.fetchall():
        logger.info(f"  {row[1]:30} {row[2]:5} files")
        total_docs += row[2]

    cursor.execute("""
        SELECT id
        FROM documents
        WHERE file_path LIKE ?
        AND document_type IS NOT NULL
        AND document_type != 'unknown'
        ORDER BY id
    """, (f"%{args.inbox}%",))

    doc_ids = [row[0] for row in cursor.fetchall()]
    conn.close()

    logger.info(f"\nOrganizing {len(doc_ids)} files...")

    if doc_ids:
        config_path = PROJECT_ROOT / "ifmos" / "config" / "domain_mapping.yml"
        organizer = FileOrganizer(str(config_path), str(args.db))
        result = organizer.organize_batch(doc_ids, dry_run=args.dry_run)

        logger.info("\n" + "=" * 80)
        logger.info("ORGANIZATION RESULTS")
        logger.info("=" * 80)
        logger.info(f"Total: {result['total']}")
        logger.info(f"Organized: {result['successful']}")
        logger.info(f"Failed: {result['failed']}")

        if result['total'] > 0:
            logger.info(f"Success Rate: {result['successful']/result['total']*100:.1f}%")

        if args.dry_run:
            logger.info("\n[DRY RUN] No files moved")

    logger.info("\n" + "=" * 80)
    logger.info("WORKFLOW COMPLETE")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
