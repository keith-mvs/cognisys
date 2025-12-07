#!/usr/bin/env python3
"""
CogniSys Comprehensive Reclassification Engine
Learns from ALL mistakes and reclassifies everything
"""

import sqlite3
import re
import os
from pathlib import Path
from typing import Dict, Optional, List, Tuple
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ComprehensiveReclassifier:
    """Advanced reclassifier with extensive pattern matching"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self.rules = self._build_comprehensive_rules()

    def _build_comprehensive_rules(self) -> List[Dict]:
        """Build extensive reclassification rules learned from mistakes"""
        return [
            # ================================================================
            # AUTOMOTIVE - Highest Priority (Most Misclassified)
            # ================================================================
            {
                'priority': 1,
                'name': 'Automotive - BMW E-Series Technical',
                'patterns': [
                    r"3'\s*E\d{2}\s+\d{3}i",  # 3' E92 328i
                    r'E\d{2}\s+[A-Z]\d+\b',  # E92 M3, E46 328i
                    r'F\d{2}\s+[A-Z0-9]+',  # F30 335i
                ],
                'new_type': 'automotive_technical',
                'confidence': 0.98
            },
            {
                'priority': 1,
                'name': 'Automotive - BMW Parts/Systems',
                'patterns': [
                    r'(?:transmission|gearshift|oil\s+pan|drive|output)',
                    r'GA6L45R',  # BMW transmission code
                    r'(?:belt\s+drive|generator|AC|power\s+steering)',
                    r'(?:headlight|fog\s+light|turn\s+indicator|rear\s+light)',
                    r'(?:cooling|water\s+hose|thermostat)',
                    r'(?:brake|suspension|axle)',
                ],
                'new_type': 'automotive_technical',
                'confidence': 0.95,
                'exclude_if': [r'yoga', r'meditation', r'chapter']  # Avoid false positives
            },
            {
                'priority': 1,
                'name': 'Automotive - Service Manuals',
                'patterns': [
                    r'(?:service|repair|maintenance).*(?:manual|guide|instruction)',
                    r'parts?\s+(?:diagram|manual|catalog)',
                    r'BMW.*(?:technical|service|repair)',
                ],
                'new_type': 'automotive_technical',
                'confidence': 0.93
            },
            {
                'priority': 1,
                'name': 'Automotive - Diagnostic Reports',
                'patterns': [
                    r'\[?P\d{6}\]?.*(?:vehicle|diagnostic)',
                    r'vehicle\s+diagnostic\s+report',
                    r'(?:measuring|checking).*(?:ride|level|height).*vehicle',
                ],
                'new_type': 'automotive_service',
                'confidence': 0.98
            },
            {
                'priority': 1,
                'name': 'Automotive - CARFAX',
                'patterns': [r'CARFAX', r'vehicle\s+history\s+report'],
                'new_type': 'automotive_service',
                'confidence': 1.00
            },
            {
                'priority': 1,
                'name': 'Automotive - VIN Documents',
                'patterns': [r'\b[A-HJ-NPR-Z0-9]{17}\b'],  # VIN format
                'new_type': 'automotive_service',
                'confidence': 0.90
            },
            {
                'priority': 1,
                'name': 'Automotive - BMW Model Specific',
                'patterns': [
                    r'BMW\s+(?:M3|M5|M6|328i|335i|535i|X5|X3)',
                    r'\d{4}.*BMW',  # Year + BMW
                ],
                'new_type': 'automotive_technical',
                'confidence': 0.90
            },

            # ================================================================
            # PERSONAL DOCUMENTS - High Priority
            # ================================================================
            {
                'priority': 2,
                'name': 'Personal - Own Resumes/CVs',
                'patterns': [
                    r'%Resume[_-]CV',
                    r'resume[-_]cv[-_]\d{8}',
                    r'Resume[-_]CV[-_]v\d+',
                    r'CL\.(?:Jan|Nov|Dec|Oct)\d{2}',  # Cover letters
                    r'CLv\d+\.(?:Jan|Nov|Dec)',
                    r'Cover\s+Letter\s+\d{8}',
                ],
                'new_type': 'personal_career',
                'confidence': 0.98
            },
            {
                'priority': 2,
                'name': 'Personal - Yoga/Meditation Journals',
                'patterns': [
                    r'Chapter.*(?:Yoga|Patanjali|Sukha|Mantra|Ashtanga)',
                    r'(?:Yoga|Meditation).*(?:Sutras|Shala)',
                    r'Eight\s+Limbs.*Ashtanga',
                    r'Sukha[-_]Shala',
                ],
                'new_type': 'personal_journal',
                'confidence': 1.00
            },
            {
                'priority': 2,
                'name': 'Personal - Essays/Scholarship',
                'patterns': [
                    r'(?:AIAA|CSMP).*(?:Scholarship|Essay)',
                    r'Career\s+Goals',
                    r'Scholarship.*(?:Goals|Essay|Application)',
                ],
                'new_type': 'personal_essay',
                'confidence': 1.00
            },
            {
                'priority': 2,
                'name': 'Personal - Career Tools',
                'patterns': [
                    r'salary[-_]estimator',
                    r'compensation[-_]calculator',
                    r'career[-_](?:planner|tool)',
                ],
                'new_type': 'personal_career_tool',
                'confidence': 0.95
            },
            {
                'priority': 2,
                'name': 'Personal - Financial Calculators',
                'patterns': [
                    r'mortgage[-_](?:calculator|comparison)',
                    r'Down.*Conventional.*Mortgage',
                    r'(?:loan|payment)[-_]calculator',
                ],
                'new_type': 'personal_finance_tool',
                'confidence': 0.95
            },

            # ================================================================
            # TECHNICAL/MANUALS
            # ================================================================
            {
                'priority': 3,
                'name': 'Technical - Product Manuals',
                'patterns': [
                    r'(?:instruction|installation|user)[-_\s]manual',
                    r'RS[-_]\d{2}K.*(?:manual|instruction)',
                    r'(?:product|equipment).*manual',
                ],
                'new_type': 'technical_manual',
                'confidence': 0.90
            },
            {
                'priority': 3,
                'name': 'Technical - BMW Training Modules',
                'patterns': [
                    r'ST\d{4}.*BMW',
                    r'ST\d{4}.*(?:training|module|course)',
                ],
                'new_type': 'technical_documentation',
                'confidence': 0.95
            },
            {
                'priority': 3,
                'name': 'Technical - Configuration Files',
                'patterns': [
                    r'\.(?:json|yml|yaml|xml|conf|config)$',
                    r'(?:config|configuration).*\.(?:json|txt)',
                ],
                'new_type': 'technical_config',
                'confidence': 0.85
            },

            # ================================================================
            # BUSINESS DOCUMENTS
            # ================================================================
            {
                'priority': 4,
                'name': 'Business - Real Estate Listings',
                'patterns': [
                    r'\d{4}_-_\d{4}_\w+.*(?:suite|flyer)',
                    r'(?:property|listing).*(?:flyer|brochure)',
                ],
                'new_type': 'realestate_listing',
                'confidence': 0.90
            },
            {
                'priority': 4,
                'name': 'Business - Proposals',
                'patterns': [
                    r'(?:business|project)[-_\s]plan',
                    r'proposal.*\d{8}',
                ],
                'new_type': 'business_proposal',
                'confidence': 0.90
            },

            # ================================================================
            # MEDICAL (Actual Medical, Not Automotive)
            # ================================================================
            {
                'priority': 5,
                'name': 'Medical - Healthcare Directives',
                'patterns': [
                    r'(?:health\s+care|healthcare)\s+directive',
                    r'(?:blue\s+cross|medical|healthcare).*(?:directive|consent)',
                ],
                'new_type': 'medical',
                'confidence': 0.95,
                'exclude_if': [r'vehicle', r'BMW', r'diagnostic\s+report']
            },
            {
                'priority': 5,
                'name': 'Medical - Bills/Records',
                'patterns': [
                    r'SB[-_]\d{8}[-_]\d{4}',  # Medical bill format
                    r'(?:medical|patient).*(?:bill|invoice|record)',
                ],
                'new_type': 'medical_bill',
                'confidence': 0.90,
                'exclude_if': [r'vehicle', r'BMW']
            },

            # ================================================================
            # COMMUNICATIONS
            # ================================================================
            {
                'priority': 6,
                'name': 'Communications - Product Brochures',
                'patterns': [
                    r'3M_EU_IB',
                    r'(?:brochure|catalog|datasheet)',
                    r'Dryconn.*Connectors',
                ],
                'new_type': 'technical_documentation',
                'confidence': 0.85
            },
            {
                'priority': 6,
                'name': 'Communications - Emails',
                'patterns': [
                    r'[-_]email\.pdf$',
                    r'(?:employee|award).*nomination',
                ],
                'new_type': 'communication_email',
                'confidence': 0.90
            },

            # ================================================================
            # FINANCIAL (Actual Invoices/Statements)
            # ================================================================
            {
                'priority': 7,
                'name': 'Financial - Order Numbers',
                'patterns': [
                    r'Order\s+R\d{9}',  # Order R289686309
                    r'(?:invoice|order)[-_\s]#?\d{6,}',
                ],
                'new_type': 'financial_invoice',
                'confidence': 0.92
            },
            {
                'priority': 7,
                'name': 'Financial - Statements',
                'patterns': [
                    r'statement[-_]\d{8}[-_]\d{8}',
                    r'(?:bank|account).*statement',
                ],
                'new_type': 'financial_statement',
                'confidence': 0.90
            },

            # ================================================================
            # HR/EMPLOYMENT (Actual Job Applications, Not Personal)
            # ================================================================
            {
                'priority': 8,
                'name': 'HR - Job Listings',
                'patterns': [
                    r'(?:job|position).*(?:description|listing)',
                    r'(?:engineer|developer).*Job\s+ID',
                ],
                'new_type': 'hr_job_listing',
                'confidence': 0.90,
                'exclude_if': [r'resume[-_]cv', r'Cover\s+Letter']
            },

            # ================================================================
            # LEGAL
            # ================================================================
            {
                'priority': 9,
                'name': 'Legal - Contracts',
                'patterns': [
                    r'(?:contract|agreement).*\d{8}',
                    r'(?:employment|vendor).*(?:contract|agreement)',
                ],
                'new_type': 'legal_contract',
                'confidence': 0.88
            },

            # ================================================================
            # GENERIC CCO FILES (Need Review)
            # ================================================================
            {
                'priority': 10,
                'name': 'Review Required - CCO Files',
                'patterns': [
                    r'\d{4}-\d{2}-\d{2}_review_cco_\d{6}',
                ],
                'new_type': 'unknown',
                'confidence': 0.40  # Low confidence - needs manual review
            },

            # ================================================================
            # SCREENSHOTS/IMAGES
            # ================================================================
            {
                'priority': 11,
                'name': 'Screenshots',
                'patterns': [
                    r'Screenshot\s+\d{4}-\d{2}-\d{2}',
                    r'Capture\.(?:PNG|png)',
                ],
                'new_type': 'screenshot',
                'confidence': 1.00
            },
        ]

    def _should_exclude(self, filename: str, exclude_patterns: List[str]) -> bool:
        """Check if filename matches any exclude patterns"""
        if not exclude_patterns:
            return False
        for pattern in exclude_patterns:
            if re.search(pattern, filename, re.IGNORECASE):
                return True
        return False

    def analyze_filename(self, filename: str) -> Optional[Tuple[str, float, str]]:
        """
        Analyze filename with priority-based matching
        Returns: (new_type, confidence, reason) or None
        """
        # Sort rules by priority
        sorted_rules = sorted(self.rules, key=lambda x: x.get('priority', 100))

        for rule in sorted_rules:
            # Check exclude patterns first
            if self._should_exclude(filename, rule.get('exclude_if', [])):
                continue

            # Check if any pattern matches
            for pattern in rule['patterns']:
                if re.search(pattern, filename, re.IGNORECASE):
                    logger.debug(f"Matched rule '{rule['name']}' for: {filename}")
                    return (rule['new_type'], rule['confidence'], rule['name'])

        return None

    def reclassify_all(self, dry_run: bool = True) -> Dict:
        """
        Comprehensive reclassification of all documents
        """
        logger.info("=" * 80)
        logger.info("COMPREHENSIVE DOCUMENT RECLASSIFICATION")
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

                # Reclassify if different type and higher/equal confidence
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
        self._print_stats(stats, reclassifications, dry_run)

        return stats, reclassifications

    def _print_stats(self, stats: Dict, reclassifications: List, dry_run: bool):
        """Print reclassification statistics"""
        logger.info("RECLASSIFICATION SUMMARY:")
        logger.info(f"  Total Documents: {stats['total']}")
        logger.info(f"  Reclassified: {stats['reclassified']}")
        logger.info(f"  Unchanged: {stats['unchanged']}")
        logger.info(f"  Improvement: {(stats['reclassified']/stats['total']*100):.1f}%")
        logger.info("")

        if stats['by_old_type']:
            logger.info("RECLASSIFICATIONS BY OLD TYPE:")
            for old_type, count in sorted(stats['by_old_type'].items(), key=lambda x: x[1], reverse=True)[:15]:
                logger.info(f"  {old_type:35} {count:5} documents")
            logger.info("")

        if stats['by_new_type']:
            logger.info("RECLASSIFICATIONS BY NEW TYPE:")
            for new_type, count in sorted(stats['by_new_type'].items(), key=lambda x: x[1], reverse=True)[:15]:
                logger.info(f"  {new_type:35} {count:5} documents")
            logger.info("")

        if stats['by_reason']:
            logger.info("TOP RECLASSIFICATION REASONS:")
            for reason, count in sorted(stats['by_reason'].items(), key=lambda x: x[1], reverse=True)[:15]:
                logger.info(f"  {reason:55} {count:5} documents")
            logger.info("")

        if reclassifications:
            logger.info("SAMPLE RECLASSIFICATIONS (first 30):")
            for reclass in reclassifications[:30]:
                logger.info(f"  {reclass['old_type']:25} → {reclass['new_type']:30} | {reclass['filename'][:45]}")
            if len(reclassifications) > 30:
                logger.info(f"  ... and {len(reclassifications)-30} more")
            logger.info("")

        if dry_run:
            logger.info("[DRY RUN] No changes made to database")
            logger.info("Run with --execute to apply changes")
        else:
            logger.info(f"✓ Successfully reclassified {stats['reclassified']} documents")

    def close(self):
        self.conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Comprehensive CogniSys reclassification")
    parser.add_argument('--db', type=str, default='cognisys/data/training/cognisys_ml.db')
    parser.add_argument('--execute', action='store_true')

    args = parser.parse_args()

    reclassifier = ComprehensiveReclassifier(args.db)
    try:
        stats, reclassifications = reclassifier.reclassify_all(dry_run=not args.execute)
    finally:
        reclassifier.close()
