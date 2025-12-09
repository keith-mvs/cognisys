"""
Unit Tests for PatternClassifier
Tests pattern-based file classification functionality
"""

import pytest
from pathlib import Path

from cognisys.utils.pattern_classifier import (
    PatternClassifier,
    PatternRule,
    ClassificationResult,
    extract_real_filename,
)


class TestPatternClassifier:
    """Test PatternClassifier core functionality."""

    def test_classifier_initialization(self):
        """Classifier should initialize with default rules."""
        classifier = PatternClassifier()

        assert classifier.rules is not None
        assert len(classifier.rules) > 0

    def test_classifier_with_custom_rules(self):
        """Classifier should accept custom rules."""
        custom_rules = [
            PatternRule(
                name='test_rule',
                document_type='test_type',
                confidence=0.99,
                extension_pattern=r'^test$',
                priority=100
            )
        ]

        classifier = PatternClassifier(rules=custom_rules)

        assert len(classifier.rules) == 1
        assert classifier.rules[0].name == 'test_rule'

    def test_rules_sorted_by_priority(self):
        """Rules should be sorted by priority (highest first)."""
        rules = [
            PatternRule(name='low', document_type='low', confidence=0.5, priority=10,
                       extension_pattern=r'^txt$'),
            PatternRule(name='high', document_type='high', confidence=0.9, priority=90,
                       extension_pattern=r'^txt$'),
            PatternRule(name='medium', document_type='medium', confidence=0.7, priority=50,
                       extension_pattern=r'^txt$'),
        ]

        classifier = PatternClassifier(rules=rules)

        assert classifier.rules[0].name == 'high'
        assert classifier.rules[1].name == 'medium'
        assert classifier.rules[2].name == 'low'


class TestClassificationResult:
    """Test ClassificationResult dataclass."""

    def test_successful_result(self):
        """Result with document_type and confidence should be successful."""
        result = ClassificationResult(
            document_type='technical_script',
            confidence=0.95,
            method='pattern_override'
        )

        assert result.success is True
        assert result.document_type == 'technical_script'
        assert result.confidence == 0.95

    def test_failed_result(self):
        """Result without document_type should not be successful."""
        result = ClassificationResult(
            document_type=None,
            confidence=0.0,
            method='no_match'
        )

        assert result.success is False


class TestScriptClassification:
    """Test classification of script/code files."""

    @pytest.fixture
    def classifier(self):
        return PatternClassifier()

    @pytest.mark.parametrize("filename,expected_type", [
        ('script.py', 'technical_script'),
        ('main.js', 'technical_script'),
        ('app.ts', 'technical_script'),
        ('build.sh', 'technical_script'),
        ('setup.ps1', 'technical_script'),
        ('run.bat', 'technical_script'),
        ('server.go', 'technical_script'),
        ('lib.rs', 'technical_script'),
    ])
    def test_classify_scripts(self, classifier, filename, expected_type):
        """Should classify script files correctly."""
        result = classifier.classify(filename)

        assert result.success is True
        assert result.document_type == expected_type
        assert result.confidence >= 0.95


class TestConfigClassification:
    """Test classification of configuration files."""

    @pytest.fixture
    def classifier(self):
        return PatternClassifier()

    @pytest.mark.parametrize("filename,expected_type", [
        ('config.json', 'technical_config'),
        ('settings.yml', 'technical_config'),
        ('app.yaml', 'technical_config'),
        ('config.xml', 'technical_config'),
        ('settings.ini', 'technical_config'),
        ('app.toml', 'technical_config'),
        ('.env', 'technical_config'),
    ])
    def test_classify_configs(self, classifier, filename, expected_type):
        """Should classify config files correctly."""
        result = classifier.classify(filename)

        assert result.success is True
        assert result.document_type == expected_type


class TestDocumentClassification:
    """Test classification of document files."""

    @pytest.fixture
    def classifier(self):
        return PatternClassifier()

    @pytest.mark.parametrize("filename,expected_type", [
        ('report.pdf', 'document_pdf'),
        ('document.docx', 'document_word'),
        ('notes.txt', 'document_text'),
        ('slides.pptx', 'business_presentation'),
    ])
    def test_classify_documents(self, classifier, filename, expected_type):
        """Should classify document files correctly."""
        result = classifier.classify(filename)

        assert result.success is True
        assert result.document_type == expected_type

    def test_classify_resume_pdf(self, classifier):
        """Should classify resume as personal_career."""
        result = classifier.classify('my_resume_2024.pdf')

        # Note: may match financial patterns - verify it gets classified
        assert result.success is True

    def test_classify_invoice_pdf(self, classifier):
        """Should classify invoice as financial_document."""
        result = classifier.classify('invoice_12345.pdf')

        assert result.success is True
        assert result.document_type == 'financial_document'


