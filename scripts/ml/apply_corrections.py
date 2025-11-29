#!/usr/bin/env python3
"""
IFMOS Corrections Application Script
Applies manual corrections from CSV review and collects training data
"""

import sqlite3
import csv
import os
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# Domain → Function mapping (from reorganize_function_form.py)
DOMAIN_FUNCTION_MAP = {
    'automotive_technical': ('Automotive', 'Technical_Manuals'),
    'automotive_service': ('Automotive', 'Service_Records'),
    'personal_career': ('Personal', 'Career'),
    'personal_journal': ('Personal', 'Journals'),
    'personal_essay': ('Personal', 'Essays'),
    'personal_career_tool': ('Personal', 'Career_Tools'),
    'personal_finance_tool': ('Personal', 'Finance_Tools'),
    'financial_invoice': ('Financial', 'Invoices'),
    'financial_statement': ('Financial', 'Statements'),
    'financial_receipt': ('Financial', 'Receipts'),
    'legal_contract': ('Legal', 'Contracts'),
    'legal_court': ('Legal', 'Court_Documents'),
    'legal_agreement': ('Legal', 'Agreements'),
    'tax_document': ('Tax', 'Documents'),
    'tax_form': ('Tax', 'Forms'),
    'tax_return': ('Tax', 'Returns'),
    'medical': ('Medical', 'Records'),
    'medical_bill': ('Medical', 'Bills'),
    'medical_record': ('Medical', 'Records'),
    'hr_resume': ('HR', 'Job_Applicant_Resumes'),
    'hr_application': ('HR', 'Applications'),
    'hr_benefits': ('HR', 'Benefits'),
    'hr_job_listing': ('HR', 'Job_Listings'),
    'technical_documentation': ('Technical', 'Documentation'),
    'technical_manual': ('Technical', 'Manuals'),
    'technical_config': ('Technical', 'Configuration'),
    'technical_research': ('Technical', 'Research'),
    'technical_code': ('Technical', 'Code'),
    'communication_email': ('Communications', 'Emails'),
    'communication_letter': ('Communications', 'Letters'),
    'business_proposal': ('Business', 'Proposals'),
    'business_marketing': ('Business', 'Marketing'),
    'realestate_listing': ('Business', 'Real_Estate_Listings'),
    'realestate_contract': ('Business', 'Real_Estate_Contracts'),
    'screenshot': ('Miscellaneous', 'Screenshots'),
    'report': ('Reports', 'General'),
    'form': ('Forms', 'General'),
    'general_document': ('General', 'Documents'),
    'general_document_short': ('General', 'Documents'),
    'unknown': ('Review_Required', 'Unclassified'),
}


