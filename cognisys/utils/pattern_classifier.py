"""
Pattern-based file classifier.
Consolidates pattern matching rules from multiple scripts into a reusable module.
"""

import re
from pathlib import Path
from typing import Tuple, Optional, Dict, List
from dataclasses import dataclass, field


@dataclass
class ClassificationResult:
    """Result of pattern-based classification."""
    document_type: Optional[str]
    confidence: float
    method: str
    matched_rule: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.document_type is not None and self.confidence > 0


@dataclass
class PatternRule:
    """A pattern matching rule for classification."""
    name: str
    document_type: str
    confidence: float
    file_pattern: Optional[str] = None  # Regex for filename
    extension_pattern: Optional[str] = None  # Regex for extension only
    context_pattern: Optional[str] = None  # Regex for filename stem (context)
    exclude_pattern: Optional[str] = None  # Pattern to exclude
    priority: int = 50  # Higher = checked first


class PatternClassifier:
    """
    Rule-based file classifier using filename patterns.

    Consolidates pattern matching logic from:
    - reclassify_unknown_files.py
    - reclassify_null_files.py
    - classify_training_sample.py
    - final_unknown_cleanup.py
    - apply_pattern_classifications.py
    """

    def __init__(self, rules: Optional[List[PatternRule]] = None):
        """
        Initialize classifier with rules.

        Args:
            rules: Custom rules. If None, uses default rules.
        """
        self.rules = rules or self._default_rules()
        # Sort by priority (higher first)
        self.rules.sort(key=lambda r: r.priority, reverse=True)

    def classify(self, filepath: str) -> ClassificationResult:
        """
        Classify a file using pattern matching.

        Args:
            filepath: File path (can be absolute or just filename)

        Returns:
            ClassificationResult with document_type, confidence, method
        """
        path = Path(filepath)
        filename = path.name.lower()
        stem = path.stem.lower()
        ext = path.suffix.lower()

        # Try each rule in priority order
        for rule in self.rules:
            if self._matches_rule(filename, stem, ext, rule):
                return ClassificationResult(
                    document_type=rule.document_type,
                    confidence=rule.confidence,
                    method='pattern_override' if rule.priority >= 90 else 'pattern_extension',
                    matched_rule=rule.name
                )

        return ClassificationResult(
            document_type=None,
            confidence=0.0,
            method='no_match'
        )

    def classify_batch(self, filepaths: List[str]) -> Dict[str, ClassificationResult]:
        """
        Classify multiple files.

        Args:
            filepaths: List of file paths

        Returns:
            Dict mapping filepath to ClassificationResult
        """
        return {fp: self.classify(fp) for fp in filepaths}

    def _matches_rule(self, filename: str, stem: str, ext: str, rule: PatternRule) -> bool:
        """Check if filename matches rule patterns."""
        # Check exclusion first
        if rule.exclude_pattern:
            if re.search(rule.exclude_pattern, filename, re.IGNORECASE):
                return False

        # Check file pattern
        if rule.file_pattern:
            if re.search(rule.file_pattern, filename, re.IGNORECASE):
                return True

        # Check extension pattern
        if rule.extension_pattern:
            ext_check = ext.lstrip('.')
            if re.search(rule.extension_pattern, ext_check, re.IGNORECASE):
                # If context pattern required, check it
                if rule.context_pattern:
                    return bool(re.search(rule.context_pattern, stem, re.IGNORECASE))
                return True

        return False

    @staticmethod
    def _default_rules() -> List[PatternRule]:
        """Default pattern matching rules."""
        return [
            # ===== HIGH PRIORITY OVERRIDES (90+) =====

            # Scripts & Code
            PatternRule(
                name='script_files',
                document_type='technical_script',
                confidence=0.98,
                extension_pattern=r'^(ps1|py|js|ts|jsx|tsx|sh|bat|cmd|vbs|rb|php|go|rs|swift|kt)$',
                priority=95
            ),

            # Config files
            PatternRule(
                name='config_files',
                document_type='technical_config',
                confidence=0.98,
                extension_pattern=r'^(json|yml|yaml|xml|ini|conf|config|toml|properties|cfg)$',
                priority=95
            ),

            # Dotenv files (special case - no extension)
            PatternRule(
                name='dotenv_files',
                document_type='technical_config',
                confidence=0.98,
                file_pattern=r'^\.env(\..+)?$',  # .env, .env.local, .env.production, etc.
                priority=95
            ),

            # HR/Career documents
            PatternRule(
                name='career_documents',
                document_type='personal_career',
                confidence=0.95,
                file_pattern=r'(resume|cv|cover[-_]letter|job[-_]application|benefits.*guide|staff.*benefits)',
                priority=95
            ),

            # Financial documents
            PatternRule(
                name='financial_documents',
                document_type='financial_document',
                confidence=0.95,
                file_pattern=r'(invoice|receipt|tax|1099|w-2|statement|paystub|paycheck)',
                priority=95
            ),

            # Screenshots
            PatternRule(
                name='screenshots',
                document_type='media_screenshot',
                confidence=0.95,
                file_pattern=r'(screenshot|capture|screen.*shot).*\.(png|jpg|jpeg)',
                priority=95
            ),

            # ===== EXTENSION-BASED (80-89) =====

            # Technical Documentation
            PatternRule(
                name='markdown_tech',
                document_type='technical_documentation',
                confidence=0.95,
                extension_pattern=r'^(md|markdown|rst|adoc|asciidoc)$',
                context_pattern=r'(commit|pr|pull[-_]request|git|sandbox|migration|api|readme|documentation|guide)',
                priority=85
            ),
            PatternRule(
                name='markdown_general',
                document_type='technical_documentation',
                confidence=0.90,
                extension_pattern=r'^(md|markdown|rst|adoc|asciidoc)$',
                exclude_pattern=r'(bmw|e\d{2}|f\d{2}|vehicle|axle|transmission|engine|brake|service)',
                priority=80
            ),

            # Spreadsheets
            PatternRule(
                name='spreadsheets',
                document_type='business_spreadsheet',
                confidence=0.90,
                extension_pattern=r'^(xlsx|xls|csv)$',
                exclude_pattern=r'(vehicle|bmw|car|service|repair|diagnostic)',
                priority=85
            ),

            # Legal/Government
            PatternRule(
                name='legal_documents',
                document_type='legal_document',
                confidence=0.90,
                file_pattern=r'(contract|agreement|reporting|compliance|foreign.*contact|entry.*appearance|legal|court)',
                priority=85
            ),

            # Design/CAD
            PatternRule(
                name='cad_files',
                document_type='design_cad',
                confidence=0.95,
                extension_pattern=r'^(dwg|dxf|skp|step|stp|iges|prt|asm|sldprt)$',
                priority=85
            ),

            # Vector graphics
            PatternRule(
                name='vector_graphics',
                document_type='design_vector',
                confidence=0.85,
                extension_pattern=r'^(eps|ai|svg)$',
                priority=85
            ),

            # Photoshop
            PatternRule(
                name='photoshop_files',
                document_type='design_photoshop',
                confidence=0.90,
                extension_pattern=r'^psd$',
                priority=85
            ),

            # ===== MEDIA FILES (75-84) =====

            # Video
            PatternRule(
                name='video_files',
                document_type='media_video',
                confidence=0.95,
                extension_pattern=r'^(mp4|avi|mov|mkv|wmv|flv|webm)$',
                priority=80
            ),

            # Audio
            PatternRule(
                name='audio_files',
                document_type='media_audio',
                confidence=0.95,
                extension_pattern=r'^(mp3|wav|flac|aac|ogg|m4a|wma)$',
                priority=80
            ),

            # Images
            PatternRule(
                name='image_logo',
                document_type='media_graphic',
                confidence=0.90,
                file_pattern=r'(logo|icon|avatar).*\.(png|jpg|jpeg|gif|svg|webp)$',
                priority=85
            ),
            PatternRule(
                name='image_general',
                document_type='media_image',
                confidence=0.80,
                extension_pattern=r'^(jpg|jpeg|png|webp|heic|bmp|gif|tiff)$',
                priority=75
            ),

            # ===== DOCUMENT FILES (70-79) =====

            # PDF context-based
            PatternRule(
                name='pdf_financial',
                document_type='financial_document',
                confidence=0.90,
                extension_pattern=r'^pdf$',
                context_pattern=r'(invoice|receipt|order.*#|statement.*#)',
                priority=80
            ),
            PatternRule(
                name='pdf_technical',
                document_type='technical_documentation',
                confidence=0.85,
                extension_pattern=r'^pdf$',
                context_pattern=r'(manual|guide|tutorial|reference.*guide|quick.*guide|user.*manual)',
                priority=78
            ),
            PatternRule(
                name='pdf_health',
                document_type='personal_health',
                confidence=0.90,
                extension_pattern=r'^pdf$',
                context_pattern=r'(yoga|exercise|health|fitness)',
                priority=78
            ),
            PatternRule(
                name='pdf_general',
                document_type='document_pdf',
                confidence=0.70,
                extension_pattern=r'^pdf$',
                priority=70
            ),

            # Word documents
            PatternRule(
                name='word_health',
                document_type='personal_health',
                confidence=0.90,
                extension_pattern=r'^(docx|doc)$',
                context_pattern=r'(yoga|exercise|health)',
                priority=78
            ),
            PatternRule(
                name='word_career',
                document_type='personal_career',
                confidence=0.95,
                extension_pattern=r'^(docx|doc)$',
                context_pattern=r'(resume|cv)',
                priority=80
            ),
            PatternRule(
                name='word_general',
                document_type='document_word',
                confidence=0.75,
                extension_pattern=r'^(docx|doc)$',
                priority=70
            ),

            # Presentations
            PatternRule(
                name='presentation_career',
                document_type='personal_career',
                confidence=0.90,
                extension_pattern=r'^(pptx|ppt|key|odp)$',
                context_pattern=r'(about.*me|resume|portfolio)',
                priority=78
            ),
            PatternRule(
                name='presentation_general',
                document_type='business_presentation',
                confidence=0.85,
                extension_pattern=r'^(pptx|ppt|key|odp)$',
                priority=75
            ),

            # ===== TECHNICAL FILES (65-74) =====

            # Database files
            PatternRule(
                name='database_files',
                document_type='technical_database',
                confidence=0.90,
                extension_pattern=r'^(db|sqlite|sqlite3|mdb|accdb)$',
                priority=75
            ),

            # Archives
            PatternRule(
                name='archives',
                document_type='archive',
                confidence=0.90,
                extension_pattern=r'^(zip|rar|7z|tar|gz|bz2)$',
                priority=75
            ),

            # Web files
            PatternRule(
                name='web_fonts',
                document_type='web_font',
                confidence=0.95,
                extension_pattern=r'^(ttf|otf|woff|woff2|eot)$',
                priority=75
            ),
            PatternRule(
                name='html_bookmarks',
                document_type='web_bookmark',
                confidence=0.95,
                extension_pattern=r'^html?$',
                context_pattern=r'(bookmark|favorite|export|consolidate)',
                priority=78
            ),
            PatternRule(
                name='html_general',
                document_type='web_page',
                confidence=0.85,
                extension_pattern=r'^html?$',
                priority=72
            ),
            PatternRule(
                name='css_files',
                document_type='web_stylesheet',
                confidence=0.90,
                extension_pattern=r'^css$',
                priority=75
            ),

            # Log files
            PatternRule(
                name='log_files',
                document_type='technical_log',
                confidence=0.90,
                extension_pattern=r'^log$',
                priority=75
            ),

            # Text files
            PatternRule(
                name='text_readme',
                document_type='technical_documentation',
                confidence=0.85,
                extension_pattern=r'^txt$',
                context_pattern=r'(readme|license)',
                priority=75
            ),
            PatternRule(
                name='text_general',
                document_type='document_text',
                confidence=0.70,
                extension_pattern=r'^txt$',
                priority=65
            ),

            # Executables
            PatternRule(
                name='software_installers',
                document_type='software_installer',
                confidence=0.90,
                extension_pattern=r'^(exe|msi|dmg|pkg|deb|rpm|appimage)$',
                exclude_pattern=r'(bmw|vehicle|diagnostic|obd)',
                priority=75
            ),
        ]

    @classmethod
    def from_yaml(cls, yaml_path: str) -> 'PatternClassifier':
        """
        Load rules from YAML configuration file.

        Args:
            yaml_path: Path to YAML file with rules

        Returns:
            PatternClassifier instance
        """
        import yaml

        with open(yaml_path) as f:
            config = yaml.safe_load(f)

        rules = []
        for rule_dict in config.get('rules', []):
            rules.append(PatternRule(**rule_dict))

        return cls(rules=rules)

    def add_rule(self, rule: PatternRule) -> None:
        """Add a rule and re-sort."""
        self.rules.append(rule)
        self.rules.sort(key=lambda r: r.priority, reverse=True)

    def get_stats(self) -> Dict:
        """Return statistics about the classifier."""
        return {
            'total_rules': len(self.rules),
            'rules_by_priority': {
                'high (90+)': sum(1 for r in self.rules if r.priority >= 90),
                'medium (70-89)': sum(1 for r in self.rules if 70 <= r.priority < 90),
                'low (<70)': sum(1 for r in self.rules if r.priority < 70),
            },
            'document_types': list(set(r.document_type for r in self.rules)),
        }


def extract_real_filename(path: str) -> str:
    """
    Extract real filename from templated path.
    Handles patterns like: 2025-11-28_{vehicle}_{service_type}_Front_axle.pdf -> Front_axle.pdf

    Args:
        path: Full path or filename

    Returns:
        Extracted filename without template variables
    """
    filename = Path(path).name

    # Pattern: YYYY-MM-DD_{template}_{template}_REAL_FILENAME
    match = re.match(r'\d{4}-\d{2}-\d{2}_(?:\{[^}]+\}_)*(.+)$', filename)
    if match:
        return match.group(1)

    return filename
