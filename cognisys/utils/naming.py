"""
Naming convention utilities for CogniSys.
Handles file/folder name normalization, sanitization, and extraction.
"""

import re
from pathlib import Path
from typing import Optional


def sanitize_name(name: str) -> str:
    """
    Sanitize a name for use in file/folder paths.
    Removes invalid characters and normalizes spacing.

    Args:
        name: Original name

    Returns:
        Sanitized name safe for filesystem use
    """
    # Remove invalid filesystem characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '', name)

    # Replace multiple spaces with single underscore
    sanitized = re.sub(r'\s+', '_', sanitized)

    # Remove leading/trailing underscores
    sanitized = sanitized.strip('_')

    return sanitized


def normalize_filename(filename: str) -> str:
    """
    Normalize filename for comparison by removing common duplicate suffixes.
    Removes patterns like: (1), (2), - Copy, _copy, _backup, dates, version tags.

    Args:
        filename: Original filename

    Returns:
        Normalized filename
    """
    name = filename

    # Patterns to remove (in order)
    patterns = [
        r'\s*\(\d+\)',              # (1), (2), etc.
        r'\s*-\s*Copy\s*\d*',       # - Copy, - Copy 1
        r'\s*_copy\s*\d*',          # _copy, _copy1
        r'\s*-\s*copy\s*\d*',       # -copy, -copy1
        r'\s*_backup\s*\d*',        # _backup, _backup1
        r'\s*\d{4}-\d{2}-\d{2}',    # Date patterns YYYY-MM-DD
        r'\s*\d{8}',                # Date patterns YYYYMMDD
        r'\s*_v\d+',                # _v1, _v2 version tags
        r'\s*v\d+',                 # v1, v2 version tags
        r'\s*_final\s*',            # _final
        r'\s*_FINAL\s*',            # _FINAL
        r'\s*\(final\)',            # (final)
    ]

    for pattern in patterns:
        name = re.sub(pattern, '', name, flags=re.IGNORECASE)

    # Normalize case and whitespace
    name = name.lower().strip()

    return name


def extract_version(filename: str) -> Optional[str]:
    """
    Extract version string from filename.

    Args:
        filename: Filename to parse

    Returns:
        Version string (e.g., "v01") or None
    """
    # Look for patterns like v1, v01, v2.0, version1, etc.
    patterns = [
        r'_v(\d+)',
        r'v(\d+)',
        r'version[\s_-]?(\d+)',
        r'\(v?(\d+)\)',
    ]

    for pattern in patterns:
        match = re.search(pattern, filename, re.IGNORECASE)
        if match:
            version_num = match.group(1)
            return f"v{int(version_num):02d}"  # Format as v01, v02, etc.

    return None


def extract_project_name(file_path: str) -> Optional[str]:
    """
    Extract project name from file path.
    Looks for common project folder patterns.

    Args:
        file_path: Full file path

    Returns:
        Project name or None
    """
    path = Path(file_path)
    parts = path.parts

    # Common project folder indicators
    project_indicators = ['projects', 'work', 'dev', 'development', 'code']

    for i, part in enumerate(parts):
        if part.lower() in project_indicators and i + 1 < len(parts):
            # Next folder is likely the project name
            return sanitize_name(parts[i + 1])

    return None


def apply_naming_convention(
    original_name: str,
    date_str: str,
    project_name: str,
    file_type: str,
    version: str,
    extension: str
) -> str:
    """
    Apply standard naming convention to a filename.
    Pattern: YYYY-MM-DD_ProjectName_Type_Version.ext

    Args:
        original_name: Original filename
        date_str: Date string (YYYY-MM-DD)
        project_name: Project or category name
        file_type: File type/category
        version: Version string (e.g., v01)
        extension: File extension

    Returns:
        Formatted filename
    """
    components = [
        date_str,
        sanitize_name(project_name),
        sanitize_name(file_type),
        version
    ]

    # Remove empty components
    components = [c for c in components if c]

    # Join with underscores
    new_name = '_'.join(components)

    # Add extension
    if extension and not extension.startswith('.'):
        extension = f'.{extension}'

    return f"{new_name}{extension}"
