#!/usr/bin/env python3
"""
Retrain ML model with new training data from classified sample
Combines existing data with new high-confidence classifications
"""

import sys
import pickle
import pandas as pd
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def load_training_data():
    """Load training data from CSV"""

    training_csv = Path('.ifmos/training_data.csv')

    if not training_csv.exists():
        logger.error("Training data not found: .ifmos/training_data.csv")
        logger.error("Run classify_training_sample.py first")
        return None

    df = pd.read_csv(training_csv)
    logger.info(f"Loaded {len(df)} training examples from CSV")

    return df


def prepare_features(df):
    """Prepare features from filenames"""

    # Use filenames as features
    filenames = df['filename'].tolist()
    labels = df['doc_type'].tolist()

    logger.info(f"Total samples: {len(filenames)}")
    logger.info(f"Unique categories: {df['doc_type'].nunique()}")

    # Show category distribution
    logger.info("\nCategory distribution:")
    for category, count in df['doc_type'].value_counts().head(15).items():
        pct = count / len(df) * 100
        logger.info(f"  {category:35} {count:4} ({pct:5.1f}%)")

    return filenames, labels


def train_model(filenames, labels, test_size=0.2):
    """Train Random Forest classifier"""

    logger.info("\n" + "=" * 80)
    logger.info("TRAINING ML MODEL")
    logger.info("=" * 80)

    # Count samples per class
    from collections import Counter
    label_counts = Counter(labels)

    # Remove classes with only 1 sample (can't stratify)
    rare_classes = [label for label, count in label_counts.items() if count < 2]
    if rare_classes:
        logger.warning(f"\nRemoving {len(rare_classes)} rare classes with <2 samples:")
        for label in rare_classes:
            logger.warning(f"  - {label}")

        # Filter out rare classes
        filtered_data = [(f, l) for f, l in zip(filenames, labels) if l not in rare_classes]
        filenames = [f for f, l in filtered_data]
        labels = [l for f, l in filtered_data]

        logger.info(f"\nAfter filtering: {len(filenames)} samples, {len(set(labels))} classes")

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        filenames, labels, test_size=test_size, random_state=42, stratify=labels
    )

    logger.info(f"\nTraining set: {len(X_train)} samples")
    logger.info(f"Test set: {len(X_test)} samples")

    # Vectorize filenames (TF-IDF)
    logger.info("\nVectorizing filenames...")
    vectorizer = TfidfVectorizer(
        analyzer='char_wb',  # Character n-grams
        ngram_range=(2, 4),  # 2-4 character n-grams
        max_features=2000,
        lowercase=True
    )

    X_train_vec = vectorizer.fit_transform(X_train)
    X_test_vec = vectorizer.transform(X_test)

    logger.info(f"Feature dimensions: {X_train_vec.shape[1]}")

    # Train Random Forest
    logger.info("\nTraining Random Forest classifier...")
    clf = RandomForestClassifier(
        n_estimators=200,  # More trees for better accuracy
        max_depth=30,
        min_samples_split=5,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1  # Use all CPU cores
    )

    clf.fit(X_train_vec, y_train)

    # Evaluate
    logger.info("\nEvaluating model...")
    y_pred = clf.predict(X_test_vec)
    accuracy = accuracy_score(y_test, y_pred)

    logger.info(f"\nTest Accuracy: {accuracy:.2%}")

    # Detailed report
    logger.info("\nClassification Report:")
    print(classification_report(y_test, y_pred, zero_division=0))

    return clf, vectorizer, accuracy


def save_model(clf, vectorizer, accuracy):
    """Save trained model"""

    model_dir = Path('ifmos/models/trained')
    model_dir.mkdir(parents=True, exist_ok=True)

    # Create label mappings
    label_mapping = {label: idx for idx, label in enumerate(clf.classes_)}
    reverse_mapping = {idx: label for label, idx in label_mapping.items()}

    label_mappings = {
        'label_mapping': label_mapping,
        'reverse_mapping': reverse_mapping,
        'classes': list(clf.classes_),
        'n_classes': len(clf.classes_),
        'accuracy': accuracy
    }

    # Save model
    with open(model_dir / 'random_forest_classifier.pkl', 'wb') as f:
        pickle.dump(clf, f)
    logger.info("✓ Model saved to ifmos/models/trained/random_forest_classifier.pkl")

    # Save vectorizer
    with open(model_dir / 'tfidf_vectorizer.pkl', 'wb') as f:
        pickle.dump(vectorizer, f)
    logger.info("✓ Vectorizer saved to ifmos/models/trained/tfidf_vectorizer.pkl")

    # Save label mappings
    with open(model_dir / 'label_mappings.pkl', 'wb') as f:
        pickle.dump(label_mappings, f)
    logger.info("✓ Label mappings saved to ifmos/models/trained/label_mappings.pkl")

    logger.info(f"\nModel training complete! Test accuracy: {accuracy:.2%}")


def main():
    print("=" * 80)
    print("ML MODEL RETRAINING")
    print("=" * 80)
    print()

    # Load data
    df = load_training_data()
    if df is None:
        return

    # Prepare features
    filenames, labels = prepare_features(df)

    # Train model
    clf, vectorizer, accuracy = train_model(filenames, labels)

    # Save model
    save_model(clf, vectorizer, accuracy)

    print("\n" + "=" * 80)
    print("TRAINING COMPLETE")
    print("=" * 80)
    print(f"Categories: {len(set(labels))}")
    print(f"Samples: {len(filenames)}")
    print(f"Test Accuracy: {accuracy:.2%}")
    print("\nThe new model is ready to use!")
    print("=" * 80)


if __name__ == '__main__':
    main()
