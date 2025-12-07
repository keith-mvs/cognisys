#!/usr/bin/env python3
"""
IFMOS Inbox Processing Workflow
Complete workflow: Scan → Classify → Organize
"""

import sys
import logging
import sqlite3
from pathlib import Path
from datetime import datetime
import hashlib

# Add IFMOS to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from cognisys.core.file_organizer import FileOrganizer
from scripts.ml.comprehensive_reclassify import ComprehensiveReclassifier

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class InboxProcessor:
    """Process files from inbox: scan, classify, organize"""

    def __init__(self, inbox_path: str, db_path: str):
        self.inbox_path = Path(inbox_path)
        self.db_path = Path(db_path)
        self.conn = sqlite3.connect(str(self.db_path))
        self.cursor = self.conn.cursor()

    def scan_inbox(self) -> list:
        """
        Scan inbox directory and add files to database

        Returns:
            List of (file_id, file_path) tuples
        """
        logger.info(f"Scanning inbox: {self.inbox_path}")

        # Get all files in inbox
        files = list(self.inbox_path.rglob('*'))
        files = [f for f in files if f.is_file()]

        logger.info(f"Found {len(files)} files in inbox")

        # Add files to database if not already present
        added = []
        skipped = 0

        for file_path in files:
            try:
                # Check if file already in database
                self.cursor.execute(
                    "SELECT id FROM documents WHERE file_path = ?",
                    (str(file_path),)
                )
                existing = self.cursor.fetchone()

                if existing:
                    skipped += 1
                    added.append((existing[0], str(file_path)))
                    continue

                # Get file info
                stat = file_path.stat()
                file_name = file_path.name
                file_ext = file_path.suffix.lower()
                file_size = stat.st_size

                # Insert into database
                self.cursor.execute("""
                    INSERT INTO documents (
                        file_name, file_path, file_type
                    ) VALUES (?, ?, ?)
                """, (
                    file_name,
                    str(file_path),
                    file_ext
                ))

                file_id = self.cursor.lastrowid
                added.append((file_id, str(file_path)))

            except Exception as e:
                logger.error(f"Error scanning {file_path}: {e}")
                continue

        self.conn.commit()

        logger.info(f"Scan complete: {len(added)} files ({len(added) - skipped} new, {skipped} existing)")
        return added

    def classify_files(self, file_ids: list) -> dict:
        """
        Classify files using comprehensive reclassifier

        Args:
            file_ids: List of (file_id, file_path) tuples

        Returns:
            Classification statistics
        """
        logger.info(f"Classifying {len(file_ids)} files...")

        # Use comprehensive reclassifier
        reclassifier = ComprehensiveReclassifier(str(self.db_path))

        classified = 0
        failed = 0

        for file_id, file_path in file_ids:
            try:
                result = reclassifier.reclassify_document(file_id)
                if result['changed']:
                    classified += 1
            except Exception as e:
                logger.error(f"Error classifying {file_path}: {e}")
                failed += 1

        reclassifier.conn.close()

        logger.info(f"Classification complete: {classified} classified, {failed} failed")

        return {
            'total': len(file_ids),
            'classified': classified,
            'failed': failed
        }

    def get_classification_stats(self) -> dict:
        """Get statistics on classified documents"""
        self.cursor.execute("""
            SELECT document_type, COUNT(*) as count
            FROM documents
            WHERE file_path LIKE ?
            AND document_type IS NOT NULL
            GROUP BY document_type
            ORDER BY count DESC
        """, (f"%{self.inbox_path}%",))

        stats = {}
        for row in self.cursor.fetchall():
            stats[row[0]] = row[1]

        return stats

    def organize_files(self, dry_run: bool = False) -> dict:
        """
        Organize classified files into domain folders

        Args:
            dry_run: If True, simulate without moving files

        Returns:
            Organization results
        """
        logger.info("Organizing classified files...")

        # Get documents from inbox that have been classified
        self.cursor.execute("""
            SELECT id
            FROM documents
            WHERE file_path LIKE ?
            AND document_type IS NOT NULL
            AND document_type != 'unknown'
            ORDER BY id
        """, (f"%{self.inbox_path}%",))

        doc_ids = [row[0] for row in self.cursor.fetchall()]

        if not doc_ids:
            logger.warning("No classified documents found in inbox")
            return {'total': 0, 'successful': 0, 'failed': 0}

        logger.info(f"Found {len(doc_ids)} classified documents to organize")

        # Initialize organizer
        config_path = PROJECT_ROOT / "ifmos" / "config" / "domain_mapping.yml"
        organizer = FileOrganizer(str(config_path), str(self.db_path))

        # Organize files
        result = organizer.organize_batch(doc_ids, dry_run=dry_run)

        return result


