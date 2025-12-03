"""
Train ensemble classifier (Random Forest + SVM) for document classification.
Uses the same training data as DistilBERT for fair comparison.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import pickle
import json
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier
from sklearn.svm import SVC
from sklearn.ensemble import VotingClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, accuracy_score, confusion_matrix
from sklearn.preprocessing import LabelEncoder
from sklearn.utils.class_weight import compute_class_weight
import warnings
warnings.filterwarnings('ignore')

from ifmos.ml.content_extraction import ContentExtractor


class EnsembleTrainer:
    """Train and evaluate ensemble classifier."""

    def __init__(
        self,
        max_features: int = 1000,
        min_samples: int = 10,
        test_size: float = 0.15,
        random_state: int = 42
    ):
        self.max_features = max_features
        self.min_samples = min_samples
        self.test_size = test_size
        self.random_state = random_state

        # Models
        self.vectorizer = TfidfVectorizer(
            max_features=max_features,
            ngram_range=(1, 3),
            min_df=2,
            max_df=0.9,
            stop_words='english',
            sublinear_tf=True
        )

        self.label_encoder = LabelEncoder()
        self.ensemble = None
        self.class_weights = None

        # Content extractor
        self.extractor = ContentExtractor(max_chars=2000)

        print(f"Ensemble Trainer initialized")
        print(f"  TF-IDF features: {max_features}")
        print(f"  Min samples per class: {min_samples}")
        print(f"  Test split: {test_size}")

    def load_training_data(self, csv_path: str) -> pd.DataFrame:
        """Load and filter training data."""
        print(f"\nLoading training data from: {csv_path}")

        df = pd.read_csv(csv_path)
        print(f"  Total samples: {len(df):,}")

        # Filter classes with minimum samples
        class_counts = df['document_type'].value_counts()
        valid_classes = class_counts[class_counts >= self.min_samples].index

        df_filtered = df[df['document_type'].isin(valid_classes)]

        removed = len(df) - len(df_filtered)
        print(f"  Removed {removed:,} samples from classes with <{self.min_samples} examples")
        print(f"  Final samples: {len(df_filtered):,}")
        print(f"  Classes: {len(valid_classes)}")

        return df_filtered

    def extract_content(self, file_path: str) -> str:
        """Extract text content from file."""
        try:
            path = Path(file_path)
            if not path.exists():
                return path.name

            result = self.extractor.extract(path)
            content = result.get('content', '')

            if not content:
                content = path.name

            return content
        except Exception as e:
            return Path(file_path).name

    def prepare_data(self, df: pd.DataFrame) -> tuple:
        """Extract content and prepare train/test splits."""
        print(f"\nExtracting content from {len(df):,} files...")

        texts = []
        labels = []

        for idx, row in df.iterrows():
            content = self.extract_content(row['file_path'])
            texts.append(content)
            labels.append(row['document_type'])

            if (idx + 1) % 1000 == 0:
                print(f"  Processed {idx + 1:,}/{len(df):,} files...")

        print(f"Content extraction complete")

        # Encode labels
        y = self.label_encoder.fit_transform(labels)

        # Compute class weights
        self.class_weights = compute_class_weight(
            class_weight='balanced',
            classes=np.unique(y),
            y=y
        )

        print(f"\nClass distribution:")
        unique, counts = np.unique(y, return_counts=True)
        for label_id, count in zip(unique, counts):
            label_name = self.label_encoder.inverse_transform([label_id])[0]
            weight = self.class_weights[label_id]
            print(f"  {label_name}: {count:,} samples (weight: {weight:.3f})")

        # Train/test split (stratified)
        X_train_text, X_test_text, y_train, y_test = train_test_split(
            texts, y,
            test_size=self.test_size,
            random_state=self.random_state,
            stratify=y
        )

        print(f"\nData split:")
        print(f"  Train: {len(X_train_text):,} samples")
        print(f"  Test: {len(X_test_text):,} samples")

        # TF-IDF vectorization
        print(f"\nVectorizing text with TF-IDF...")
        X_train = self.vectorizer.fit_transform(X_train_text)
        X_test = self.vectorizer.transform(X_test_text)

        print(f"  Feature matrix: {X_train.shape}")
        print(f"  Vocabulary size: {len(self.vectorizer.vocabulary_):,}")

        return X_train, X_test, y_train, y_test

    def build_ensemble(self) -> RandomForestClassifier:
        """Build Random Forest classifier."""
        print(f"\nBuilding Random Forest classifier...")

        # Random Forest with class weights
        rf = RandomForestClassifier(
            n_estimators=200,
            max_depth=20,
            min_samples_split=10,
            min_samples_leaf=2,
            max_features='sqrt',
            class_weight='balanced',
            random_state=self.random_state,
            n_jobs=-1,
            verbose=1
        )

        print(f"  Random Forest: 200 trees, max_depth=20, class_weight=balanced")
        print(f"  Note: SVM removed due to sparse matrix compatibility issues")

        return rf

    def train(self, X_train, y_train):
        """Train the ensemble."""
        print(f"\nTraining ensemble...")
        start_time = datetime.now()

        self.ensemble = self.build_ensemble()
        self.ensemble.fit(X_train, y_train)

        elapsed = (datetime.now() - start_time).total_seconds()
        print(f"Training complete in {elapsed:.1f}s")

    def evaluate(self, X_test, y_test):
        """Evaluate on test set."""
        print(f"\nEvaluating on test set...")

        # Predictions
        y_pred = self.ensemble.predict(X_test)
        y_proba = self.ensemble.predict_proba(X_test)

        # Overall accuracy
        accuracy = accuracy_score(y_test, y_pred)
        print(f"\n{'='*60}")
        print(f"TEST SET ACCURACY: {accuracy:.4f} ({accuracy*100:.2f}%)")
        print(f"{'='*60}")

        # Per-class metrics
        report = classification_report(
            y_test, y_pred,
            target_names=self.label_encoder.classes_,
            output_dict=True,
            zero_division=0
        )

        # Show top/bottom classes
        class_f1 = [(name, metrics['f1-score'])
                    for name, metrics in report.items()
                    if name not in ['accuracy', 'macro avg', 'weighted avg']]
        class_f1.sort(key=lambda x: x[1], reverse=True)

        print(f"\nTop 10 classes (by F1-score):")
        for name, f1 in class_f1[:10]:
            precision = report[name]['precision']
            recall = report[name]['recall']
            support = int(report[name]['support'])
            print(f"  {name:30s} P:{precision:.2f} R:{recall:.2f} F1:{f1:.2f} ({support:3d})")

        print(f"\nBottom 10 classes (by F1-score):")
        for name, f1 in class_f1[-10:]:
            precision = report[name]['precision']
            recall = report[name]['recall']
            support = int(report[name]['support'])
            print(f"  {name:30s} P:{precision:.2f} R:{recall:.2f} F1:{f1:.2f} ({support:3d})")

        # Macro/weighted averages
        print(f"\nAggregate metrics:")
        print(f"  Macro avg    - P:{report['macro avg']['precision']:.4f} R:{report['macro avg']['recall']:.4f} F1:{report['macro avg']['f1-score']:.4f}")
        print(f"  Weighted avg - P:{report['weighted avg']['precision']:.4f} R:{report['weighted avg']['recall']:.4f} F1:{report['weighted avg']['f1-score']:.4f}")

        return {
            'accuracy': accuracy,
            'report': report,
            'predictions': y_pred,
            'probabilities': y_proba
        }

    def save_model(self, output_dir: str = "ifmos/models/ensemble"):
        """Save trained model."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        print(f"\nSaving model to: {output_path}")

        # Save ensemble
        model_path = output_path / "model.pkl"
        with open(model_path, 'wb') as f:
            pickle.dump(self.ensemble, f)
        print(f"  Saved: model.pkl ({model_path.stat().st_size / 1e6:.1f} MB)")

        # Save vectorizer
        vectorizer_path = output_path / "vectorizer.pkl"
        with open(vectorizer_path, 'wb') as f:
            pickle.dump(self.vectorizer, f)
        print(f"  Saved: vectorizer.pkl ({vectorizer_path.stat().st_size / 1e6:.1f} MB)")

        # Save label encoder
        encoder_path = output_path / "label_encoder.pkl"
        with open(encoder_path, 'wb') as f:
            pickle.dump(self.label_encoder, f)
        print(f"  Saved: label_encoder.pkl")

        # Save metadata
        metadata = {
            'model_type': 'ensemble',
            'algorithms': ['RandomForest', 'SVM'],
            'voting': 'soft',
            'max_features': self.max_features,
            'num_classes': len(self.label_encoder.classes_),
            'classes': self.label_encoder.classes_.tolist(),
            'trained_at': datetime.now().isoformat(),
            'vocabulary_size': len(self.vectorizer.vocabulary_)
        }

        metadata_path = output_path / "metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        print(f"  Saved: metadata.json")

        print(f"\nModel saved successfully!")


def main():
    """Main training pipeline."""
    print("="*60)
    print("ENSEMBLE CLASSIFIER TRAINING")
    print("Random Forest + SVM with TF-IDF features")
    print("="*60)

    # Initialize trainer
    trainer = EnsembleTrainer(
        max_features=1000,
        min_samples=10,
        test_size=0.15,
        random_state=42
    )

    # Load data
    df = trainer.load_training_data('.ifmos/training_data.csv')

    # Prepare features
    X_train, X_test, y_train, y_test = trainer.prepare_data(df)

    # Train
    trainer.train(X_train, y_train)

    # Evaluate
    results = trainer.evaluate(X_test, y_test)

    # Save
    trainer.save_model()

    print(f"\n{'='*60}")
    print(f"TRAINING COMPLETE")
    print(f"Final Test Accuracy: {results['accuracy']*100:.2f}%")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
