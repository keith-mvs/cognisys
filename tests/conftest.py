"""Pytest fixtures for CogniSys tests."""

import pytest
import tempfile
import os
from pathlib import Path

from cognisys.models.database import Database


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_db(temp_dir):
    """Create a temporary database for testing."""
    db_path = temp_dir / "test.db"
    db = Database(str(db_path))
    yield db
    db.close()


@pytest.fixture
def sample_files(temp_dir):
    """Create sample files for testing."""
    files = {}

    # Small text file
    small_txt = temp_dir / "small.txt"
    small_txt.write_text("Hello, World!")
    files['small_txt'] = small_txt

    # Larger file (>1MB for quick hash testing)
    large_file = temp_dir / "large.bin"
    large_file.write_bytes(b"x" * (1024 * 1024 + 1000))  # 1MB + 1000 bytes
    files['large_file'] = large_file

    # Duplicate content
    dup1 = temp_dir / "original.txt"
    dup1.write_text("Duplicate content here")
    files['dup1'] = dup1

    dup2 = temp_dir / "original (1).txt"
    dup2.write_text("Duplicate content here")
    files['dup2'] = dup2

    # PDF-like file
    pdf_file = temp_dir / "document.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 fake pdf content")
    files['pdf'] = pdf_file

    yield files


@pytest.fixture
def nested_dir_structure(temp_dir):
    """Create a nested directory structure for scanner testing."""
    # Create structure
    (temp_dir / "docs").mkdir()
    (temp_dir / "docs" / "work").mkdir()
    (temp_dir / "images").mkdir()
    (temp_dir / "code").mkdir()

    # Add files
    (temp_dir / "docs" / "readme.txt").write_text("Root doc")
    (temp_dir / "docs" / "work" / "report.pdf").write_bytes(b"%PDF-1.4 report")
    (temp_dir / "images" / "photo.jpg").write_bytes(b"\xff\xd8\xff fake jpg")
    (temp_dir / "code" / "script.py").write_text("print('hello')")

    yield temp_dir
