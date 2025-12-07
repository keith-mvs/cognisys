#!/usr/bin/env python3
"""
IFMOS: ML-Based Classification with PDF Content Extraction
Uses actual document content + ML training for accurate classification
"""

import sys
import sqlite3
import logging
import re
from pathlib import Path
from typing import Dict, Optional, Tuple
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from cognisys.ml.utils.content_extractor import ContentExtractor
from cognisys.ml.nlp.text_analyzer import TextAnalyzer
from scripts.ml.comprehensive_reclassify import ComprehensiveReclassifier

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MLContentClassifier:
    """
    ML-based classifier that uses PDF content extraction
    Combines pattern matching + content analysis + ML
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()

        # Initialize extractors
        self.content_extractor = ContentExtractor()
        self.text_analyzer = TextAnalyzer()
        self.pattern_classifier = ComprehensiveReclassifier(db_path)

        # Content-based classification rules
        self.content_rules = self._build_content_rules()

    def _build_content_rules(self) -> list:
        """
        Build content-based classification rules
        These look at actual PDF text, not just filenames
        """
        return [
            # Financial Documents
            {
                'name': 'Invoice Detection',
                'keywords': ['invoice', 'bill to', 'amount due', 'payment terms', 'total amount'],
                'required': 2,
                'document_type': 'financial_invoice',
                'confidence': 0.95
            },
            {
                'name': 'Bank Statement Detection',
                'keywords': ['account number', 'statement period', 'beginning balance', 'ending balance', 'deposits'],
                'required': 3,
                'document_type': 'financial_statement',
                'confidence': 0.95
            },
            {
                'name': 'Tax Document Detection',
                'keywords': ['form 1040', 'form w-2', 'tax year', 'internal revenue', 'social security number'],
                'required': 2,
                'document_type': 'tax_document',
                'confidence': 0.98
            },

            # Legal Documents
            {
                'name': 'Contract Detection',
                'keywords': ['this agreement', 'whereas', 'parties agree', 'in witness whereof', 'executed'],
                'required': 3,
                'document_type': 'legal_contract',
                'confidence': 0.90
            },
            {
                'name': 'Court Document Detection',
                'keywords': ['court', 'docket', 'plaintiff', 'defendant', 'case number', 'judicial'],
                'required': 3,
                'document_type': 'legal_court',
                'confidence': 0.92
            },

            # Medical Documents
            {
                'name': 'Medical Record Detection',
                'keywords': ['patient', 'diagnosis', 'physician', 'medical history', 'prescription', 'vital signs'],
                'required': 3,
                'document_type': 'medical',
                'confidence': 0.93
            },

            # Automotive Documents
            {
                'name': 'Vehicle Service Detection',
                'keywords': ['vehicle', 'service', 'repair', 'maintenance', 'mileage', 'diagnostic'],
                'required': 3,
                'document_type': 'automotive_service',
                'confidence': 0.88
            },
            {
                'name': 'Vehicle Manual Detection',
                'keywords': ['owner manual', 'vehicle operation', 'maintenance schedule', 'specifications', 'warranty'],
                'required': 2,
                'document_type': 'automotive_technical',
                'confidence': 0.90
            },

            # HR Documents
            {
                'name': 'Resume Detection',
                'keywords': ['experience', 'education', 'skills', 'objective', 'references', 'employment'],
                'required': 3,
                'document_type': 'hr_resume',
                'confidence': 0.85
            },

            # Technical Documents
            {
                'name': 'Technical Manual Detection',
                'keywords': ['technical specifications', 'installation', 'configuration', 'troubleshooting', 'system requirements'],
                'required': 3,
                'document_type': 'technical_manual',
                'confidence': 0.87
            }
        ]

    def classify_document(self, doc_id: int, file_path: str) -> Dict:
        """
        Classify a document using multi-stage approach:
        1. Filename pattern matching
        2. PDF content extraction
        3. Content-based keyword detection
        4. ML-based prediction (future)

        Args:
            doc_id: Document ID in database
            file_path: Path to file

        Returns:
            {
                'document_type': str,
                'confidence': float,
                'method': str,
                'metadata': Dict,
                'success': bool
            }
        """
        file_path = Path(file_path)
        filename = file_path.name

        logger.info(f"Classifying: {filename}")

        # Stage 1: Filename pattern matching
        filename_result = self.pattern_classifier.analyze_filename(filename)

        if filename_result:
            doc_type, confidence, reason = filename_result
            if confidence >= 0.90:  # High confidence from filename alone
                logger.info(f"  -> Filename match: {doc_type} ({confidence:.2f})")
                return {
                    'document_type': doc_type,
                    'confidence': confidence,
                    'method': 'filename_pattern',
                    'reason': reason,
                    'metadata': {},
                    'success': True
                }

        # Stage 2: Extract PDF content
        if file_path.suffix.lower() == '.pdf':
            try:
                extraction_result = self.content_extractor.extract_content(str(file_path))

                if extraction_result['success'] and extraction_result['text']:
                    text = extraction_result['text'].lower()

                    # Stage 3: Content-based classification
                    content_result = self._classify_by_content(text)

                    if content_result:
                        logger.info(f"  -> Content match: {content_result['document_type']} ({content_result['confidence']:.2f})")

                        # Extract metadata
                        metadata = self._extract_metadata(text, content_result['document_type'])
                        content_result['metadata'] = metadata

                        return content_result

                    # No content match, but we have text - analyze it
                    analysis = self.text_analyzer.analyze_text(extraction_result['text'][:5000])  # First 5000 chars

                    # Use text analysis to guess document type
                    inferred_type = self._infer_type_from_analysis(analysis)
                    if inferred_type:
                        logger.info(f"  -> Text analysis: {inferred_type} (0.60)")
                        return {
                            'document_type': inferred_type,
                            'confidence': 0.60,
                            'method': 'text_analysis',
                            'metadata': {},
                            'success': True
                        }

            except Exception as e:
                logger.error(f"  -> Content extraction failed: {e}")

        # Fallback: Use filename result if available
        if filename_result:
            doc_type, confidence, reason = filename_result
            logger.info(f"  -> Fallback to filename: {doc_type} ({confidence:.2f})")
            return {
                'document_type': doc_type,
                'confidence': confidence,
                'method': 'filename_fallback',
                'reason': reason,
                'metadata': {},
                'success': True
            }

        # Last resort: generic classification
        logger.info(f"  -> No match, using general_document")
        return {
            'document_type': 'general_document',
            'confidence': 0.50,
            'method': 'fallback',
            'metadata': {},
            'success': True
        }

    def _classify_by_content(self, text: str) -> Optional[Dict]:
        """
        Classify document based on content keywords

        Args:
            text: Lowercase document text

        Returns:
            Classification result or None
        """
        best_match = None
        best_score = 0

        for rule in self.content_rules:
            # Count keyword matches
            matches = sum(1 for keyword in rule['keywords'] if keyword in text)

            if matches >= rule['required']:
                score = matches / len(rule['keywords'])  # Ratio of keywords found

                if score > best_score:
                    best_score = score
                    best_match = {
                        'document_type': rule['document_type'],
                        'confidence': rule['confidence'] * score,  # Adjust confidence by match ratio
                        'method': 'content_keywords',
                        'rule': rule['name'],
                        'keywords_matched': matches,
                        'success': True
                    }

        return best_match

    def _infer_type_from_analysis(self, analysis: Dict) -> Optional[str]:
        """
        Infer document type from text analysis features

        Args:
            analysis: Text analysis result from TextAnalyzer

        Returns:
            Inferred document type or None
        """
        features = analysis.get('features', {})
        entities = analysis.get('entities', [])

        # Check for high money/date mentions (likely financial)
        if features.get('money_count', 0) > 3 and features.get('date_count', 0) > 2:
            return 'financial_invoice'

        # Check for many person names (likely HR or legal)
        if features.get('person_count', 0) > 5:
            return 'hr_resume'

        # Check for technical jargon
        if features.get('noun_ratio', 0) > 0.4:  # High noun density
            return 'technical_documentation'

        return None

    def _extract_metadata(self, text: str, document_type: str) -> Dict:
        """
        Extract metadata from document text based on type

        Args:
            text: Document text
            document_type: Classified document type

        Returns:
            Dictionary of extracted metadata
        """
        metadata = {}

        # Extract dates
        date_pattern = r'\b(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}[-/]\d{1,2}[-/]\d{1,2})\b'
        dates = re.findall(date_pattern, text)
        if dates:
            metadata['dates'] = dates[:5]  # First 5 dates

        # Document-specific extraction
        if 'financial' in document_type:
            # Extract amounts
            amount_pattern = r'\$\s?([\d,]+\.?\d{0,2})'
            amounts = re.findall(amount_pattern, text)
            if amounts:
                metadata['amounts'] = amounts[:3]

            # Extract invoice numbers
            invoice_pattern = r'(?:invoice|inv|bill)[\s#:]*([A-Z0-9-]+)'
            invoices = re.findall(invoice_pattern, text, re.IGNORECASE)
            if invoices:
                metadata['invoice_numbers'] = invoices[:2]

        elif 'automotive' in document_type:
            # Extract VIN
            vin_pattern = r'\b[A-HJ-NPR-Z0-9]{17}\b'
            vins = re.findall(vin_pattern, text)
            if vins:
                metadata['vin'] = vins[0]

            # Extract mileage
            mileage_pattern = r'(\d{1,3},?\d{3,6})\s*(?:miles|km|mi)'
            mileages = re.findall(mileage_pattern, text, re.IGNORECASE)
            if mileages:
                metadata['mileage'] = mileages[0]

        elif 'legal' in document_type:
            # Extract case numbers
            case_pattern = r'(?:case|docket)[\s#:]*([A-Z0-9-]+)'
            cases = re.findall(case_pattern, text, re.IGNORECASE)
            if cases:
                metadata['case_numbers'] = cases[:2]

        return metadata

    def classify_batch(self, doc_ids: list, update_db: bool = True) -> Dict:
        """
        Classify multiple documents

        Args:
            doc_ids: List of document IDs
            update_db: Whether to update database with results

        Returns:
            Statistics dictionary
        """
        stats = {
            'total': len(doc_ids),
            'classified': 0,
            'failed': 0,
            'by_method': {},
            'by_type': {}
        }

        for doc_id in doc_ids:
            # Get file path
            self.cursor.execute("SELECT file_path FROM documents WHERE id = ?", (doc_id,))
            row = self.cursor.fetchone()

            if not row:
                stats['failed'] += 1
                continue

            file_path = row[0]

            try:
                result = self.classify_document(doc_id, file_path)

                if result['success']:
                    stats['classified'] += 1

                    # Track methods used
                    method = result['method']
                    stats['by_method'][method] = stats['by_method'].get(method, 0) + 1

                    # Track document types
                    doc_type = result['document_type']
                    stats['by_type'][doc_type] = stats['by_type'].get(doc_type, 0) + 1

                    # Update database
                    if update_db:
                        self.cursor.execute("""
                            UPDATE documents
                            SET document_type = ?, confidence = ?, extracted_text = ?
                            WHERE id = ?
                        """, (
                            result['document_type'],
                            result['confidence'],
                            str(result.get('metadata', {}))[:1000],  # Store first 1000 chars of metadata
                            doc_id
                        ))
                else:
                    stats['failed'] += 1

            except Exception as e:
                logger.error(f"Error classifying doc {doc_id}: {e}")
                stats['failed'] += 1

        if update_db:
            self.conn.commit()

        return stats

    def close(self):
        self.pattern_classifier.close()
        self.conn.close()


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--db', default=None)
    parser.add_argument('--limit', type=int, help='Limit number of files to process')
    parser.add_argument('--reprocess', action='store_true', help='Re-process all files (not just unclassified)')

    args = parser.parse_args()

    if args.db is None:
        args.db = PROJECT_ROOT / "ifmos" / "data" / "training" / "ifmos_ml.db"

    logger.info("=" * 80)
    logger.info("IFMOS ML CONTENT-BASED CLASSIFICATION")
    logger.info("=" * 80)
    logger.info(f"Database: {args.db}")
    logger.info("=" * 80)

    classifier = MLContentClassifier(str(args.db))

    try:
        # Get documents to classify
        if args.reprocess:
            # Re-process everything
            classifier.cursor.execute("SELECT id FROM documents ORDER BY id")
        else:
            # Only unclassified
            classifier.cursor.execute("""
                SELECT id FROM documents
                WHERE document_type IS NULL OR document_type = 'general_document'
                ORDER BY id
            """)

        doc_ids = [row[0] for row in classifier.cursor.fetchall()]

        if args.limit:
            doc_ids = doc_ids[:args.limit]

        logger.info(f"\nProcessing {len(doc_ids)} documents...")
        logger.info("-" * 80)

        # Classify
        stats = classifier.classify_batch(doc_ids, update_db=True)

        # Print results
        logger.info("\n" + "=" * 80)
        logger.info("CLASSIFICATION RESULTS")
        logger.info("=" * 80)
        logger.info(f"Total Processed: {stats['total']}")
        logger.info(f"Successfully Classified: {stats['classified']}")
        logger.info(f"Failed: {stats['failed']}")

        logger.info("\nClassification Methods:")
        for method, count in sorted(stats['by_method'].items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  {method:30} {count:5} files")

        logger.info("\nDocument Types:")
        for doc_type, count in sorted(stats['by_type'].items(), key=lambda x: x[1], reverse=True)[:15]:
            logger.info(f"  {doc_type:40} {count:5} files")

    finally:
        classifier.close()

    logger.info("\n" + "=" * 80)
    logger.info("COMPLETE")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
