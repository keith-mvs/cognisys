# IFMOS Testing Guide

Comprehensive guide for testing the Intelligent File Management and Organization System.

## Overview

IFMOS uses **pytest** for automated testing with a structured test suite covering:
- Unit tests for individual components
- Integration tests for workflows
- Security tests for vulnerabilities
- Performance benchmarks

## Quick Start

```bash
# Install test dependencies
pip install -r requirements-test.txt

# Run all tests
pytest tests/ -v

# Run with coverage report
pytest --cov=ifmos tests/

# Run specific test categories
pytest tests/unit/ -v          # Unit tests only
pytest tests/integration/ -v    # Integration tests only
pytest -m slow                  # Slow tests only
pytest -m "not slow"            # Fast tests only
```

## Test Structure

```
tests/
├── __init__.py                 # Test suite initialization
├── unit/                       # Unit tests
│   ├── test_hashing.py        # Hashing utilities (6 tests)
│   ├── test_naming.py         # Naming utilities (6 tests)
│   └── test_*.py              # Additional unit tests
├── integration/                # Integration tests
│   ├── test_content_extraction.py  # Content extraction (5 tests)
│   └── test_*.py              # Additional integration tests
└── fixtures/                   # Test data and fixtures
```

## Test Categories

### Unit Tests

Test individual functions and classes in isolation.

**Hashing Tests** (`tests/unit/test_hashing.py`):
- `test_quick_hash_consistency` - Quick hash determinism
- `test_full_hash_consistency` - Full hash determinism
- `test_adaptive_hash_small_file` - Small file hashing strategy
- `test_adaptive_hash_large_file` - Large file hashing strategy
- `test_hash_different_files` - Hash uniqueness
- `test_nonexistent_file` - Error handling

**Naming Tests** (`tests/unit/test_naming.py`):
- `test_normalize_basic` - Basic normalization
- `test_normalize_with_spaces` - Space handling
- `test_sanitize_special_characters` - Special character removal
- `test_sanitize_path_traversal` - Path traversal protection
- `test_sanitize_windows_reserved` - Windows reserved characters
- `test_sanitize_unicode` - Unicode handling

### Integration Tests

Test complete workflows and component interactions.

**Content Extraction** (`tests/integration/test_content_extraction.py`):
- `test_extract_text_file` - Text file extraction
- `test_extract_csv_file` - CSV file extraction
- `test_nonexistent_file` - File not found handling
- `test_unsupported_format` - Unsupported format handling
- `test_metadata_extraction` - Metadata completeness

## Writing Tests

### Basic Test Template

```python
import pytest
from ifmos.component import function_to_test


class TestComponent:
    """Test suite for Component"""

    @pytest.fixture
    def sample_data(self):
        """Create test data"""
        # Setup
        data = {"key": "value"}
        yield data
        # Teardown (optional)
        pass

    def test_basic_functionality(self, sample_data):
        """Test basic functionality"""
        result = function_to_test(sample_data)
        assert result is not None
        assert result['success'] is True
```

### Using Fixtures

```python
@pytest.fixture
def temp_file():
    """Create temporary file for testing"""
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(b"test content")
        temp_path = f.name

    yield temp_path

    # Cleanup
    import os
    os.unlink(temp_path)


def test_with_fixture(temp_file):
    """Test using fixture"""
    assert os.path.exists(temp_file)
```

### Test Markers

Use pytest markers to categorize tests:

```python
@pytest.mark.unit
def test_unit_component():
    pass


@pytest.mark.integration
def test_integration_workflow():
    pass


@pytest.mark.slow
def test_expensive_operation():
    pass


@pytest.mark.gpu
def test_gpu_acceleration():
    pass
```

Run marked tests:
```bash
pytest -m unit              # Run unit tests only
pytest -m "slow and gpu"    # Run slow GPU tests
pytest -m "not slow"        # Skip slow tests
```

## Test Coverage

### Current Coverage

| Module | Coverage | Tests | Status |
|--------|----------|-------|--------|
| ifmos.utils.hashing | 100% | 6 | ✅ Passing |
| ifmos.utils.naming | 67% | 6 | ⚠️ 4/6 Passing |
| ifmos.ml.utils.content_extractor | 85% | 5 | ✅ Passing |
| **Total** | **88%** | **17** | **15/17 Passing** |

### Generating Coverage Reports

```bash
# Terminal coverage report
pytest --cov=ifmos tests/

# HTML coverage report
pytest --cov=ifmos --cov-report=html tests/
# Open htmlcov/index.html in browser

# XML coverage report (for CI/CD)
pytest --cov=ifmos --cov-report=xml tests/
```

