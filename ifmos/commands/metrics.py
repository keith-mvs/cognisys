"""
IFMOS Metrics Command
Compute and track accuracy metrics for IFMOS pipeline
"""

import sqlite3
import json
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def compute_classification_accuracy(db_path):
    """
    Compute classification accuracy based on manual corrections.

    Returns:
        dict with accuracy metrics
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Total files classified
    cursor.execute("""
        SELECT COUNT(*) FROM file_registry
        WHERE classification_method IS NOT NULL
    """)
    total_classified = cursor.fetchone()[0]

    # Total corrections made
    cursor.execute("SELECT COUNT(*) FROM manual_corrections")
    total_corrections = cursor.fetchone()[0]

    # Accuracy = (total - corrections) / total
    if total_classified > 0:
        accuracy = (total_classified - total_corrections) / total_classified
    else:
        accuracy = 0.0

    # Breakdown by method
    cursor.execute("""
        SELECT classification_method, COUNT(*) as count
        FROM file_registry
        WHERE classification_method IS NOT NULL
        GROUP BY classification_method
    """)
    by_method = dict(cursor.fetchall())

    # Corrections by wrong type
    cursor.execute("""
        SELECT wrong_type, COUNT(*) as count
        FROM manual_corrections
        GROUP BY wrong_type
        ORDER BY count DESC
        LIMIT 10
    """)
    common_errors = dict(cursor.fetchall())

    conn.close()

    return {
        'total_classified': total_classified,
        'total_corrections': total_corrections,
        'accuracy': accuracy,
        'accuracy_pct': accuracy * 100,
        'by_method': by_method,
        'common_errors': common_errors
    }


def compute_stability_metric(db_path):
    """
    Compute stability metric (how often files are moved).

    Returns:
        dict with stability metrics
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Average moves per file
    cursor.execute("""
        SELECT AVG(move_count) as avg_moves
        FROM file_registry
        WHERE canonical_state = 'organized'
    """)
    avg_moves = cursor.fetchone()[0] or 0.0

    # Files moved multiple times
    cursor.execute("""
        SELECT COUNT(*) FROM file_registry
        WHERE move_count > 1
    """)
    multi_moves = cursor.fetchone()[0]

    # Total organized files
    cursor.execute("""
        SELECT COUNT(*) FROM file_registry
        WHERE canonical_state = 'organized'
    """)
    total_organized = cursor.fetchone()[0]

    # Stability = percentage of files never moved (move_count <= 1)
    if total_organized > 0:
        stability = ((total_organized - multi_moves) / total_organized)
    else:
        stability = 1.0

    conn.close()

    return {
        'avg_moves_per_file': avg_moves,
        'files_moved_multiple_times': multi_moves,
        'total_organized': total_organized,
        'stability': stability,
        'stability_pct': stability * 100
    }


def compute_deduplication_rate(db_path):
    """
    Compute deduplication rate.

    Returns:
        dict with deduplication metrics
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Total files
    cursor.execute("SELECT COUNT(*) FROM file_registry")
    total_files = cursor.fetchone()[0]

    # Duplicate files
    cursor.execute("""
        SELECT COUNT(*) FROM file_registry
        WHERE is_duplicate = 1
    """)
    duplicate_files = cursor.fetchone()[0]

    # Deduplication rate = duplicates / total
    if total_files > 0:
        dedup_rate = duplicate_files / total_files
    else:
        dedup_rate = 0.0

    conn.close()

    return {
        'total_files': total_files,
        'duplicate_files': duplicate_files,
        'unique_files': total_files - duplicate_files,
        'deduplication_rate': dedup_rate,
        'deduplication_pct': dedup_rate * 100
    }


def compute_all_metrics(db_path):
    """
    Compute all IFMOS metrics.

    Args:
        db_path: Path to SQLite database

    Returns:
        dict with all metrics
    """
    logger.info("Computing IFMOS metrics...")

    classification_metrics = compute_classification_accuracy(db_path)
    stability_metrics = compute_stability_metric(db_path)
    dedup_metrics = compute_deduplication_rate(db_path)

    metrics = {
        'timestamp': datetime.now().isoformat(),
        'classification': classification_metrics,
        'stability': stability_metrics,
        'deduplication': dedup_metrics
    }

    return metrics


def save_metrics_snapshot(db_path, metrics):
    """
    Save metrics snapshot to database.

    Args:
        db_path: Path to SQLite database
        metrics: Metrics dict from compute_all_metrics()

    Returns:
        int: snapshot_id
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Save each metric type
    for metric_type, metric_data in metrics.items():
        if metric_type == 'timestamp':
            continue

        # Get primary metric value
        if metric_type == 'classification':
            metric_value = metric_data.get('accuracy', 0.0)
        elif metric_type == 'stability':
            metric_value = metric_data.get('stability', 0.0)
        elif metric_type == 'deduplication':
            metric_value = metric_data.get('deduplication_rate', 0.0)
        else:
            metric_value = 0.0

        cursor.execute("""
            INSERT INTO metrics_snapshots
            (snapshot_date, metric_type, metric_value, metric_data)
            VALUES (?, ?, ?, ?)
        """, (
            metrics['timestamp'],
            metric_type,
            metric_value,
            json.dumps(metric_data)
        ))

    conn.commit()
    snapshot_id = cursor.lastrowid
    conn.close()

    logger.info(f"Metrics snapshot saved (ID: {snapshot_id})")

    return snapshot_id


def print_metrics_report(metrics):
    """
    Print formatted metrics report.

    Args:
        metrics: Metrics dict from compute_all_metrics()
    """
    print()
    print("="*80)
    print("IFMOS METRICS REPORT")
    print("="*80)
    print(f"Generated: {metrics['timestamp']}")
    print()

    # Classification Accuracy
    cls = metrics['classification']
    print("CLASSIFICATION ACCURACY")
    print("-"*80)
    print(f"  Total classified: {cls['total_classified']}")
    print(f"  Manual corrections: {cls['total_corrections']}")
    print(f"  Accuracy: {cls['accuracy_pct']:.2f}%")
    print()
    print("  By method:")
    for method, count in cls['by_method'].items():
        print(f"    {method}: {count} files")
    print()
    if cls['common_errors']:
        print("  Most common errors:")
        for wrong_type, count in cls['common_errors'].items():
            print(f"    {wrong_type}: {count} corrections")
    print()

    # Stability
    stab = metrics['stability']
    print("STABILITY")
    print("-"*80)
    print(f"  Total organized: {stab['total_organized']}")
    print(f"  Avg moves per file: {stab['avg_moves_per_file']:.2f}")
    print(f"  Files moved multiple times: {stab['files_moved_multiple_times']}")
    print(f"  Stability: {stab['stability_pct']:.2f}%")
    print()

    # Deduplication
    dedup = metrics['deduplication']
    print("DEDUPLICATION")
    print("-"*80)
    print(f"  Total files: {dedup['total_files']}")
    print(f"  Unique files: {dedup['unique_files']}")
    print(f"  Duplicate files: {dedup['duplicate_files']}")
    print(f"  Deduplication rate: {dedup['deduplication_pct']:.2f}%")
    print()


def generate_metrics_report(db_path, save_snapshot=True):
    """
    Generate complete metrics report.

    Args:
        db_path: Path to SQLite database
        save_snapshot: If True, save metrics to database

    Returns:
        dict with all metrics
    """
    metrics = compute_all_metrics(db_path)

    print_metrics_report(metrics)

    if save_snapshot:
        save_metrics_snapshot(db_path, metrics)

    return metrics
