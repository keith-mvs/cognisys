"""
Cascade Classifier
Multi-model pipeline with fallback support for trade-off studies
"""

import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass
from enum import Enum


class ModelType(Enum):
    """Available model types for cascade."""
    NVIDIA_AI = "nvidia_ai"
    DISTILBERT_V2 = "distilbert_v2"
    DISTILBERT_V1 = "distilbert_v1"
    ENSEMBLE_RF = "ensemble_rf"  # Trained Random Forest
    ENSEMBLE_ML = "ensemble_ml"  # XGBoost/LightGBM/RF (old)
    RANDOM_FOREST = "random_forest"
    RULE_BASED = "rule_based"


@dataclass
class ModelConfig:
    """Configuration for a model in the cascade."""
    model_type: ModelType
    min_confidence: float = 0.7
    enabled: bool = True
    priority: int = 0  # Lower = higher priority


class CascadeClassifier:
    """
    Cascade classifier that tries models in order until confidence threshold is met.
    Supports multiple model backends for trade-off studies.
    """

    def __init__(self, config: List[ModelConfig] = None):
        """
        Initialize cascade classifier.

        Args:
            config: List of model configurations in priority order
        """
        self.logger = logging.getLogger(__name__)

        # Default cascade: NVIDIA AI -> DistilBERT v2 -> Ensemble -> Rule-based
        if config is None:
            config = [
                ModelConfig(ModelType.NVIDIA_AI, min_confidence=0.85, priority=0),
                ModelConfig(ModelType.DISTILBERT_V2, min_confidence=0.70, priority=1),
                ModelConfig(ModelType.ENSEMBLE_ML, min_confidence=0.60, priority=2),
                ModelConfig(ModelType.RULE_BASED, min_confidence=0.0, priority=3),
            ]

        self.config = sorted(config, key=lambda x: x.priority)
        self.models = {}
        self.stats = {m.model_type.value: {'calls': 0, 'successes': 0} for m in self.config}

        self.logger.info(f"Cascade initialized with {len(self.config)} models")

    def _load_model(self, model_type: ModelType):
        """Lazy load model on first use."""
        if model_type in self.models:
            return self.models[model_type]

        try:
            if model_type == ModelType.NVIDIA_AI:
                from cognisys.ml.nvidia_classifier import NvidiaClassifier
                self.models[model_type] = NvidiaClassifier()

            elif model_type in (ModelType.DISTILBERT_V1, ModelType.DISTILBERT_V2):
                from cognisys.ml.classification.distilbert_classifier import DistilBERTClassifier
                version = "v2" if model_type == ModelType.DISTILBERT_V2 else "v1"
                classifier = DistilBERTClassifier(model_version=version)
                classifier.load_model()
                self.models[model_type] = classifier

            elif model_type == ModelType.ENSEMBLE_RF:
                from cognisys.ml.classification.ensemble_classifier import EnsembleClassifier
                classifier = EnsembleClassifier()
                self.models[model_type] = classifier

            elif model_type == ModelType.ENSEMBLE_ML:
                from cognisys.ml.classification.ml_classifier import MLClassifier
                classifier = MLClassifier()
                classifier.load_model()
                self.models[model_type] = classifier

            elif model_type == ModelType.RANDOM_FOREST:
                from cognisys.ml.classification.ml_classifier import MLClassifier
                classifier = MLClassifier()
                classifier.load_model()
                self.models[model_type] = classifier

            elif model_type == ModelType.RULE_BASED:
                # Rule-based classifier is a simple fallback
                self.models[model_type] = RuleBasedClassifier()

            self.logger.info(f"Loaded model: {model_type.value}")
            return self.models[model_type]

        except Exception as e:
            self.logger.warning(f"Failed to load {model_type.value}: {e}")
            return None

    def predict(self, text: str, file_path: str = None) -> Dict:
        """
        Classify text using cascade of models.

        Args:
            text: Document text content
            file_path: Optional file path for context

        Returns:
            {
                'predicted_category': str,
                'confidence': float,
                'model_used': str,
                'cascade_path': List[str],
                'success': bool
            }
        """
        cascade_path = []
        last_result = None

        for model_config in self.config:
            if not model_config.enabled:
                continue

            model_type = model_config.model_type
            cascade_path.append(model_type.value)

            # Load model
            model = self._load_model(model_type)
            if model is None:
                continue

            # Get prediction
            try:
                self.stats[model_type.value]['calls'] += 1

                if model_type == ModelType.NVIDIA_AI:
                    result = model.classify(text)
                elif model_type == ModelType.RULE_BASED:
                    result = model.classify(text, file_path)
                else:
                    result = model.predict(text)

                if not result.get('success', False):
                    continue

                confidence = result.get('confidence', 0)
                last_result = result

                # Check if confidence meets threshold
                if confidence >= model_config.min_confidence:
                    self.stats[model_type.value]['successes'] += 1
                    return {
                        'predicted_category': result['predicted_category'],
                        'confidence': confidence,
                        'model_used': model_type.value,
                        'cascade_path': cascade_path,
                        'probabilities': result.get('probabilities', {}),
                        'success': True
                    }

            except Exception as e:
                self.logger.warning(f"Model {model_type.value} failed: {e}")
                continue

        # Return last result if all models tried
        if last_result:
            return {
                'predicted_category': last_result.get('predicted_category', 'unknown'),
                'confidence': last_result.get('confidence', 0),
                'model_used': cascade_path[-1] if cascade_path else 'none',
                'cascade_path': cascade_path,
                'success': True
            }

        return {
            'predicted_category': 'unknown',
            'confidence': 0,
            'model_used': 'none',
            'cascade_path': cascade_path,
            'success': False,
            'error': 'All models failed'
        }

    def predict_with_all(self, text: str) -> Dict:
        """
        Get predictions from ALL enabled models for comparison.
        Useful for trade-off studies.

        Args:
            text: Document text content

        Returns:
            Dict with predictions from each model
        """
        results = {}

        for model_config in self.config:
            if not model_config.enabled:
                continue

            model_type = model_config.model_type
            model = self._load_model(model_type)

            if model is None:
                results[model_type.value] = {'success': False, 'error': 'Model not loaded'}
                continue

            try:
                if model_type == ModelType.NVIDIA_AI:
                    result = model.classify(text)
                elif model_type == ModelType.RULE_BASED:
                    result = model.classify(text)
                else:
                    result = model.predict(text)

                results[model_type.value] = result

            except Exception as e:
                results[model_type.value] = {'success': False, 'error': str(e)}

        return results

    def get_stats(self) -> Dict:
        """Get cascade statistics."""
        return {
            'model_stats': self.stats,
            'config': [
                {
                    'model': m.model_type.value,
                    'min_confidence': m.min_confidence,
                    'enabled': m.enabled,
                    'priority': m.priority
                }
                for m in self.config
            ]
        }

    def set_model_enabled(self, model_type: ModelType, enabled: bool):
        """Enable or disable a model in the cascade."""
        for config in self.config:
            if config.model_type == model_type:
                config.enabled = enabled
                self.logger.info(f"Model {model_type.value} {'enabled' if enabled else 'disabled'}")
                return


