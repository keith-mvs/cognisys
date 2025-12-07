"""
IFMOS Correct Command
Log manual corrections for accuracy tracking and ML model improvement
"""

import sqlite3
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def correct_file_classification(db_path, file_path, correct_type, reason=None):
    """
    Log a manual correction for a misclassified file.

    Args:
        db_path: Path to SQLite database
        file_path: Path to the file (original or canonical)
        correct_type: The correct document type
        reason: Optional reason for correction

    Returns:
        bool: True if successful, False otherwise
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Find file in database
        cursor.execute("""
            SELECT file_id, document_type, canonical_path
            FROM file_registry
            WHERE original_path = ? OR canonical_path = ?
        """, (str(file_path), str(file_path)))

        result = cursor.fetchone()

        if not result:
            logger.error(f"File not found in database: {file_path}")
            return False

        file_id, wrong_type, canonical_path = result

        # Log correction
        cursor.execute("""
            INSERT INTO manual_corrections
            (file_id, wrong_type, correct_type, correction_reason, correction_timestamp)
            VALUES (?, ?, ?, ?, datetime('now'))
        """, (file_id, wrong_type, correct_type, reason))

        # Update file classification
        cursor.execute("""
            UPDATE file_registry
            SET document_type = ?,
                classification_method = 'manual_correction',
                requires_review = 0,
                updated_at = datetime('now')
            WHERE file_id = ?
        """, (correct_type, file_id))

        conn.commit()

        logger.info(f"Correction logged: {Path(file_path).name}")
        logger.info(f"  Wrong: {wrong_type} -> Correct: {correct_type}")

        return True

    except Exception as e:
        logger.error(f"Error logging correction: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()


def get_files_requiring_review(db_path, limit=50):
    """
    Get list of files flagged for review.

    Args:
        db_path: Path to SQLite database
        limit: Maximum number of files to return

    Returns:
        list of (file_id, path, document_type, confidence) tuples
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT file_id, canonical_path, document_type, confidence
        FROM file_registry
        WHERE requires_review = 1
        ORDER BY confidence ASC
        LIMIT ?
    """, (limit,))

    results = cursor.fetchall()
    conn.close()

    return results


def export_corrections_for_training(db_path, output_path):
    """
    Export all manual corrections to CSV for ML model retraining.

    Args:
        db_path: Path to SQLite database
        output_path: Path to output CSV file

    Returns:
        int: Number of corrections exported
    """
    import csv

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            fr.original_path,
            fr.canonical_path,
            mc.wrong_type,
            mc.correct_type,
            mc.correction_timestamp,
            mc.correction_reason
        FROM manual_corrections mc
        JOIN file_registry fr ON mc.file_id = fr.file_id
        ORDER BY mc.correction_timestamp DESC
    """)

    corrections = cursor.fetchall()
    conn.close()

    # Write to CSV
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'original_path',
            'canonical_path',
            'wrong_type',
            'correct_type',
            'correction_timestamp',
            'reason'
        ])
        writer.writerows(corrections)

    logger.info(f"Exported {len(corrections)} corrections to {output_path}")

    return len(corrections)
