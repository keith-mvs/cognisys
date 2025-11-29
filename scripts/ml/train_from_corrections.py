#!/usr/bin/env python3
"""
IFMOS: Train ML Classifier from Existing Classifications
Learn from your 2,482 manually corrected documents
"""

import sys
import sqlite3
import logging
import pickle
from pathlib import Path
from typing import List, Dict, Tuple
from collections import Counter

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ifmos.ml.utils.content_extractor import ContentExtractor
from ifmos.ml.nlp.text_analyzer import TextAnalyzer

# ML imports
try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.model_selection import train_test_split, cross_val_score
    from sklearn.metrics import classification_report, accuracy_score
    import numpy as np
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MLTrainer:
    """Train ML classifier from existing classified documents"""

    def __init__(self, db_path: str):
        if not SKLEARN_AVAILABLE:
            raise ImportError("scikit-learn not installed. Run: pip install scikit-learn")

        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()

        self.content_extractor = ContentExtractor()
        self.text_analyzer = TextAnalyzer()

        # ML components
        self.vectorizer = TfidfVectorizer(max_features=500, ngram_range=(1, 2))
        self.classifier = RandomForestClassifier(n_estimators=100, random_state=42)

        self.label_mapping = {}  # document_type -> int
        self.reverse_mapping = {}  # int -> document_type

    def load_training_data(self, min_confidence: float = 0.70, min_samples_per_class: int = 5) -> Tuple[List[Dict], List[str]]:
        """
        Load classified documents from database

        Args:
            min_confidence: Minimum confidence threshold
            min_samples_per_class: Minimum samples needed per class to include it

        Returns:
            (documents, labels)
        """
        logger.info("Loading training data from database...")

        # Get all classified documents
        self.cursor.execute("""
            SELECT id, file_path, file_name, document_type, confidence, extracted_text
            FROM documents
            WHERE document_type IS NOT NULL
            AND document_type != 'unknown'
            AND confidence >= ?
            ORDER BY document_type, id
        """, (min_confidence,))

        rows = self.cursor.fetchall()
        logger.info(f"Found {len(rows)} classified documents (confidence >= {min_confidence})")

        # Count samples per class
        type_counts = Counter(row[3] for row in rows)
        logger.info(f"Found {len(type_counts)} document types")

        # Filter out classes with too few samples
        valid_types = {doc_type for doc_type, count in type_counts.items() if count >= min_samples_per_class}
        logger.info(f"Keeping {len(valid_types)} types with >= {min_samples_per_class} samples")

        # Filter rows
        filtered_rows = [row for row in rows if row[3] in valid_types]
        logger.info(f"Training on {len(filtered_rows)} documents across {len(valid_types)} classes")

        # Show distribution
        logger.info("\nClass distribution:")
        type_counts_filtered = Counter(row[3] for row in filtered_rows)
        for doc_type, count in type_counts_filtered.most_common(15):
            logger.info(f"  {doc_type:40} {count:5} samples")

        return filtered_rows, list(valid_types)

    def extract_features(self, documents: List[Tuple]) -> Tuple[List[str], List[str]]:
        """
        Extract text features from documents

        Args:
            documents: List of database rows

        Returns:
            (texts, labels)
        """
        logger.info("\nExtracting features...")

        texts = []
        labels = []
        extracted = 0

        for row in documents:
            doc_id, file_path, file_name, doc_type, confidence, extracted_text = row

            # Combine filename + extracted content
            text_features = []

            # Add filename (重複3次 to increase weight)
            text_features.append(file_name.lower())
            text_features.append(file_name.lower())
            text_features.append(file_name.lower())

            # Try to extract PDF content if not already extracted
            if file_path.endswith('.pdf'):
                if extracted_text:
                    # Use cached extraction
                    text_features.append(extracted_text[:2000])  # First 2000 chars
                else:
                    # Extract content
                    try:
                        result = self.content_extractor.extract_content(file_path)
                        if result['success'] and result['text']:
                            content = result['text'][:2000]  # First 2000 chars
                            text_features.append(content.lower())
                            extracted += 1
                    except Exception as e:
                        pass  # Skip extraction errors

            # Combine all text
            combined_text = ' '.join(text_features)

            if combined_text.strip():
                texts.append(combined_text)
                labels.append(doc_type)

        logger.info(f"Extracted {len(texts)} feature vectors")
        logger.info(f"Fresh extractions: {extracted}")

        return texts, labels

    def train(self, texts: List[str], labels: List[str]) -> Dict:
        """
        Train the classifier

        Args:
            texts: List of text features
            labels: List of document type labels

        Returns:
            Training statistics
        """
        logger.info("\n" + "=" * 80)
        logger.info("TRAINING ML CLASSIFIER")
        logger.info("=" * 80)

        # Create label mapping
        unique_labels = sorted(set(labels))
        self.label_mapping = {label: idx for idx, label in enumerate(unique_labels)}
        self.reverse_mapping = {idx: label for label, idx in self.label_mapping.items()}

        logger.info(f"Classes: {len(unique_labels)}")
        logger.info(f"Samples: {len(texts)}")

        # Convert labels to integers
        y = np.array([self.label_mapping[label] for label in labels])

        # Split data
        X_train_text, X_test_text, y_train, y_test = train_test_split(
            texts, y, test_size=0.2, random_state=42, stratify=y
        )

        logger.info(f"\nTraining set: {len(X_train_text)} samples")
        logger.info(f"Test set: {len(X_test_text)} samples")

        # Vectorize
        logger.info("\nVectorizing text...")
        X_train = self.vectorizer.fit_transform(X_train_text)
        X_test = self.vectorizer.transform(X_test_text)

        logger.info(f"Feature dimensions: {X_train.shape[1]}")

        # Train
        logger.info("\nTraining Random Forest...")
        self.classifier.fit(X_train, y_train)

        # Evaluate
        logger.info("\nEvaluating...")

        # Training accuracy
        train_pred = self.classifier.predict(X_train)
        train_acc = accuracy_score(y_train, train_pred)

        # Test accuracy
        test_pred = self.classifier.predict(X_test)
        test_acc = accuracy_score(y_test, test_pred)

        # Cross-validation
        cv_scores = cross_val_score(self.classifier, X_train, y_train, cv=5)

        logger.info("\n" + "=" * 80)
        logger.info("TRAINING RESULTS")
        logger.info("=" * 80)
        logger.info(f"Training Accuracy: {train_acc:.3f}")
        logger.info(f"Test Accuracy: {test_acc:.3f}")
        logger.info(f"Cross-Val Accuracy: {cv_scores.mean():.3f} (+/- {cv_scores.std():.3f})")

        # Detailed classification report
        logger.info("\nPer-Class Performance:")
        test_labels_str = [self.reverse_mapping[label] for label in y_test]
        pred_labels_str = [self.reverse_mapping[pred] for pred in test_pred]

        print(classification_report(test_labels_str, pred_labels_str, zero_division=0))

        return {
            'train_accuracy': train_acc,
            'test_accuracy': test_acc,
            'cv_mean': cv_scores.mean(),
            'cv_std': cv_scores.std(),
            'n_classes': len(unique_labels),
            'n_features': X_train.shape[1]
        }

    def save_model(self, output_dir: str):
        """
        Save trained model and vectorizer

        Args:
            output_dir: Directory to save models
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Save classifier
        classifier_path = output_path / "random_forest_classifier.pkl"
        with open(classifier_path, 'wb') as f:
            pickle.dump(self.classifier, f)

        # Save vectorizer
        vectorizer_path = output_path / "tfidf_vectorizer.pkl"
        with open(vectorizer_path, 'wb') as f:
            pickle.dump(self.vectorizer, f)

        # Save label mappings
        mappings_path = output_path / "label_mappings.pkl"
        with open(mappings_path, 'wb') as f:
            pickle.dump({
                'label_mapping': self.label_mapping,
                'reverse_mapping': self.reverse_mapping
            }, f)

        logger.info(f"\nModels saved to: {output_path}")
        logger.info(f"  - {classifier_path.name}")
        logger.info(f"  - {vectorizer_path.name}")
        logger.info(f"  - {mappings_path.name}")

    def close(self):
        self.conn.close()


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--db', default=None)
    parser.add_argument('--output', default=None, help='Output directory for trained models')
    parser.add_argument('--min-confidence', type=float, default=0.70, help='Minimum confidence threshold')
    parser.add_argument('--min-samples', type=int, default=5, help='Minimum samples per class')

    args = parser.parse_args()

    if args.db is None:
        args.db = PROJECT_ROOT / "ifmos" / "data" / "training" / "ifmos_ml.db"

    if args.output is None:
        args.output = PROJECT_ROOT / "ifmos" / "models" / "trained"

    logger.info("=" * 80)
    logger.info("IFMOS ML CLASSIFIER TRAINING")
    logger.info("=" * 80)
    logger.info(f"Database: {args.db}")
    logger.info(f"Output: {args.output}")
    logger.info("=" * 80)

    trainer = MLTrainer(str(args.db))

    try:
        # Load data
        documents, valid_types = trainer.load_training_data(
            min_confidence=args.min_confidence,
            min_samples_per_class=args.min_samples
        )

        if len(documents) < 100:
            logger.error("\nNot enough training data!")
            logger.error(f"Found {len(documents)} documents, need at least 100")
            return

        # Extract features
        texts, labels = trainer.extract_features(documents)

        # Train
        stats = trainer.train(texts, labels)

        # Save model
        trainer.save_model(args.output)

        logger.info("\n" + "=" * 80)
        logger.info("TRAINING COMPLETE!")
        logger.info("=" * 80)
        logger.info(f"Model Accuracy: {stats['test_accuracy']:.1%}")
        logger.info(f"Ready for production use")

    finally:
        trainer.close()


if __name__ == "__main__":
    main()
