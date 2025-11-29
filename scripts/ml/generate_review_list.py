#!/usr/bin/env python3
"""
IFMOS Manual Review List Generator
Creates prioritized list of files for manual classification review
"""

import sqlite3
import csv
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ReviewListGenerator:
    """Generates prioritized review list for manual correction"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()

    def _suggest_types(self, filename: str, current_type: str) -> List[str]:
        """Suggest alternative types based on filename patterns"""
        suggestions = []

        # Automotive patterns
        if re.search(r'(?i)(bmw|vehicle|diagnostic|carfax|vin|automotive|engine|repair)', filename):
            if current_type not in ['automotive_technical', 'automotive_service']:
                suggestions.append('automotive_technical OR automotive_service')

        # Personal career patterns
        if re.search(r'(?i)(resume|cv|cover.?letter|cl\.|%resume)', filename):
            if current_type not in ['personal_career', 'hr_resume']:
                suggestions.append('personal_career (if yours) OR hr_resume (if applicant)')

        # Personal journal patterns
        if re.search(r'(?i)(yoga|meditation|patanjali|journal|chapter|essay)', filename):
            if current_type not in ['personal_journal', 'personal_essay']:
                suggestions.append('personal_journal OR personal_essay')

        # Tool/calculator patterns
        if re.search(r'(?i)(calculator|estimator|tool|planner|template)', filename):
            if current_type != 'personal_career_tool' and current_type != 'personal_finance_tool':
                suggestions.append('personal_career_tool OR personal_finance_tool')

        # Financial patterns
        if re.search(r'(?i)(invoice|receipt|statement|bill)', filename):
            if not current_type.startswith('financial'):
                suggestions.append('financial_invoice OR financial_statement OR financial_receipt')

        # Legal patterns
        if re.search(r'(?i)(contract|agreement|legal|court|settlement)', filename):
            if not current_type.startswith('legal'):
                suggestions.append('legal_contract OR legal_agreement OR legal_court')

        # Medical patterns
        if re.search(r'(?i)(medical|patient|doctor|hospital|prescription)', filename):
            # BUT exclude automotive
            if not re.search(r'(?i)(vehicle|bmw|diagnostic.report|vin)', filename):
                if current_type != 'medical' and current_type != 'medical_bill':
                    suggestions.append('medical OR medical_bill')

        # Tax patterns
        if re.search(r'(?i)(tax|1040|w-?2|1099|irs)', filename):
            if not current_type.startswith('tax'):
                suggestions.append('tax_document OR tax_form OR tax_return')

        # Screenshot patterns
        if re.search(r'(?i)(screenshot|screen.?shot|capture)', filename):
            if current_type != 'screenshot':
                suggestions.append('screenshot')

        return suggestions

    def _get_review_reason(self, doc_type: str, confidence: float, filename: str) -> str:
        """Determine why this file needs review"""
        reasons = []

        # Low confidence
        if confidence < 0.50:
            reasons.append("VERY LOW confidence")
        elif confidence < 0.75:
            reasons.append("Low confidence")

        # Generic types
        if doc_type in ['unknown', 'general_document', 'general_document_short', 'form']:
            reasons.append("Generic classification")

        # Potentially misclassified patterns
        if doc_type == 'medical' and re.search(r'(?i)(vehicle|diagnostic|bmw|vin)', filename):
            reasons.append("LIKELY automotive, not medical")

        if doc_type == 'hr_resume' and re.search(r'(?i)(%resume|cl\.|cover.?letter)', filename):
            reasons.append("LIKELY personal career, not HR recruiting")

        if doc_type == 'financial_invoice' and re.search(r'(?i)(calculator|estimator|tool)', filename):
            reasons.append("LIKELY tool, not invoice")

        if doc_type == 'hr_resume' and re.search(r'(?i)(yoga|meditation|journal|chapter)', filename):
            reasons.append("LIKELY personal journal, not resume")

        # Cryptic filenames
        if re.match(r'^file-[A-Za-z0-9]{22}-[A-F0-9]{8}-', filename):
            reasons.append("Cryptic filename - needs content review")

        # CCO files
        if re.search(r'cco_\d{6}', filename):
            reasons.append("Generic CCO file - needs context")

        if not reasons:
            reasons.append("Flagged for review")

        return "; ".join(reasons)

    def generate_review_list(self, output_csv: str, priority: str = 'all') -> Dict:
        """
        Generate prioritized review list

        Priority levels:
        - critical: VERY low confidence (<0.50) + known misclassifications
        - high: Low confidence (<0.75) + generic types
        - all: All files needing review
        """

        logger.info("=" * 80)
        logger.info("GENERATING MANUAL REVIEW LIST")
        logger.info("=" * 80)
        logger.info(f"Priority: {priority.upper()}")
        logger.info("")

        # Build query based on priority
        if priority == 'critical':
            where_clause = """
                WHERE (confidence < 0.50
                   OR document_type IN ('unknown')
                   OR (document_type = 'medical' AND file_name LIKE '%vehicle%')
                   OR (document_type = 'hr_resume' AND (file_name LIKE '%resume%' OR file_name LIKE '%CL.%'))
                   OR (document_type = 'financial_invoice' AND (file_name LIKE '%calculator%' OR file_name LIKE '%estimator%')))
            """
        elif priority == 'high':
            where_clause = """
                WHERE (confidence < 0.75
                   OR document_type IN ('unknown', 'general_document', 'general_document_short', 'form'))
            """
        else:  # all
            where_clause = """
                WHERE (confidence < 0.75
                   OR document_type IN ('unknown', 'general_document', 'general_document_short', 'form')
                   OR (document_type = 'medical' AND file_name LIKE '%vehicle%')
                   OR (document_type = 'hr_resume' AND (file_name LIKE '%resume%' OR file_name LIKE '%yoga%'))
                   OR (document_type = 'financial_invoice' AND (file_name LIKE '%calculator%' OR file_name LIKE '%estimator%')))
            """

        self.cursor.execute(f"""
            SELECT id, file_name, file_path, document_type, confidence
            FROM documents
            {where_clause}
            ORDER BY
                CASE
                    WHEN confidence < 0.50 THEN 1
                    WHEN document_type = 'unknown' THEN 2
                    WHEN confidence < 0.75 THEN 3
                    ELSE 4
                END,
                confidence ASC,
                file_name
        """)

        files = self.cursor.fetchall()

        logger.info(f"Files flagged for review: {len(files)}")
        logger.info("")

        # Generate review list
        review_items = []

        for doc_id, filename, filepath, doc_type, confidence in files:
            suggestions = self._suggest_types(filename, doc_type)
            reason = self._get_review_reason(doc_type, confidence or 0, filename)

            review_items.append({
                'id': doc_id,
                'filename': filename,
                'current_type': doc_type,
                'confidence': confidence or 0,
                'suggested_types': ' | '.join(suggestions) if suggestions else '',
                'reason': reason,
                'filepath': filepath
            })

        # Write to CSV
        with open(output_csv, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['id', 'filename', 'current_type', 'confidence', 'suggested_types', 'reason', 'correct_type', 'notes', 'filepath']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            for item in review_items:
                writer.writerow({
                    'id': item['id'],
                    'filename': item['filename'],
                    'current_type': item['current_type'],
                    'confidence': f"{item['confidence']:.2f}",
                    'suggested_types': item['suggested_types'],
                    'reason': item['reason'],
                    'correct_type': '',  # User fills this in
                    'notes': '',  # User fills this in
                    'filepath': item['filepath']
                })

        logger.info(f"✓ Review list saved to: {output_csv}")
        logger.info("")

        # Statistics
        by_type = {}
        by_reason = {}
        for item in review_items:
            by_type[item['current_type']] = by_type.get(item['current_type'], 0) + 1
            for reason in item['reason'].split('; '):
                by_reason[reason] = by_reason.get(reason, 0) + 1

        logger.info("FILES BY CURRENT TYPE:")
        for doc_type, count in sorted(by_type.items(), key=lambda x: x[1], reverse=True)[:10]:
            logger.info(f"  {doc_type:30} {count:5} files")
        logger.info("")

        logger.info("REVIEW REASONS (Top 10):")
        for reason, count in sorted(by_reason.items(), key=lambda x: x[1], reverse=True)[:10]:
            logger.info(f"  {reason:50} {count:5} files")
        logger.info("")

        # Sample
        logger.info("SAMPLE REVIEW ITEMS (First 10):")
        for item in review_items[:10]:
            logger.info(f"  [{item['current_type']:25}] {item['filename'][:50]}")
            logger.info(f"     Confidence: {item['confidence']:.2f} | Reason: {item['reason']}")
            if item['suggested_types']:
                logger.info(f"     Suggestions: {item['suggested_types']}")
        logger.info("")

        logger.info("=" * 80)
        logger.info("INSTRUCTIONS:")
        logger.info("=" * 80)
        logger.info("1. Open the CSV file in Excel or similar")
        logger.info("2. For each row:")
        logger.info("   - Review the filename, current type, and confidence")
        logger.info("   - Check suggestions and reasons")
        logger.info("   - Fill in 'correct_type' column with the right classification")
        logger.info("   - Add any notes in 'notes' column")
        logger.info("3. Save the CSV when done")
        logger.info("4. Run: python scripts/ml/apply_corrections.py --csv <your_file.csv>")
        logger.info("")

        return {
            'total': len(review_items),
            'by_type': by_type,
            'by_reason': by_reason
        }

    def close(self):
        self.conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate manual review list for IFMOS")
    parser.add_argument('--db', type=str, default='ifmos/data/training/ifmos_ml.db')
    parser.add_argument('--output', type=str, default='manual_review_list.csv')
    parser.add_argument('--priority', type=str, choices=['critical', 'high', 'all'], default='high',
                        help='Priority level: critical (most urgent), high (recommended), all (everything)')

    args = parser.parse_args()

    generator = ReviewListGenerator(args.db)
    try:
        stats = generator.generate_review_list(args.output, args.priority)
    finally:
        generator.close()
