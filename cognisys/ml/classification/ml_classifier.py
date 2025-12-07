"""
ML Classification Engine
Ensemble learning with XGBoost, LightGBM, and Random Forest
"""

import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import pickle
import json

try:
    from sklearn.ensemble import RandomForestClassifier, VotingClassifier
    from sklearn.model_selection import train_test_split, cross_val_score
    from sklearn.preprocessing import LabelEncoder
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
    import numpy as np
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False

try:
    import lightgbm as lgb
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False


class MLClassifier:
    """
    Ensemble ML classifier for document categorization.
    Combines XGBoost, LightGBM, and Random Forest with soft voting.
    """

    def __init__(self, model_dir: str = None):
        """
        Initialize ML classifier.

        Args:
            model_dir: Directory to save/load models
        """
        if not SKLEARN_AVAILABLE:
            raise ImportError("scikit-learn not installed")

        self.logger = logging.getLogger(__name__)

        # Model directory
        if model_dir is None:
            model_dir = Path(__file__).parent.parent.parent / 'models' / 'current'
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)

        # Components
        self.tfidf_vectorizer = TfidfVectorizer(
            max_features=500,
            ngram_range=(1, 2),
            min_df=2,
            max_df=0.8,
            stop_words='english'
        )

        self.label_encoder = LabelEncoder()
        self.ensemble_model = None
        self.is_trained = False

        # Feature configuration
        self.text_features = ['text', 'keywords', 'summary']
        self.categorical_features = ['document_type', 'sentiment']
        self.numerical_features = [
            'confidence', 'page_count', 'word_count', 'char_count',
            'person_count', 'org_count', 'date_count', 'money_count',
            'noun_ratio', 'verb_ratio', 'adj_ratio'
        ]

        self.logger.info(f"ML Classifier initialized. Model dir: {self.model_dir}")

    def prepare_features(self, documents: List[Dict]) -> Tuple[np.ndarray, np.ndarray]:
        """
        Extract and prepare features from document dictionaries.

        Args:
            documents: List of document dicts with extraction + analysis results

        Returns:
            Tuple of (X_features, y_labels)
        """
        if not documents:
            raise ValueError("No documents provided")

        # Combine text fields for TF-IDF
        text_data = []
        for doc in documents:
            text_parts = []

            # Content extraction text
            if 'extraction' in doc and 'text' in doc['extraction']:
                text_parts.append(doc['extraction']['text'][:5000])  # Limit text length

            # Analysis keywords and summary
            if 'analysis' in doc:
                if 'keywords' in doc['analysis']:
                    text_parts.append(' '.join(doc['analysis']['keywords'][:20]))
                if 'summary' in doc['analysis']:
                    text_parts.append(doc['analysis']['summary'])

            text_data.append(' '.join(text_parts))

        # TF-IDF features
        tfidf_features = self.tfidf_vectorizer.fit_transform(text_data).toarray()

        # Numerical/categorical features
        structured_features = []
        for doc in documents:
            features = []

            # Numerical features from extraction
            if 'extraction' in doc:
                features.append(doc['extraction'].get('confidence', 0.0))
                features.append(doc['extraction'].get('page_count', 1))

            # Features from analysis
            if 'analysis' in doc:
                stats = doc['analysis'].get('statistics', {})
                features.append(stats.get('word_count', 0))
                features.append(stats.get('char_count', 0))

                # Entity counts
                doc_features = doc['analysis'].get('features', {})
                features.append(doc_features.get('person_count', 0))
                features.append(doc_features.get('org_count', 0))
                features.append(doc_features.get('date_count', 0))
                features.append(doc_features.get('money_count', 0))

                # POS ratios
                features.append(doc_features.get('noun_ratio', 0.0))
                features.append(doc_features.get('verb_ratio', 0.0))
                features.append(doc_features.get('adj_ratio', 0.0))

            # Document type one-hot encoding (simplified)
            if 'analysis' in doc:
                doc_type = doc['analysis'].get('document_type', 'unknown')
                # Add indicator features for main types
                features.append(1 if 'financial' in doc_type else 0)
                features.append(1 if 'legal' in doc_type else 0)
                features.append(1 if 'medical' in doc_type else 0)
                features.append(1 if 'tax' in doc_type else 0)

            structured_features.append(features)

        structured_features = np.array(structured_features)

        # Combine TF-IDF and structured features
        X = np.concatenate([tfidf_features, structured_features], axis=1)

        # Extract labels
        y = np.array([doc.get('label', 'Unknown') for doc in documents])
        y = self.label_encoder.fit_transform(y)

        self.logger.info(f"Prepared features: {X.shape}, Labels: {len(y)} ({len(np.unique(y))} classes)")
        return X, y

    def build_ensemble(self) -> VotingClassifier:
        """Build ensemble model with available classifiers."""
        estimators = []

        # Random Forest (always available with sklearn)
        rf_model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            random_state=42,
            n_jobs=-1
        )
        estimators.append(('rf', rf_model))
        self.logger.info("Added Random Forest to ensemble")

        # XGBoost
        if XGBOOST_AVAILABLE:
            xgb_model = xgb.XGBClassifier(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.1,
                random_state=42,
                tree_method='hist',
                device='cuda',  # Use GPU if available
                n_jobs=-1
            )
            estimators.append(('xgb', xgb_model))
            self.logger.info("Added XGBoost to ensemble (GPU enabled)")
        else:
            self.logger.warning("XGBoost not available")

        # LightGBM
        if LIGHTGBM_AVAILABLE:
            lgb_model = lgb.LGBMClassifier(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.1,
                random_state=42,
                device='gpu',  # Use GPU if available
                n_jobs=-1,
                verbose=-1
            )
            estimators.append(('lgb', lgb_model))
            self.logger.info("Added LightGBM to ensemble (GPU enabled)")
        else:
            self.logger.warning("LightGBM not available")

        # Soft voting ensemble
        ensemble = VotingClassifier(
            estimators=estimators,
            voting='soft',
            n_jobs=-1
        )

        return ensemble

    def train(self, documents: List[Dict], test_size: float = 0.2) -> Dict:
        """
        Train the ensemble classifier.

        Args:
            documents: List of labeled documents with extraction + analysis
            test_size: Fraction for test set

        Returns:
            Training metrics
        """
        self.logger.info(f"Training on {len(documents)} documents")

        # Prepare features
        X, y = self.prepare_features(documents)

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42, stratify=y
        )

        # Build and train ensemble
        self.ensemble_model = self.build_ensemble()
        self.ensemble_model.fit(X_train, y_train)

        # Evaluate
        y_pred = self.ensemble_model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)

        # Get predictions with probabilities
        y_pred_proba = self.ensemble_model.predict_proba(X_test)

        self.is_trained = True
        self.logger.info(f"Training complete. Accuracy: {accuracy:.3f}")

        # Build metrics
        metrics = {
            'accuracy': float(accuracy),
            'train_size': len(X_train),
            'test_size': len(X_test),
            'num_classes': len(self.label_encoder.classes_),
            'classes': self.label_encoder.classes_.tolist(),
            'classification_report': classification_report(
                y_test, y_pred,
                target_names=self.label_encoder.classes_,
                output_dict=True
            )
        }

        return metrics

    def predict(self, document: Dict) -> Dict:
        """
        Predict category for a single document.

        Args:
            document: Document dict with extraction + analysis

        Returns:
            {
                'predicted_category': str,
                'confidence': float,
                'probabilities': Dict[str, float],
                'success': bool
            }
        """
        if not self.is_trained:
            return {'success': False, 'error': 'Model not trained'}

        try:
            # Prepare features (single document)
            X, _ = self.prepare_features([document])

            # Predict
            y_pred = self.ensemble_model.predict(X)[0]
            y_proba = self.ensemble_model.predict_proba(X)[0]

            # Decode label
            predicted_label = self.label_encoder.inverse_transform([y_pred])[0]
            confidence = float(np.max(y_proba))

            # Build probability dict
            probabilities = {
                label: float(prob)
                for label, prob in zip(self.label_encoder.classes_, y_proba)
            }

            # Sort by probability
            probabilities = dict(sorted(probabilities.items(), key=lambda x: x[1], reverse=True))

            return {
                'predicted_category': predicted_label,
                'confidence': confidence,
                'probabilities': probabilities,
                'success': True
            }

        except Exception as e:
            self.logger.error(f"Prediction failed: {e}")
            return {'success': False, 'error': str(e)}

    def predict_batch(self, documents: List[Dict]) -> List[Dict]:
        """
        Predict categories for multiple documents.

        Args:
            documents: List of document dicts

        Returns:
            List of prediction results
        """
        if not self.is_trained:
            return [{'success': False, 'error': 'Model not trained'}] * len(documents)

        try:
            # Prepare features
            X, _ = self.prepare_features(documents)

            # Predict
            y_pred = self.ensemble_model.predict(X)
            y_proba = self.ensemble_model.predict_proba(X)

            results = []
            for i in range(len(documents)):
                predicted_label = self.label_encoder.inverse_transform([y_pred[i]])[0]
                confidence = float(np.max(y_proba[i]))

                probabilities = {
                    label: float(prob)
                    for label, prob in zip(self.label_encoder.classes_, y_proba[i])
                }

                results.append({
                    'predicted_category': predicted_label,
                    'confidence': confidence,
                    'probabilities': probabilities,
                    'success': True
                })

            return results

        except Exception as e:
            self.logger.error(f"Batch prediction failed: {e}")
            return [{'success': False, 'error': str(e)}] * len(documents)

    def save_model(self, name: str = "classifier") -> bool:
        """
        Save trained model to disk.

        Args:
            name: Model name

        Returns:
            Success status
        """
        if not self.is_trained:
            self.logger.error("Cannot save untrained model")
            return False

        try:
            model_path = self.model_dir / f"{name}.pkl"
            vectorizer_path = self.model_dir / f"{name}_vectorizer.pkl"
            encoder_path = self.model_dir / f"{name}_encoder.pkl"
            metadata_path = self.model_dir / f"{name}_metadata.json"

            # Save components
            with open(model_path, 'wb') as f:
                pickle.dump(self.ensemble_model, f)

            with open(vectorizer_path, 'wb') as f:
                pickle.dump(self.tfidf_vectorizer, f)

            with open(encoder_path, 'wb') as f:
                pickle.dump(self.label_encoder, f)

            # Save metadata
            metadata = {
                'model_name': name,
                'classes': self.label_encoder.classes_.tolist(),
                'num_classes': len(self.label_encoder.classes_),
                'feature_count': self.tfidf_vectorizer.max_features
            }

            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)

            self.logger.info(f"Model saved: {model_path}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to save model: {e}")
            return False

    def load_model(self, name: str = "classifier") -> bool:
        """
        Load trained model from disk.

        Args:
            name: Model name

        Returns:
            Success status
        """
        try:
            model_path = self.model_dir / f"{name}.pkl"
            vectorizer_path = self.model_dir / f"{name}_vectorizer.pkl"
            encoder_path = self.model_dir / f"{name}_encoder.pkl"

            if not model_path.exists():
                self.logger.error(f"Model not found: {model_path}")
                return False

            # Load components
            with open(model_path, 'rb') as f:
                self.ensemble_model = pickle.load(f)

            with open(vectorizer_path, 'rb') as f:
                self.tfidf_vectorizer = pickle.load(f)

            with open(encoder_path, 'rb') as f:
                self.label_encoder = pickle.load(f)

            self.is_trained = True
            self.logger.info(f"Model loaded: {model_path}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to load model: {e}")
            return False


# Convenience function
def create_classifier(model_dir: str = None):
    """
    Factory function to create ML classifier.

    Args:
        model_dir: Model directory

    Returns:
        Configured MLClassifier
    """
    return MLClassifier(model_dir=model_dir)
