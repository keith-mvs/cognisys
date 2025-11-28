#!/usr/bin/env python3
"""
IFMOS Automated File Organization Workflow
Runs after classification to organize files into domain folders
"""

import sys
import logging
from pathlib import Path

# Add IFMOS to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ifmos.core.file_organizer import FileOrganizer
import sqlite3

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_unorganized_documents(db_path: str) -> list:
    """Get documents that haven't been organized yet"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Documents that are still in inbox/To_Review directories
    cursor.execute("""
        SELECT id, file_path, document_type
        FROM documents
        WHERE document_type IS NOT NULL
        AND (file_path LIKE '%Inbox%' OR file_path LIKE '%To_Review%')
        ORDER BY id DESC
    """)

    docs = cursor.fetchall()
    conn.close()

    return [(row[0], row[1], row[2]) for row in docs]


def organize_workflow(dry_run: bool = False, max_files: int = None):
    """
    Main organization workflow

    Args:
        dry_run: If True, simulate without moving files
        max_files: Maximum number of files to organize (None = all)
    """
    db_path = PROJECT_ROOT / "ifmos" / "data" / "training" / "ifmos_ml.db"
    config_path = PROJECT_ROOT / "ifmos" / "config" / "domain_mapping.yml"

    logger.info("=" * 80)
    logger.info("IFMOS AUTOMATED FILE ORGANIZATION")
    logger.info("=" * 80)

    # Get unorganized documents
    unorganized = get_unorganized_documents(str(db_path))

    logger.info(f"Found {len(unorganized)} unorganized documents")

    if len(unorganized) == 0:
        logger.info("No documents to organize. All files are already organized!")
        return

    # Limit if specified
    if max_files:
        unorganized = unorganized[:max_files]
        logger.info(f"Limited to {max_files} files")

    # Show document type distribution
    type_counts = {}
    for doc_id, path, doc_type in unorganized:
        type_counts[doc_type] = type_counts.get(doc_type, 0) + 1

    logger.info("\nDocument Type Distribution:")
    for doc_type, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
        logger.info(f"  {doc_type}: {count} files")

    # Initialize organizer
    organizer = FileOrganizer(str(config_path), str(db_path))

    # Get document IDs
    doc_ids = [doc_id for doc_id, _, _ in unorganized]

    # Execute organization
    logger.info(f"\n{'[DRY RUN] ' if dry_run else ''}Starting organization...")

    result = organizer.organize_batch(doc_ids, dry_run=dry_run)

    # Display results
    logger.info("\n" + "=" * 80)
    logger.info("ORGANIZATION RESULTS")
    logger.info("=" * 80)
    logger.info(f"Total Documents: {result['total']}")
    logger.info(f"Successfully Organized: {result['successful']}")
    logger.info(f"Failed: {result['failed']}")
    logger.info(f"Success Rate: {result['successful']/result['total']*100:.1f}%")

    if dry_run:
        logger.info("\n[DRY RUN] No files were actually moved")
        logger.info("Run without --dry-run to execute organization")

    # Show sample results
    logger.info("\nSample Organized Files:")
    for i, file_result in enumerate(result['results'][:5], 1):
        if file_result['success']:
            original = Path(file_result['original_path']).name
            target = Path(file_result['target_path']).relative_to(Path(file_result['target_path']).parts[0])
            logger.info(f"  {i}. {original[:40]}")
            logger.info(f"     → {target}")

    if result['failed'] > 0:
        logger.info(f"\nFailed Files:")
        for file_result in result['results']:
            if not file_result['success']:
                logger.error(f"  Doc {file_result['doc_id']}: {file_result.get('error', 'Unknown error')}")


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='IFMOS Automated File Organization')
    parser.add_argument('--dry-run', action='store_true', help='Simulate without moving files')
    parser.add_argument('--max-files', type=int, help='Maximum files to organize')

    args = parser.parse_args()

    organize_workflow(dry_run=args.dry_run, max_files=args.max_files)


if __name__ == "__main__":
    main()
