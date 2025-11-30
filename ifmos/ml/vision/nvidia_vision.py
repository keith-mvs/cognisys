"""
NVIDIA Vision Integration for IFMOS
Uses NVIDIA NIM APIs for image-to-text and content understanding
"""

import os
import logging
from pathlib import Path
from typing import Optional, Tuple
import requests

logger = logging.getLogger(__name__)


class NVIDIAVisionClassifier:
    """
    NVIDIA Vision-based classification for images and PDFs
    Uses NVIDIA Cosmos NEVA-22B for content understanding
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize NVIDIA Vision classifier

        Args:
            api_key: NVIDIA API key (or set NVIDIA_API_KEY env var)
        """
        self.api_key = api_key or os.getenv('NVIDIA_API_KEY')
        self.base_url = "https://integrate.api.nvidia.com/v1"
        self.model = "nvidia/neva-22b"  # NVIDIA Cosmos NEVA-22B

        if not self.api_key:
            logger.warning("NVIDIA API key not found - vision classification unavailable")
            logger.warning("Set NVIDIA_API_KEY environment variable or pass api_key parameter")

    def classify_image(self, image_path: Path) -> Tuple[Optional[str], float, str]:
        """
        Classify an image file using NVIDIA vision model

        Args:
            image_path: Path to image file

        Returns:
            (document_type, confidence, method) or (None, 0.0, None) if failed
        """
        if not self.api_key:
            return None, 0.0, None

        try:
            # Read image
            with open(image_path, 'rb') as f:
                image_data = f.read()

            # Call NVIDIA API
            response = self._call_nvidia_api(image_data, image_path.suffix)

            if not response:
                return None, 0.0, None

            # Parse response and determine category
            doc_type, confidence = self._parse_description(response)

            if doc_type:
                return doc_type, confidence, 'nvidia_vision'

            return None, 0.0, None

        except Exception as e:
            logger.error(f"NVIDIA vision classification failed for {image_path}: {e}")
            return None, 0.0, None

    def _call_nvidia_api(self, image_data: bytes, file_ext: str) -> Optional[str]:
        """
        Call NVIDIA NIM API for image description

        Args:
            image_data: Image binary data
            file_ext: File extension (.png, .jpg, .pdf, etc.)

        Returns:
            Image description text or None if failed
        """
        try:
            # Prepare request
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            # For image-to-text, we need to prompt the model
            prompt = """Analyze this image and describe its content in 2-3 sentences.
            Specifically identify if it contains:
            - Code or terminal output
            - Charts, graphs, or data visualizations
            - Invoices, receipts, or financial documents
            - Technical diagrams or schematics
            - Screenshots of applications
            - Photos of people, places, or objects
            - Documents with text"""

            payload = {
                "model": self.model,
                "prompt": prompt,
                "image": image_data.decode('latin-1'),  # Base64 or binary encoding
                "max_tokens": 150,
                "temperature": 0.2  # Low temperature for consistent classification
            }

            # Make request
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                description = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                return description
            else:
                logger.error(f"NVIDIA API error: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            logger.error(f"NVIDIA API call failed: {e}")
            return None

    def _parse_description(self, description: str) -> Tuple[Optional[str], float]:
        """
        Parse NVIDIA description and map to document type

        Args:
            description: Text description from NVIDIA vision model

        Returns:
            (document_type, confidence)
        """
        desc_lower = description.lower()

        # Code/Terminal
        if any(term in desc_lower for term in ['code', 'terminal', 'programming', 'script', 'syntax']):
            return 'media_screenshot_code', 0.85

        # Charts/Visualizations
        if any(term in desc_lower for term in ['chart', 'graph', 'visualization', 'plot', 'data vis']):
            return 'media_screenshot_dataviz', 0.85

        # Financial
        if any(term in desc_lower for term in ['invoice', 'receipt', 'bill', 'payment', 'total $', 'amount due']):
            return 'financial_invoice', 0.90

        # Technical diagrams
        if any(term in desc_lower for term in ['diagram', 'schematic', 'blueprint', 'circuit', 'flowchart']):
            return 'design_diagram', 0.85

        # Screenshots (general)
        if any(term in desc_lower for term in ['screenshot', 'application', 'user interface', 'window']):
            return 'media_screenshot', 0.80

        # Photos
        if any(term in desc_lower for term in ['photo', 'photograph', 'picture of', 'showing']):
            return 'media_image', 0.75

        # Documents with text
        if any(term in desc_lower for term in ['document', 'text', 'page', 'paragraph']):
            return 'scanned_document', 0.75

        # Default: couldn't determine
        return None, 0.0

    def classify_pdf(self, pdf_path: Path) -> Tuple[Optional[str], float, str]:
        """
        Classify a PDF by rendering first page to image and analyzing

        Args:
            pdf_path: Path to PDF file

        Returns:
            (document_type, confidence, method)
        """
        # For now, treat PDFs as images (render first page)
        # In production, you might want to use pdf2image
        logger.info(f"PDF classification not yet implemented for {pdf_path}")
        return None, 0.0, None


# Example usage
def test_nvidia_vision():
    """Test NVIDIA vision classification"""
    classifier = NVIDIAVisionClassifier()

    # Test on a sample image
    test_image = Path("sample_screenshot.png")
    if test_image.exists():
        doc_type, conf, method = classifier.classify_image(test_image)
        print(f"Classification: {doc_type} (confidence: {conf:.2f}, method: {method})")


if __name__ == '__main__':
    test_nvidia_vision()