## Continuous Integration

### GitHub Actions Example

```yaml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pip install -r requirements-test.txt
      - run: pytest --cov=ifmos tests/
      - uses: codecov/codecov-action@v3
```

## Test Best Practices

### 1. Test Isolation

Each test should be independent:
```python
# Good
def test_function_a():
    result = process_data(input_a)
    assert result == expected_a


# Bad - depends on previous test
shared_state = None
def test_function_b():
    global shared_state
    shared_state = process_data(input_b)

def test_function_c():
    # Fails if test_function_b didn't run
    assert shared_state == expected_c
```

### 2. Descriptive Names

```python
# Good - clear what's being tested
def test_quick_hash_returns_same_value_for_same_file():
    pass


# Bad - vague
def test_hash():
    pass
```

### 3. AAA Pattern

Arrange, Act, Assert:
```python
def test_document_processing():
    # Arrange
    file_path = create_test_document()

    # Act
    result = process_document(file_path)

    # Assert
    assert result['success'] is True
    assert len(result['text']) > 0
```

### 4. Test Edge Cases

```python
def test_function():
    # Normal case
    assert function("normal input") == "expected"

    # Empty input
    assert function("") == ""

    # None input
    assert function(None) is None

    # Large input
    assert function("x" * 1000000) is not None
```

## Troubleshooting

### Common Issues

**Import Errors**:
```bash
# Ensure IFMOS is in PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
pytest tests/
```

**GPU Tests Failing**:
```bash
# Skip GPU tests if no GPU available
pytest -m "not gpu" tests/
```

**Slow Tests Timing Out**:
```bash
# Increase timeout
pytest --timeout=300 tests/
```

### Test Debugging

```python
# Add print statements
def test_debug():
    result = function_to_test()
    print(f"Result: {result}")  # Will show with pytest -s
    assert result is not None


# Use pytest -s to see print output
pytest -s tests/test_file.py
```

```python
# Use breakpoint for interactive debugging
def test_interactive():
    result = function_to_test()
    breakpoint()  # Will drop into debugger
    assert result is not None


# Run with pytest --pdb
pytest --pdb tests/test_file.py
```

## Performance Testing

### Benchmark Example

```python
import time


def test_performance():
    """Ensure function completes within time limit"""
    start = time.time()

    result = expensive_operation()

    duration = time.time() - start
    assert duration < 5.0  # Must complete in <5 seconds
    assert result is not None
```

### Using pytest-benchmark

```bash
pip install pytest-benchmark
```

```python
def test_hash_performance(benchmark):
    """Benchmark hashing performance"""
    result = benchmark(calculate_full_hash, "large_file.dat")
    assert result is not None
```

## Security Testing

### Test for Vulnerabilities

```python
def test_path_traversal_protection():
    """Ensure path traversal attacks are blocked"""
    malicious_paths = [
        "../../../etc/passwd",
        "..\\..\\..\\windows\\system32",
        "file://../../secret.txt"
    ]

    for path in malicious_paths:
        sanitized = sanitize_path(path)
        assert ".." not in sanitized
        assert "/" not in sanitized
        assert "\\" not in sanitized
```

```python
def test_sql_injection_protection():
    """Ensure SQL injection is prevented"""
    malicious_inputs = [
        "'; DROP TABLE users; --",
        "1' OR '1'='1",
        "admin'--"
    ]

    for input_val in malicious_inputs:
        result = query_database(input_val)
        # Should not execute SQL injection
        assert result is None or result['error'] is not None
```

## Test Data Management

### Fixtures Directory

```
tests/fixtures/
├── sample_documents/
│   ├── test.pdf
│   ├── test.docx
│   └── test.txt
├── expected_outputs/
│   └── test_results.json
└── config/
    └── test_config.yml
```

### Loading Test Data

```python
from pathlib import Path


@pytest.fixture
def fixtures_dir():
    """Get fixtures directory path"""
    return Path(__file__).parent.parent / "fixtures"


def test_with_fixture_file(fixtures_dir):
    """Test using fixture file"""
    test_file = fixtures_dir / "sample_documents" / "test.pdf"
    result = process_document(test_file)
    assert result['success'] is True
```

## Next Steps

1. **Increase Coverage**: Target 95%+ coverage
2. **Add ML Tests**: Test classification accuracy
3. **Performance Benchmarks**: Add speed benchmarks
4. **Security Audits**: Automated security scanning
5. **Load Testing**: Test with 10,000+ files

---

**Last Updated**: 2025-11-27
**Test Framework Version**: pytest 9.0.1
**Coverage**: 88% (15/17 tests passing)
