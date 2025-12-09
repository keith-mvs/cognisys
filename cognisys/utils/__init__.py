"""Utility modules for CogniSys."""

from .hashing import calculate_quick_hash, calculate_full_hash
from .logging_config import setup_logging, get_logger
from .naming import sanitize_name, normalize_filename, extract_version, extract_project_name
from .pattern_classifier import PatternClassifier, PatternRule, ClassificationResult, extract_real_filename
from .stats_collector import StatsCollector, ClassificationStats, ProgressTracker

__all__ = [
    # Hashing
    'calculate_quick_hash',
    'calculate_full_hash',
    # Logging
    'setup_logging',
    'get_logger',
    # Naming
    'sanitize_name',
    'normalize_filename',
    'extract_version',
    'extract_project_name',
    # Pattern classification
    'PatternClassifier',
    'PatternRule',
    'ClassificationResult',
    'extract_real_filename',
    # Statistics
    'StatsCollector',
    'ClassificationStats',
    'ProgressTracker',
]
