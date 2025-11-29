#!/usr/bin/env python3
"""
IFMOS Function/Form/Fit Reorganization
Reorganizes all files removing chronological nesting
Structure: Domain → Function → Files
"""

import sqlite3
import os
import shutil
from pathlib import Path
from collections import defaultdict
import logging
import argparse

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# Domain → Function mapping (NO chronological nesting!)
DOMAIN_FUNCTION_MAP = {
    # Automotive
    'automotive_technical': ('Automotive', 'Technical_Manuals'),
    'automotive_service': ('Automotive', 'Service_Records'),

    # Personal
    'personal_career': ('Personal', 'Career'),
    'personal_journal': ('Personal', 'Journals'),
    'personal_essay': ('Personal', 'Essays'),
    'personal_career_tool': ('Personal', 'Career_Tools'),
    'personal_finance_tool': ('Personal', 'Finance_Tools'),

    # Financial
    'financial_invoice': ('Financial', 'Invoices'),
    'financial_statement': ('Financial', 'Statements'),
    'financial_receipt': ('Financial', 'Receipts'),

    # Legal
    'legal_contract': ('Legal', 'Contracts'),
    'legal_court': ('Legal', 'Court_Documents'),
    'legal_agreement': ('Legal', 'Agreements'),

    # Tax
    'tax_document': ('Tax', 'Documents'),
    'tax_form': ('Tax', 'Forms'),
    'tax_return': ('Tax', 'Returns'),

    # Medical
    'medical': ('Medical', 'Records'),
    'medical_bill': ('Medical', 'Bills'),
    'medical_record': ('Medical', 'Records'),

    # HR
    'hr_resume': ('HR', 'Job_Applicant_Resumes'),
    'hr_application': ('HR', 'Applications'),
    'hr_benefits': ('HR', 'Benefits'),
    'hr_job_listing': ('HR', 'Job_Listings'),

    # Technical/IT
    'technical_documentation': ('Technical', 'Documentation'),
    'technical_manual': ('Technical', 'Manuals'),
    'technical_config': ('Technical', 'Configuration'),
    'technical_research': ('Technical', 'Research'),
    'technical_code': ('Technical', 'Code'),

    # Communications
    'communication_email': ('Communications', 'Emails'),
    'communication_letter': ('Communications', 'Letters'),

    # Business
    'business_proposal': ('Business', 'Proposals'),
    'business_marketing': ('Business', 'Marketing'),
    'realestate_listing': ('Business', 'Real_Estate_Listings'),
    'realestate_contract': ('Business', 'Real_Estate_Contracts'),

    # Miscellaneous
    'screenshot': ('Miscellaneous', 'Screenshots'),
    'report': ('Reports', 'General'),
    'form': ('Forms', 'General'),
    'general_document': ('General', 'Documents'),
    'general_document_short': ('General', 'Documents'),
    'unknown': ('Review_Required', 'Unclassified'),
}


def reorganize_all(db_path: str, new_root: str, dry_run: bool = True):
    """Reorganize all files with Function/Form structure"""

    logger.info("=" * 80)
    logger.info("FUNCTION/FORM REORGANIZATION (NO CHRONOLOGICAL NESTING!)")
    logger.info("=" * 80)
    logger.info(f"Mode: {'DRY RUN' if dry_run else 'EXECUTE'}")
    logger.info("")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all organized documents
    cursor.execute('''
        SELECT id, file_name, document_type, file_path
        FROM documents
        WHERE file_path LIKE '%Organized%'
        ORDER BY document_type
    ''')

    all_docs = cursor.fetchall()

    logger.info(f"Total documents to reorganize: {len(all_docs)}")
    logger.info("")

    # Plan reorganization
    reorganization_plan = []

    for doc_id, filename, doc_type, old_path in all_docs:
        if doc_type in DOMAIN_FUNCTION_MAP:
            domain, function = DOMAIN_FUNCTION_MAP[doc_type]
            new_path = os.path.join(new_root, domain, function, filename)

            # Normalize paths for comparison
            old_path_normalized = old_path.replace('\\', '/').replace('//', '/')
            new_path_normalized = new_path.replace('\\', '/').replace('//', '/')

            # Only include if paths actually differ
            if old_path_normalized != new_path_normalized:
                reorganization_plan.append({
                    'id': doc_id,
                    'filename': filename,
                    'doc_type': doc_type,
                    'old_path': old_path,
                    'new_path': new_path,
                    'domain': domain,
                    'function': function
                })

    logger.info(f"Files to reorganize: {len(reorganization_plan)}")
    logger.info("")

    # Show sample
    logger.info("SAMPLE REORGANIZATION (first 20):")
    for i, item in enumerate(reorganization_plan[:20]):
        logger.info(f"{i+1}. [{item['doc_type']}]")
        logger.info(f"   {item['domain']}/{item['function']}/{item['filename'][:50]}")

    if len(reorganization_plan) > 20:
        logger.info(f"... and {len(reorganization_plan) - 20} more")
    logger.info("")

    # Stats by domain
    by_domain = defaultdict(int)
    for item in reorganization_plan:
        by_domain[item['domain']] += 1

    logger.info("FILES PER DOMAIN:")
    for domain, count in sorted(by_domain.items(), key=lambda x: x[1], reverse=True):
        logger.info(f"  {domain:30} {count:5} files")
    logger.info("")

    if not dry_run:
        logger.info("Executing reorganization...")
        success_count = 0
        error_count = 0

        for item in reorganization_plan:
            try:
                # Create target directory
                target_dir = os.path.dirname(item['new_path'])
                os.makedirs(target_dir, exist_ok=True)

                # Move file
                shutil.move(item['old_path'], item['new_path'])

                # Update database
                cursor.execute("""
                    UPDATE documents
                    SET file_path = ?
                    WHERE id = ?
                """, (item['new_path'], item['id']))

                success_count += 1

                if success_count % 100 == 0:
                    logger.info(f"  Processed {success_count}/{len(reorganization_plan)} files...")

            except Exception as e:
                logger.error(f"Error moving {item['filename']}: {e}")
                error_count += 1

        conn.commit()

        logger.info("")
        logger.info(f"✓ Reorganization complete!")
        logger.info(f"  Success: {success_count}")
        logger.info(f"  Errors: {error_count}")
    else:
        logger.info("[DRY RUN] No files moved")
        logger.info("Run with --execute to apply reorganization")

    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reorganize IFMOS with Function/Form structure")
    parser.add_argument('--db', type=str, default='ifmos/data/training/ifmos_ml.db')
    parser.add_argument('--new-root', type=str, default='C:/Users/kjfle/Documents/Organized_V2')
    parser.add_argument('--execute', action='store_true')

    args = parser.parse_args()

    reorganize_all(args.db, args.new_root, dry_run=not args.execute)
