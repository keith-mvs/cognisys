#!/usr/bin/env python3
"""
CogniSys Document Reclassification Script
Fixes misclassifications using pattern matching and contextual analysis
"""

import sqlite3
import re
import os
from pathlib import Path
from typing import Dict, Optional, List, Tuple
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DocumentReclassifier:
    """Reclassifies documents using filename/content pattern matching"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()

        # Reclassification rules (pattern → new_type, confidence)
        self.rules = self._build_rules()

    def _build_rules(self) -> List[Dict]:
        """Build comprehensive reclassification rules"""
        return [
            # ================================================================
            # AUTOMOTIVE PATTERNS
            # ================================================================
            {
                'name': 'Automotive - Vehicle Diagnostic Reports',
                'patterns': [
                    r'\[?P\d{6}\]?\s*Vehicle\s+Diagnostic',
                    r'Vehicle\s+Diagnostic\s+Report',
                    r'Diagnostic\s+Report.*\d{8}',  # Diagnostic Report 20250319
                ],
                'new_type': 'automotive_service',
                'confidence': 0.95,
                'reason': 'Vehicle diagnostic report pattern'
            },
            {
                'name': 'Automotive - BMW Technical',
                'patterns': [
                    r'BMW\s+[A-Z0-9]+,?\s*\d+kW',
                    r'BMW.*(?:Engine|Transmission|Chassis)',
                    r'\b[E|F]\d{2}\s+[A-Z0-9]+\b',  # E92 328i, F30 335i
                    r'ST\d{4}.*BMW',  # ST1450 Introduction to BMW
                ],
                'new_type': 'automotive_technical',
                'confidence': 0.95,
                'reason': 'BMW technical documentation'
            },
            {
                'name': 'Automotive - Service/Repair Manuals',
                'patterns': [
                    r'(?:Service|Repair|Maintenance).*(?:Manual|Instruction|Guide)',
                    r'Parts?\s+(?:Diagram|Manual|List)',
                    r'(?:Engine|Transmission|Brake|Suspension).*(?:Service|Repair)',
                    r'Measuring.*(?:ride|level|height).*vehicle',
                    r'(?:Oil|Coolant|Fluid).*(?:Service|Change|Top)',
                    r'AIR\s*-\s*Repair\s+instruction',
                ],
                'new_type': 'automotive_technical',
                'confidence': 0.90,
                'reason': 'Automotive service manual'
            },
            {
                'name': 'Automotive - CARFAX Reports',
                'patterns': [
                    r'CARFAX',
                    r'Vehicle\s+History\s+Report',
                ],
                'new_type': 'automotive_service',
                'confidence': 1.00,
                'reason': 'CARFAX vehicle history report'
            },
            {
                'name': 'Automotive - VIN-based Documents',
                'patterns': [
                    r'\b[A-HJ-NPR-Z0-9]{17}\b',  # Standard VIN format
                ],
                'new_type': 'automotive_service',
                'confidence': 0.85,
                'reason': 'Contains VIN number'
            },

            # ================================================================
            # PERSONAL DOCUMENTS (NOT HR!)
            # ================================================================
            {
                'name': 'Personal - Own Resumes/CVs',
                'patterns': [
                    r'(?:Resume|CV)[-_](?:CV|resume)',
                    r'%Resume_CV',
                    r'resume-cv_\d{8}',
                    r'CL\.(?:Jan|Nov|Dec)\d{2}',  # CL.Jan15, CLv2.Jan15
                ],
                'new_type': 'personal_career',
                'confidence': 0.95,
                'reason': 'Personal resume/CV (not HR recruiting)'
            },
            {
                'name': 'Personal - Cover Letters',
                'patterns': [
                    r'Cover\s+Letter\s+\d{8}',
                ],
                'new_type': 'personal_career',
                'confidence': 0.95,
                'reason': 'Personal cover letter (not HR recruiting)'
            },
            {
                'name': 'Personal - Yoga/Meditation Journals',
                'patterns': [
                    r'Chapter.*(?:Yoga|Patanjali|Sukha|Mantra)',
                    r'(?:Yoga|Meditation).*(?:Sutras|Shala)',
                    r'Eight\s+Limbs.*Ashtanga',
                ],
                'new_type': 'personal_journal',
                'confidence': 1.00,
                'reason': 'Yoga/meditation journal entry'
            },
            {
                'name': 'Personal - Essays/Career Goals',
                'patterns': [
                    r'AIAA\s+Scholarship',
                    r'CSMP_ESSAY',
                    r'Career\s+Goals',
                ],
                'new_type': 'personal_essay',
                'confidence': 1.00,
                'reason': 'Personal essay/career goals'
            },

            # ================================================================
            # TECHNICAL/TRAINING DOCUMENTS
            # ================================================================
            {
                'name': 'Technical - Training Modules',
                'patterns': [
                    r'ST\d{4}.*(?:Training|Module|Course)',
                    r'(?:Training|Module).*(?:Manual|Guide)',
                ],
                'new_type': 'technical_documentation',
                'confidence': 0.90,
                'reason': 'Technical training module'
            },

            # ================================================================
            # BUSINESS DOCUMENTS
            # ================================================================
            {
                'name': 'Business - Business Plans',
                'patterns': [
                    r'Business[-_\s]Plan',
                ],
                'new_type': 'business_proposal',
                'confidence': 0.95,
                'reason': 'Business plan document'
            },

            # ================================================================
            # GENERIC CCO FILES (NEED REVIEW)
            # ================================================================
            {
                'name': 'Review Required - CCO Files',
                'patterns': [
                    r'\d{4}-\d{2}-\d{2}_review_cco_\d{6}',
                    r'cco_\d{6}',
                ],
                'new_type': 'unknown',
                'confidence': 0.50,
                'reason': 'Generic CCO file - needs manual review'
            },
        ]

    def analyze_filename(self, filename: str) -> Optional[Tuple[str, float, str]]:
        """
        Analyze filename against patterns
        Returns: (new_type, confidence, reason) or None
        """
        for rule in self.rules:
            for pattern in rule['patterns']:
                if re.search(pattern, filename, re.IGNORECASE):
                    logger.debug(f"Matched rule '{rule['name']}' for: {filename}")
                    return (rule['new_type'], rule['confidence'], rule['reason'])
        return None

    def reclassify_all(self, dry_run: bool = True) -> Dict:
        """
        Reclassify all documents using pattern matching
        """
        logger.info("=" * 80)
        logger.info("DOCUMENT RECLASSIFICATION")
        logger.info("=" * 80)
        logger.info(f"Mode: {'DRY RUN' if dry_run else 'EXECUTE'}")
        logger.info("")

        # Get all documents
        self.cursor.execute("""
            SELECT id, file_name, document_type, confidence
            FROM documents
            WHERE document_type IS NOT NULL
            ORDER BY document_type, file_name
        """)

        documents = self.cursor.fetchall()

        stats = {
            'total': len(documents),
            'reclassified': 0,
            'unchanged': 0,
            'by_old_type': {},
            'by_new_type': {},
            'by_reason': {},
        }

        reclassifications = []

        for doc_id, filename, old_type, old_confidence in documents:
            result = self.analyze_filename(filename)

            if result:
                new_type, new_confidence, reason = result

                # Only reclassify if pattern match has higher confidence
                if new_type != old_type and new_confidence >= (old_confidence or 0):
                    stats['reclassified'] += 1
                    stats['by_old_type'][old_type] = stats['by_old_type'].get(old_type, 0) + 1
                    stats['by_new_type'][new_type] = stats['by_new_type'].get(new_type, 0) + 1
                    stats['by_reason'][reason] = stats['by_reason'].get(reason, 0) + 1

                    reclassifications.append({
                        'id': doc_id,
                        'filename': filename,
                        'old_type': old_type,
                        'new_type': new_type,
                        'old_confidence': old_confidence,
                        'new_confidence': new_confidence,
                        'reason': reason
                    })

                    if not dry_run:
                        self.cursor.execute("""
                            UPDATE documents
                            SET document_type = ?, confidence = ?
                            WHERE id = ?
                        """, (new_type, new_confidence, doc_id))
                else:
                    stats['unchanged'] += 1
            else:
                stats['unchanged'] += 1

        if not dry_run:
            self.conn.commit()

        # Print results
        logger.info("RECLASSIFICATION SUMMARY:")
        logger.info(f"  Total Documents: {stats['total']}")
        logger.info(f"  Reclassified: {stats['reclassified']}")
        logger.info(f"  Unchanged: {stats['unchanged']}")
        logger.info(f"  Success Rate: {(stats['reclassified']/stats['total']*100):.1f}%")
        logger.info("")

        if stats['by_old_type']:
            logger.info("RECLASSIFICATIONS BY OLD TYPE:")
            for old_type, count in sorted(stats['by_old_type'].items(), key=lambda x: x[1], reverse=True):
                logger.info(f"  {old_type:30} {count:5} documents")
            logger.info("")

        if stats['by_new_type']:
            logger.info("RECLASSIFICATIONS BY NEW TYPE:")
            for new_type, count in sorted(stats['by_new_type'].items(), key=lambda x: x[1], reverse=True):
                logger.info(f"  {new_type:30} {count:5} documents")
            logger.info("")

        if stats['by_reason']:
            logger.info("RECLASSIFICATION REASONS:")
            for reason, count in sorted(stats['by_reason'].items(), key=lambda x: x[1], reverse=True):
                logger.info(f"  {reason:50} {count:5} documents")
            logger.info("")

        # Show sample reclassifications
        if reclassifications:
            logger.info("SAMPLE RECLASSIFICATIONS (first 20):")
            for reclass in reclassifications[:20]:
                logger.info(f"  {reclass['old_type']:20} → {reclass['new_type']:25} | {reclass['filename'][:50]}")
                logger.info(f"     Reason: {reclass['reason']}")
            logger.info("")

        if dry_run:
            logger.info("[DRY RUN] No changes made to database")
            logger.info("Run with --execute to apply changes")
        else:
            logger.info(f"✓ Successfully reclassified {stats['reclassified']} documents")

        return stats

    def close(self):
        self.conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Reclassify CogniSys documents using pattern matching")
    parser.add_argument('--db', type=str, default='cognisys/data/training/cognisys_ml.db',
                        help='Path to CogniSys database')
    parser.add_argument('--execute', action='store_true',
                        help='Execute reclassification (default is dry-run)')

    args = parser.parse_args()

    reclassifier = DocumentReclassifier(args.db)
    try:
        stats = reclassifier.reclassify_all(dry_run=not args.execute)
    finally:
        reclassifier.close()
