"""
ML Classifier Engine for IFMOS.
Provides content-based document classification using trained ML models.
"""

import uuid
import time
from pathlib import Path
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from ..models.database import Database
from ..ml.content_extraction import ContentExtractor
from ..ml.classification import (
    create_distilbert_classifier,
    create_cascade,
    RuleBasedClassifier
)
from ..utils.logging_config import get_logger

logger = get_logger(__name__)


class MLClassifier:
    """
    ML-based document classifier for IFMOS files.
    Supports multiple classifier backends and batch processing.
    """

    def __init__(
        self,
        database: Database,
        model: str = "distilbert_v2",
        cascade_preset: str = None,
        batch_size: int = 32,
        max_workers: int = 4
    ):
        """
        Initialize ML classifier.

        Args:
            database: Database instance
            model: Model to use (distilbert_v2, rule_based, or cascade preset)
            cascade_preset: If set, use cascade classifier with this preset
            batch_size: Batch size for classification
            max_workers: Number of worker threads for content extraction
        """
        self.db = database
        self.model_name = model
        self.cascade_preset = cascade_preset
        self.batch_size = batch_size
        self.max_workers = max_workers
        self.lock = threading.Lock()

        # Stats
        self.stats = {
            'files_classified': 0,
            'errors': 0,
            'high_confidence': 0,
            'low_confidence': 0,
            'total_time': 0
        }

        # Initialize classifier
        self._init_classifier()

        # Content extractor
        self.extractor = ContentExtractor(max_chars=2000)

        logger.info(f"ML Classifier initialized: {self.model_name}")

    def _init_classifier(self):
        """Initialize the appropriate classifier."""
        if self.cascade_preset:
            self.classifier = create_cascade(self.cascade_preset)
            self.model_name = f"cascade_{self.cascade_preset}"
        elif self.model_name == "distilbert_v2":
            self.classifier = create_distilbert_classifier("v2")
        elif self.model_name == "distilbert_v1":
            self.classifier = create_distilbert_classifier("v1")
        elif self.model_name == "rule_based":
            self.classifier = RuleBasedClassifier()
        else:
            # Default to cascade with local_only preset
            self.classifier = create_cascade("local_only")
            self.model_name = "cascade_local_only"

    def classify_session(
        self,
        session_id: str,
        min_size: int = 100,
        extensions: List[str] = None,
        limit: int = None
    ) -> Dict:
        """
        Classify all files in a scan session.

        Args:
            session_id: Session ID to classify
            min_size: Minimum file size to classify (skip tiny files)
            extensions: Optional list of extensions to classify
            limit: Optional limit on number of files

        Returns:
            Classification statistics
        """
        logger.info(f"Starting classification for session: {session_id}")
        start_time = time.time()

        # Get files from session
        cursor = self.db.conn.cursor()

        query = """
            SELECT file_id, path, name, extension, size_bytes
            FROM files
            WHERE scan_session_id = ?
            AND size_bytes >= ?
        """
        params = [session_id, min_size]

        if extensions:
            placeholders = ','.join('?' * len(extensions))
            query += f" AND extension IN ({placeholders})"
            params.extend([f".{e.lstrip('.')}" for e in extensions])

        if limit:
            query += f" LIMIT {limit}"

        cursor.execute(query, params)
        files = [dict(row) for row in cursor.fetchall()]

        logger.info(f"Found {len(files)} files to classify")

        # Process in batches
        classifications = []
        batch_results = []

        for i in range(0, len(files), self.batch_size):
            batch = files[i:i + self.batch_size]
            batch_classifications = self._classify_batch(batch, session_id)
            classifications.extend(batch_classifications)

            # Store batch results
            if batch_classifications:
                self.db.insert_ml_classifications_batch(batch_classifications)

            # Progress logging
            progress = min(i + self.batch_size, len(files))
            elapsed = time.time() - start_time
            rate = progress / elapsed if elapsed > 0 else 0
            logger.info(
                f"[PROGRESS] {progress}/{len(files)} files | "
                f"{rate:.1f} files/sec | "
                f"High conf: {self.stats['high_confidence']} | "
                f"Errors: {self.stats['errors']}"
            )

        # Final stats
        self.stats['total_time'] = time.time() - start_time

        logger.info(f"[OK] Classification complete!")
        logger.info(f"  Files classified: {self.stats['files_classified']}")
        logger.info(f"  High confidence (>=0.7): {self.stats['high_confidence']}")
        logger.info(f"  Low confidence (<0.5): {self.stats['low_confidence']}")
        logger.info(f"  Errors: {self.stats['errors']}")
        logger.info(f"  Duration: {self.stats['total_time']:.1f}s")

        return self.stats.copy()

    def _classify_batch(self, files: List[Dict], session_id: str) -> List[Dict]:
        """Classify a batch of files."""
        results = []

        # Extract content in parallel
        contents = {}
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_file = {
                executor.submit(self._extract_content, f['path']): f
                for f in files
            }

            for future in as_completed(future_to_file):
                file_info = future_to_file[future]
                try:
                    content = future.result()
                    contents[file_info['file_id']] = content
                except Exception as e:
                    logger.debug(f"Content extraction failed: {file_info['path']}: {e}")
                    with self.lock:
                        self.stats['errors'] += 1

        # Classify each file
        for file_info in files:
            file_id = file_info['file_id']
            content = contents.get(file_id)

            if not content:
                continue

            try:
                # Get prediction
                if hasattr(self.classifier, 'predict'):
                    result = self.classifier.predict(content)
                else:
                    result = self.classifier.classify(content)

                if result.get('success'):
                    confidence = result.get('confidence', 0)

                    classification = {
                        'classification_id': str(uuid.uuid4()),
                        'file_id': file_id,
                        'model_name': result.get('model_used', self.model_name),
                        'predicted_category': result['predicted_category'],
                        'confidence': confidence,
                        'probabilities': result.get('probabilities', {}),
                        'session_id': session_id
                    }
                    results.append(classification)

                    with self.lock:
                        self.stats['files_classified'] += 1
                        if confidence >= 0.7:
                            self.stats['high_confidence'] += 1
                        elif confidence < 0.5:
                            self.stats['low_confidence'] += 1

            except Exception as e:
                logger.debug(f"Classification failed: {file_info['path']}: {e}")
                with self.lock:
                    self.stats['errors'] += 1

        return results

    def _extract_content(self, file_path: str) -> Optional[str]:
        """Extract text content from file."""
        try:
            result = self.extractor.extract(Path(file_path))
            content = result.get('content', '')
            if not content:
                content = Path(file_path).name
            return content
        except Exception:
            return Path(file_path).name

    def classify_file(self, file_path: str) -> Dict:
        """
        Classify a single file.

        Args:
            file_path: Path to file

        Returns:
            Classification result
        """
        content = self._extract_content(file_path)

        if hasattr(self.classifier, 'predict'):
            result = self.classifier.predict(content)
        else:
            result = self.classifier.classify(content)

        result['file_path'] = file_path
        return result

    def get_stats(self) -> Dict:
        """Get classification statistics."""
        return self.stats.copy()
