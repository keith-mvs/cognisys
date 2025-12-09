#!/usr/bin/env python3
"""
Export Training Data for ML Model

Exports high-confidence classifications from the database to create
training dataset for PyTorch DistilBERT fine-tuning.

Criteria:
- Confidence >= 0.85 (high quality labels)
- Document type != 'unknown'
- Canonical state = 'organized' (active files)
- Exclude 'default' classification method (low quality)

Author: Claude Code
Date: 2025-12-01
"""

import sqlite3
import csv
from pathlib import Path
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class TrainingDataExporter:
    """Export high-confidence classifications for ML training"""

    def __init__(self, db_path: str = '.cognisys/file_registry.db'):
        self.db_path = Path(db_path)
        self.stats = {
            'total_files': 0,
            'high_confidence': 0,
            'by_method': {},
            'by_type': {}
        }

    def export(
        self,
        output_csv: str = '.cognisys/training_data.csv',
        min_confidence: float = 0.85
    ):
        """
        Export training data to CSV.

        Args:
            output_csv: Output CSV file path
            min_confidence: Minimum confidence threshold
        """
        print("\n" + "=" * 80)
        print("EXPORTING TRAINING DATA")
        print("=" * 80)
        print(f"\nDatabase: {self.db_path}")
        print(f"Min Confidence: {min_confidence}")

        if not self.db_path.exists():
            logger.error(f"Database not found: {self.db_path}")
            return None

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get high-confidence classifications
        cursor.execute('''
            SELECT
                original_path,
                canonical_path,
                document_type,
                confidence,
                classification_method
            FROM file_registry
            WHERE canonical_state = 'organized'
              AND document_type IS NOT NULL
              AND document_type != 'unknown'
              AND confidence >= ?
              AND classification_method != 'default'
            ORDER BY confidence DESC
        ''', (min_confidence,))

        rows = cursor.fetchall()
        self.stats['total_files'] = len(rows)

        print(f"\nFound {len(rows):,} high-confidence files")

        # Analyze distribution
        method_counts = {}
        type_counts = {}

        for _, _, doc_type, conf, method in rows:
            method_counts[method] = method_counts.get(method, 0) + 1
            type_counts[doc_type] = type_counts.get(doc_type, 0) + 1

        self.stats['by_method'] = method_counts
        self.stats['by_type'] = type_counts

        # Print distribution
        print(f"\nBy Classification Method:")
        for method in sorted(method_counts.keys(), key=lambda x: method_counts[x], reverse=True)[:10]:
            print(f"  {method:30} : {method_counts[method]:,}")

        print(f"\nBy Document Type (top 15):")
        for doc_type in sorted(type_counts.keys(), key=lambda x: type_counts[x], reverse=True)[:15]:
            print(f"  {doc_type:35} : {type_counts[doc_type]:,}")

        # Write to CSV
        output_path = Path(output_csv)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        print(f"\nWriting to: {output_path}")

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['file_path', 'document_type', 'confidence', 'classification_method'])

            for original, canonical, doc_type, conf, method in rows:
                # Use canonical path if available, otherwise original
                file_path = canonical if canonical else original
                writer.writerow([file_path, doc_type, conf, method])

        print(f"[OK] Exported {len(rows):,} training examples")

        # Save statistics
        stats_path = output_path.parent / 'training_data_stats.json'
        import json
        with open(stats_path, 'w') as f:
            json.dump({
                'exported': datetime.now().isoformat(),
                'total_examples': len(rows),
                'min_confidence': min_confidence,
                'unique_methods': len(method_counts),
                'unique_types': len(type_counts),
                'by_method': method_counts,
                'by_type': type_counts
            }, f, indent=2)

        print(f"[OK] Statistics saved to: {stats_path}")

        conn.close()

        print("\n" + "=" * 80)
        print("EXPORT COMPLETE")
        print("=" * 80)
        print(f"\nTraining data: {output_path}")
        print(f"Statistics: {stats_path}")
        print(f"Total examples: {len(rows):,}")
        print(f"Unique document types: {len(type_counts)}")
        print("=" * 80)

        return output_path


def main():
    """Main execution"""
    exporter = TrainingDataExporter()

    # Export with confidence >= 0.85
    output_path = exporter.export(
        output_csv='.cognisys/training_data.csv',
        min_confidence=0.85
    )

    if output_path:
        print(f"\n[SUCCESS] Training data ready for ML training")
        print(f"\nNext step: Extract content from these {exporter.stats['total_files']:,} files")
        print(f"Command: python extract_content_for_training.py")


if __name__ == '__main__':
    main()