class RuleBasedClassifier:
    """Simple rule-based classifier as final fallback."""

    def __init__(self):
        self.rules = {
            # Financial
            ('invoice', 'payment', 'amount', 'total', 'tax'): 'financial_document',
            ('bank', 'statement', 'balance', 'transaction'): 'financial_statement',
            ('budget', 'expense', 'revenue', 'profit'): 'business_spreadsheet',

            # Technical
            ('import', 'def ', 'class ', 'function', 'return'): 'technical_script',
            ('config', 'settings', 'options', 'parameter'): 'technical_config',
            ('#include', 'typedef', 'struct', 'extern'): 'source_header',

            # Documents
            ('resume', 'experience', 'education', 'skills'): 'personal_document',
            ('contract', 'agreement', 'party', 'terms'): 'legal_document',
            ('meeting', 'agenda', 'minutes', 'action items'): 'business_document',
        }

    def classify(self, text: str, file_path: str = None) -> Dict:
        """Classify using keyword rules."""
        text_lower = text.lower()

        best_match = None
        best_score = 0

        for keywords, category in self.rules.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > best_score:
                best_score = score
                best_match = category

        if best_match and best_score >= 2:
            confidence = min(0.5 + (best_score * 0.1), 0.8)
            return {
                'predicted_category': best_match,
                'confidence': confidence,
                'success': True,
                'model': 'rule_based'
            }

        # Fallback based on file extension
        if file_path:
            ext = Path(file_path).suffix.lower()
            ext_map = {
                '.py': 'technical_script',
                '.js': 'technical_script',
                '.h': 'source_header',
                '.c': 'technical_script',
                '.xlsx': 'business_spreadsheet',
                '.pdf': 'document',
                '.docx': 'document',
            }
            if ext in ext_map:
                return {
                    'predicted_category': ext_map[ext],
                    'confidence': 0.3,
                    'success': True,
                    'model': 'rule_based'
                }

        return {
            'predicted_category': 'unknown',
            'confidence': 0.1,
            'success': True,
            'model': 'rule_based'
        }


