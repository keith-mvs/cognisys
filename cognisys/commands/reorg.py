"""
CogniSys Reorg Command
Idempotent reorganization - refines canonical tree structure in-place

This command reorganizes files already in the canonical tree based on:
- Updated classification rules
- Improved path templates
- Manual corrections

Key property: Running multiple times converges to stable state (idempotent)
"""

import sqlite3
import shutil
from pathlib import Path
from datetime import datetime
import logging

# Import organize logic
import sys
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from cognisys.commands.organize import (
    get_domain_for_document_type,
    extract_metadata_from_filename,
    apply_path_template
)

logger = logging.getLogger(__name__)


def reclassify_organized_files(db_path, config, reclassify_all=False):
    """
    Re-run classification on organized files.

    Args:
        db_path: Path to SQLite database
        config: Configuration dict
        reclassify_all: If True, reclassify all files; if False, only low-confidence ones

    Returns:
        dict with statistics
    """
    from cognisys.commands.classify import (
        load_ml_model,
        classify_with_ml,
        classify_with_patterns
    )

    logger.info("Reclassifying organized files...")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Load ML model
    model, vectorizer, label_mappings = load_ml_model(
        config['cognisys']['ml_model_path'],
        config['cognisys']['tfidf_vectorizer_path'],
        config['cognisys']['label_mappings_path']
    )

    # Load classification rules
    cursor.execute("""
        SELECT rule_name, rule_pattern, target_document_type, priority
        FROM classification_rules
        WHERE active = 1 AND rule_type = 'pattern'
        ORDER BY priority DESC
    """)
    classification_rules = cursor.fetchall()

    # Get organized files
    if reclassify_all:
        cursor.execute("""
            SELECT file_id, canonical_path, document_type, confidence
            FROM file_registry
            WHERE canonical_state = 'organized'
        """)
    else:
        # Only reclassify low-confidence or fallback classifications
        threshold = config['cognisys'].get('confidence_threshold', 0.70)
        cursor.execute("""
            SELECT file_id, canonical_path, document_type, confidence
            FROM file_registry
            WHERE canonical_state = 'organized'
            AND (confidence < ? OR classification_method IN ('fallback', 'pattern'))
        """, (threshold,))

    organized_files = cursor.fetchall()
    logger.info(f"Found {len(organized_files)} files to reclassify")

    stats = {
        'processed': 0,
        'reclassified': 0,
        'unchanged': 0
    }

    confidence_threshold = config['cognisys'].get('confidence_threshold', 0.70)

    for file_id, canonical_path, old_type, old_confidence in organized_files:
        stats['processed'] += 1

        # Try ML classification
        new_type, new_confidence, method = classify_with_ml(
            canonical_path,
            model,
            vectorizer,
            label_mappings,
            confidence_threshold
        )

        # Fallback to pattern matching
        if new_type is None:
            new_type, new_confidence, method, rule_name = classify_with_patterns(
                canonical_path,
                classification_rules
            )

        # Check if classification changed
        if new_type and new_type != old_type:
            logger.info(f"Reclassified: {Path(canonical_path).name}")
            logger.info(f"  {old_type} ({old_confidence:.2f}) -> {new_type} ({new_confidence:.2f})")

            cursor.execute("""
                UPDATE file_registry
                SET document_type = ?,
                    confidence = ?,
                    classification_method = ?,
                    updated_at = datetime('now')
                WHERE file_id = ?
            """, (new_type, new_confidence, method, file_id))

            stats['reclassified'] += 1
        else:
            stats['unchanged'] += 1

    conn.commit()
    conn.close()

    logger.info(f"Reclassification complete: {stats['reclassified']} changed, {stats['unchanged']} unchanged")

    return stats


