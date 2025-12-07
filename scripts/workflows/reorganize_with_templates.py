#!/usr/bin/env python3
"""
IFMOS: Reorganize Files with Proper Template Substitution
Fills in {vehicle_id}, {vendor}, etc. from extracted metadata
"""

import sys
import sqlite3
import logging
import re
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from cognisys.ml.utils.content_extractor import ContentExtractor
import yaml

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TemplateSubstitutor:
    """Fills template placeholders with extracted metadata"""

    def __init__(self, db_path: str, config_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()

        # Load domain mapping
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        self.content_extractor = ContentExtractor()

    def fill_template(self, template: str, metadata: Dict, doc_info: Dict) -> str:
        """
        Fill template placeholders with actual values

        Args:
            template: Template string like "{YYYY-MM-DD}_{vendor}_{invoice_id}_{original}"
            metadata: Extracted metadata from document
            doc_info: Document information (filename, date, etc.)

        Returns:
            Filled template string
        """
        result = template

        # Standard date/time placeholders
        file_date = datetime.now()
        if doc_info.get('modified_date'):
            try:
                file_date = datetime.fromisoformat(doc_info['modified_date'])
            except:
                pass

        replacements = {
            'YYYY': str(file_date.year),
            'MM': f"{file_date.month:02d}",
            'DD': f"{file_date.day:02d}",
            'YYYY-MM-DD': file_date.strftime('%Y-%m-%d'),
            'original': Path(doc_info['file_name']).stem
        }

        # Metadata-based placeholders
        if metadata:
            # Vendor/Invoice
            if 'invoice_numbers' in metadata and metadata['invoice_numbers']:
                replacements['invoice_id'] = metadata['invoice_numbers'][0]

            # Vehicle info
            if 'vin' in metadata:
                replacements['vehicle_id'] = metadata['vin'][-8:]  # Last 8 of VIN
                replacements['vehicle'] = metadata['vin'][-8:]

            if 'mileage' in metadata:
                replacements['mileage'] = metadata['mileage'].replace(',', '')

            # Financial
            if 'amounts' in metadata and metadata['amounts']:
                replacements['amount'] = metadata['amounts'][0]

            # Legal
            if 'case_numbers' in metadata and metadata['case_numbers']:
                replacements['case_number'] = metadata['case_numbers'][0]

        # Fill in known values
        for key, value in replacements.items():
            # Handle both {key} and {key_type} patterns
            result = result.replace(f'{{{key}}}', str(value))

        # Remove unfilled placeholders (replace with defaults)
        result = re.sub(r'\{vendor\}', 'VENDOR', result)
        result = re.sub(r'\{service_type\}', 'SERVICE', result)
        result = re.sub(r'\{vehicle\}', 'VEHICLE', result)
        result = re.sub(r'\{project\}', 'PROJECT', result)
        result = re.sub(r'\{product\}', 'PRODUCT', result)
        result = re.sub(r'\{version\}', 'v1.0', result)
        result = re.sub(r'\{[^}]+\}', 'UNKNOWN', result)  # Catch-all

        # Clean up
        result = re.sub(r'_+', '_', result)  # Remove consecutive underscores
        result = re.sub(r'[<>:"/\\|?*]', '_', result)  # Remove invalid chars

        return result

    def reorganize_document(self, doc_id: int, dry_run: bool = False) -> Dict:
        """
        Reorganize a single document with proper template filling

        Args:
            doc_id: Document ID
            dry_run: If True, don't actually move files

        Returns:
            Result dictionary
        """
        # Get document info
        self.cursor.execute("""
            SELECT file_path, file_name, document_type, extracted_text
            FROM documents
            WHERE id = ?
        """, (doc_id,))

        row = self.cursor.fetchone()
        if not row:
            return {'success': False, 'error': 'Document not found'}

        file_path, file_name, doc_type, extracted_text = row

        # Parse metadata from extracted_text (stored as string representation of dict)
        metadata = {}
        if extracted_text:
            try:
                metadata = eval(extracted_text)  # Safe here since we control the data
            except:
                pass

        # Find domain for this document type
        domain = None
        domain_config = None

        for domain_name, domain_data in self.config['domains'].items():
            if doc_type in domain_data.get('types', []):
                domain = domain_name
                domain_config = domain_data
                break

        if not domain_config:
            # Check fallback/general
            if doc_type in self.config.get('general', {}).get('types', []):
                domain_config = self.config['general']
            else:
                domain_config = self.config.get('fallback', {})

        # Build target path
        structure_template = domain_config.get('structure', 'General/{YYYY}/{MM}')
        naming_template = domain_config.get('naming', '{YYYY-MM-DD}_{original}')

        doc_info = {
            'file_name': file_name,
            'modified_date': None  # Would need to get from file system
        }

        # Fill templates
        folder_path = self.fill_template(structure_template, metadata, doc_info)
        new_filename = self.fill_template(naming_template, metadata, doc_info)

        # Add original extension
        extension = Path(file_name).suffix
        if not new_filename.endswith(extension):
            new_filename += extension

        # Build full target path
        repo_root = Path(self.config['repository_root'])
        target_path = repo_root / folder_path / new_filename

        logger.info(f"\n{file_name}")
        logger.info(f"  Type: {doc_type}")
        logger.info(f"  Current: {file_path}")
        logger.info(f"  Target: {target_path}")

        if not dry_run:
            # Create directories
            target_path.parent.mkdir(parents=True, exist_ok=True)

            # Move file
            src_path = Path(file_path)
            if src_path.exists():
                # Handle conflicts
                if target_path.exists():
                    base = target_path.stem
                    ext = target_path.suffix
                    counter = 1
                    while target_path.exists():
                        target_path = target_path.parent / f"{base}_{counter}{ext}"
                        counter += 1

                shutil.move(str(src_path), str(target_path))

                # Update database
                self.cursor.execute("""
                    UPDATE documents
                    SET file_path = ?
                    WHERE id = ?
                """, (str(target_path), doc_id))

                self.conn.commit()

        return {
            'success': True,
            'original': file_path,
            'target': str(target_path),
            'metadata_used': bool(metadata)
        }

    def reorganize_all(self, target_dir: str = None, dry_run: bool = False) -> Dict:
        """
        Reorganize all documents (or documents in a specific directory)

        Args:
            target_dir: Optional directory to limit reorganization to
            dry_run: If True, simulate without moving files

        Returns:
            Statistics dictionary
        """
        # Get documents to reorganize
        if target_dir:
            self.cursor.execute("""
                SELECT id FROM documents
                WHERE file_path LIKE ?
                AND document_type IS NOT NULL
                ORDER BY id
            """, (f"%{target_dir}%",))
        else:
            self.cursor.execute("""
                SELECT id FROM documents
                WHERE document_type IS NOT NULL
                ORDER BY id
            """)

        doc_ids = [row[0] for row in self.cursor.fetchall()]

        logger.info(f"Reorganizing {len(doc_ids)} documents...")
        logger.info(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
        logger.info("-" * 80)

        stats = {
            'total': len(doc_ids),
            'success': 0,
            'failed': 0,
            'metadata_used': 0
        }

        for doc_id in doc_ids:
            try:
                result = self.reorganize_document(doc_id, dry_run=dry_run)

                if result['success']:
                    stats['success'] += 1
                    if result.get('metadata_used'):
                        stats['metadata_used'] += 1
                else:
                    stats['failed'] += 1

            except Exception as e:
                logger.error(f"Error reorganizing doc {doc_id}: {e}")
                stats['failed'] += 1

        return stats

    def close(self):
        self.conn.close()


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--db', default=None)
    parser.add_argument('--config', default=None)
    parser.add_argument('--target-dir', help='Reorganize only files in this directory (e.g., "Organized_V2")')
    parser.add_argument('--dry-run', action='store_true')

    args = parser.parse_args()

    if args.db is None:
        args.db = PROJECT_ROOT / "ifmos" / "data" / "training" / "ifmos_ml.db"

    if args.config is None:
        args.config = PROJECT_ROOT / "ifmos" / "config" / "domain_mapping.yml"

    logger.info("=" * 80)
    logger.info("IFMOS RECURSIVE REORGANIZATION WITH TEMPLATE FILLING")
    logger.info("=" * 80)
    logger.info(f"Database: {args.db}")
    logger.info(f"Config: {args.config}")
    if args.target_dir:
        logger.info(f"Target Directory: {args.target_dir}")
    logger.info("=" * 80)

    substitutor = TemplateSubstitutor(str(args.db), str(args.config))

    try:
        stats = substitutor.reorganize_all(
            target_dir=args.target_dir,
            dry_run=args.dry_run
        )

        logger.info("\n" + "=" * 80)
        logger.info("REORGANIZATION RESULTS")
        logger.info("=" * 80)
        logger.info(f"Total Documents: {stats['total']}")
        logger.info(f"Successfully Reorganized: {stats['success']}")
        logger.info(f"Failed: {stats['failed']}")
        logger.info(f"Used Extracted Metadata: {stats['metadata_used']}")

        if args.dry_run:
            logger.info("\n[DRY RUN] No files were moved")

    finally:
        substitutor.close()


if __name__ == "__main__":
    main()
