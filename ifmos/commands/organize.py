"""
IFMOS Organize Command
Moves classified files to their canonical locations based on domain mapping
"""

import sqlite3
import shutil
import re
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def extract_metadata_from_filename(filename, metadata_fields):
    """
    Extract metadata from filename using pattern matching.

    Args:
        filename: Original filename
        metadata_fields: List of fields to extract

    Returns:
        dict of extracted metadata
    """
    metadata = {}

    # Common patterns for metadata extraction
    patterns = {
        'date': r'(\d{4}[-_]\d{2}[-_]\d{2})',
        'YYYY': r'(\d{4})',
        'MM': r'[-_](\d{2})[-_]',
        'DD': r'[-_](\d{2})(?:\D|$)',
        'invoice_number': r'(?:invoice|inv|#)[\s_-]*([A-Z0-9\-]+)',
        'vendor_name': r'^([A-Za-z]+)_',
        'vin': r'\b([A-HJ-NPR-Z0-9]{17})\b',
    }

    filename_lower = filename.lower()

    for field in metadata_fields:
        if field in patterns:
            match = re.search(patterns[field], filename, re.IGNORECASE)
            if match:
                metadata[field] = match.group(1)

    # Extract date components if date found
    if 'date' in metadata:
        date_str = metadata['date'].replace('_', '-')
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            metadata['YYYY'] = str(date_obj.year)
            metadata['MM'] = f"{date_obj.month:02d}"
            metadata['DD'] = f"{date_obj.day:02d}"
            metadata['YYYY-MM-DD'] = date_str
        except ValueError:
            pass

    # Default to current date if not found
    if 'YYYY' not in metadata:
        now = datetime.now()
        metadata['YYYY'] = str(now.year)
        metadata['MM'] = f"{now.month:02d}"
        metadata['DD'] = f"{now.day:02d}"
        metadata['YYYY-MM-DD'] = now.strftime('%Y-%m-%d')

    return metadata


def apply_path_template(template, metadata, defaults, original_filename):
    """
    Apply path template with metadata substitution.

    Args:
        template: Path template string with {placeholders}
        metadata: Extracted metadata dict
        defaults: Default values for missing metadata
        original_filename: Original filename

    Returns:
        Path object
    """
    # Combine metadata with defaults
    values = {**defaults, **metadata}

    # Add original filename without extension and full filename
    path_obj = Path(original_filename)
    values['original'] = path_obj.stem
    values['original_ext'] = path_obj.suffix
    values['original_full'] = path_obj.name

    # Replace placeholders
    path_str = template

    for key, value in values.items():
        placeholder = f"{{{key}}}"
        if placeholder in path_str:
            path_str = path_str.replace(placeholder, str(value))

    return Path(path_str)


def get_domain_for_document_type(document_type, domain_mapping):
    """
    Find which domain a document type belongs to.

    Args:
        document_type: Document type (e.g., 'financial_invoice')
        domain_mapping: Domain mapping from config

    Returns:
        tuple: (domain_name, domain_config) or (None, None)
    """
    for domain_name, domain_config in domain_mapping.items():
        if document_type in domain_config.get('types', []):
            return domain_name, domain_config

    return None, None


def organize_classified_files(db_path, config, dry_run=False):
    """
    Move classified files to their canonical locations.

    Args:
        db_path: Path to SQLite database
        config: Configuration dict
        dry_run: If True, don't actually move files

    Returns:
        dict with statistics
    """
    logger.info("Organizing classified files...")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get classified files
    cursor.execute("""
        SELECT file_id, original_path, document_type, confidence
        FROM file_registry
        WHERE canonical_state = 'classified'
    """)

    classified_files = cursor.fetchall()
    logger.info(f"Found {len(classified_files)} classified files")

    stats = {
        'processed': 0,
        'organized': 0,
        'skipped': 0,
        'errors': 0
    }

    canonical_root = Path(config['ifmos']['canonical_root'])
    domain_mapping = config.get('domain_mapping', {})
    template_defaults = config.get('template_defaults', {})

    for file_id, original_path, document_type, confidence in classified_files:
        stats['processed'] += 1

        try:
            original_path_obj = Path(original_path)

            if not original_path_obj.exists():
                logger.warning(f"File not found: {original_path}")
                stats['errors'] += 1
                continue

            # Find domain for this document type
            domain_name, domain_config = get_domain_for_document_type(
                document_type,
                domain_mapping
            )

            if domain_config is None:
                logger.warning(f"No domain mapping found for {document_type}")
                # Use fallback path
                canonical_path = canonical_root / "General" / original_path_obj.name
            else:
                # Get path template
                path_template = domain_config.get('path_template', '{original}')

                # Extract metadata
                metadata_fields = domain_config.get('metadata_extract', [])
                metadata = extract_metadata_from_filename(
                    original_path_obj.name,
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
                    original_path_obj.name
                )

                canonical_path = canonical_root / relative_path

            # Check if already at canonical location
            if original_path_obj.resolve() == canonical_path.resolve():
                logger.info(f"SKIP (already in place): {original_path_obj.name}")
                stats['skipped'] += 1

                if not dry_run:
                    cursor.execute("""
                        UPDATE file_registry
                        SET canonical_state = 'organized',
                            canonical_path = ?,
                            updated_at = datetime('now')
                        WHERE file_id = ?
                    """, (str(canonical_path), file_id))
                continue

            logger.info(f"ORGANIZE: {original_path_obj.name}")
            logger.info(f"  -> {canonical_path}")

            if not dry_run:
                # Create target directory
                canonical_path.parent.mkdir(parents=True, exist_ok=True)

                # Move file
                try:
                    shutil.move(str(original_path_obj), str(canonical_path))
                except OSError:
                    # Cross-device move - copy then delete
                    shutil.copy2(str(original_path_obj), str(canonical_path))
                    original_path_obj.unlink()

                # Update database
                cursor.execute("""
                    UPDATE file_registry
                    SET canonical_path = ?,
                        canonical_state = 'organized',
                        move_count = move_count + 1,
                        last_moved = datetime('now'),
                        updated_at = datetime('now')
                    WHERE file_id = ?
                """, (str(canonical_path), file_id))

                # Record move in history
                cursor.execute("""
                    INSERT INTO move_history
                    (file_id, from_path, to_path, move_timestamp, reason)
                    VALUES (?, ?, ?, datetime('now'), 'initial_organization')
                """, (file_id, str(original_path_obj), str(canonical_path)))

            stats['organized'] += 1

        except Exception as e:
            logger.error(f"Error organizing {original_path}: {e}")
            stats['errors'] += 1

    if not dry_run:
        conn.commit()

    conn.close()

    # Print summary
    logger.info("")
    logger.info("="*80)
    logger.info("ORGANIZATION SUMMARY")
    logger.info("="*80)
    logger.info(f"  Files processed: {stats['processed']}")
    logger.info(f"  Files organized: {stats['organized']}")
    logger.info(f"  Skipped (already in place): {stats['skipped']}")
    logger.info(f"  Errors: {stats['errors']}")

    if dry_run:
        logger.info("\nDRY RUN - No files were moved")

    return stats
