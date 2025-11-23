"""
Hashing utilities for file content comparison.
Implements both quick hash (first 1MB) and full hash (entire file) strategies.
"""

import hashlib
from pathlib import Path
from typing import Optional


def calculate_quick_hash(file_path: Path, chunk_size: int = 1_048_576) -> Optional[str]:
    """
    Calculate SHA-256 hash of first chunk of file (default 1MB).
    Used for fast pre-filtering of potential duplicates.

    Args:
        file_path: Path to the file
        chunk_size: Size of chunk to hash (default 1MB)

    Returns:
        Hexadecimal hash string, or None if file cannot be read
    """
    try:
        hash_obj = hashlib.sha256()

        with open(file_path, 'rb') as f:
            chunk = f.read(chunk_size)
            hash_obj.update(chunk)

        return hash_obj.hexdigest()

    except (PermissionError, OSError, IOError) as e:
        return None


def calculate_full_hash(file_path: Path, buffer_size: int = 65536) -> Optional[str]:
    """
    Calculate SHA-256 hash of entire file.
    Used for exact duplicate verification.

    Args:
        file_path: Path to the file
        buffer_size: Buffer size for reading (default 64KB)

    Returns:
        Hexadecimal hash string, or None if file cannot be read
    """
    try:
        hash_obj = hashlib.sha256()

        with open(file_path, 'rb') as f:
            while True:
                data = f.read(buffer_size)
                if not data:
                    break
                hash_obj.update(data)

        return hash_obj.hexdigest()

    except (PermissionError, OSError, IOError) as e:
        return None


def calculate_adaptive_hash(file_path: Path, file_size: int) -> tuple[Optional[str], Optional[str]]:
    """
    Adaptively calculate hashes based on file size.
    For small files (<1MB), quick hash = full hash.
    For larger files, calculate quick hash only (full hash on demand).

    Args:
        file_path: Path to the file
        file_size: Size of file in bytes

    Returns:
        Tuple of (quick_hash, full_hash)
    """
    if file_size <= 1_048_576:
        # Small file - calculate once
        full_hash = calculate_full_hash(file_path)
        return full_hash, full_hash
    else:
        # Large file - quick hash only
        quick_hash = calculate_quick_hash(file_path)
        return quick_hash, None
