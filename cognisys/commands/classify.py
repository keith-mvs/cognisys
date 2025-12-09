"""
CogniSys Classify Command
Classifies pending files using ML model and pattern matching
"""

import sqlite3
import pickle
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


def load_ml_model(model_path, vectorizer_path, label_mappings_path):
    """Load trained ML model, vectorizer, and label mappings"""
    try:
        with open(model_path, 'rb') as f:
            model = pickle.load(f)

        with open(vectorizer_path, 'rb') as f:
            vectorizer = pickle.load(f)

        with open(label_mappings_path, 'rb') as f:
            label_mappings = pickle.load(f)

        return model, vectorizer, label_mappings

    except FileNotFoundError as e:
        logger.warning(f"ML model not found: {e}")
        return None, None, None


def classify_with_ml(filepath, model, vectorizer, label_mappings, confidence_threshold=0.70):
    """
    Classify a file using ML model.

    Returns:
        tuple: (document_type, confidence, method)
    """
    if model is None:
        return None, 0.0, 'ml_unavailable'

    # Extract features from filename
    filename = Path(filepath).name

    try:
        # Vectorize filename
        features = vectorizer.transform([filename])

        # Predict
        prediction = model.predict(features)[0]
        probabilities = model.predict_proba(features)[0]
        confidence = max(probabilities)

        # Get document type from label mapping
        # Handle both dict and nested dict structures
        if isinstance(label_mappings, dict) and 'reverse_mapping' in label_mappings:
            reverse_mappings = label_mappings['reverse_mapping']
        elif isinstance(label_mappings, dict) and 'label_mapping' in label_mappings:
            # Create reverse from label_mapping
            reverse_mappings = {v: k for k, v in label_mappings['label_mapping'].items()}
        else:
            # Assume it's already the mapping
            reverse_mappings = {v: k for k, v in label_mappings.items()}

        document_type = reverse_mappings.get(prediction, 'general_document')

        if confidence >= confidence_threshold:
            return document_type, confidence, 'ml_model'
        else:
            return None, confidence, 'ml_low_confidence'

    except Exception as e:
        logger.error(f"ML classification failed for {filepath}: {e}")
        return None, 0.0, 'ml_error'


def classify_with_patterns(filepath, classification_rules):
    """
    Classify a file using pattern matching rules.

    Args:
        filepath: Path to file
        classification_rules: List of (rule_name, pattern, target_type, priority) tuples

    Returns:
        tuple: (document_type, confidence, method, rule_name)
    """
    import re

    filename = Path(filepath).name.lower()

    # Sort rules by priority (highest first)
    sorted_rules = sorted(classification_rules, key=lambda x: x[3], reverse=True)

    for rule_name, pattern, target_type, priority in sorted_rules:
        if pattern and re.search(pattern, filename, re.IGNORECASE):
            # Pattern match gives high confidence (0.95)
            return target_type, 0.95, 'pattern', rule_name

    return None, 0.0, 'no_pattern_match', None


def classify_pending_files(db_path, config, dry_run=False):
    """
    Classify all files with canonical_state='pending'.

    Args:
        db_path: Path to SQLite database
        config: Configuration dict
        dry_run: If True, don't update database

    Returns:
        dict with statistics
    """
    logger.info("Classifying pending files...")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Load ML model
    model, vectorizer, label_mappings = load_ml_model(
        config['cognisys']['ml_model_path'],
        config['cognisys']['tfidf_vectorizer_path'],
        config['cognisys']['label_mappings_path']
    )

    if model is None:
        logger.warning("ML model not available, using pattern matching only")

    # Load classification rules from database
    cursor.execute("""
        SELECT rule_name, rule_pattern, target_document_type, priority
        FROM classification_rules
        WHERE active = 1 AND rule_type = 'pattern'
        ORDER BY priority DESC
    """)
    classification_rules = cursor.fetchall()

    # Get pending files
    cursor.execute("""
        SELECT file_id, original_path, canonical_path
        FROM file_registry
        WHERE canonical_state = 'pending'
    """)

    pending_files = cursor.fetchall()
    logger.info(f"Found {len(pending_files)} pending files")

    stats = {
        'processed': 0,
        'classified_ml': 0,
        'classified_pattern': 0,
        'requires_review': 0,
        'errors': 0
    }

    confidence_threshold = config['cognisys'].get('confidence_threshold', 0.70)

    for file_id, original_path, canonical_path in pending_files:
        stats['processed'] += 1

        try:
            # Try ML classification first
            document_type, confidence, method = classify_with_ml(
                original_path,
                model,
                vectorizer,
                label_mappings,
                confidence_threshold
            )

            # If ML failed or low confidence, try pattern matching
            if document_type is None:
                document_type, confidence, method, rule_name = classify_with_patterns(
                    original_path,
                    classification_rules
                )
            else:
                rule_name = None

            # If still no classification, mark for review
            if document_type is None:
                document_type = 'general_document'
                confidence = 0.0
                method = 'fallback'
                requires_review = 1
                stats['requires_review'] += 1
            else:
                requires_review = 0
                if method == 'ml_model':
                    stats['classified_ml'] += 1
                elif method == 'pattern':
                    stats['classified_pattern'] += 1

            logger.info(f"Classified: {Path(original_path).name} -> {document_type} ({confidence:.2f}, {method})")

            if not dry_run:
                cursor.execute("""
                    UPDATE file_registry
                    SET document_type = ?,
                        confidence = ?,
                        classification_method = ?,
                        requires_review = ?,
                        canonical_state = 'classified',
                        updated_at = datetime('now')
                    WHERE file_id = ?
                """, (document_type, confidence, method, requires_review, file_id))

        except Exception as e:
            logger.error(f"Error classifying {original_path}: {e}")
            stats['errors'] += 1

    if not dry_run:
        conn.commit()

    conn.close()

    # Print summary
    logger.info("")
    logger.info("="*80)
    logger.info("CLASSIFICATION SUMMARY")
    logger.info("="*80)
    logger.info(f"  Files processed: {stats['processed']}")
    logger.info(f"  Classified by ML: {stats['classified_ml']}")
    logger.info(f"  Classified by pattern: {stats['classified_pattern']}")
    logger.info(f"  Requires review: {stats['requires_review']}")
    logger.info(f"  Errors: {stats['errors']}")

    if dry_run:
        logger.info("\nDRY RUN - No files were classified")

    return stats
