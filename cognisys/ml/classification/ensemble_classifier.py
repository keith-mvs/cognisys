"""
Ensemble Classifier Wrapper
Wraps trained Random Forest model for use in cascade pipeline.
"""

import pickle
import json
from pathlib import Path
from typing import Dict, Optional
import numpy as np


class EnsembleClassifier:
    """
    Wrapper for trained Random Forest ensemble classifier.
    Provides consistent API with other classifiers for cascade integration.
    """

    def __init__(self, model_dir: str = None):
        """
        Initialize ensemble classifier.

        Args:
            model_dir: Directory containing trained model files
        """
        if model_dir is None:
            model_dir = Path(__file__).parent.parent.parent / 'models' / 'ensemble'

        self.model_dir = Path(model_dir)

        if not self.model_dir.exists():
            raise FileNotFoundError(f"Model directory not found: {model_dir}")

        # Load model components
        self.model = None
        self.vectorizer = None
        self.label_encoder = None
        self.metadata = None

        self._load_model()

    def _load_model(self):
        """Load trained model from disk."""
        model_path = self.model_dir / "model.pkl"
        vectorizer_path = self.model_dir / "vectorizer.pkl"
        encoder_path = self.model_dir / "label_encoder.pkl"
        metadata_path = self.model_dir / "metadata.json"

        if not model_path.exists():
            raise FileNotFoundError(f"Model not found: {model_path}")

        # Load components
        with open(model_path, 'rb') as f:
            self.model = pickle.load(f)

        with open(vectorizer_path, 'rb') as f:
            self.vectorizer = pickle.load(f)

        with open(encoder_path, 'rb') as f:
            self.label_encoder = pickle.load(f)

        if metadata_path.exists():
            with open(metadata_path) as f:
                self.metadata = json.load(f)

    def predict(self, text: str) -> Dict:
        """
        Predict document category.

        Args:
            text: Document text content

        Returns:
            {
                'predicted_category': str,
                'confidence': float,
                'probabilities': dict,
                'success': bool,
                'model_used': str
            }
        """
        try:
            # Vectorize text
            X = self.vectorizer.transform([text])

            # Predict
            y_pred = self.model.predict(X)[0]
            y_proba = self.model.predict_proba(X)[0]

            # Decode label
            predicted_label = self.label_encoder.inverse_transform([y_pred])[0]
            confidence = float(np.max(y_proba))

            # Build probability dict
            probabilities = {
                label: float(prob)
                for label, prob in zip(self.label_encoder.classes_, y_proba)
            }

            # Sort by probability
            probabilities = dict(sorted(
                probabilities.items(),
                key=lambda x: x[1],
                reverse=True
            ))

            return {
                'predicted_category': predicted_label,
                'confidence': confidence,
                'probabilities': probabilities,
                'success': True,
                'model_used': 'ensemble_rf'
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'predicted_category': 'unknown',
                'confidence': 0.0
            }

    def predict_batch(self, texts: list, batch_size: int = 32) -> list:
        """
        Predict categories for multiple texts.

        Args:
            texts: List of text strings
            batch_size: Batch size for processing

        Returns:
            List of prediction results
        """
        results = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]

            # Vectorize batch
            X = self.vectorizer.transform(batch)

            # Predict
            y_pred = self.model.predict(X)
            y_proba = self.model.predict_proba(X)

            for j in range(len(batch)):
                predicted_label = self.label_encoder.inverse_transform([y_pred[j]])[0]
                confidence = float(np.max(y_proba[j]))

                probabilities = {
                    label: float(prob)
                    for label, prob in zip(self.label_encoder.classes_, y_proba[j])
                }

                results.append({
                    'predicted_category': predicted_label,
                    'confidence': confidence,
                    'probabilities': probabilities,
                    'success': True,
                    'model_used': 'ensemble_rf'
                })

        return results

    def get_info(self) -> Dict:
        """Get model information."""
        return {
            'model_type': 'ensemble',
            'algorithm': 'RandomForest',
            'num_classes': len(self.label_encoder.classes_),
            'classes': self.label_encoder.classes_.tolist(),
            'metadata': self.metadata
        }


def create_ensemble_classifier(model_dir: str = None) -> EnsembleClassifier:
    """
    Factory function to create ensemble classifier.

    Args:
        model_dir: Model directory

    Returns:
        Configured EnsembleClassifier
    """
    return EnsembleClassifier(model_dir=model_dir)
