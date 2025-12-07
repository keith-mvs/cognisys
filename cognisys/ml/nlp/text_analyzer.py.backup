"""
Text Analysis Pipeline
Entity recognition, keyword extraction, and document understanding
"""

import logging
from typing import Dict, List, Optional, Set
from collections import Counter
import re

try:
    import spacy
    from spacy.tokens import Doc
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False

try:
    import nltk
    from nltk.corpus import stopwords
    from nltk.tokenize import word_tokenize
    NLTK_AVAILABLE = True
except ImportError:
    NLTK_AVAILABLE = False


class TextAnalyzer:
    """
    Advanced text analysis using spaCy and NLTK.
    Extracts entities, keywords, and document features for classification.
    """

    def __init__(self, language_model: str = "en_core_web_sm"):
        """
        Initialize text analyzer.

        Args:
            language_model: spaCy model to use (default: en_core_web_sm)
        """
        self.logger = logging.getLogger(__name__)

        # Load spaCy model
        if not SPACY_AVAILABLE:
            raise ImportError("spaCy not installed. Run: pip install spacy")

        try:
            self.nlp = spacy.load(language_model)
            self.logger.info(f"Loaded spaCy model: {language_model}")
        except OSError:
            self.logger.error(f"spaCy model '{language_model}' not found. Run: python -m spacy download {language_model}")
            raise

        # Initialize NLTK
        if NLTK_AVAILABLE:
            try:
                self.stop_words = set(stopwords.words('english'))
            except LookupError:
                self.logger.warning("NLTK stopwords not found. Downloading...")
                nltk.download('stopwords', quiet=True)
                nltk.download('punkt', quiet=True)
                self.stop_words = set(stopwords.words('english'))
        else:
            self.logger.warning("NLTK not available. Using basic stopword list.")
            self.stop_words = set(['the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for'])

    def analyze_text(self, text: str, filename: str = "") -> Dict:
        """
        Perform comprehensive text analysis.

        Args:
            text: Input text to analyze
            filename: Optional filename for context (helps with classification)

        Returns:
            {
                'entities': List[Dict],      # Named entities found
                'keywords': List[str],       # Important keywords
                'summary': str,              # Brief summary
                'document_type': str,        # Inferred document type
                'features': Dict,            # Classification features
                'sentiment': str,            # Basic sentiment
                'statistics': Dict           # Text statistics
            }
        """
        if not text or len(text.strip()) < 10:
            return self._empty_result()

        try:
            # Process text with spaCy
            doc = self.nlp(text[:1000000])  # Limit to 1M chars for performance

            # Extract entities
            entities = self._extract_entities(doc)

            # Extract keywords
            keywords = self._extract_keywords(doc)

            # Infer document type (now with filename context)
            doc_type = self._infer_document_type(text, entities, keywords, filename)

            # Extract classification features
            features = self._extract_features(doc, entities, keywords)

            # Basic sentiment
            sentiment = self._analyze_sentiment(doc)

            # Statistics
            statistics = self._compute_statistics(text, doc)

            # Generate summary (first sentence or key information)
            summary = self._generate_summary(doc, entities)

            return {
                'entities': entities,
                'keywords': keywords[:20],  # Top 20 keywords
                'summary': summary,
                'document_type': doc_type,
                'features': features,
                'sentiment': sentiment,
                'statistics': statistics,
                'success': True
            }

        except Exception as e:
            self.logger.error(f"Text analysis failed: {e}")
            return self._empty_result(error=str(e))

    def _extract_entities(self, doc: Doc) -> List[Dict]:
        """Extract named entities (people, organizations, dates, money, etc.)."""
        entities = []
        seen = set()

        for ent in doc.ents:
            # Deduplicate entities
            key = (ent.text.lower(), ent.label_)
            if key not in seen:
                entities.append({
                    'text': ent.text,
                    'label': ent.label_,
                    'description': spacy.explain(ent.label_)
                })
                seen.add(key)

        # Sort by entity type priority for classification
        priority = ['ORG', 'PERSON', 'DATE', 'MONEY', 'GPE', 'PRODUCT']
        entities.sort(key=lambda x: priority.index(x['label']) if x['label'] in priority else 99)

        return entities

    def _extract_keywords(self, doc: Doc) -> List[str]:
        """Extract important keywords using frequency and POS filtering."""
        # Filter for nouns, proper nouns, and verbs
        word_freq = Counter()

        for token in doc:
            # Skip stopwords, punctuation, and short words
            if (token.is_stop or
                token.is_punct or
                len(token.text) < 3 or
                token.pos_ not in ['NOUN', 'PROPN', 'VERB', 'ADJ']):
                continue

            # Normalize to lowercase lemma
            lemma = token.lemma_.lower()
            word_freq[lemma] += 1

        # Get most common keywords
        keywords = [word for word, count in word_freq.most_common(50)]

        return keywords

    def _infer_document_type(self, text: str, entities: List[Dict], keywords: List[str], filename: str = "") -> str:
        """
        Infer document type using multi-signal classification with confidence scoring.

        Enhanced approach:
        - Uses filename patterns (extension, naming conventions)
        - Contextual keyword matching (not just presence)
        - Confidence scoring (requires minimum threshold)
        - More granular categories
        - Hierarchical fallback logic

        Types: invoice, contract, letter, report, form, resume, email, legal, financial, medical, technical, etc.
        """
        text_lower = text.lower()
        entity_labels = [e['label'] for e in entities]
        filename_lower = filename.lower() if filename else ""

        # Score-based classification (category -> confidence score)
        scores = {}

        # === FILENAME-BASED CLASSIFICATION (highest priority) ===
        # Technical documents
        if any(ext in filename_lower for ext in ['.json', '.xml', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf']):
            scores['technical_config'] = 95

        if any(ext in filename_lower for ext in ['.py', '.js', '.java', '.cpp', '.c', '.h', '.cs', '.go', '.rs']):
            scores['technical_code'] = 95

        if any(ext in filename_lower for ext in ['.md', '.rst', '.txt']):
            if any(pattern in filename_lower for pattern in ['readme', 'doc', 'guide', 'manual']):
                scores['technical_documentation'] = 90

        # Resume patterns in filename
        if any(pattern in filename_lower for pattern in ['resume', 'cv', 'curriculum']):
            scores['hr_resume'] = 85

        # Invoice patterns in filename
        if any(pattern in filename_lower for pattern in ['invoice', 'bill', 'receipt']):
            scores['financial_invoice'] = 80

        # === CONTENT-BASED CLASSIFICATION ===
        # Financial - Invoice (strict contextual matching)
        invoice_score = 0
        if self._contains_phrase(text_lower, ['invoice number', 'bill to', 'invoice date', 'due date']):
            invoice_score += 40
        if 'MONEY' in entity_labels and len([e for e in entities if e['label'] == 'MONEY']) >= 2:
            invoice_score += 20
        if self._contains_phrase(text_lower, ['amount due', 'total amount', 'subtotal', 'tax amount']):
            invoice_score += 20
        if self._contains_phrase(text_lower, ['payment terms', 'pay by', 'remit to']):
            invoice_score += 10
        if invoice_score >= 40:
            scores['financial_invoice'] = invoice_score

        # Financial - Bank Statement
        statement_score = 0
        if self._contains_phrase(text_lower, ['account number', 'statement period', 'beginning balance', 'ending balance']):
            statement_score += 40
        if self._contains_phrase(text_lower, ['transaction', 'deposit', 'withdrawal', 'debit', 'credit']):
            statement_score += 20
        if 'DATE' in entity_labels and len([e for e in entities if e['label'] == 'DATE']) >= 3:
            statement_score += 10
        if statement_score >= 40:
            scores['financial_statement'] = statement_score

        # Legal - Contract
        contract_score = 0
        if self._contains_phrase(text_lower, ['this agreement', 'parties agree', 'hereby', 'whereas']):
            contract_score += 40
        if self._contains_phrase(text_lower, ['terms and conditions', 'effective date', 'termination']):
            contract_score += 20
        if 'DATE' in entity_labels and 'PERSON' in entity_labels:
            contract_score += 10
        if contract_score >= 40:
            scores['legal_contract'] = contract_score

        # Legal - Court Document
        court_score = 0
        if self._contains_phrase(text_lower, ['plaintiff', 'defendant', 'case number', 'court']):
            court_score += 40
        if self._contains_phrase(text_lower, ['motion', 'hearing', 'order', 'judgment']):
            court_score += 20
        if court_score >= 40:
            scores['legal_court'] = court_score

        # Medical
        medical_score = 0
        if self._contains_phrase(text_lower, ['patient', 'diagnosis', 'treatment', 'prescription']):
            medical_score += 40
        if self._contains_phrase(text_lower, ['medical history', 'symptoms', 'medication', 'doctor']):
            medical_score += 20
        if 'DATE' in entity_labels:
            medical_score += 5
        if medical_score >= 40:
            scores['medical'] = medical_score

        # HR - Resume (strict matching to avoid false positives)
        resume_score = 0
        if self._contains_phrase(text_lower, ['professional experience', 'work experience', 'employment history']):
            resume_score += 30
        if self._contains_phrase(text_lower, ['education', 'degree', 'university', 'graduated']):
            resume_score += 20
        if self._contains_phrase(text_lower, ['skills', 'proficient', 'expertise']):
            resume_score += 15
        if self._contains_phrase(text_lower, ['resume', 'curriculum vitae', 'cv']):
            resume_score += 15
        if resume_score >= 40:
            scores['hr_resume'] = resume_score

        # Tax Documents
        tax_score = 0
        if self._contains_phrase(text_lower, ['1099', 'w-2', 'w2', '1040', 'tax return']):
            tax_score += 50
        if self._contains_phrase(text_lower, ['tax year', 'taxable income', 'withholding']):
            tax_score += 20
        if 'irs' in text_lower:
            tax_score += 10
        if tax_score >= 40:
            scores['tax_document'] = tax_score

        # Business Communication
        if self._contains_phrase(text_lower, ['dear', 'sincerely', 'regards', 'best regards']):
            if '@' in text and 'from:' in text_lower:
                scores['communication_email'] = 60
            else:
                scores['communication_letter'] = 55

        # Forms
        form_score = 0
        if self._contains_phrase(text_lower, ['application form', 'please fill', 'signature required']):
            form_score += 30
        if text_lower.count('☐') > 5 or text_lower.count('[ ]') > 5:  # Checkboxes
            form_score += 20
        if form_score >= 30:
            scores['form'] = form_score

        # Technical - User Manual
        if self._contains_phrase(text_lower, ['user manual', 'installation guide', 'troubleshooting', 'specifications']):
            scores['technical_manual'] = 60

        # Technical - Research Paper
        if self._contains_phrase(text_lower, ['abstract', 'introduction', 'methodology', 'conclusion', 'references']):
            if len([e for e in entities if e['label'] == 'PERSON']) >= 3:  # Multiple authors
                scores['technical_research'] = 65

        # Reports
        if self._contains_phrase(text_lower, ['executive summary', 'findings', 'recommendations', 'analysis']):
            scores['report'] = 50

        # === SELECT BEST CATEGORY ===
        if scores:
            # Return category with highest confidence
            best_category = max(scores.items(), key=lambda x: x[1])
            return best_category[0]

        # === FALLBACK: Use simple keyword matching for uncategorized ===
        # Only if nothing else matched above
        if len(text) < 500:
            return 'general_document_short'

        return 'general_document'

    def _contains_phrase(self, text: str, phrases: List[str]) -> bool:
        """Check if text contains any of the given phrases (as whole phrases, not just keywords)."""
        return any(phrase in text for phrase in phrases)

    def _extract_features(self, doc: Doc, entities: List[Dict], keywords: List[str]) -> Dict:
        """
        Extract features for ML classification.

        Returns structured features that can be used by classifiers.
        """
        entity_counts = Counter(e['label'] for e in entities)

        features = {
            # Entity features
            'has_person': 'PERSON' in entity_counts,
            'has_organization': 'ORG' in entity_counts,
            'has_date': 'DATE' in entity_counts,
            'has_money': 'MONEY' in entity_counts,
            'has_location': 'GPE' in entity_counts or 'LOC' in entity_counts,
            'person_count': entity_counts.get('PERSON', 0),
            'org_count': entity_counts.get('ORG', 0),
            'date_count': entity_counts.get('DATE', 0),
            'money_count': entity_counts.get('MONEY', 0),

            # Keyword features
            'keyword_count': len(keywords),
            'top_keywords': keywords[:10],

            # Text structure features
            'sentence_count': len(list(doc.sents)),
            'avg_sentence_length': sum(len(sent) for sent in doc.sents) / max(len(list(doc.sents)), 1),

            # POS tag distributions
            'noun_ratio': len([t for t in doc if t.pos_ == 'NOUN']) / max(len(doc), 1),
            'verb_ratio': len([t for t in doc if t.pos_ == 'VERB']) / max(len(doc), 1),
            'adj_ratio': len([t for t in doc if t.pos_ == 'ADJ']) / max(len(doc), 1),

            # Document characteristics
            'has_numbers': any(token.like_num for token in doc),
            'has_email': bool(re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', doc.text)),
            'has_url': bool(re.search(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', doc.text)),
        }

        return features

    def _analyze_sentiment(self, doc: Doc) -> str:
        """Basic sentiment analysis based on word patterns."""
        positive_words = {'good', 'great', 'excellent', 'success', 'approved', 'congratulations'}
        negative_words = {'bad', 'error', 'failure', 'denied', 'rejected', 'urgent', 'overdue'}

        text_lower = doc.text.lower()
        pos_count = sum(1 for word in positive_words if word in text_lower)
        neg_count = sum(1 for word in negative_words if word in text_lower)

        if pos_count > neg_count:
            return 'positive'
        elif neg_count > pos_count:
            return 'negative'
        else:
            return 'neutral'

    def _compute_statistics(self, text: str, doc: Doc) -> Dict:
        """Compute text statistics."""
        return {
            'char_count': len(text),
            'word_count': len([t for t in doc if not t.is_punct]),
            'sentence_count': len(list(doc.sents)),
            'unique_words': len(set(t.lemma_.lower() for t in doc if not t.is_punct and not t.is_stop)),
            'avg_word_length': sum(len(t.text) for t in doc if not t.is_punct) / max(len([t for t in doc if not t.is_punct]), 1),
        }

    def _generate_summary(self, doc: Doc, entities: List[Dict]) -> str:
        """Generate brief summary from first sentence + key entities."""
        # Get first sentence (up to 200 chars)
        first_sent = next(doc.sents, None)
        if first_sent:
            summary = first_sent.text[:200]
        else:
            summary = doc.text[:200]

        # Add key entities
        if entities:
            key_entities = [e['text'] for e in entities[:3]]
            summary += f" | Key entities: {', '.join(key_entities)}"

        return summary

    def _empty_result(self, error: str = None) -> Dict:
        """Return empty analysis result."""
        result = {
            'entities': [],
            'keywords': [],
            'summary': '',
            'document_type': 'unknown',
            'features': {},
            'sentiment': 'neutral',
            'statistics': {},
            'success': False
        }
        if error:
            result['error'] = error
        return result

    def analyze_batch(self, texts: List[str]) -> List[Dict]:
        """
        Analyze multiple texts efficiently using spaCy's pipe.

        Args:
            texts: List of text strings

        Returns:
            List of analysis results
        """
        results = []

        # Use spaCy's efficient batch processing
        for doc in self.nlp.pipe(texts, batch_size=50):
            # Create fake text variable for compatibility
            original_text = doc.text

            entities = self._extract_entities(doc)
            keywords = self._extract_keywords(doc)
            doc_type = self._infer_document_type(original_text, entities, keywords, "")  # No filename in batch
            features = self._extract_features(doc, entities, keywords)
            sentiment = self._analyze_sentiment(doc)
            statistics = self._compute_statistics(original_text, doc)
            summary = self._generate_summary(doc, entities)

            results.append({
                'entities': entities,
                'keywords': keywords[:20],
                'summary': summary,
                'document_type': doc_type,
                'features': features,
                'sentiment': sentiment,
                'statistics': statistics,
                'success': True
            })

        return results


# Convenience function
def create_analyzer(language_model: str = "en_core_web_sm"):
    """
    Factory function to create text analyzer.

    Args:
        language_model: spaCy model name

    Returns:
        Configured TextAnalyzer
    """
    return TextAnalyzer(language_model=language_model)
