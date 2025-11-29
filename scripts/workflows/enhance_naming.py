#!/usr/bin/env python3
"""
IFMOS File Naming Enhancement
Applies V1-style metadata extraction to V2 structure
Combines: V2 clean structure (no date folders) + V1 intelligent naming (metadata extraction)
"""

import sqlite3
import os
import re
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Tuple
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class FileNamingEnhancer:
    """Enhances filenames with metadata extraction while preserving V2 structure"""

    def __init__(self, db_path: str, organized_root: str):
        self.db_path = db_path
        self.organized_root = organized_root
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()

        # Metadata extraction patterns (from V1 domain_mapping.yml)
        self.extraction_patterns = {
            'dates': [
                r'(\d{4})[_-](\d{2})[_-](\d{2})',  # YYYY-MM-DD or YYYY_MM_DD
                r'(\d{2})[/_-](\d{2})[/_-](\d{4})',  # MM/DD/YYYY
                r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{1,2}),?\s+(\d{4})\b',
                r'(\d{8})',  # YYYYMMDD
            ],
            'invoice_numbers': [
                r'(?:Invoice|INV|invoice)[#\s_-]*:?\s*([A-Z0-9_-]+)',
                r'\b(INV[0-9]+)\b',
                r'#(\d{5,})',
            ],
            'amounts': [
                r'\$([0-9,]+\.?\d{0,2})',
                r'([0-9,]+\.\d{2})',
            ],
            'case_numbers': [
                r'(?:Case|Docket|case)[#\s_-]*:?\s*([A-Z0-9_-]+)',
            ],
            'vendors': [
                r'^(\d{4}-\d{2}-\d{2})_([^_]+?)_',  # Extract vendor from existing pattern
                r'^([A-Z][a-zA-Z\s&]+?)[-_]',  # Company names at start
            ],
        }

    def _extract_date(self, filename: str, content: Optional[str] = None) -> Optional[str]:
        """Extract date and return as YYYY-MM-DD format"""
        for pattern in self.extraction_patterns['dates']:
            match = re.search(pattern, filename)
            if match:
                try:
                    groups = match.groups()
                    if len(groups) == 3:
                        # Check format
                        if len(groups[0]) == 4:  # YYYY-MM-DD
                            return f"{groups[0]}-{groups[1]}-{groups[2]}"
                        elif len(groups[2]) == 4:  # MM-DD-YYYY or Month DD, YYYY
                            if groups[0].isalpha():  # Month name
                                month_map = {'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
                                           'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
                                           'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'}
                                month = month_map.get(groups[0][:3], '01')
                                day = groups[1].zfill(2)
                                return f"{groups[2]}-{month}-{day}"
                            else:  # MM-DD-YYYY
                                return f"{groups[2]}-{groups[0].zfill(2)}-{groups[1].zfill(2)}"
                    elif len(groups) == 1 and len(groups[0]) == 8:  # YYYYMMDD
                        date_str = groups[0]
                        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
                except:
                    continue
        return None

    def _extract_vendor(self, filename: str) -> Optional[str]:
        """Extract vendor/company name"""
        for pattern in self.extraction_patterns['vendors']:
            match = re.search(pattern, filename)
            if match:
                vendor = match.group(2) if match.lastindex >= 2 else match.group(1)
                # Clean up vendor name
                vendor = re.sub(r'[_-]+', ' ', vendor).strip()
                vendor = re.sub(r'\s+', '_', vendor)
                return vendor[:30]  # Limit length
        return None

    def _extract_invoice_number(self, filename: str) -> Optional[str]:
        """Extract invoice number"""
        for pattern in self.extraction_patterns['invoice_numbers']:
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                return match.group(1)[:20]  # Limit length
        return None

    def _extract_case_number(self, filename: str) -> Optional[str]:
        """Extract case/docket number"""
        for pattern in self.extraction_patterns['case_numbers']:
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                return match.group(1)[:20]
        return None

    def _sanitize_component(self, text: str) -> str:
        """Sanitize filename component"""
        if not text:
            return ""
        # Remove special chars but keep underscores, hyphens
        text = re.sub(r'[<>:"/\\|?*]', '', text)
        # Replace multiple spaces/separators with single underscore
        text = re.sub(r'[\s_-]+', '_', text)
        # Remove leading/trailing separators
        text = text.strip('_-')
        return text

    def _generate_enhanced_name(self, filename: str, doc_type: str) -> Optional[str]:
        """
        Generate enhanced filename based on document type
        Returns: (new_basename, metadata_dict) or None if no enhancement needed
        """
        # Get file extension
        name, ext = os.path.splitext(filename)

        # Skip if already has good naming (YYYY-MM-DD prefix)
        if re.match(r'^\d{4}-\d{2}-\d{2}_', filename):
            return None

        # Extract metadata
        date = self._extract_date(filename)
        vendor = self._extract_vendor(filename)
        invoice_num = self._extract_invoice_number(filename)
        case_num = self._extract_case_number(filename)

        # Build enhanced name based on doc type
        components = []

        # Date (if found)
        if date:
            components.append(date)

        # Type-specific components
        if doc_type in ['financial_invoice', 'financial_statement', 'financial_receipt']:
            if vendor:
                components.append(vendor)
            if invoice_num:
                components.append(invoice_num)

        elif doc_type in ['legal_contract', 'legal_court', 'legal_agreement']:
            if case_num:
                components.append(case_num)
            elif vendor:
                components.append(vendor)

        elif doc_type in ['automotive_technical', 'automotive_service']:
            # Extract vehicle info
            vehicle_match = re.search(r'(BMW|Mercedes|Audi|VW|Volkswagen)\s*([A-Z0-9]+)', filename, re.IGNORECASE)
            if vehicle_match:
                components.append(f"{vehicle_match.group(1)}_{vehicle_match.group(2)}")

        elif doc_type in ['personal_career', 'hr_resume']:
            # Extract resume version
            version_match = re.search(r'v(\d+)', filename, re.IGNORECASE)
            if version_match:
                components.append(f"v{version_match.group(1)}")

        # Add sanitized original name (shortened if already has metadata)
        original_clean = self._sanitize_component(name)
        if len(components) > 0:
            # Already has metadata, shorten original
            original_clean = original_clean[:50]
        else:
            # No metadata extracted, keep full original
            original_clean = original_clean[:100]

        components.append(original_clean)

        # Build final filename
        if len(components) > 1:  # Only rename if we extracted something
            new_name = '_'.join(filter(None, components))
            # Remove duplicate components
            parts = new_name.split('_')
            seen = set()
            unique_parts = []
            for part in parts:
                if part.lower() not in seen:
                    unique_parts.append(part)
                    seen.add(part.lower())
            new_name = '_'.join(unique_parts)
            return self._sanitize_component(new_name) + ext
        else:
            return None

    def enhance_all_names(self, dry_run: bool = True) -> Dict:
        """Enhance all filenames in Organized_V2"""

        logger.info("=" * 80)
        logger.info("FILE NAMING ENHANCEMENT")
        logger.info("=" * 80)
        logger.info(f"Mode: {'DRY RUN' if dry_run else 'EXECUTE'}")
        logger.info("")

        # Get all files in Organized_V2
        self.cursor.execute("""
            SELECT id, file_name, file_path, document_type
            FROM documents
            WHERE file_path LIKE '%Organized_V2%'
            ORDER BY document_type, file_name
        """)

        files = self.cursor.fetchall()

        logger.info(f"Total files to process: {len(files)}")
        logger.info("")

        stats = {
            'total': len(files),
            'enhanced': 0,
            'skipped': 0,
            'errors': 0,
            'by_type': {},
        }

        enhancements = []

        for doc_id, filename, old_path, doc_type in files:
            try:
                new_name = self._generate_enhanced_name(filename, doc_type)

                if new_name and new_name != filename:
                    # Generate new path
                    old_path_obj = Path(old_path)
                    new_path = str(old_path_obj.parent / new_name)

                    # Check if target already exists
                    if os.path.exists(new_path) and new_path != old_path:
                        logger.warning(f"Target exists, skipping: {new_name}")
                        stats['skipped'] += 1
                        continue

                    enhancements.append({
                        'id': doc_id,
                        'old_name': filename,
                        'new_name': new_name,
                        'old_path': old_path,
                        'new_path': new_path,
                        'doc_type': doc_type
                    })

                    stats['enhanced'] += 1
                    stats['by_type'][doc_type] = stats['by_type'].get(doc_type, 0) + 1
                else:
                    stats['skipped'] += 1

            except Exception as e:
                logger.error(f"Error processing {filename}: {e}")
                stats['errors'] += 1

        logger.info("ENHANCEMENT SUMMARY:")
        logger.info(f"  Total files: {stats['total']}")
        logger.info(f"  To be enhanced: {stats['enhanced']}")
        logger.info(f"  Skipped (already good): {stats['skipped']}")
        logger.info(f"  Errors: {stats['errors']}")
        logger.info("")

        if stats['by_type']:
            logger.info("ENHANCEMENTS BY TYPE:")
            for doc_type, count in sorted(stats['by_type'].items(), key=lambda x: x[1], reverse=True)[:15]:
                logger.info(f"  {doc_type:30} {count:5} files")
            logger.info("")

        # Show sample
        logger.info("SAMPLE ENHANCEMENTS (first 20):")
        for item in enhancements[:20]:
            logger.info(f"  [{item['doc_type']:25}]")
            logger.info(f"     OLD: {item['old_name'][:60]}")
            logger.info(f"     NEW: {item['new_name'][:60]}")
        if len(enhancements) > 20:
            logger.info(f"  ... and {len(enhancements) - 20} more")
        logger.info("")

        # Execute enhancements
        if not dry_run and stats['enhanced'] > 0:
            logger.info("Applying enhancements...")
            success = 0
            errors = 0

            for item in enhancements:
                try:
                    # Rename file
                    os.rename(item['old_path'], item['new_path'])

                    # Update database
                    self.cursor.execute("""
                        UPDATE documents
                        SET file_name = ?, file_path = ?
                        WHERE id = ?
                    """, (item['new_name'], item['new_path'], item['id']))

                    success += 1

                    if success % 100 == 0:
                        logger.info(f"  Enhanced {success}/{stats['enhanced']} files...")

                except Exception as e:
                    logger.error(f"Error renaming {item['old_name']}: {e}")
                    errors += 1

            self.conn.commit()

            logger.info("")
            logger.info(f"✓ Enhancement complete!")
            logger.info(f"  Success: {success}")
            logger.info(f"  Errors: {errors}")
        else:
            logger.info("[DRY RUN] No files renamed")
            logger.info("Run with --execute to apply enhancements")

        return stats

    def close(self):
        self.conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Enhance file naming with metadata extraction")
    parser.add_argument('--db', type=str, default='ifmos/data/training/ifmos_ml.db')
    parser.add_argument('--root', type=str, default='C:/Users/kjfle/Documents/Organized_V2')
    parser.add_argument('--execute', action='store_true',
                        help='Execute renaming (default is dry-run)')

    args = parser.parse_args()

    enhancer = FileNamingEnhancer(args.db, args.root)
    try:
        stats = enhancer.enhance_all_names(dry_run=not args.execute)
    finally:
        enhancer.close()
