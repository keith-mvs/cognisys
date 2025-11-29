#!/usr/bin/env python3
"""
Test Phase 3 Pipeline: Register → Classify → Organize

This script demonstrates the complete IFMOS pipeline:
1. Register files from drop directory
2. Classify pending files (ML + patterns)
3. Organize classified files to canonical locations
"""

import sys
from pathlib import Path
import yaml
import logging

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ifmos.commands import (
    register_files_from_drop,
    classify_pending_files,
    organize_classified_files
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_phase3_pipeline(dry_run=True):
    """
    Run complete Phase 3 pipeline.

    Args:
        dry_run: If True, don't actually modify files/database
    """
    logger.info("="*80)
    logger.info("IFMOS PHASE 3 PIPELINE TEST")
    logger.info("="*80)
    logger.info(f"Mode: {'DRY RUN' if dry_run else 'LIVE EXECUTION'}")
    logger.info("")

    # Load config
    config_path = PROJECT_ROOT / ".ifmos" / "config.yml"
    with open(config_path) as f:
        config = yaml.safe_load(f)

    db_path = PROJECT_ROOT / config['ifmos']['database']
    drop_dir = Path(config['ifmos']['drop_directory'])

    # Step 1: Register files from drop directory
    logger.info("STEP 1: Registering files from drop directory")
    logger.info("-"*80)

    try:
        register_stats = register_files_from_drop(drop_dir, db_path, dry_run=dry_run)
        logger.info(f"Registration complete: {register_stats['registered']} new files")
    except Exception as e:
        logger.error(f"Registration failed: {e}")
        return 1

    # Step 2: Classify pending files
    logger.info("")
    logger.info("STEP 2: Classifying pending files")
    logger.info("-"*80)

    try:
        classify_stats = classify_pending_files(db_path, config, dry_run=dry_run)
        logger.info(f"Classification complete: {classify_stats['classified_ml'] + classify_stats['classified_pattern']} files classified")
    except Exception as e:
        logger.error(f"Classification failed: {e}")
        return 1

    # Step 3: Organize classified files
    logger.info("")
    logger.info("STEP 3: Organizing classified files")
    logger.info("-"*80)

    try:
        organize_stats = organize_classified_files(db_path, config, dry_run=dry_run)
        logger.info(f"Organization complete: {organize_stats['organized']} files moved")
    except Exception as e:
        logger.error(f"Organization failed: {e}")
        return 1

    # Final summary
    logger.info("")
    logger.info("="*80)
    logger.info("PHASE 3 PIPELINE COMPLETE")
    logger.info("="*80)
    logger.info(f"  Files registered: {register_stats['registered']}")
    logger.info(f"  Files classified: {classify_stats['classified_ml'] + classify_stats['classified_pattern']}")
    logger.info(f"  Files organized: {organize_stats['organized']}")
    logger.info(f"  Requires review: {classify_stats['requires_review']}")
    logger.info("")

    if dry_run:
        logger.info("This was a DRY RUN. No files were modified.")
        logger.info("Run with --execute to perform the pipeline.")

    return 0


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Test IFMOS Phase 3 Pipeline')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without modifying files')
    parser.add_argument('--execute', action='store_true', help='Actually perform the pipeline')

    args = parser.parse_args()

    # Default to dry-run if neither specified
    if not args.dry_run and not args.execute:
        args.dry_run = True
        logger.info("No mode specified, defaulting to --dry-run")
        logger.info("")

    dry_run = args.dry_run

    try:
        return test_phase3_pipeline(dry_run=dry_run)
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
