"""
IFMOS ML - Classification Module
ML-powered document classification with multiple backends
"""

from .ml_classifier import MLClassifier, create_classifier
from .distilbert_classifier import DistilBERTClassifier, create_distilbert_classifier
from .ensemble_classifier import EnsembleClassifier, create_ensemble_classifier
from .nvidia_classifier import NvidiaAIClassifier, create_nvidia_classifier
from .cascade_classifier import (
    CascadeClassifier,
    ModelType,
    ModelConfig,
    create_cascade,
    RuleBasedClassifier
)

__all__ = [
    # Ensemble ML (XGBoost/LightGBM/RF)
    'MLClassifier',
    'create_classifier',

    # DistilBERT
    'DistilBERTClassifier',
    'create_distilbert_classifier',

    # Random Forest Ensemble
    'EnsembleClassifier',
    'create_ensemble_classifier',

    # NVIDIA AI
    'NvidiaAIClassifier',
    'create_nvidia_classifier',

    # Cascade
    'CascadeClassifier',
    'ModelType',
    'ModelConfig',
    'create_cascade',
    'RuleBasedClassifier',
]