def main():
    """Main workflow"""
    import argparse

    parser = argparse.ArgumentParser(description='IFMOS Inbox Processing')
    parser.add_argument('--inbox', default='C:\\Users\\kjfle\\00_Inbox',
                       help='Inbox directory path')
    parser.add_argument('--db', default=None,
                       help='Database path (default: ifmos/data/training/ifmos_ml.db)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Simulate organization without moving files')
    parser.add_argument('--classify-only', action='store_true',
                       help='Only scan and classify, do not organize')
    parser.add_argument('--organize-only', action='store_true',
                       help='Only organize already classified files')

    args = parser.parse_args()

    # Set database path
    if args.db is None:
        args.db = PROJECT_ROOT / "ifmos" / "data" / "training" / "ifmos_ml.db"

    logger.info("=" * 80)
    logger.info("IFMOS INBOX PROCESSING WORKFLOW")
    logger.info("=" * 80)
    logger.info(f"Inbox: {args.inbox}")
    logger.info(f"Database: {args.db}")
    logger.info(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    logger.info("=" * 80)

    processor = InboxProcessor(args.inbox, args.db)

    # Step 1: Scan inbox (unless organize-only)
    if not args.organize_only:
        logger.info("\n[STEP 1] SCANNING INBOX")
        logger.info("-" * 80)
        scanned_files = processor.scan_inbox()

        # Step 2: Classify files
        logger.info("\n[STEP 2] CLASSIFYING FILES")
        logger.info("-" * 80)
        classification_result = processor.classify_files(scanned_files)

        # Show classification stats
        logger.info("\n[STEP 2.1] CLASSIFICATION STATISTICS")
        logger.info("-" * 80)
        stats = processor.get_classification_stats()
        for doc_type, count in list(stats.items())[:15]:
            logger.info(f"  {doc_type}: {count}")

    # Step 3: Organize files (unless classify-only)
    if not args.classify_only:
        logger.info("\n[STEP 3] ORGANIZING FILES")
        logger.info("-" * 80)
        org_result = processor.organize_files(dry_run=args.dry_run)

        logger.info("\n" + "=" * 80)
        logger.info("ORGANIZATION RESULTS")
        logger.info("=" * 80)
        logger.info(f"Total Documents: {org_result['total']}")
        logger.info(f"Successfully Organized: {org_result['successful']}")
        logger.info(f"Failed: {org_result['failed']}")

        if org_result['total'] > 0:
            logger.info(f"Success Rate: {org_result['successful']/org_result['total']*100:.1f}%")

        if args.dry_run:
            logger.info("\n[DRY RUN] No files were actually moved")
            logger.info("Run without --dry-run to execute organization")

        # Show sample results
        if org_result.get('results'):
            logger.info("\nSample Organized Files:")
            for i, file_result in enumerate(org_result['results'][:5], 1):
                if file_result['success']:
                    original = Path(file_result['original_path']).name
                    target = file_result['target_path']
                    logger.info(f"  {i}. {original}")
                    logger.info(f"     -> {target}")

    # Close database
    processor.conn.close()

    logger.info("\n" + "=" * 80)
    logger.info("WORKFLOW COMPLETE")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
