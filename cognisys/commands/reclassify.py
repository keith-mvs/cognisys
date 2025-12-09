"""
CLI Commands for File Reclassification

Consolidates functionality from multiple root scripts:
- reclassify_unknown_files.py
- reclassify_null_files.py
- apply_pattern_classifications.py
- final_unknown_cleanup.py

Uses the shared PatternClassifier and StatsCollector utilities.
"""

import click
import sqlite3
import pickle
from pathlib import Path
from datetime import datetime
from typing import Optional

from ..utils.pattern_classifier import PatternClassifier, extract_real_filename
from ..utils.stats_collector import ClassificationStats, StatsCollector, ProgressTracker
from ..utils.logging_config import get_logger

logger = get_logger(__name__)


def get_db_path() -> str:
    """Get the default database path."""
    return '.cognisys/file_registry.db'


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Get database connection."""
    conn = sqlite3.connect(db_path or get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def load_ml_model(model_dir: str = 'cognisys/models/trained'):
    """Load trained ML model components."""
    try:
        model_path = Path(model_dir)

        with open(model_path / 'random_forest_classifier.pkl', 'rb') as f:
            model = pickle.load(f)
        with open(model_path / 'tfidf_vectorizer.pkl', 'rb') as f:
            vectorizer = pickle.load(f)
        with open(model_path / 'label_mappings.pkl', 'rb') as f:
            label_mappings = pickle.load(f)

        return model, vectorizer, label_mappings
    except Exception as e:
        logger.warning(f"Failed to load ML model: {e}")
        return None, None, None


def classify_with_ml(filename: str, model, vectorizer, label_mappings, confidence_threshold: float = 0.70):
    """Classify filename using ML model."""
    try:
        features = vectorizer.transform([filename])
        prediction = model.predict(features)[0]
        probabilities = model.predict_proba(features)[0]
        confidence = max(probabilities)

        # Get document type from label mapping
        if isinstance(label_mappings, dict) and 'reverse_mapping' in label_mappings:
            reverse_mappings = label_mappings['reverse_mapping']
        elif isinstance(label_mappings, dict) and 'label_mapping' in label_mappings:
            reverse_mappings = {v: k for k, v in label_mappings['label_mapping'].items()}
        else:
            reverse_mappings = {v: k for k, v in label_mappings.items()}

        document_type = reverse_mappings.get(prediction, 'general_document')

        return document_type, confidence, 'ml_model'

    except Exception as e:
        logger.debug(f"Classification failed for {filename}: {e}")
        return None, 0.0, 'classification_error'


@click.group()
def reclassify():
    """Reclassify files using patterns and ML models."""
    pass


@reclassify.command('unknown')
@click.option('--db', default=None, help='Database path')
@click.option('--execute', is_flag=True, help='Execute changes (default is dry-run)')
@click.option('--batch-size', default=100, type=int, help='Batch size for updates')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed output')
def reclassify_unknown(db: Optional[str], execute: bool, batch_size: int, verbose: bool):
    """Reclassify files marked as 'unknown' using pattern matching."""

    mode = 'EXECUTE' if execute else 'DRY RUN'
    click.echo(f"\n[INFO] Reclassifying unknown files ({mode})")
    click.echo("=" * 60)

    conn = get_connection(db)
    cursor = conn.cursor()

    # Get all unknown files
    cursor.execute('''
        SELECT file_id, original_path
        FROM file_registry
        WHERE document_type = 'unknown'
    ''')

    unknown_files = cursor.fetchall()
    total = len(unknown_files)

    if total == 0:
        click.echo("[INFO] No unknown files found.")
        conn.close()
        return

    click.echo(f"[INFO] Found {total:,} unknown files")

    # Initialize classifier and stats
    classifier = PatternClassifier()
    stats = ClassificationStats()
    tracker = ProgressTracker(total, report_interval=batch_size)

    updates = []

    for file_id, path in unknown_files:
        filepath = Path(path)
        result = classifier.classify(str(filepath))

        stats.record(
            doc_type=result.document_type,
            confidence=result.confidence,
            method=result.method,
            old_type='unknown'
        )

        if result.success:
            updates.append((
                result.document_type,
                result.confidence,
                result.method,
                file_id
            ))

            if verbose and len(updates) <= 20:
                click.echo(f"  {filepath.name[:40]:40} -> {result.document_type:25} [{result.method}]")

        msg = tracker.update()
        if msg:
            click.echo(f"  {msg}")

    # Show summary
    click.echo("\n" + "=" * 60)
    click.echo("RECLASSIFICATION SUMMARY")
    click.echo("=" * 60)
    click.echo(stats.summary())

    click.echo("\nTop document types:")
    for doc_type, count in sorted(stats.by_type.items(), key=lambda x: -x[1])[:10]:
        click.echo(f"  {doc_type:30} {count:6}")

    # Execute updates
    if execute and updates:
        click.echo(f"\n[INFO] Updating {len(updates):,} records...")

        cursor.executemany('''
            UPDATE file_registry
            SET document_type = ?,
                confidence = ?,
                classification_method = ?,
                updated_at = datetime('now')
            WHERE file_id = ?
        ''', updates)

        conn.commit()
        click.echo(f"[SUCCESS] Updated {len(updates):,} records")
    elif not execute:
        click.echo(f"\n[DRY RUN] Would update {len(updates):,} records")
        click.echo("[TIP] Run with --execute to apply changes")

    conn.close()
    click.echo(tracker.finish())


@reclassify.command('null')
@click.option('--db', default=None, help='Database path')
@click.option('--execute', is_flag=True, help='Execute changes (default is dry-run)')
@click.option('--confidence', default=0.70, type=float, help='Confidence threshold')
@click.option('--use-ml/--no-ml', default=True, help='Use ML model as fallback')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed output')
def reclassify_null(db: Optional[str], execute: bool, confidence: float, use_ml: bool, verbose: bool):
    """Reclassify files with NULL document_type using patterns and ML."""

    mode = 'EXECUTE' if execute else 'DRY RUN'
    click.echo(f"\n[INFO] Reclassifying NULL files ({mode})")
    click.echo("=" * 60)

    conn = get_connection(db)
    cursor = conn.cursor()

    # Get files with NULL document_type
    cursor.execute('''
        SELECT file_id, original_path, canonical_path
        FROM file_registry
        WHERE document_type IS NULL
    ''')

    null_files = cursor.fetchall()
    total = len(null_files)

    if total == 0:
        click.echo("[INFO] No NULL files found.")
        conn.close()
        return

    click.echo(f"[INFO] Found {total:,} files with NULL document_type")

    # Initialize classifier and ML model
    classifier = PatternClassifier()
    model, vectorizer, label_mappings = (None, None, None)

    if use_ml:
        model, vectorizer, label_mappings = load_ml_model()
        if model:
            click.echo("[INFO] ML model loaded successfully")
        else:
            click.echo("[WARN] ML model not available, using patterns only")

    stats = ClassificationStats()
    tracker = ProgressTracker(total, report_interval=100)

    updates = []

    for file_id, original_path, canonical_path in null_files:
        # Extract real filename
        path = original_path or canonical_path
        real_filename = extract_real_filename(path)

        # Try pattern classification first
        result = classifier.classify(real_filename)

        if result.success:
            doc_type = result.document_type
            conf = result.confidence
            method = result.method
        elif model is not None:
            # Fall back to ML
            doc_type, conf, method = classify_with_ml(
                real_filename, model, vectorizer, label_mappings, confidence
            )
        else:
            doc_type, conf, method = None, 0.0, 'no_match'

        stats.record(doc_type=doc_type, confidence=conf, method=method)

        if doc_type and conf >= confidence:
            updates.append((doc_type, conf, method, file_id))

            if verbose and len(updates) <= 20:
                click.echo(f"  {real_filename[:40]:40} -> {doc_type:25} [{method}]")

        msg = tracker.update()
        if msg:
            click.echo(f"  {msg}")

    # Show summary
    click.echo("\n" + "=" * 60)
    click.echo("RECLASSIFICATION SUMMARY")
    click.echo("=" * 60)
    click.echo(stats.summary())

    click.echo("\nBy method:")
    for method, count in sorted(stats.by_method.items(), key=lambda x: -x[1]):
        click.echo(f"  {method:25} {count:6}")

    click.echo("\nTop document types:")
    for doc_type, count in sorted(stats.by_type.items(), key=lambda x: -x[1])[:15]:
        click.echo(f"  {doc_type:30} {count:6}")

    # Execute updates
    if execute and updates:
        click.echo(f"\n[INFO] Updating {len(updates):,} records...")

        cursor.executemany('''
            UPDATE file_registry
            SET document_type = ?,
                confidence = ?,
                classification_method = ?,
                updated_at = datetime('now')
            WHERE file_id = ?
        ''', updates)

        conn.commit()
        click.echo(f"[SUCCESS] Updated {len(updates):,} records")
    elif not execute:
        click.echo(f"\n[DRY RUN] Would update {len(updates):,} records")
        click.echo("[TIP] Run with --execute to apply changes")

    conn.close()
    click.echo(tracker.finish())


@reclassify.command('all')
@click.option('--db', default=None, help='Database path')
@click.option('--execute', is_flag=True, help='Execute changes (default is dry-run)')
@click.option('--confidence', default=0.70, type=float, help='Confidence threshold')
@click.option('--use-ml/--no-ml', default=True, help='Use ML model as fallback')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed output')
def reclassify_all(db: Optional[str], execute: bool, confidence: float, use_ml: bool, verbose: bool):
    """Reclassify ALL files using patterns and ML (full re-evaluation)."""

    mode = 'EXECUTE' if execute else 'DRY RUN'
    click.echo(f"\n[INFO] Reclassifying ALL files ({mode})")
    click.echo("[WARN] This will re-evaluate classifications for ALL files")
    click.echo("=" * 60)

    if not click.confirm("Continue?"):
        click.echo("Cancelled.")
        return

    conn = get_connection(db)
    cursor = conn.cursor()

    # Get ALL files
    cursor.execute('''
        SELECT file_id, original_path, canonical_path, document_type
        FROM file_registry
    ''')

    all_files = cursor.fetchall()
    total = len(all_files)

    if total == 0:
        click.echo("[INFO] No files in registry.")
        conn.close()
        return

    click.echo(f"[INFO] Processing {total:,} files")

    # Initialize classifier and ML model
    classifier = PatternClassifier()
    model, vectorizer, label_mappings = (None, None, None)

    if use_ml:
        model, vectorizer, label_mappings = load_ml_model()
        if model:
            click.echo("[INFO] ML model loaded successfully")

    stats = ClassificationStats()
    tracker = ProgressTracker(total, report_interval=500)

    updates = []

    for file_id, original_path, canonical_path, old_type in all_files:
        path = original_path or canonical_path
        real_filename = extract_real_filename(path)

        # Try pattern classification first
        result = classifier.classify(real_filename)

        if result.success:
            doc_type = result.document_type
            conf = result.confidence
            method = result.method
        elif model is not None:
            doc_type, conf, method = classify_with_ml(
                real_filename, model, vectorizer, label_mappings, confidence
            )
        else:
            doc_type, conf, method = None, 0.0, 'no_match'

        stats.record(
            doc_type=doc_type,
            confidence=conf,
            method=method,
            old_type=old_type
        )

        if doc_type:
            updates.append((doc_type, conf, method, file_id))

        msg = tracker.update()
        if msg:
            click.echo(f"  {msg}")

    # Show summary
    click.echo("\n" + "=" * 60)
    click.echo("RECLASSIFICATION SUMMARY")
    click.echo("=" * 60)
    click.echo(stats.summary())

    click.echo("\nBy method:")
    for method, count in sorted(stats.by_method.items(), key=lambda x: -x[1]):
        click.echo(f"  {method:25} {count:6} ({count/total*100:.1f}%)")

    # Execute updates
    if execute and updates:
        click.echo(f"\n[INFO] Updating {len(updates):,} records...")

        cursor.executemany('''
            UPDATE file_registry
            SET document_type = ?,
                confidence = ?,
                classification_method = ?,
                updated_at = datetime('now')
            WHERE file_id = ?
        ''', updates)

        conn.commit()
        click.echo(f"[SUCCESS] Updated {len(updates):,} records")
    elif not execute:
        click.echo(f"\n[DRY RUN] Would update {len(updates):,} records")

    conn.close()
    click.echo(tracker.finish())


@reclassify.command('stats')
@click.option('--db', default=None, help='Database path')
def show_stats(db: Optional[str]):
    """Show classification statistics for the file registry."""

    db_path = db or get_db_path()

    try:
        with StatsCollector(db_path) as collector:
            report = collector.generate_report()
            click.echo(report)
    except Exception as e:
        click.echo(f"[ERROR] Failed to generate stats: {e}", err=True)


@reclassify.command('low-confidence')
@click.option('--db', default=None, help='Database path')
@click.option('--threshold', default=0.5, type=float, help='Confidence threshold')
@click.option('--limit', default=100, type=int, help='Max files to show')
def show_low_confidence(db: Optional[str], threshold: float, limit: int):
    """Show files with low classification confidence."""

    db_path = db or get_db_path()

    try:
        with StatsCollector(db_path) as collector:
            files = collector.get_low_confidence_files(threshold=threshold, limit=limit)

            click.echo(f"\nFiles with confidence < {threshold:.0%}:")
            click.echo("=" * 80)

            for f in files:
                path = Path(f['original_path']).name if f['original_path'] else 'N/A'
                click.echo(
                    f"  {path[:40]:40} "
                    f"{f['document_type'] or 'NULL':20} "
                    f"{f['confidence']:.2%}"
                )

            click.echo(f"\nTotal: {len(files)} files")
    except Exception as e:
        click.echo(f"[ERROR] Failed to get low confidence files: {e}", err=True)