class CorrectionsApplicator:
    """Applies manual corrections and collects training data"""

    def __init__(self, db_path: str, organized_root: str):
        self.db_path = db_path
        self.organized_root = organized_root
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()

    def apply_corrections(self, csv_path: str, dry_run: bool = True) -> Dict:
        """Apply corrections from CSV file"""

        logger.info("=" * 80)
        logger.info("APPLYING MANUAL CORRECTIONS")
        logger.info("=" * 80)
        logger.info(f"Mode: {'DRY RUN' if dry_run else 'EXECUTE'}")
        logger.info("")

        # Read corrections CSV
        corrections = []
        with open(csv_path, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                # Only process rows with a correct_type filled in
                if row['correct_type'].strip():
                    corrections.append({
                        'id': int(row['id']),
                        'filename': row['filename'],
                        'old_type': row['current_type'],
                        'new_type': row['correct_type'].strip(),
                        'notes': row.get('notes', '').strip(),
                        'old_path': row['filepath']
                    })

        logger.info(f"Total corrections to apply: {len(corrections)}")
        logger.info("")

        if len(corrections) == 0:
            logger.warning("No corrections found in CSV (correct_type column is empty)")
            logger.info("Please fill in the 'correct_type' column and try again")
            return {'total': 0, 'applied': 0, 'errors': 0}

        # Statistics
        stats = {
            'total': len(corrections),
            'applied': 0,
            'errors': 0,
            'moved': 0,
            'by_old_type': {},
            'by_new_type': {},
        }

        training_data = []

        for correction in corrections:
            try:
                # Validate new type
                if correction['new_type'] not in DOMAIN_FUNCTION_MAP:
                    logger.error(f"Invalid type '{correction['new_type']}' for {correction['filename']}")
                    stats['errors'] += 1
                    continue

                # Get new domain/function
                domain, function = DOMAIN_FUNCTION_MAP[correction['new_type']]
                new_path = os.path.join(self.organized_root, domain, function, correction['filename'])

                # Check if move is needed
                needs_move = correction['old_path'] != new_path

                if not dry_run:
                    # Update database
                    self.cursor.execute("""
                        UPDATE documents
                        SET document_type = ?, file_path = ?
                        WHERE id = ?
                    """, (correction['new_type'], new_path, correction['id']))

                    # Move file if needed
                    if needs_move and os.path.exists(correction['old_path']):
                        os.makedirs(os.path.dirname(new_path), exist_ok=True)
                        shutil.move(correction['old_path'], new_path)
                        stats['moved'] += 1

                # Collect training data
                training_data.append({
                    'filename': correction['filename'],
                    'old_type': correction['old_type'],
                    'correct_type': correction['new_type'],
                    'notes': correction['notes']
                })

                stats['applied'] += 1
                stats['by_old_type'][correction['old_type']] = stats['by_old_type'].get(correction['old_type'], 0) + 1
                stats['by_new_type'][correction['new_type']] = stats['by_new_type'].get(correction['new_type'], 0) + 1

                if stats['applied'] % 50 == 0:
                    logger.info(f"  Processed {stats['applied']}/{stats['total']} corrections...")

            except Exception as e:
                logger.error(f"Error applying correction for {correction['filename']}: {e}")
                stats['errors'] += 1

        if not dry_run:
            self.conn.commit()

        # Save training data
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        training_csv = f'training_data_{timestamp}.csv'

        with open(training_csv, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['filename', 'old_type', 'correct_type', 'notes']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(training_data)

        logger.info("")
        logger.info("CORRECTION SUMMARY:")
        logger.info(f"  Total corrections: {stats['total']}")
        logger.info(f"  Applied: {stats['applied']}")
        logger.info(f"  Files moved: {stats['moved']}")
        logger.info(f"  Errors: {stats['errors']}")
        logger.info("")

        if stats['by_old_type']:
            logger.info("CORRECTIONS BY OLD TYPE:")
            for old_type, count in sorted(stats['by_old_type'].items(), key=lambda x: x[1], reverse=True):
                logger.info(f"  {old_type:30} {count:5} corrections")
            logger.info("")

        if stats['by_new_type']:
            logger.info("CORRECTIONS BY NEW TYPE:")
            for new_type, count in sorted(stats['by_new_type'].items(), key=lambda x: x[1], reverse=True):
                logger.info(f"  {new_type:30} {count:5} corrections")
            logger.info("")

        logger.info(f"✓ Training data saved to: {training_csv}")
        logger.info("")

        if dry_run:
            logger.info("[DRY RUN] No changes made to database or files")
            logger.info("Run with --execute to apply corrections")
        else:
            logger.info(f"✓ Successfully applied {stats['applied']} corrections")
            logger.info("")
            logger.info("NEXT STEPS:")
            logger.info("1. Use training data to enhance ML model:")
            logger.info(f"   python scripts/ml/enhance_model.py --training {training_csv}")
            logger.info("2. Or continue manual review with remaining files")

        return stats

    def close(self):
        self.conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Apply manual corrections from CSV review")
    parser.add_argument('--csv', type=str, required=True,
                        help='Path to corrected CSV file')
    parser.add_argument('--db', type=str, default='ifmos/data/training/ifmos_ml.db')
    parser.add_argument('--root', type=str, default='C:/Users/kjfle/Documents/Organized_V2')
    parser.add_argument('--execute', action='store_true',
                        help='Execute corrections (default is dry-run)')

    args = parser.parse_args()

    applicator = CorrectionsApplicator(args.db, args.root)
    try:
        stats = applicator.apply_corrections(args.csv, dry_run=not args.execute)
    finally:
        applicator.close()
