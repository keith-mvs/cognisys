"""
CogniSys File Organizer
Automatically organizes classified documents based on domain mapping
"""

import logging
import shutil
import re
import yaml
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Tuple
import sqlite3
import json

logger = logging.getLogger(__name__)


class FileOrganizer:
    """Organizes classified files into domain-based folder structures"""

    def __init__(self, config_path: str, db_path: str):
        """
        Initialize file organizer

        Args:
            config_path: Path to domain_mapping.yml
            db_path: Path to CogniSys database
        """
        self.config_path = Path(config_path)
        self.db_path = Path(db_path)
        self.config = self._load_config()
        self.repository_root = Path(self.config['repository_root'])

        # Create repository root if needed
        self.repository_root.mkdir(parents=True, exist_ok=True)

    def _load_config(self) -> Dict:
        """Load domain mapping configuration"""
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)

    def organize_document(self, doc_id: int, dry_run: bool = False) -> Dict:
        """
        Organize a single classified document

        Args:
            doc_id: Document ID from database
            dry_run: If True, don't actually move files

        Returns:
            {
                'success': bool,
                'doc_id': int,
                'original_path': str,
                'target_path': str,
                'action': str,
                'message': str
            }
        """
        try:
            # Get document info from database
            doc_info = self._get_document_info(doc_id)

            if not doc_info:
                return self._error_result(doc_id, f"Document {doc_id} not found in database")

            # Determine target location
            target_result = self._determine_target_path(doc_info)

            if not target_result['success']:
                return target_result

            target_path = Path(target_result['target_path'])
            original_path = Path(doc_info['file_path'])

            # Check if file exists
            if not original_path.exists():
                return self._error_result(doc_id, f"Source file not found: {original_path}")

            # Handle conflict if target exists
            if target_path.exists() and target_path != original_path:
                target_path = self._resolve_conflict(target_path)

            # Perform move operation
            if not dry_run:
                move_result = self._move_file(original_path, target_path, doc_info)

                if not move_result['success']:
                    return move_result

                # Update database with new path
                self._update_database_path(doc_id, target_path)

            return {
                'success': True,
                'doc_id': doc_id,
                'original_path': str(original_path),
                'target_path': str(target_path),
                'action': 'moved' if not dry_run else 'dry_run',
                'message': 'File organized successfully'
            }

        except Exception as e:
            logger.error(f"Failed to organize document {doc_id}: {e}")
            return self._error_result(doc_id, str(e))

    def _get_document_info(self, doc_id: int) -> Optional[Dict]:
        """Get document information from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, file_path, file_name, document_type, extracted_text,
                   processing_timestamp, confidence
            FROM documents
            WHERE id = ?
        """, (doc_id,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return {
            'id': row[0],
            'file_path': row[1],
            'file_name': row[2],
            'document_type': row[3],
            'extracted_text': row[4],
            'processing_timestamp': row[5],
            'confidence': row[6]
        }

    def _determine_target_path(self, doc_info: Dict) -> Dict:
        """Determine target file path based on classification"""
        doc_type = doc_info['document_type']

        # Find domain for this document type
        domain = self._find_domain(doc_type)

        if not domain:
            # Use fallback structure
            structure = self.config['fallback']['structure']
            naming = self.config['fallback']['naming']
        elif domain == 'general':
            # Handle general domain (top-level config key)
            structure = self.config['general']['structure']
            naming = self.config['general']['naming']
        else:
            structure = self.config['domains'][domain]['structure']
            naming = self.config['domains'][domain]['naming']

        # Extract metadata for path/name variables
        metadata = self._extract_metadata(doc_info, domain)

        # Replace variables in structure
        target_dir = self._replace_variables(structure, metadata, doc_info)

        # Generate target filename
        target_filename = self._generate_filename(naming, metadata, doc_info)

        # Build full target path
        target_path = self.repository_root / target_dir / target_filename

        return {
            'success': True,
            'target_path': str(target_path),
            'domain': domain,
            'metadata': metadata
        }

    def _find_domain(self, doc_type: str) -> Optional[str]:
        """Find which domain a document type belongs to"""
        for domain_name, domain_config in self.config['domains'].items():
            if doc_type in domain_config.get('types', []):
                return domain_name

        # Check general domain
        if doc_type in self.config.get('general', {}).get('types', []):
            return 'general'

        return None

    def _extract_metadata(self, doc_info: Dict, domain: Optional[str]) -> Dict:
        """Extract metadata from document for naming/path variables"""
        metadata = {
            'original': Path(doc_info['file_name']).stem,
            'ext': Path(doc_info['file_name']).suffix[1:],  # Remove dot
            'doc_type': doc_info['document_type'],
            'file_type': Path(doc_info['file_name']).suffix[1:]  # For fallback structure
        }

        # Extract date from processing timestamp
        if doc_info['processing_timestamp']:
            dt = datetime.fromisoformat(doc_info['processing_timestamp'])
            metadata.update({
                'YYYY': dt.strftime('%Y'),
                'MM': dt.strftime('%m'),
                'DD': dt.strftime('%d'),
                'YYYY-MM-DD': dt.strftime('%Y-%m-%d'),
                'YYYY-MM': dt.strftime('%Y-%m')
            })
        else:
            now = datetime.now()
            metadata.update({
                'YYYY': now.strftime('%Y'),
                'MM': now.strftime('%m'),
                'DD': now.strftime('%d'),
                'YYYY-MM-DD': now.strftime('%Y-%m-%d'),
                'YYYY-MM': now.strftime('%Y-%m')
            })

        # Extract domain-specific metadata if configured
        if domain and domain in self.config['domains']:
            domain_config = self.config['domains'][domain]
            if 'metadata_extract' in domain_config:
                extracted = self._extract_domain_metadata(
                    doc_info['extracted_text'],
                    domain_config['metadata_extract']
                )
                metadata.update(extracted)

        return metadata

    def _extract_domain_metadata(self, text: str, fields: list) -> Dict:
        """Extract domain-specific metadata using regex patterns"""
        if not text:
            return {}

        metadata = {}
        patterns = self.config.get('extraction_patterns', {})

        for field in fields:
            # Try to extract using configured patterns
            if field == 'date' and 'dates' in patterns:
                for pattern in patterns['dates']:
                    match = re.search(pattern, text)
                    if match:
                        metadata['date'] = match.group(0)
                        break

            elif field == 'invoice_number' and 'invoice_numbers' in patterns:
                for pattern in patterns['invoice_numbers']:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        metadata['invoice_id'] = match.group(1)
                        break

            elif field == 'amount' and 'amounts' in patterns:
                for pattern in patterns['amounts']:
                    match = re.search(pattern, text)
                    if match:
                        metadata['amount'] = match.group(1)
                        break

            elif field == 'case_number' and 'case_numbers' in patterns:
                for pattern in patterns['case_numbers']:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        metadata['case_num'] = match.group(1)
                        break

        return metadata

    def _replace_variables(self, template: str, metadata: Dict, doc_info: Dict) -> str:
        """Replace variables in path/filename templates"""
        result = template

        # Replace all metadata variables
        for key, value in metadata.items():
            result = result.replace(f"{{{key}}}", self._sanitize_path_component(str(value)))

        # Replace doc_type if present
        result = result.replace("{doc_type}", self._sanitize_path_component(doc_info['document_type']))

        return result

    def _generate_filename(self, naming_template: str, metadata: Dict, doc_info: Dict) -> str:
        """Generate target filename from template"""
        filename = self._replace_variables(naming_template, metadata, doc_info)

        # Add extension if not present
        if not filename.endswith(f".{metadata['ext']}"):
            filename += f".{metadata['ext']}"

        # Sanitize filename
        filename = self._sanitize_filename(filename)

        # Apply naming rules
        rules = self.config['naming_rules']

        if rules.get('lowercase', False):
            filename = filename.lower()

        # Enforce max length
        max_len = rules.get('max_length', 200)
        if len(filename) > max_len:
            name, ext = filename.rsplit('.', 1)
            filename = name[:max_len - len(ext) - 1] + '.' + ext

        return filename

    def _sanitize_path_component(self, component: str) -> str:
        """Sanitize a path component (folder name)"""
        # Remove/replace invalid characters
        sanitized = re.sub(r'[<>:"|?*]', '_', component)
        sanitized = re.sub(r'[\\/]', '-', sanitized)
        return sanitized.strip()

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize a filename"""
        # Remove invalid characters
        sanitized = re.sub(r'[<>:"|?*\\\/]', '_', filename)

        # Remove control characters
        sanitized = ''.join(char for char in sanitized if ord(char) >= 32)

        # Remove consecutive underscores/spaces
        sanitized = re.sub(r'[_\s]+', '_', sanitized)

        return sanitized.strip('_. ')

    def _resolve_conflict(self, target_path: Path) -> Path:
        """Resolve file naming conflict"""
        mode = self.config['operations']['conflict_resolution']

        if mode == 'skip':
            return target_path

        elif mode == 'rename':
            # Add counter to filename
            counter = 1
            stem = target_path.stem
            ext = target_path.suffix

            while target_path.exists():
                new_stem = f"{stem}_{counter}"
                target_path = target_path.with_name(f"{new_stem}{ext}")
                counter += 1

            return target_path

        elif mode == 'overwrite':
            return target_path

        else:  # ask
            # For now, default to rename
            return self._resolve_conflict(target_path)

    def _move_file(self, source: Path, target: Path, doc_info: Dict) -> Dict:
        """Move file with backup and error handling"""
        try:
            # Create target directory
            target.parent.mkdir(parents=True, exist_ok=True)

            # Backup if configured
            if self.config['operations']['backup_before_move']:
                self._create_backup(source, doc_info)

            # Perform move
            mode = self.config['operations']['mode']

            if mode == 'move':
                shutil.move(str(source), str(target))
            elif mode == 'copy':
                shutil.copy2(str(source), str(target))
            elif mode == 'symlink':
                target.symlink_to(source)
            else:
                raise ValueError(f"Unknown operation mode: {mode}")

            logger.info(f"Successfully {mode}d file: {source} -> {target}")

            return {
                'success': True,
                'action': mode,
                'source': str(source),
                'target': str(target)
            }

        except Exception as e:
            logger.error(f"Failed to move file {source}: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _create_backup(self, file_path: Path, doc_info: Dict):
        """Create backup before moving file"""
        backup_root = Path(self.config['operations']['backup_location'])
        backup_root.mkdir(parents=True, exist_ok=True)

        # Create timestamped backup
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = backup_root / f"{timestamp}_{file_path.name}"

        shutil.copy2(str(file_path), str(backup_path))
        logger.info(f"Created backup: {backup_path}")

    def _update_database_path(self, doc_id: int, new_path: Path):
        """Update file_path in database after move"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE documents
            SET file_path = ?
            WHERE id = ?
        """, (str(new_path), doc_id))

        conn.commit()
        conn.close()

        logger.info(f"Updated database path for document {doc_id}")

    def _error_result(self, doc_id: int, error_msg: str) -> Dict:
        """Generate error result"""
        return {
            'success': False,
            'doc_id': doc_id,
            'error': error_msg
        }

    def organize_batch(self, doc_ids: list, dry_run: bool = False) -> Dict:
        """
        Organize multiple documents

        Args:
            doc_ids: List of document IDs
            dry_run: If True, simulate without moving files

        Returns:
            {
                'total': int,
                'successful': int,
                'failed': int,
                'results': List[Dict]
            }
        """
        results = []
        successful = 0
        failed = 0

        for doc_id in doc_ids:
            result = self.organize_document(doc_id, dry_run=dry_run)
            results.append(result)

            if result['success']:
                successful += 1
            else:
                failed += 1

        return {
            'total': len(doc_ids),
            'successful': successful,
            'failed': failed,
            'results': results
        }


def main():
    """CLI entry point"""
    import sys
    import argparse

    parser = argparse.ArgumentParser(description='CogniSys File Organizer')
    parser.add_argument('--config', default='cognisys/config/domain_mapping.yml')
    parser.add_argument('--db', default='cognisys/data/training/cognisys_ml.db')
    parser.add_argument('--doc-id', type=int, help='Organize specific document')
    parser.add_argument('--batch', action='store_true', help='Organize all classified documents')
    parser.add_argument('--dry-run', action='store_true', help='Simulate without moving files')

    args = parser.parse_args()

    organizer = FileOrganizer(args.config, args.db)

    if args.doc_id:
        # Organize single document
        result = organizer.organize_document(args.doc_id, dry_run=args.dry_run)
        print(json.dumps(result, indent=2))

    elif args.batch:
        # Get all documents
        conn = sqlite3.connect(args.db)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM documents WHERE document_type IS NOT NULL")
        doc_ids = [row[0] for row in cursor.fetchall()]
        conn.close()

        print(f"Organizing {len(doc_ids)} documents...")
        result = organizer.organize_batch(doc_ids, dry_run=args.dry_run)

        print(f"\nResults:")
        print(f"  Total: {result['total']}")
        print(f"  Successful: {result['successful']}")
        print(f"  Failed: {result['failed']}")

        if args.dry_run:
            print("\n[DRY RUN] No files were actually moved")


if __name__ == "__main__":
    main()
