"""
Training Database
SQLite database for storing training data, predictions, and feedback
"""

import logging
import sqlite3
from typing import Dict, List, Optional
from pathlib import Path
from datetime import datetime
import json


class TrainingDatabase:
    """
    Manages training data, predictions, and feedback for continuous learning.
    """

    def __init__(self, db_path: str = None):
        """
        Initialize training database.

        Args:
            db_path: Path to SQLite database file
        """
        self.logger = logging.getLogger(__name__)

        # Database path
        if db_path is None:
            db_path = Path(__file__).parent.parent.parent / 'data' / 'training' / 'ifmos_ml.db'

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self.conn = None
        self.connect()
        self.create_tables()

        self.logger.info(f"Training database initialized: {self.db_path}")

    def connect(self):
        """Connect to SQLite database."""
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Enable column access by name

    def create_tables(self):
        """Create database tables if they don't exist."""
        cursor = self.conn.cursor()

        # Documents table - stores processed documents
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL UNIQUE,
                file_name TEXT NOT NULL,
                file_type TEXT,
                extracted_text TEXT,
                document_type TEXT,
                processing_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                confidence REAL,
                page_count INTEGER,
                word_count INTEGER
            )
        ''')

        # Predictions table - stores ML model predictions
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                predicted_category TEXT NOT NULL,
                confidence REAL NOT NULL,
                probabilities TEXT,  -- JSON of all class probabilities
                model_version TEXT,
                prediction_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (document_id) REFERENCES documents(id)
            )
        ''')

        # Feedback table - stores user corrections and confirmations
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                prediction_id INTEGER,
                correct_category TEXT NOT NULL,
                was_correct BOOLEAN NOT NULL,
                user_comment TEXT,
                feedback_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (document_id) REFERENCES documents(id),
                FOREIGN KEY (prediction_id) REFERENCES predictions(id)
            )
        ''')

        # Training sessions table - tracks model training runs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS training_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_version TEXT NOT NULL,
                training_size INTEGER NOT NULL,
                test_size INTEGER NOT NULL,
                accuracy REAL NOT NULL,
                metrics TEXT,  -- JSON of detailed metrics
                training_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Categories table - manages available categories
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_name TEXT NOT NULL UNIQUE,
                description TEXT,
                pattern_path TEXT,  -- Legacy pattern-based destination
                is_active BOOLEAN DEFAULT 1,
                created_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        self.conn.commit()
        self.logger.info("Database tables created/verified")

    def add_document(self, file_path: str, extraction: Dict, analysis: Dict) -> int:
        """
        Add a processed document to the database.

        Args:
            file_path: Path to document file
            extraction: Content extraction results
            analysis: Text analysis results

        Returns:
            Document ID
        """
        cursor = self.conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO documents (
                    file_path, file_name, file_type, extracted_text,
                    document_type, confidence, page_count, word_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                str(file_path),
                Path(file_path).name,
                extraction.get('metadata', {}).get('file_type', 'unknown'),
                extraction.get('text', '')[:10000],  # Limit text storage
                analysis.get('document_type', 'unknown'),
                extraction.get('confidence', 0.0),
                extraction.get('page_count', 1),
                analysis.get('statistics', {}).get('word_count', 0)
            ))

            self.conn.commit()
            doc_id = cursor.lastrowid
            self.logger.info(f"Document added: {Path(file_path).name} (ID: {doc_id})")
            return doc_id

        except sqlite3.IntegrityError:
            # Document already exists, get existing ID
            cursor.execute('SELECT id FROM documents WHERE file_path = ?', (str(file_path),))
            row = cursor.fetchone()
            if row:
                return row[0]
            raise

    def add_prediction(self, document_id: int, prediction: Dict, model_version: str = "v1.0") -> int:
        """
        Store a model prediction.

        Args:
            document_id: Document ID
            prediction: Prediction results
            model_version: Model version string

        Returns:
            Prediction ID
        """
        cursor = self.conn.cursor()

        cursor.execute('''
            INSERT INTO predictions (
                document_id, predicted_category, confidence,
                probabilities, model_version
            ) VALUES (?, ?, ?, ?, ?)
        ''', (
            document_id,
            prediction.get('predicted_category', 'Unknown'),
            prediction.get('confidence', 0.0),
            json.dumps(prediction.get('probabilities', {})),
            model_version
        ))

        self.conn.commit()
        pred_id = cursor.lastrowid
        self.logger.debug(f"Prediction stored (ID: {pred_id})")
        return pred_id

    def add_feedback(self, document_id: int, correct_category: str,
                     prediction_id: Optional[int] = None,
                     was_correct: bool = False,
                     user_comment: Optional[str] = None) -> int:
        """
        Record user feedback on a classification.

        Args:
            document_id: Document ID
            correct_category: Correct category label
            prediction_id: Optional prediction ID
            was_correct: Whether prediction was correct
            user_comment: Optional user comment

        Returns:
            Feedback ID
        """
        cursor = self.conn.cursor()

        cursor.execute('''
            INSERT INTO feedback (
                document_id, prediction_id, correct_category,
                was_correct, user_comment
            ) VALUES (?, ?, ?, ?, ?)
        ''', (
            document_id,
            prediction_id,
            correct_category,
            1 if was_correct else 0,
            user_comment
        ))

        self.conn.commit()
        feedback_id = cursor.lastrowid
        self.logger.info(f"Feedback recorded: {correct_category} ({'correct' if was_correct else 'corrected'})")
        return feedback_id

    def get_training_data(self, min_confidence: float = 0.0, include_feedback: bool = True) -> List[Dict]:
        """
        Get training data for model retraining.

        Args:
            min_confidence: Minimum confidence threshold
            include_feedback: Include documents with user feedback

        Returns:
            List of training documents with labels
        """
        cursor = self.conn.cursor()

        # Query documents with predictions and optional feedback
        query = '''
            SELECT
                d.id, d.file_path, d.file_name, d.extracted_text,
                d.document_type, d.confidence, d.page_count, d.word_count,
                p.predicted_category, p.confidence as pred_confidence,
                f.correct_category, f.was_correct
            FROM documents d
            LEFT JOIN predictions p ON d.id = p.document_id
            LEFT JOIN feedback f ON d.id = f.document_id
            WHERE d.confidence >= ?
        '''

        if include_feedback:
            query += ' AND (f.correct_category IS NOT NULL OR p.predicted_category IS NOT NULL)'

        cursor.execute(query, (min_confidence,))
        rows = cursor.fetchall()

        training_data = []
        for row in rows:
            # Use feedback category if available, otherwise prediction
            label = row['correct_category'] if row['correct_category'] else row['predicted_category']

            if label:
                training_data.append({
                    'id': row['id'],
                    'file_path': row['file_path'],
                    'file_name': row['file_name'],
                    'label': label,
                    'confidence': row['confidence'],
                    'was_corrected': row['correct_category'] is not None and not row['was_correct']
                })

        self.logger.info(f"Retrieved {len(training_data)} training samples")
        return training_data

    def record_training_session(self, model_version: str, train_size: int,
                                 test_size: int, metrics: Dict) -> int:
        """
        Record a model training session.

        Args:
            model_version: Model version
            train_size: Training set size
            test_size: Test set size
            metrics: Training metrics

        Returns:
            Session ID
        """
        cursor = self.conn.cursor()

        cursor.execute('''
            INSERT INTO training_sessions (
                model_version, training_size, test_size,
                accuracy, metrics
            ) VALUES (?, ?, ?, ?, ?)
        ''', (
            model_version,
            train_size,
            test_size,
            metrics.get('accuracy', 0.0),
            json.dumps(metrics)
        ))

        self.conn.commit()
        session_id = cursor.lastrowid
        self.logger.info(f"Training session recorded (ID: {session_id}, Accuracy: {metrics.get('accuracy', 0):.3f})")
        return session_id

    def add_category(self, category_name: str, description: str = None,
                     pattern_path: str = None) -> int:
        """
        Add a new category.

        Args:
            category_name: Category name
            description: Optional description
            pattern_path: Legacy pattern-based destination path

        Returns:
            Category ID
        """
        cursor = self.conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO categories (category_name, description, pattern_path)
                VALUES (?, ?, ?)
            ''', (category_name, description, pattern_path))

            self.conn.commit()
            cat_id = cursor.lastrowid
            self.logger.info(f"Category added: {category_name}")
            return cat_id

        except sqlite3.IntegrityError:
            # Category exists
            cursor.execute('SELECT id FROM categories WHERE category_name = ?', (category_name,))
            row = cursor.fetchone()
            return row[0] if row else -1

    def get_categories(self, active_only: bool = True) -> List[Dict]:
        """
        Get all categories.

        Args:
            active_only: Only return active categories

        Returns:
            List of category dicts
        """
        cursor = self.conn.cursor()

        query = 'SELECT * FROM categories'
        if active_only:
            query += ' WHERE is_active = 1'

        cursor.execute(query)
        rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def get_statistics(self) -> Dict:
        """
        Get database statistics.

        Returns:
            Statistics dictionary
        """
        cursor = self.conn.cursor()

        stats = {}

        # Document counts
        cursor.execute('SELECT COUNT(*) FROM documents')
        stats['total_documents'] = cursor.fetchone()[0]

        # Prediction counts
        cursor.execute('SELECT COUNT(*) FROM predictions')
        stats['total_predictions'] = cursor.fetchone()[0]

        # Feedback counts
        cursor.execute('SELECT COUNT(*) FROM feedback')
        stats['total_feedback'] = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM feedback WHERE was_correct = 1')
        stats['correct_predictions'] = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM feedback WHERE was_correct = 0')
        stats['corrected_predictions'] = cursor.fetchone()[0]

        # Category counts
        cursor.execute('SELECT COUNT(*) FROM categories WHERE is_active = 1')
        stats['active_categories'] = cursor.fetchone()[0]

        # Training sessions
        cursor.execute('SELECT COUNT(*) FROM training_sessions')
        stats['training_sessions'] = cursor.fetchone()[0]

        # Latest accuracy
        cursor.execute('SELECT accuracy FROM training_sessions ORDER BY id DESC LIMIT 1')
        row = cursor.fetchone()
        stats['latest_accuracy'] = row[0] if row else None

        return stats

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.logger.info("Database connection closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# Convenience function
def create_database(db_path: str = None):
    """
    Factory function to create training database.

    Args:
        db_path: Database file path

    Returns:
        Configured TrainingDatabase
    """
    return TrainingDatabase(db_path=db_path)