# Factory functions
def create_cascade(preset: str = "default") -> CascadeClassifier:
    """
    Create cascade classifier with preset configuration.

    Args:
        preset: Configuration preset name

    Returns:
        Configured cascade classifier
    """
    presets = {
        "default": [
            ModelConfig(ModelType.NVIDIA_AI, min_confidence=0.85, priority=0),
            ModelConfig(ModelType.DISTILBERT_V2, min_confidence=0.70, priority=1),
            ModelConfig(ModelType.ENSEMBLE_RF, min_confidence=0.60, priority=2),
            ModelConfig(ModelType.RULE_BASED, min_confidence=0.0, priority=3),
        ],
        "fast": [
            ModelConfig(ModelType.ENSEMBLE_RF, min_confidence=0.05, priority=0),  # RF has lower confidence scores
            ModelConfig(ModelType.RULE_BASED, min_confidence=0.0, priority=1),
        ],
        "accurate": [
            ModelConfig(ModelType.NVIDIA_AI, min_confidence=0.90, priority=0),
            ModelConfig(ModelType.DISTILBERT_V2, min_confidence=0.85, priority=1),
            ModelConfig(ModelType.ENSEMBLE_RF, min_confidence=0.75, priority=2),
            ModelConfig(ModelType.DISTILBERT_V1, min_confidence=0.60, priority=3),
            ModelConfig(ModelType.RULE_BASED, min_confidence=0.0, priority=4),
        ],
        "local_only": [
            ModelConfig(ModelType.DISTILBERT_V2, min_confidence=0.70, priority=0),
            ModelConfig(ModelType.ENSEMBLE_RF, min_confidence=0.05, priority=1),  # RF fallback
            ModelConfig(ModelType.RULE_BASED, min_confidence=0.0, priority=2),
        ],
        "tradeoff_study": [
            ModelConfig(ModelType.NVIDIA_AI, min_confidence=0.0, priority=0, enabled=True),
            ModelConfig(ModelType.DISTILBERT_V2, min_confidence=0.0, priority=1, enabled=True),
            ModelConfig(ModelType.ENSEMBLE_RF, min_confidence=0.0, priority=2, enabled=True),
            ModelConfig(ModelType.DISTILBERT_V1, min_confidence=0.0, priority=3, enabled=True),
            ModelConfig(ModelType.RULE_BASED, min_confidence=0.0, priority=4, enabled=True),
        ],
    }

    config = presets.get(preset, presets["default"])
    return CascadeClassifier(config)
