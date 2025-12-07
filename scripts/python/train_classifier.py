"""
Train CogniSys ML Classifier
Trains the ensemble classifier using labeled feedback data from the database
"""

import sys
import logging
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from cognisys_ml.learning import create_database
from cognisys_ml.classification import create_classifier
from cognisys_ml.utils import create_extractor
from cognisys_ml.nlp import create_analyzer
from cognisys_ml.ocr import create_ocr_engine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    logger.info("=" * 60)
    logger.info("COGNISYS ML Classifier Training")
    logger.info("=" * 60)

    # Initialize database
    logger.info("Connecting to training database...")
    db = create_database()

    # Get training data
    logger.info("Retrieving training data from database...")
    training_records = db.get_training_data(min_confidence=0.0, include_feedback=True)

    logger.info(f"Found {len(training_records)} training samples")

    if len(training_records) < 10:
        logger.error(f"Insufficient training data! Need at least 10 samples, have {len(training_records)}")
        logger.info("Please process and label more documents before training.")
        return 1

    # Check class distribution
    categories = {}
    for record in training_records:
        cat = record.get('correct_category') or record.get('predicted_category')
        if cat:
            categories[cat] = categories.get(cat, 0) + 1

    logger.info("\nClass distribution:")
    for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
        logger.info(f"  {cat}: {count} samples")

    # Check minimum samples per class
    min_samples_per_class = 2
    insufficient_classes = [cat for cat, count in categories.items() if count < min_samples_per_class]
    if insufficient_classes:
        logger.warning(f"\nWarning: Some categories have fewer than {min_samples_per_class} samples:")
        for cat in insufficient_classes:
            logger.warning(f"  {cat}: {categories[cat]} samples")
        logger.warning("Training may proceed but accuracy may be low for these categories.")

    # Initialize components for feature extraction
    logger.info("\nInitializing ML components...")
    ocr_engine = create_ocr_engine()
    extractor = create_extractor(ocr_engine=ocr_engine)
    analyzer = create_analyzer()

    # Load full documents with extraction and analysis
    logger.info("Loading and analyzing documents...")
    documents = []
    labels = []

    for i, record in enumerate(training_records):
        try:
            # Get document file path
            file_path = record['file_path']

            logger.info(f"Processing {i+1}/{len(training_records)}: {Path(file_path).name}")

            # Extract content
            extraction = extractor.extract_content(file_path)

            if not extraction['success']:
                logger.warning(f"  Skipping - extraction failed")
                continue

            # Analyze text
            analysis = analyzer.analyze_text(extraction['text'])

            # Create document dict
            document = {
                'extraction': extraction,
                'analysis': analysis,
                'file_path': file_path
            }

            # Get correct category from feedback
            category = record.get('correct_category') or record.get('predicted_category')

            if category:
                documents.append(document)
                labels.append(category)
            else:
                logger.warning(f"  Skipping - no category label")

        except Exception as e:
            logger.error(f"  Error processing document: {e}")
            continue

    logger.info(f"\nSuccessfully loaded {len(documents)} documents for training")

    if len(documents) < 10:
        logger.error("Not enough valid documents after processing. Training aborted.")
        return 1

    # Initialize and train classifier
    logger.info("\nInitializing ensemble classifier...")
    classifier = create_classifier()

    logger.info("Training classifier (this may take a few minutes)...")
    logger.info("  - Training Random Forest...")
    logger.info("  - Training XGBoost (GPU)...")
    logger.info("  - Training LightGBM (GPU)...")

    metrics = classifier.train(documents, labels)

    # Display results
    logger.info("\n" + "=" * 60)
    logger.info("Training Complete!")
    logger.info("=" * 60)
    logger.info(f"\nAccuracy: {metrics['accuracy']:.3f}")
    logger.info(f"Training samples: {metrics['training_samples']}")
    logger.info(f"Number of classes: {metrics['num_classes']}")
    logger.info(f"\nClasses trained: {', '.join(metrics['classes'])}")

    if 'classification_report' in metrics:
        logger.info("\nClassification Report:")
        logger.info(metrics['classification_report'])

    # Save model
    model_version = datetime.now().strftime("v%Y%m%d_%H%M%S")
    logger.info(f"\nSaving model as: {model_version}")
    classifier.save_model(model_version)

    # Record training session in database
    logger.info("Recording training session in database...")
    db.add_training_session(
        model_version=model_version,
        accuracy=metrics['accuracy'],
        training_samples=len(documents),
        notes=f"Trained with {len(documents)} samples across {metrics['num_classes']} classes"
    )

    logger.info("\n" + "=" * 60)
    logger.info("Success! Model is ready for predictions.")
    logger.info("=" * 60)
    logger.info("\nThe ML classifier will now use this trained model for future predictions.")
    logger.info("Continue processing documents and providing feedback to improve accuracy.\n")

    db.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