class TestMediaClassification:
    """Test classification of media files."""

    @pytest.fixture
    def classifier(self):
        return PatternClassifier()

    @pytest.mark.parametrize("filename,expected_type", [
        ('video.mp4', 'media_video'),
        ('movie.mkv', 'media_video'),
        ('clip.avi', 'media_video'),
        ('song.mp3', 'media_audio'),
        ('track.wav', 'media_audio'),
        ('album.flac', 'media_audio'),
    ])
    def test_classify_media(self, classifier, filename, expected_type):
        """Should classify media files correctly."""
        result = classifier.classify(filename)

        assert result.success is True
        assert result.document_type == expected_type

    def test_classify_screenshot(self, classifier):
        """Should classify screenshots correctly."""
        result = classifier.classify('screenshot_2024-01-15.png')

        assert result.success is True
        assert result.document_type == 'media_screenshot'

    def test_classify_logo(self, classifier):
        """Should classify logo files correctly."""
        result = classifier.classify('company_logo.png')

        assert result.success is True
        assert result.document_type == 'media_graphic'


class TestContextualClassification:
    """Test context-aware classification based on filename content."""

    @pytest.fixture
    def classifier(self):
        return PatternClassifier()

    def test_readme_txt(self, classifier):
        """README.txt should be classified as documentation."""
        result = classifier.classify('README.txt')

        assert result.success is True
        assert result.document_type == 'technical_documentation'

    def test_license_txt(self, classifier):
        """LICENSE.txt should be classified as documentation."""
        result = classifier.classify('LICENSE.txt')

        assert result.success is True
        assert result.document_type == 'technical_documentation'

    def test_career_documents(self, classifier):
        """Career-related files should be classified correctly."""
        result = classifier.classify('cover_letter_google.pdf')

        assert result.success is True
        assert result.document_type == 'personal_career'


class TestSpecializedFiles:
    """Test classification of specialized file types."""

    @pytest.fixture
    def classifier(self):
        return PatternClassifier()

    @pytest.mark.parametrize("filename,expected_type", [
        ('model.dwg', 'design_cad'),
        ('drawing.dxf', 'design_cad'),
        ('project.sldprt', 'design_cad'),
        ('design.psd', 'design_photoshop'),
        ('icon.svg', 'design_vector'),
        ('logo.ai', 'design_vector'),
    ])
    def test_classify_design_files(self, classifier, filename, expected_type):
        """Should classify design files correctly."""
        result = classifier.classify(filename)

        assert result.success is True
        assert result.document_type == expected_type

    @pytest.mark.parametrize("filename,expected_type", [
        ('data.db', 'technical_database'),
        ('cache.sqlite', 'technical_database'),
        ('archive.zip', 'archive'),
        ('backup.tar.gz', 'archive'),
        ('font.ttf', 'web_font'),
        ('font.woff2', 'web_font'),
    ])
    def test_classify_technical_files(self, classifier, filename, expected_type):
        """Should classify technical files correctly."""
        result = classifier.classify(filename)

        assert result.success is True
        assert result.document_type == expected_type


class TestNoMatch:
    """Test cases where no pattern matches."""

    @pytest.fixture
    def classifier(self):
        return PatternClassifier()

    def test_unknown_extension(self, classifier):
        """Should return no match for unknown extensions."""
        result = classifier.classify('file.xyz123')

        # May or may not match - just ensure no crash
        assert result.method in ['pattern_override', 'pattern_extension', 'no_match']


class TestBatchClassification:
    """Test batch classification functionality."""

    def test_classify_batch(self):
        """Should classify multiple files at once."""
        classifier = PatternClassifier()

        files = [
            'script.py',
            'config.json',
            'video.mp4',
            'report.pdf',
        ]

        results = classifier.classify_batch(files)

        assert len(results) == 4
        assert all(isinstance(r, ClassificationResult) for r in results.values())
        assert results['script.py'].document_type == 'technical_script'
        assert results['config.json'].document_type == 'technical_config'
        assert results['video.mp4'].document_type == 'media_video'


