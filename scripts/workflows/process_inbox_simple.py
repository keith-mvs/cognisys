#!/usr/bin/env python3
"""
CogniSys Simple Inbox Processing
Scan inbox → Classify → Organize
"""

import sys
import logging
import sqlite3
from pathlib import Path
from datetime import datetime

# Add CogniSys to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from cognisys.core.file_organizer import FileOrganizer
from scripts.ml.comprehensive_reclassify import ComprehensiveReclassifier

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def scan_inbox(inbox_path: str, db_path: str) -> int:
    """Scan inbox and add files to database"""
    inbox = Path(inbox_path)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    files = list(inbox.rglob('*'))
    files = [f for f in files if f.is_file()]

    logger.info(f"Found {len(files)} files in inbox")

    added = 0
    for file_path in files:
        try:
            # Check if already exists
            cursor.execute(
                "SELECT id FROM documents WHERE file_path = ?",
                (str(file_path),)
            )
            if cursor.fetchone():
                continue

            # Add to database
            cursor.execute("""
                INSERT INTO documents (file_name, file_path, file_type)
                VALUES (?, ?, ?)
            """, (
                file_path.name,
                str(file_path),
                file_path.suffix.lower()
            ))
            added += 1

        except Exception as e:
            logger.error(f"Error scanning {file_path.name}: {e}")

    conn.commit()
    conn.close()

    logger.info(f"Added {added} new files to database")
    return added


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--inbox', default='C:\\Users\\kjfle\\00_Inbox')
    parser.add_argument('--db', default=None)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--classify-only', action='store_true')

    args = parser.parse_args()

    if args.db is None:
        args.db = PROJECT_ROOT / "cognisys" / "data" / "training" / "cognisys_ml.db"

    logger.info("=" * 80)
    logger.info("COGNISYS INBOX PROCESSING")
    logger.info("=" * 80)
    logger.info(f"Inbox: {args.inbox}")
    logger.info(f"Database: {args.db}")
    logger.info("=" * 80)

    # Step 1: Scan
    logger.info("\n[STEP 1] SCANNING INBOX")
    logger.info("-" * 80)
    added = scan_inbox(args.inbox, str(args.db))

    # Step 2: Classify
    logger.info("\n[STEP 2] CLASSIFYING FILES")
    logger.info("-" * 80)
    reclassifier = ComprehensiveReclassifier(str(args.db))
    try:
        stats, reclassifications = reclassifier.reclassify_all(dry_run=args.dry_run)
    finally:
        reclassifier.close()

    if args.classify_only:
        logger.info("\n[CLASSIFY-ONLY MODE] Skipping organization")
        return

    # Step 3: Organize
    logger.info("\n[STEP 3] ORGANIZING FILES")
    logger.info("-" * 80)

    conn = sqlite3.connect(str(args.db))
    cursor = conn.cursor()

    # Get classified documents from inbox
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

    if not doc_ids:
        logger.warning("No classified documents to organize")
        return

    logger.info(f"Found {len(doc_ids)} classified documents")

    # Organize
    config_path = PROJECT_ROOT / "cognisys" / "config" / "domain_mapping.yml"
    organizer = FileOrganizer(str(config_path), str(args.db))
    result = organizer.organize_batch(doc_ids, dry_run=args.dry_run)

    logger.info("\n" + "=" * 80)
    logger.info("RESULTS")
    logger.info("=" * 80)
    logger.info(f"Total: {result['total']}")
    logger.info(f"Organized: {result['successful']}")
    logger.info(f"Failed: {result['failed']}")

    if args.dry_run:
        logger.info("\n[DRY RUN] No files moved")

    logger.info("\n" + "=" * 80)
    logger.info("COMPLETE")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
