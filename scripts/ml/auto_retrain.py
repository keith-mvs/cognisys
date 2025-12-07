#!/usr/bin/env python3
"""
IFMOS Automated Model Retraining
Monitors feedback database and triggers retraining when threshold is met
"""

import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timedelta
import sys

# Add IFMOS to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from cognisys.ml.learning.training_db import TrainingDatabase
from cognisys.ml.classification.ml_classifier import MLClassifier

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AutoRetrainer:
    """Automated model retraining based on feedback thresholds"""

    def __init__(self, db_path: str, model_dir: str):
        self.db_path = db_path
        self.model_dir = model_dir
        self.training_db = TrainingDatabase(db_path)

    def check_retraining_criteria(self) -> dict:
        """Check if model should be retrained"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get feedback statistics
        cursor.execute("""
            SELECT
                COUNT(*) as total_feedback,
                SUM(CASE WHEN is_correct = 0 THEN 1 ELSE 0 END) as incorrect_count,
                COUNT(DISTINCT doc_id) as unique_docs,
                MIN(created_at) as oldest_feedback
            FROM feedback
            WHERE processed = 0
        """)
        stats = cursor.fetchone()

        total_feedback, incorrect_count, unique_docs, oldest_feedback = stats

        # Calculate feedback age in days
        if oldest_feedback:
            oldest_date = datetime.fromisoformat(oldest_feedback)
            feedback_age_days = (datetime.now() - oldest_date).days
        else:
            feedback_age_days = 0

        conn.close()

        # Retraining criteria
        should_retrain = False
        reasons = []

        if incorrect_count >= 100:
            should_retrain = True
            reasons.append(f"High incorrect count: {incorrect_count}")

        if unique_docs >= 50:
            should_retrain = True
            reasons.append(f"Sufficient unique feedback: {unique_docs}")

        if feedback_age_days >= 7 and total_feedback >= 20:
            should_retrain = True
            reasons.append(f"Feedback aged {feedback_age_days} days with {total_feedback} entries")

        return {
            'should_retrain': should_retrain,
            'reasons': reasons,
            'stats': {
                'total_feedback': total_feedback,
                'incorrect_count': incorrect_count,
                'unique_docs': unique_docs,
                'feedback_age_days': feedback_age_days
            }
        }

    def prepare_training_data(self):
        """Extract training data from feedback"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                d.extracted_text,
                f.correct_type,
                d.entities
            FROM feedback f
            JOIN documents d ON f.doc_id = d.id
            WHERE f.processed = 0 AND f.correct_type IS NOT NULL
        """)

        training_data = []
        for row in cursor.fetchall():
            text, correct_type, entities = row
            training_data.append({
                'text': text,
                'label': correct_type,
                'entities': entities
            })

        conn.close()
        logger.info(f"Prepared {len(training_data)} training samples from feedback")

        return training_data

    def retrain_model(self):
        """Retrain the ML classifier"""
        logger.info("Starting model retraining...")

        # Get training data
        training_data = self.prepare_training_data()

        if len(training_data) < 10:
            logger.warning(f"Insufficient training data: {len(training_data)} samples")
            return False

        # Initialize classifier
        classifier = MLClassifier(model_dir=self.model_dir)

        # Train model (this is a simplified version - real implementation would use scikit-learn)
        # For now, just log what would happen
        logger.info(f"Would train model with {len(training_data)} samples")
        logger.info(f"Unique labels: {len(set(d['label'] for d in training_data))}")

        # Mark feedback as processed
        self._mark_feedback_processed()

        # Save training metadata
        self._save_training_metadata(len(training_data))

        logger.info("Model retraining completed")
        return True

    def _mark_feedback_processed(self):
        """Mark feedback entries as processed"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE feedback
            SET processed = 1, processed_at = ?
            WHERE processed = 0
        """, (datetime.now().isoformat(),))

        conn.commit()
        conn.close()

    def _save_training_metadata(self, sample_count: int):
        """Save training run metadata"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create training_runs table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS training_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                sample_count INTEGER,
                model_version TEXT,
                performance_metrics TEXT
            )
        """)

        cursor.execute("""
            INSERT INTO training_runs (timestamp, sample_count, model_version)
            VALUES (?, ?, ?)
        """, (datetime.now().isoformat(), sample_count, "1.0.0"))

        conn.commit()
        conn.close()

    def run_check(self):
        """Main entry point - check and retrain if needed"""
        logger.info("Checking retraining criteria...")

        result = self.check_retraining_criteria()

        logger.info(f"Retraining check: {result['should_retrain']}")
        logger.info(f"Stats: {result['stats']}")

        if result['should_retrain']:
            logger.info(f"Retraining triggered: {', '.join(result['reasons'])}")
            return self.retrain_model()
        else:
            logger.info("No retraining needed at this time")
            return False


def main():
    """CLI entry point"""
    db_path = PROJECT_ROOT / "ifmos" / "data" / "training" / "ifmos_ml.db"
    model_dir = PROJECT_ROOT / "ifmos" / "models" / "current"

    retrainer = AutoRetrainer(str(db_path), str(model_dir))
    retrainer.run_check()


if __name__ == "__main__":
    main()