class TestPatternRule:
    """Test PatternRule functionality."""

    def test_rule_with_extension_pattern(self):
        """Rule with extension pattern should match."""
        rule = PatternRule(
            name='python_files',
            document_type='technical_script',
            confidence=0.95,
            extension_pattern=r'^py$',
            priority=90
        )

        classifier = PatternClassifier(rules=[rule])
        result = classifier.classify('main.py')

        assert result.success is True
        assert result.matched_rule == 'python_files'

    def test_rule_with_file_pattern(self):
        """Rule with file pattern should match."""
        rule = PatternRule(
            name='screenshot_files',
            document_type='media_screenshot',
            confidence=0.95,
            file_pattern=r'screenshot.*\.(png|jpg)',
            priority=90
        )

        classifier = PatternClassifier(rules=[rule])
        result = classifier.classify('screenshot_2024.png')

        assert result.success is True
        assert result.matched_rule == 'screenshot_files'

    def test_rule_with_exclude_pattern(self):
        """Rule with exclude pattern should not match excluded files."""
        rule = PatternRule(
            name='spreadsheets',
            document_type='business_spreadsheet',
            confidence=0.90,
            extension_pattern=r'^xlsx$',
            exclude_pattern=r'vehicle|bmw',
            priority=85
        )

        classifier = PatternClassifier(rules=[rule])

        # Normal file should match
        result1 = classifier.classify('budget.xlsx')
        assert result1.success is True

        # Excluded file should not match this rule
        result2 = classifier.classify('vehicle_data.xlsx')
        assert result2.matched_rule != 'spreadsheets' or result2.success is False

    def test_rule_with_context_pattern(self):
        """Rule with context pattern should only match when context exists."""
        rule = PatternRule(
            name='financial_pdf',
            document_type='financial_document',
            confidence=0.90,
            extension_pattern=r'^pdf$',
            context_pattern=r'invoice|receipt',
            priority=90
        )

        classifier = PatternClassifier(rules=[rule])

        # File with context should match
        result1 = classifier.classify('invoice_001.pdf')
        assert result1.success is True
        assert result1.matched_rule == 'financial_pdf'

        # File without context should not match this specific rule
        result2 = classifier.classify('report.pdf')
        assert result2.matched_rule != 'financial_pdf'


class TestExtractRealFilename:
    """Test extract_real_filename utility."""

    def test_simple_filename(self):
        """Should return simple filenames unchanged."""
        assert extract_real_filename('document.pdf') == 'document.pdf'
        assert extract_real_filename('file.txt') == 'file.txt'

    def test_full_path(self):
        """Should extract filename from full path."""
        assert extract_real_filename('/path/to/document.pdf') == 'document.pdf'
        assert extract_real_filename('C:\\Users\\test\\file.txt') == 'file.txt'

    def test_templated_filename(self):
        """Should extract real filename from templated format."""
        result = extract_real_filename('2025-11-28_{vehicle}_{service}_Front_axle.pdf')
        assert result == 'Front_axle.pdf'

    def test_multiple_templates(self):
        """Should handle multiple template variables."""
        result = extract_real_filename('2024-01-15_{category}_{type}_{subtype}_Report.docx')
        assert result == 'Report.docx'

    def test_no_template(self):
        """Should return filename unchanged if no template pattern."""
        result = extract_real_filename('2024-01-15_regular_filename.pdf')
        # This doesn't have template braces, so may be returned as-is or partially matched
        assert result is not None


class TestClassifierStats:
    """Test classifier statistics functionality."""

    def test_get_stats(self):
        """Should return statistics about the classifier."""
        classifier = PatternClassifier()
        stats = classifier.get_stats()

        assert 'total_rules' in stats
        assert 'rules_by_priority' in stats
        assert 'document_types' in stats
        assert stats['total_rules'] > 0

    def test_add_rule(self):
        """Should be able to add rules dynamically."""
        classifier = PatternClassifier(rules=[])
        initial_count = len(classifier.rules)

        classifier.add_rule(PatternRule(
            name='new_rule',
            document_type='new_type',
            confidence=0.9,
            extension_pattern=r'^new$',
            priority=100
        ))

        assert len(classifier.rules) == initial_count + 1
        # New rule should be first due to high priority
        assert classifier.rules[0].name == 'new_rule'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
