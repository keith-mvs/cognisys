"""Pytest fixtures for CogniSys tests."""

import pytest
import tempfile
import os
import json
from pathlib import Path
from datetime import datetime, timedelta

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


@pytest.fixture
def scanner_config():
    """Default configuration for FileScanner tests."""
    return {
        'scanning': {
            'exclusions': {
                'patterns': ['*.tmp', '*.bak', '.DS_Store', '*.db', '*.sqlite'],
                'folders': ['__pycache__', '.git', 'node_modules', '.venv']
            },
            'performance': {
                'threads': 2,
                'batch_size': 10
            },
            'hashing': {
                'skip_files_larger_than': 0  # No size limit for tests
            }
        }
    }


@pytest.fixture
def analyzer_config():
    """Default configuration for Analyzer tests."""
    return {
        'deduplication': {
            'exact_match': {
                'enabled': True,
                'min_file_size': 100
            },
            'fuzzy_filename': {
                'enabled': True,
                'similarity_threshold': 0.85,
                'same_folder_only': True,
                'max_folder_files': 100,
                'min_file_size': 100
            },
            'canonical_selection': {
                'preferred_paths': ['Documents', 'Canonical'],
                'priorities': ['modified_date', 'path_depth', 'filename_quality']
            }
        },
        'orphaned_files': {
            'criteria': [
                {'type': 'not_accessed_days', 'value': 365}
            ]
        }
    }


@pytest.fixture
def migrator_config():
    """Default configuration for Migrator tests."""
    return {
        'naming_conventions': {
            'files': {
                'pattern': '{YYYY-MM-DD}_{Name}_{Type}.{ext}'
            },
            'folders': {
                'case': 'PascalCase'
            }
        }
    }


@pytest.fixture
def structure_config(temp_dir):
    """Target structure configuration for migration tests."""
    return {
        'repository_root': str(temp_dir / 'organized'),
        'classification': {
            'document': {
                'target': 'Active/Documents/{YYYY}/{MM}'
            },
            'image': {
                'target': 'Active/Media/Images/{YYYY-MM}'
            },
            'code': {
                'target': 'Active/Code/{project_name}'
            },
            'archive': {
                'target': 'Archive/{YYYY}'
            }
        }
    }


@pytest.fixture
def duplicate_files_structure(temp_dir):
    """Create file structure with duplicates for analyzer testing."""
    # Create directories
    docs_dir = temp_dir / "documents"
    backup_dir = temp_dir / "backup"
    docs_dir.mkdir()
    backup_dir.mkdir()

    # Create duplicate files (exact same content)
    content = "This is the duplicate content for testing purposes."

    (docs_dir / "report.txt").write_text(content)
    (backup_dir / "report.txt").write_text(content)
    (docs_dir / "report (1).txt").write_text(content)

    # Create similar filenames (for fuzzy matching)
    (docs_dir / "quarterly_report_2024.pdf").write_bytes(b"%PDF quarter" * 100)
    (docs_dir / "quarterly_report_2024_copy.pdf").write_bytes(b"%PDF quarter" * 100)
    (docs_dir / "quarterly_report_2024_backup.pdf").write_bytes(b"%PDF quarter" * 100)

    # Create unique files
    (docs_dir / "unique_file.txt").write_text("Unique content here")
    (temp_dir / "standalone.md").write_text("# Standalone document")

    yield temp_dir


@pytest.fixture
def migration_test_structure(temp_dir):
    """Create file structure for migration testing."""
    # Source directory
    source = temp_dir / "source"
    source.mkdir()

    # Create categorized files
    (source / "report.pdf").write_bytes(b"%PDF-1.4 test report")
    (source / "photo.jpg").write_bytes(b"\xff\xd8\xff\xe0 fake jpeg")
    (source / "script.py").write_text("print('hello world')")
    (source / "data.csv").write_text("col1,col2\n1,2\n3,4")

    # Organized destination
    dest = temp_dir / "organized"
    dest.mkdir()

    yield {
        'source': source,
        'destination': dest,
        'root': temp_dir
    }


@pytest.fixture
def mock_session_with_files(temp_db, duplicate_files_structure):
    """Create a session with pre-indexed files for testing."""
    session_id = temp_db.create_session(
        root_paths=[str(duplicate_files_structure)],
        config={'test': True}
    )

    # Index all files in the structure
    file_count = 0
    for root, dirs, files in os.walk(duplicate_files_structure):
        for filename in files:
            filepath = Path(root) / filename
            stat = filepath.stat()

            # Calculate simple hash for testing
            content = filepath.read_bytes()
            import hashlib
            file_hash = hashlib.sha256(content).hexdigest()

            temp_db.insert_file({
                'file_id': f'file-{file_count:04d}',
                'path': str(filepath),
                'parent_id': None,
                'name': filename,
                'extension': filepath.suffix.lower(),
                'size_bytes': stat.st_size,
                'created_at': datetime.fromtimestamp(stat.st_ctime),
                'modified_at': datetime.fromtimestamp(stat.st_mtime),
                'accessed_at': datetime.fromtimestamp(stat.st_atime),
                'mime_type': None,
                'file_category': 'document' if filepath.suffix in ['.txt', '.pdf'] else 'other',
                'file_subcategory': filepath.suffix.lstrip('.'),
                'hash_quick': file_hash[:32],
                'hash_full': file_hash,
                'access_count': 0,
                'scan_session_id': session_id
            })
            file_count += 1

    yield {
        'session_id': session_id,
        'db': temp_db,
        'dir': duplicate_files_structure,
        'file_count': file_count
    }


@pytest.fixture
def checkpoint_dir(temp_dir):
    """Create a directory for migration checkpoints."""
    checkpoint_path = temp_dir / "checkpoints"
    checkpoint_path.mkdir()
    yield checkpoint_path
