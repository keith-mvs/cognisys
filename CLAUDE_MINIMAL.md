# IFMOS - ML Document Classification System

## Quick Start
```bash
# Classify files
ifmos scan --roots <path>  # Extension-based
ifmos classify --session <id> --cascade local_only  # ML-based

# Models: distilbert_v2 (82.9% acc), ensemble (TBD), cascade
# See README.md for details
```

## Key Files
- `ifmos/core/classifier.py` - ML classification engine
- `ifmos/ml/classification/` - Model implementations
- `train_distilbert_v2.py` - DistilBERT training (96.69% val acc)
- `train_ensemble.py` - Random Forest + SVM training
- `evaluate_classifiers.py` - Model comparison

## Training Data
- `.ifmos/training_data.csv` - 72k samples, 37 classes
- Imbalanced (24,940:1 ratio) - use class weights

## Architecture
- Scanner: Fast extension-based categorization
- Classifier: Accurate content-based ML
- Database: SQLite with ml_classifications table
- Cascade: Multi-model pipeline with fallback

## Dev Notes
- DistilBERT v2: ifmos/models/distilbert_v2/best_model/
- Ensemble: ifmos/models/ensemble/ (training in progress)
- NVIDIA AI: Requires NVIDIA_API_KEY env var
