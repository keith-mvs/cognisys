#!/usr/bin/env python3
"""
IFMOS KPI Calculator
Quantifiable metrics for measuring system success
"""

import sqlite3
import os
import json
from pathlib import Path
from collections import Counter
from datetime import datetime
import time


class IFMOSKPICalculator:
    """Calculate and track IFMOS Key Performance Indicators"""

    def __init__(self, db_path: str = '.ifmos/file_registry.db'):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()

    def calculate_all_kpis(self):
        """Calculate all KPIs and return structured results"""
        kpis = {
            'timestamp': datetime.now().isoformat(),
            'classification': self._calculate_classification_kpis(),
            'deduplication': self._calculate_deduplication_kpis(),
            'storage': self._calculate_storage_kpis(),
            'quality': self._calculate_quality_kpis(),
            'performance': self._calculate_performance_kpis(),
            'coverage': self._calculate_coverage_kpis()
        }
        return kpis

    def _calculate_classification_kpis(self):
        """Classification effectiveness metrics"""
        # Total classified
        self.cursor.execute('SELECT COUNT(*) FROM file_registry WHERE document_type IS NOT NULL')
        total_classified = self.cursor.fetchone()[0]

        # Total files
        self.cursor.execute('SELECT COUNT(*) FROM file_registry')
        total_files = self.cursor.fetchone()[0]

        # Unique files (excluding duplicates)
        self.cursor.execute('SELECT COUNT(*) FROM file_registry WHERE is_duplicate = 0')
        unique_files = self.cursor.fetchone()[0]

        # Pending files
        self.cursor.execute('SELECT COUNT(*) FROM file_registry WHERE canonical_state = "pending"')
        pending = self.cursor.fetchone()[0]

        # By method
        self.cursor.execute('''
            SELECT classification_method, COUNT(*) as count
            FROM file_registry
            WHERE classification_method IS NOT NULL
            GROUP BY classification_method
        ''')
        by_method = dict(self.cursor.fetchall())

        # ML coverage
        ml_count = by_method.get('ml_model', 0)
        pattern_count = sum(v for k, v in by_method.items() if k.startswith('pattern_'))

        return {
            'total_classified': total_classified,
            'total_files': total_files,
            'unique_files': unique_files,
            'pending_files': pending,
            'classification_rate': round(total_classified / total_files * 100, 2),
            'unique_classification_rate': round(total_classified / unique_files * 100, 2) if unique_files > 0 else 0,
            'ml_coverage_pct': round(ml_count / total_classified * 100, 2) if total_classified > 0 else 0,
            'pattern_coverage_pct': round(pattern_count / total_classified * 100, 2) if total_classified > 0 else 0,
            'methods': by_method
        }

    def _calculate_deduplication_kpis(self):
        """Deduplication effectiveness metrics"""
        # Total duplicates
        self.cursor.execute('SELECT COUNT(*) FROM file_registry WHERE is_duplicate = 1')
        total_duplicates = self.cursor.fetchone()[0]

        # Total files
        self.cursor.execute('SELECT COUNT(*) FROM file_registry')
        total_files = self.cursor.fetchone()[0]

        # Duplicate groups
        self.cursor.execute('SELECT COUNT(DISTINCT content_hash) FROM file_registry WHERE is_duplicate = 1')
        duplicate_groups = self.cursor.fetchone()[0]

        # Average duplicates per group
        avg_per_group = total_duplicates / duplicate_groups if duplicate_groups > 0 else 0

        # Largest duplicate group
        self.cursor.execute('''
            SELECT content_hash, COUNT(*) as count
            FROM file_registry
            WHERE content_hash IS NOT NULL
            GROUP BY content_hash
            HAVING count > 1
            ORDER BY count DESC
            LIMIT 1
        ''')
        largest_group = self.cursor.fetchone()
        max_duplicates = largest_group[1] if largest_group else 0

        return {
            'total_duplicates': total_duplicates,
            'duplicate_groups': duplicate_groups,
            'deduplication_rate_pct': round(total_duplicates / total_files * 100, 2),
            'avg_duplicates_per_group': round(avg_per_group, 2),
            'max_duplicates_in_group': max_duplicates,
            'unique_files': total_files - total_duplicates,
            'space_efficiency_pct': round((total_files - total_duplicates) / total_files * 100, 2)
        }

    def _calculate_storage_kpis(self):
        """Storage and space metrics"""
        # Total size
        self.cursor.execute('SELECT SUM(file_size) FROM file_registry')
        total_size = self.cursor.fetchone()[0] or 0

        # Duplicate size
        self.cursor.execute('SELECT SUM(file_size) FROM file_registry WHERE is_duplicate = 1')
        duplicate_size = self.cursor.fetchone()[0] or 0

        # Unique size
        unique_size = total_size - duplicate_size

        # Database size
        db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0

        # Storage by category
        self.cursor.execute('''
            SELECT document_type, SUM(file_size) as total_size
            FROM file_registry
            WHERE document_type IS NOT NULL
            GROUP BY document_type
            ORDER BY total_size DESC
            LIMIT 10
        ''')
        by_category = dict(self.cursor.fetchall())

        return {
            'total_size_bytes': total_size,
            'total_size_gb': round(total_size / (1024**3), 2),
            'duplicate_size_bytes': duplicate_size,
            'duplicate_size_gb': round(duplicate_size / (1024**3), 2),
            'unique_size_bytes': unique_size,
            'unique_size_gb': round(unique_size / (1024**3), 2),
            'space_savings_pct': round(duplicate_size / total_size * 100, 2) if total_size > 0 else 0,
            'database_size_mb': round(db_size / (1024**2), 2),
            'storage_efficiency_ratio': round(total_size / db_size, 2) if db_size > 0 else 0,
            'top_categories_by_size': {k: round(v / (1024**3), 2) for k, v in list(by_category.items())[:5]}
        }

    def _calculate_quality_kpis(self):
        """Classification quality metrics"""
        # Confidence distribution
        self.cursor.execute('''
            SELECT
                CASE
                    WHEN confidence >= 0.95 THEN 'very_high'
                    WHEN confidence >= 0.85 THEN 'high'
                    WHEN confidence >= 0.70 THEN 'medium'
                    WHEN confidence > 0 THEN 'low'
                    ELSE 'none'
                END as confidence_level,
                COUNT(*) as count
            FROM file_registry
            GROUP BY confidence_level
        ''')
        confidence_dist = dict(self.cursor.fetchall())

        # Average confidence
        self.cursor.execute('SELECT AVG(confidence) FROM file_registry WHERE confidence > 0')
        avg_confidence = self.cursor.fetchone()[0] or 0

        # High confidence rate
        self.cursor.execute('SELECT COUNT(*) FROM file_registry WHERE confidence >= 0.85')
        high_conf_count = self.cursor.fetchone()[0]

        self.cursor.execute('SELECT COUNT(*) FROM file_registry WHERE confidence > 0')
        total_with_conf = self.cursor.fetchone()[0]

        # Unknown rate
        self.cursor.execute('SELECT COUNT(*) FROM file_registry WHERE document_type = "unknown"')
        unknown_count = self.cursor.fetchone()[0]

        self.cursor.execute('SELECT COUNT(*) FROM file_registry')
        total_files = self.cursor.fetchone()[0]

        # Manual review needed (low confidence)
        self.cursor.execute('SELECT COUNT(*) FROM file_registry WHERE confidence < 0.70 AND confidence > 0')
        review_needed = self.cursor.fetchone()[0]

        return {
            'avg_confidence': round(avg_confidence, 4),
            'high_confidence_pct': round(high_conf_count / total_with_conf * 100, 2) if total_with_conf > 0 else 0,
            'unknown_rate_pct': round(unknown_count / total_files * 100, 2),
            'review_needed_count': review_needed,
            'review_rate_pct': round(review_needed / total_files * 100, 2),
            'confidence_distribution': confidence_dist
        }

    def _calculate_performance_kpis(self):
        """System performance metrics"""
        # Database query performance (sample query)
        start = time.time()
        self.cursor.execute('SELECT COUNT(*) FROM file_registry')
        count_time = time.time() - start

        # Index efficiency test
        start = time.time()
        self.cursor.execute('SELECT * FROM file_registry WHERE content_hash = "test" LIMIT 1')
        hash_lookup_time = time.time() - start

        # Document type lookup
        start = time.time()
        self.cursor.execute('SELECT COUNT(*) FROM file_registry WHERE document_type = "technical_script"')
        type_lookup_time = time.time() - start

        # Table statistics
        self.cursor.execute('SELECT COUNT(*) FROM file_registry')
        row_count = self.cursor.fetchone()[0]

        # Database file size
        db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0

        return {
            'database_rows': row_count,
            'database_size_mb': round(db_size / (1024**2), 2),
            'bytes_per_row': round(db_size / row_count, 2) if row_count > 0 else 0,
            'count_query_ms': round(count_time * 1000, 2),
            'hash_lookup_ms': round(hash_lookup_time * 1000, 2),
            'type_lookup_ms': round(type_lookup_time * 1000, 2),
            'queries_per_second_estimate': round(1 / count_time, 0) if count_time > 0 else 0
        }

    def _calculate_coverage_kpis(self):
        """Coverage and completeness metrics"""
        # Document type diversity
        self.cursor.execute('SELECT COUNT(DISTINCT document_type) FROM file_registry WHERE document_type IS NOT NULL')
        type_diversity = self.cursor.fetchone()[0]

        # Extension diversity
        self.cursor.execute('SELECT COUNT(*) FROM file_registry')
        total_files = self.cursor.fetchone()[0]

        # Top types coverage
        self.cursor.execute('''
            SELECT document_type, COUNT(*) as count
            FROM file_registry
            WHERE document_type IS NOT NULL
            GROUP BY document_type
            ORDER BY count DESC
            LIMIT 10
        ''')
        top_types = dict(self.cursor.fetchall())

        # Top 5 coverage percentage
        top_5_count = sum(list(top_types.values())[:5])
        top_5_coverage_pct = round(top_5_count / total_files * 100, 2)

        # Method diversity
        self.cursor.execute('SELECT COUNT(DISTINCT classification_method) FROM file_registry WHERE classification_method IS NOT NULL')
        method_diversity = self.cursor.fetchone()[0]

        return {
            'document_type_diversity': type_diversity,
            'classification_method_diversity': method_diversity,
            'top_5_types_coverage_pct': top_5_coverage_pct,
            'top_10_document_types': top_types
        }

    def generate_kpi_report(self, save_json=True):
        """Generate comprehensive KPI report"""
        kpis = self.calculate_all_kpis()

        print("=" * 80)
        print("IFMOS KEY PERFORMANCE INDICATORS (KPIs)")
        print("=" * 80)
        print(f"Generated: {kpis['timestamp']}")
        print()

        # Classification KPIs
        print("-" * 80)
        print("CLASSIFICATION METRICS")
        print("-" * 80)
        c = kpis['classification']
        print(f"  Classification Rate: {c['classification_rate']}% ({c['total_classified']:,}/{c['total_files']:,})")
        print(f"  Unique File Coverage: {c['unique_classification_rate']}% ({c['total_classified']:,}/{c['unique_files']:,})")
        print(f"  Pending Files: {c['pending_files']:,}")
        print(f"  ML Coverage: {c['ml_coverage_pct']}%")
        print(f"  Pattern Coverage: {c['pattern_coverage_pct']}%")
        print()

        # Deduplication KPIs
        print("-" * 80)
        print("DEDUPLICATION METRICS")
        print("-" * 80)
        d = kpis['deduplication']
        print(f"  Deduplication Rate: {d['deduplication_rate_pct']}% ({d['total_duplicates']:,}/{d['total_duplicates'] + d['unique_files']:,})")
        print(f"  Duplicate Groups: {d['duplicate_groups']:,}")
        print(f"  Avg Duplicates/Group: {d['avg_duplicates_per_group']}")
        print(f"  Max Duplicates in Group: {d['max_duplicates_in_group']}")
        print(f"  Space Efficiency: {d['space_efficiency_pct']}%")
        print()

        # Storage KPIs
        print("-" * 80)
        print("STORAGE METRICS")
        print("-" * 80)
        s = kpis['storage']
        print(f"  Total Storage: {s['total_size_gb']:.2f} GB")
        print(f"  Duplicate Storage: {s['duplicate_size_gb']:.2f} GB ({s['space_savings_pct']}%)")
        print(f"  Unique Storage: {s['unique_size_gb']:.2f} GB")
        print(f"  Database Size: {s['database_size_mb']:.2f} MB")
        print(f"  Storage/DB Ratio: {s['storage_efficiency_ratio']:.0f}x")
        print()

        # Quality KPIs
        print("-" * 80)
        print("QUALITY METRICS")
        print("-" * 80)
        q = kpis['quality']
        print(f"  Average Confidence: {q['avg_confidence']:.2%}")
        print(f"  High Confidence Rate: {q['high_confidence_pct']}%")
        print(f"  Unknown Rate: {q['unknown_rate_pct']}%")
        print(f"  Review Needed: {q['review_needed_count']:,} ({q['review_rate_pct']}%)")
        print()

        # Performance KPIs
        print("-" * 80)
        print("PERFORMANCE METRICS")
        print("-" * 80)
        p = kpis['performance']
        print(f"  Database Rows: {p['database_rows']:,}")
        print(f"  Database Size: {p['database_size_mb']:.2f} MB")
        print(f"  Bytes per Row: {p['bytes_per_row']:.0f}")
        print(f"  Count Query: {p['count_query_ms']:.2f} ms")
        print(f"  Hash Lookup: {p['hash_lookup_ms']:.2f} ms")
        print(f"  Queries/Second: {p['queries_per_second_estimate']:.0f}")
        print()

        # Coverage KPIs
        print("-" * 80)
        print("COVERAGE METRICS")
        print("-" * 80)
        cov = kpis['coverage']
        print(f"  Document Type Diversity: {cov['document_type_diversity']} types")
        print(f"  Classification Methods: {cov['classification_method_diversity']} methods")
        print(f"  Top 5 Types Coverage: {cov['top_5_types_coverage_pct']}%")
        print()

        print("=" * 80)

        # Save JSON
        if save_json:
            filename = f"kpi_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(filename, 'w') as f:
                json.dump(kpis, f, indent=2)
            print(f"KPI report saved: {filename}")
            print("=" * 80)

        return kpis

    def calculate_benchmarks(self, kpis):
        """Calculate performance against industry benchmarks"""
        benchmarks = {
            'classification_rate': {'target': 95.0, 'excellent': 98.0, 'good': 90.0},
            'deduplication_rate': {'target': 20.0, 'excellent': 30.0, 'good': 15.0},
            'avg_confidence': {'target': 0.85, 'excellent': 0.90, 'good': 0.80},
            'high_confidence_pct': {'target': 70.0, 'excellent': 85.0, 'good': 60.0},
            'unknown_rate': {'target': 10.0, 'excellent': 5.0, 'good': 15.0},  # Lower is better
            'space_efficiency': {'target': 80.0, 'excellent': 85.0, 'good': 75.0}
        }

        scores = {}
        scores['classification_rate'] = self._score_metric(
            kpis['classification']['unique_classification_rate'],
            benchmarks['classification_rate'],
            higher_better=True
        )
        scores['deduplication_rate'] = self._score_metric(
            kpis['deduplication']['deduplication_rate_pct'],
            benchmarks['deduplication_rate'],
            higher_better=True
        )
        scores['avg_confidence'] = self._score_metric(
            kpis['quality']['avg_confidence'] * 100,
            benchmarks['avg_confidence'],
            higher_better=True
        )
        scores['high_confidence_pct'] = self._score_metric(
            kpis['quality']['high_confidence_pct'],
            benchmarks['high_confidence_pct'],
            higher_better=True
        )
        scores['unknown_rate'] = self._score_metric(
            kpis['quality']['unknown_rate_pct'],
            benchmarks['unknown_rate'],
            higher_better=False
        )
        scores['space_efficiency'] = self._score_metric(
            kpis['deduplication']['space_efficiency_pct'],
            benchmarks['space_efficiency'],
            higher_better=True
        )

        return scores, benchmarks

    def _score_metric(self, value, benchmark, higher_better=True):
        """Score a metric against benchmark"""
        if higher_better:
            if value >= benchmark['excellent']:
                return 'EXCELLENT'
            elif value >= benchmark['target']:
                return 'GOOD'
            elif value >= benchmark['good']:
                return 'ACCEPTABLE'
            else:
                return 'NEEDS_IMPROVEMENT'
        else:
            if value <= benchmark['excellent']:
                return 'EXCELLENT'
            elif value <= benchmark['target']:
                return 'GOOD'
            elif value <= benchmark['good']:
                return 'ACCEPTABLE'
            else:
                return 'NEEDS_IMPROVEMENT'

    def close(self):
        """Close database connection"""
        self.conn.close()


def main():
    calculator = IFMOSKPICalculator()
    kpis = calculator.generate_kpi_report(save_json=True)

    # Calculate benchmark scores
    scores, benchmarks = calculator.calculate_benchmarks(kpis)

    print()
    print("=" * 80)
    print("BENCHMARK PERFORMANCE")
    print("=" * 80)
    for metric, score in scores.items():
        print(f"  {metric}: {score}")
    print("=" * 80)

    calculator.close()


if __name__ == '__main__':
    main()
