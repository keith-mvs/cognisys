"""
DistilBERT Document Classifier
Fine-tuned transformer model for document classification
"""

import logging
import json
from typing import Dict, List, Optional
from pathlib import Path

try:
    import torch
    from transformers import DistilBertTokenizer, DistilBertForSequenceClassification
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

# Import content extraction
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


class DistilBERTClassifier:
    """
    DistilBERT-based document classifier.
    Uses fine-tuned transformer model for high-accuracy classification.
    """

    def __init__(
        self,
        model_dir: str = None,
        model_version: str = "v2",
        device: str = None,
        max_length: int = 256
    ):
        """
        Initialize DistilBERT classifier.

        Args:
            model_dir: Directory containing trained model
            model_version: Model version (v1, v2, etc.)
            device: Device to use (cuda/cpu)
            max_length: Max sequence length for tokenization
        """
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch and transformers not installed")

        self.logger = logging.getLogger(__name__)
        self.max_length = max_length

        # Set device
        if device is None:
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        else:
            self.device = torch.device(device)

        # Model paths
        if model_dir is None:
            base_dir = Path(__file__).parent.parent.parent / 'models'
            if model_version == "v2":
                model_dir = base_dir / 'distilbert_v2' / 'best_model'
            else:
                model_dir = base_dir / 'distilbert' / 'checkpoint_epoch3'

        self.model_dir = Path(model_dir)
        self.model = None
        self.tokenizer = None
        self.label_to_id = None
        self.id_to_label = None
        self.is_loaded = False

        self.logger.info(f"DistilBERT Classifier initialized")
        self.logger.info(f"Model dir: {self.model_dir}")
        self.logger.info(f"Device: {self.device}")

    def load_model(self) -> bool:
        """Load trained model and tokenizer."""
        try:
            if not self.model_dir.exists():
                self.logger.error(f"Model directory not found: {self.model_dir}")
                return False

            # Load label mapping
            label_mapping_path = self.model_dir.parent / 'label_mapping.json'
            if not label_mapping_path.exists():
                label_mapping_path = self.model_dir / 'label_mapping.json'

            if label_mapping_path.exists():
                with open(label_mapping_path) as f:
                    mapping = json.load(f)
                    self.label_to_id = mapping['label_to_id']
                    self.id_to_label = {int(k): v for k, v in mapping['id_to_label'].items()}
            else:
                self.logger.warning("Label mapping not found, predictions will be numeric")

            # Load model
            self.logger.info("Loading DistilBERT model...")
            self.model = DistilBertForSequenceClassification.from_pretrained(
                str(self.model_dir)
            )
            self.model.to(self.device)
            self.model.eval()

            # Load tokenizer
            self.tokenizer = DistilBertTokenizer.from_pretrained(str(self.model_dir))

            self.is_loaded = True
            self.logger.info(f"Model loaded successfully. Classes: {len(self.id_to_label) if self.id_to_label else 'unknown'}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to load model: {e}")
            return False

    def predict(self, text: str) -> Dict:
        """
        Predict document type for text content.

        Args:
            text: Document text content

        Returns:
            {
                'predicted_category': str,
                'confidence': float,
                'probabilities': Dict[str, float],
                'success': bool
            }
        """
        if not self.is_loaded:
            if not self.load_model():
                return {'success': False, 'error': 'Model not loaded'}

        try:
            # Tokenize
            inputs = self.tokenizer(
                text[:2000],  # Limit text length
                max_length=self.max_length,
                padding='max_length',
                truncation=True,
                return_tensors='pt'
            )

            # Move to device
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            # Predict
            with torch.no_grad():
                outputs = self.model(**inputs)
                logits = outputs.logits
                probs = torch.softmax(logits, dim=1)[0]

            # Get top prediction
            pred_id = torch.argmax(probs).item()
            confidence = probs[pred_id].item()

            # Map to label
            if self.id_to_label:
                predicted_label = self.id_to_label.get(pred_id, f"class_{pred_id}")
            else:
                predicted_label = f"class_{pred_id}"

            # Build probability dict (top 5)
            probs_np = probs.cpu().numpy()
            top_indices = probs_np.argsort()[-5:][::-1]

            probabilities = {}
            for idx in top_indices:
                label = self.id_to_label.get(idx, f"class_{idx}") if self.id_to_label else f"class_{idx}"
                probabilities[label] = float(probs_np[idx])

            return {
                'predicted_category': predicted_label,
                'confidence': confidence,
                'probabilities': probabilities,
                'success': True,
                'model': 'distilbert'
            }

        except Exception as e:
            self.logger.error(f"Prediction failed: {e}")
            return {'success': False, 'error': str(e)}

    def predict_file(self, file_path: str) -> Dict:
        """
        Predict document type for a file.

        Args:
            file_path: Path to file

        Returns:
            Prediction result dict
        """
        try:
            from ifmos.ml.content_extraction import ContentExtractor

            extractor = ContentExtractor(max_chars=2000)
            result = extractor.extract(Path(file_path))

            content = result.get('content', '')
            if not content:
                content = Path(file_path).name

            prediction = self.predict(content)
            prediction['file_path'] = str(file_path)
            return prediction

        except Exception as e:
            self.logger.error(f"File prediction failed: {e}")
            return {'success': False, 'error': str(e), 'file_path': str(file_path)}

    def predict_batch(self, texts: List[str], batch_size: int = 16) -> List[Dict]:
        """
        Predict document types for multiple texts.

        Args:
            texts: List of text contents
            batch_size: Batch size for inference

        Returns:
            List of prediction results
        """
        if not self.is_loaded:
            if not self.load_model():
                return [{'success': False, 'error': 'Model not loaded'}] * len(texts)

        results = []

        try:
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i + batch_size]

                # Tokenize batch
                inputs = self.tokenizer(
                    [t[:2000] for t in batch_texts],
                    max_length=self.max_length,
                    padding='max_length',
                    truncation=True,
                    return_tensors='pt'
                )

                inputs = {k: v.to(self.device) for k, v in inputs.items()}

                # Predict
                with torch.no_grad():
                    outputs = self.model(**inputs)
                    probs = torch.softmax(outputs.logits, dim=1)

                # Process each result
                for j in range(len(batch_texts)):
                    pred_id = torch.argmax(probs[j]).item()
                    confidence = probs[j][pred_id].item()

                    if self.id_to_label:
                        predicted_label = self.id_to_label.get(pred_id, f"class_{pred_id}")
                    else:
                        predicted_label = f"class_{pred_id}"

                    results.append({
                        'predicted_category': predicted_label,
                        'confidence': confidence,
                        'success': True,
                        'model': 'distilbert'
                    })

            return results

        except Exception as e:
            self.logger.error(f"Batch prediction failed: {e}")
            return [{'success': False, 'error': str(e)}] * len(texts)

    def get_model_info(self) -> Dict:
        """Get information about loaded model."""
        return {
            'model_type': 'DistilBERT',
            'model_dir': str(self.model_dir),
            'device': str(self.device),
            'is_loaded': self.is_loaded,
            'num_classes': len(self.id_to_label) if self.id_to_label else 0,
            'max_length': self.max_length
        }


# Factory function
def create_distilbert_classifier(
    model_version: str = "v2",
    device: str = None
) -> DistilBERTClassifier:
    """
    Create DistilBERT classifier.

    Args:
        model_version: Model version (v1 or v2)
        device: Device to use

    Returns:
        Configured classifier
    """
    return DistilBERTClassifier(model_version=model_version, device=device)
