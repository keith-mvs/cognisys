"""
NVIDIA AI Classifier
Uses NVIDIA NIM API for document classification
"""

import os
import requests
from typing import Dict, Optional
from pathlib import Path
import time


class NvidiaAIClassifier:
    """
    Document classifier using NVIDIA AI Foundation Models API.
    Uses Llama or Mistral for zero-shot classification.
    """

    def __init__(
        self,
        api_key: str = None,
        model: str = "meta/llama-3.1-8b-instruct",
        base_url: str = "https://integrate.api.nvidia.com/v1",
        timeout: int = 30
    ):
        """
        Initialize NVIDIA AI classifier.

        Args:
            api_key: NVIDIA API key (or set NVIDIA_API_KEY env var)
            model: Model to use
            base_url: NVIDIA API base URL
            timeout: Request timeout in seconds
        """
        self.api_key = api_key or os.getenv('NVIDIA_API_KEY')
        if not self.api_key:
            raise ValueError("NVIDIA_API_KEY not provided")

        self.model = model
        self.base_url = base_url
        self.timeout = timeout

        # Document categories (same as DistilBERT)
        self.categories = [
            "business_financial", "business_invoice", "business_receipt",
            "business_contract", "business_memo", "business_presentation",
            "legal_document", "legal_contract", "legal_agreement",
            "medical_record", "medical_report", "medical_prescription",
            "tax_form", "tax_receipt", "tax_statement",
            "personal_career", "personal_document", "personal_journal",
            "academic_research", "academic_thesis", "academic_article",
            "technical_documentation", "technical_manual", "technical_spec",
            "technical_config", "technical_script", "technical_log",
            "creative_writing", "creative_design", "creative_art",
            "communication_email", "communication_letter", "communication_memo",
            "education_textbook", "education_course", "education_assignment",
            "form_application", "form_survey", "form_questionnaire",
            "cache_package_manager", "design_document", "web_template"
        ]

    def predict(self, text: str, max_chars: int = 2000) -> Dict:
        """
        Classify document text using NVIDIA AI.

        Args:
            text: Document text content
            max_chars: Maximum characters to send to API

        Returns:
            {
                'predicted_category': str,
                'confidence': float,
                'probabilities': dict,
                'success': bool,
                'model_used': str
            }
        """
        try:
            # Truncate text
            text_sample = text[:max_chars]

            # Build prompt
            prompt = self._build_classification_prompt(text_sample)

            # Call NVIDIA API
            response = self._call_api(prompt)

            # Parse response
            result = self._parse_response(response)
            result['model_used'] = f"nvidia_{self.model.split('/')[-1]}"

            return result

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'predicted_category': 'unknown',
                'confidence': 0.0
            }

    def _build_classification_prompt(self, text: str) -> str:
        """Build few-shot classification prompt."""
        categories_str = ', '.join(self.categories[:20])  # First 20 for brevity

        prompt = f"""You are a document classification expert. Classify the following document into one of these categories:

{categories_str}

Document text:
---
{text}
---

Respond with ONLY the category name, nothing else. Choose the most specific category that fits."""

        return prompt

    def _call_api(self, prompt: str) -> str:
        """Call NVIDIA API."""
        url = f"{self.base_url}/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.1,
            "top_p": 0.9,
            "max_tokens": 50
        }

        start_time = time.time()
        response = requests.post(url, headers=headers, json=data, timeout=self.timeout)
        latency = time.time() - start_time

        response.raise_for_status()

        result = response.json()
        content = result['choices'][0]['message']['content'].strip()

        return content

    def _parse_response(self, response: str) -> Dict:
        """Parse API response and extract category."""
        # Clean response
        category = response.lower().strip()

        # Remove common prefixes
        category = category.replace('category:', '').strip()
        category = category.replace('answer:', '').strip()

        # Match to known categories
        matched_category = None
        max_overlap = 0

        for cat in self.categories:
            # Check for exact match
            if cat == category:
                matched_category = cat
                break

            # Check for partial match
            overlap = sum(1 for c in category.split('_') if c in cat.split('_'))
            if overlap > max_overlap:
                max_overlap = overlap
                matched_category = cat

        # Default if no match
        if not matched_category or max_overlap == 0:
            matched_category = 'personal_document'

        # Confidence based on match quality
        confidence = min(0.95, 0.6 + (max_overlap * 0.1))

        return {
            'predicted_category': matched_category,
            'confidence': confidence,
            'probabilities': {matched_category: confidence},
            'success': True,
            'raw_response': response
        }

    def predict_batch(self, texts: list, batch_size: int = 10) -> list:
        """
        Batch prediction (sequential to avoid rate limits).

        Args:
            texts: List of text strings
            batch_size: Not used (kept for API compatibility)

        Returns:
            List of prediction results
        """
        results = []
        for text in texts:
            result = self.predict(text)
            results.append(result)
            time.sleep(0.1)  # Rate limiting

        return results


def create_nvidia_classifier(
    api_key: str = None,
    model: str = "meta/llama-3.1-8b-instruct"
) -> NvidiaAIClassifier:
    """
    Factory function to create NVIDIA AI classifier.

    Args:
        api_key: NVIDIA API key
        model: Model to use

    Returns:
        Configured NvidiaAIClassifier
    """
    return NvidiaAIClassifier(api_key=api_key, model=model)
