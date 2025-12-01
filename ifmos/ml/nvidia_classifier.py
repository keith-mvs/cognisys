"""
NVIDIA AI Classifier for IFMOS

Uses NVIDIA NIM (NVIDIA Inference Microservices) for intelligent document classification
based on actual content, not just filenames.

Models supported:
- meta/llama-3.1-8b-instruct: General text understanding
- mistralai/mistral-7b-instruct: Document classification
- microsoft/phi-3-mini: Lightweight analysis

Author: Claude Code
Date: 2025-12-01
"""

import logging
import json
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import os

logger = logging.getLogger(__name__)


class NVIDIAClassifier:
    """
    Classify documents using NVIDIA AI models via API.

    Uses content-based classification for superior accuracy compared to filename-only approaches.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "meta/llama-3.1-8b-instruct",
        confidence_threshold: float = 0.85
    ):
        """
        Initialize NVIDIA classifier.

        Args:
            api_key: NVIDIA API key (or set NVIDIA_API_KEY env var)
            model: Model to use for classification
            confidence_threshold: Minimum confidence to accept classification
        """
        self.api_key = api_key or os.getenv('NVIDIA_API_KEY')
        self.model = model
        self.confidence_threshold = confidence_threshold

        # Check if API is available
        self.available = self._check_availability()

        # Document categories (from IFMOS)
        self.categories = [
            'archive', 'automotive_technical', 'backup_versioned',
            'business_presentation', 'business_spreadsheet',
            'compiled_code', 'dependency_python', 'design_cad',
            'financial_document', 'financial_invoice', 'legal_document',
            'media_audio', 'media_image', 'media_screenshot', 'media_video',
            'personal_career', 'personal_document',
            'software_installer', 'source_header',
            'technical_archive', 'technical_config', 'technical_dataset',
            'technical_documentation', 'technical_script',
            'unknown'
        ]

    def _check_availability(self) -> bool:
        """Check if NVIDIA API is available"""
        if not self.api_key:
            logger.warning("NVIDIA API key not provided - classifier unavailable")
            return False

        try:
            import openai
            self.has_openai = True
            return True
        except ImportError:
            logger.warning("openai package not installed - NVIDIA classifier unavailable")
            self.has_openai = False
            return False

    def classify(self, content: str, filename: str = "") -> Dict[str, any]:
        """
        Classify document based on content.

        Args:
            content: Document content (first 2000 chars)
            filename: Optional filename for context

        Returns:
            Dictionary with:
            - category: Predicted document type
            - confidence: Confidence score (0-1)
            - reasoning: Why this classification was chosen
            - method: 'nvidia_ai'
            - success: Boolean
            - error: Error message if failed
        """
        if not self.available:
            return {
                'category': 'unknown',
                'confidence': 0.0,
                'reasoning': None,
                'method': 'nvidia_unavailable',
                'success': False,
                'error': 'NVIDIA API not available'
            }

        if not content or len(content.strip()) == 0:
            return {
                'category': 'unknown',
                'confidence': 0.0,
                'reasoning': 'No content to analyze',
                'method': 'nvidia_ai',
                'success': False,
                'error': 'Empty content'
            }

        try:
            import openai

            # Initialize OpenAI client with NVIDIA endpoint
            client = openai.OpenAI(
                base_url="https://integrate.api.nvidia.com/v1",
                api_key=self.api_key
            )

            # Build prompt
            prompt = self._build_classification_prompt(content, filename)

            # Call API
            response = client.chat.completions.create(
                model=self.model,
                messages=[{
                    "role": "user",
                    "content": prompt
                }],
                temperature=0.1,  # Low temperature for consistent classification
                max_tokens=200
            )

            # Parse response
            result_text = response.choices[0].message.content.strip()

            # Try to parse as JSON
            try:
                result = json.loads(result_text)
            except json.JSONDecodeError:
                # Fallback: extract from text
                result = self._parse_text_response(result_text)

            category = result.get('category', 'unknown')
            confidence = float(result.get('confidence', 0.0))
            reasoning = result.get('reasoning', '')

            # Validate category
            if category not in self.categories:
                logger.warning(f"Invalid category returned: {category}, defaulting to 'unknown'")
                category = 'unknown'
                confidence = 0.0

            return {
                'category': category,
                'confidence': confidence,
                'reasoning': reasoning,
                'method': 'nvidia_ai',
                'success': confidence >= self.confidence_threshold
            }

        except Exception as e:
            logger.error(f"NVIDIA API error: {e}")
            return {
                'category': 'unknown',
                'confidence': 0.0,
                'reasoning': None,
                'method': 'nvidia_error',
                'success': False,
                'error': str(e)
            }

    def _build_classification_prompt(self, content: str, filename: str = "") -> str:
        """Build classification prompt for NVIDIA AI"""
        categories_str = ', '.join(self.categories)

        prompt = f"""You are a document classification expert. Classify this document into ONE of these categories:

{categories_str}

Document filename: {filename if filename else 'unknown'}

Document content (first 2000 chars):
{content}

Return a JSON object with:
- category: The best matching category from the list above
- confidence: A number from 0.0 to 1.0 indicating confidence
- reasoning: Brief explanation (1 sentence) why you chose this category

Consider:
- The actual content and purpose of the document
- Keywords and technical terms
- Document structure and formatting
- Financial data (invoices have line items, amounts, payment terms)
- Technical content (code has syntax, configs have key-value pairs)
- Legal language (contracts have parties, terms, signatures)

Be accurate and conservative with confidence scores.

JSON response:"""

        return prompt

    def _parse_text_response(self, text: str) -> Dict:
        """Fallback parser if JSON parsing fails"""
        # Try to extract category and confidence from text
        result = {
            'category': 'unknown',
            'confidence': 0.0,
            'reasoning': text[:100]  # First 100 chars as reasoning
        }

        # Look for category mentions
        text_lower = text.lower()
        for category in self.categories:
            if category.lower() in text_lower:
                result['category'] = category
                break

        # Look for confidence score (0.XX or 0.X format)
        import re
        confidence_match = re.search(r'confidence["\s:]+(\d+\.?\d*)', text_lower)
        if confidence_match:
            try:
                result['confidence'] = float(confidence_match.group(1))
                # If > 1.0, assume it's a percentage
                if result['confidence'] > 1.0:
                    result['confidence'] /= 100.0
            except ValueError:
                pass

        return result

    def classify_batch(self, documents: List[Tuple[str, str]]) -> List[Dict]:
        """
        Classify multiple documents.

        Args:
            documents: List of (content, filename) tuples

        Returns:
            List of classification results
        """
        results = []
        for content, filename in documents:
            result = self.classify(content, filename)
            results.append(result)

        return results


# Example usage
if __name__ == '__main__':
    import sys

    logging.basicConfig(level=logging.INFO)

    # Test with sample content
    sample_invoice = """
    Invoice #12345
    Date: 2024-11-30
    From: Acme Corporation
    To: Beta LLC

    Line Items:
    1. Widget A - Qty: 10 - Price: $100.00
    2. Service B - Qty: 1 - Price: $234.56

    Subtotal: $1,234.56
    Tax (8%): $98.76
    Total Due: $1,333.32

    Payment Terms: Net 30
    """

    sample_code = """
    import numpy as np
    from sklearn.ensemble import RandomForestClassifier

    def train_model(X, y):
        clf = RandomForestClassifier(n_estimators=200)
        clf.fit(X, y)
        return clf
    """

    sample_contract = """
    SERVICE AGREEMENT

    This agreement entered into on January 1, 2024, between:
    - Party A: Acme Corp
    - Party B: Beta LLC

    Terms:
    1. Monthly service fee: $5,000
    2. Term: 12 months
    3. Termination: 30-day notice required
    4. Confidentiality clause applies

    Signatures:
    _______________  _______________
    """

    # Initialize classifier
    api_key = os.getenv('NVIDIA_API_KEY')
    if not api_key:
        print("ERROR: NVIDIA_API_KEY environment variable not set")
        print("Set it with: $env:NVIDIA_API_KEY = 'nvapi-...'")
        sys.exit(1)

    classifier = NVIDIAClassifier(api_key=api_key)

    # Test samples
    samples = [
        (sample_invoice, "invoice_acme_12345.pdf"),
        (sample_code, "train_model.py"),
        (sample_contract, "service_agreement_2024.pdf")
    ]

    print(f"\n{'='*80}")
    print("NVIDIA AI CLASSIFICATION TEST")
    print(f"{'='*80}\n")

    for content, filename in samples:
        print(f"Classifying: {filename}")
        print(f"{'-'*80}")

        result = classifier.classify(content, filename)

        print(f"Category: {result['category']}")
        print(f"Confidence: {result['confidence']:.2%}")
        print(f"Reasoning: {result['reasoning']}")
        print(f"Success: {result['success']}")

        if not result['success'] and 'error' in result:
            print(f"Error: {result['error']}")

        print(f"{'-'*80}\n")

    print(f"{'='*80}\n")