def reorganize_canonical_tree(db_path, config, dry_run=False):
    """
    Idempotent reorganization of canonical tree.

    Process:
    1. Reclassify organized files (if needed)
    2. Recompute target paths based on current templates
    3. Move files if target path changed
    4. Converges to stable state (idempotent)

    Args:
        db_path: Path to SQLite database
        config: Configuration dict
        dry_run: If True, don't actually move files

    Returns:
        dict with statistics
    """
    logger.info("="*80)
    logger.info("IDEMPOTENT REORGANIZATION")
    logger.info("="*80)
    logger.info(f"Mode: {'DRY RUN' if dry_run else 'LIVE EXECUTION'}")
    logger.info("")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Step 1: Reclassify files (only low-confidence ones)
    logger.info("Step 1: Reclassifying low-confidence files...")
    reclassify_stats = reclassify_organized_files(db_path, config, reclassify_all=False)

    # Step 2: Recompute paths and move if needed
    logger.info("")
    logger.info("Step 2: Recomputing paths and moving files...")

    cursor.execute("""
        SELECT file_id, canonical_path, document_type
        FROM file_registry
        WHERE canonical_state = 'organized'
    """)

    organized_files = cursor.fetchall()

    stats = {
        'scanned': len(organized_files),
        'reclassified': reclassify_stats['reclassified'],
        'moved': 0,
        'unchanged': 0,
        'errors': 0
    }

    canonical_root = Path(config['cognisys']['canonical_root'])
    domain_mapping = config.get('domain_mapping', {})
    template_defaults = config.get('template_defaults', {})

    for file_id, canonical_path, document_type in organized_files:
        try:
            current_path = Path(canonical_path)

            if not current_path.exists():
                logger.warning(f"File not found: {canonical_path}")
                stats['errors'] += 1
                continue

            # Compute new target path
            domain_name, domain_config = get_domain_for_document_type(
                document_type,
                domain_mapping
            )

            if domain_config is None:
                # No template, keep current location
                stats['unchanged'] += 1
                continue

            # Get path template
            path_template = domain_config.get('path_template', '{original}')

            # Extract metadata
            metadata_fields = domain_config.get('metadata_extract', [])
            metadata = extract_metadata_from_filename(
                current_path.name,
                metadata_fields
            )

            # Add document subtype
            doc_parts = document_type.split('_')
            if len(doc_parts) > 1:
                metadata['doc_subtype'] = '_'.join(doc_parts[1:]).title().replace('_', ' ')
            else:
                metadata['doc_subtype'] = document_type.title()

            # Apply template
            relative_path = apply_path_template(
                path_template,
                metadata,
                template_defaults,
                current_path.name
            )

            new_path = canonical_root / relative_path

            # Check if path changed
            if current_path.resolve() == new_path.resolve():
                stats['unchanged'] += 1
                continue

            # Path changed - move file
            logger.info(f"MOVE: {current_path.name}")
            logger.info(f"  From: {current_path.relative_to(canonical_root)}")
            logger.info(f"  To:   {new_path.relative_to(canonical_root)}")

            if not dry_run:
                # Create target directory
                new_path.parent.mkdir(parents=True, exist_ok=True)

                # Move file
                try:
                    shutil.move(str(current_path), str(new_path))
                except OSError:
                    # Cross-device move
                    shutil.copy2(str(current_path), str(new_path))
                    current_path.unlink()

                # Update database
                cursor.execute("""
                    UPDATE file_registry
                    SET canonical_path = ?,
                        move_count = move_count + 1,
                        last_moved = datetime('now'),
                        updated_at = datetime('now')
                    WHERE file_id = ?
                """, (str(new_path), file_id))

                # Record move in history
                cursor.execute("""
                    INSERT INTO move_history
                    (file_id, from_path, to_path, move_timestamp, reason)
                    VALUES (?, ?, ?, datetime('now'), 'idempotent_reorg')
                """, (file_id, str(current_path), str(new_path)))

            stats['moved'] += 1

        except Exception as e:
            logger.error(f"Error reorganizing {canonical_path}: {e}")
            stats['errors'] += 1

    if not dry_run:
        conn.commit()

    conn.close()

    # Print summary
    logger.info("")
    logger.info("="*80)
    logger.info("REORGANIZATION SUMMARY")
    logger.info("="*80)
    logger.info(f"  Files scanned: {stats['scanned']}")
    logger.info(f"  Files reclassified: {stats['reclassified']}")
    logger.info(f"  Files moved: {stats['moved']}")
    logger.info(f"  Unchanged: {stats['unchanged']}")
    logger.info(f"  Errors: {stats['errors']}")
    logger.info("")

    if dry_run:
        logger.info("This was a DRY RUN. No files were moved.")
    else:
        logger.info("Reorganization complete!")
        logger.info("")
        logger.info("Note: Running reorg again should show 0 moves (idempotent)")

    return stats
