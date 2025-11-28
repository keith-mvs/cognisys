#!/usr/bin/env python3
"""
IFMOS Pattern Detection System
Analyzes classification patterns and identifies anomalies, trends, and optimization opportunities
"""

import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import sys

# Add IFMOS to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PatternDetector:
    """Detects patterns in document classifications"""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def detect_classification_drift(self) -> dict:
        """Detect if classification patterns have changed over time"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get classifications from last 7 days vs previous 7 days
        cursor.execute("""
            SELECT
                CASE
                    WHEN datetime(created_at) > datetime('now', '-7 days') THEN 'recent'
                    ELSE 'previous'
                END as period,
                doc_type,
                COUNT(*) as count
            FROM documents
            WHERE datetime(created_at) > datetime('now', '-14 days')
            GROUP BY period, doc_type
        """)

        recent = defaultdict(int)
        previous = defaultdict(int)

        for period, doc_type, count in cursor.fetchall():
            if period == 'recent':
                recent[doc_type] = count
            else:
                previous[doc_type] = count

        # Calculate drift
        drift_analysis = []
        all_types = set(recent.keys()) | set(previous.keys())

        for doc_type in all_types:
            recent_count = recent.get(doc_type, 0)
            previous_count = previous.get(doc_type, 0)

            if previous_count > 0:
                change_pct = ((recent_count - previous_count) / previous_count) * 100
                if abs(change_pct) > 50:  # 50% threshold
                    drift_analysis.append({
                        'type': doc_type,
                        'recent': recent_count,
                        'previous': previous_count,
                        'change_pct': change_pct
                    })

        conn.close()
        return drift_analysis

    def detect_low_confidence_patterns(self) -> dict:
        """Find patterns in low-confidence classifications"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                doc_type,
                COUNT(*) as count,
                AVG(confidence) as avg_confidence,
                MIN(confidence) as min_confidence
            FROM documents
            WHERE confidence < 0.7
            GROUP BY doc_type
            HAVING count >= 3
            ORDER BY count DESC
        """)

        low_confidence_types = []
        for row in cursor.fetchall():
            doc_type, count, avg_conf, min_conf = row
            low_confidence_types.append({
                'type': doc_type,
                'count': count,
                'avg_confidence': avg_conf,
                'min_confidence': min_conf
            })

        conn.close()
        return low_confidence_types

    def detect_misclassification_hotspots(self) -> dict:
        """Identify document types frequently corrected via feedback"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                d.doc_type as predicted_type,
                f.correct_type,
                COUNT(*) as error_count
            FROM feedback f
            JOIN documents d ON f.doc_id = d.id
            WHERE f.is_correct = 0
            GROUP BY d.doc_type, f.correct_type
            HAVING error_count >= 3
            ORDER BY error_count DESC
        """)

        hotspots = []
        for row in cursor.fetchall():
            predicted, correct, count = row
            hotspots.append({
                'predicted_type': predicted,
                'correct_type': correct,
                'error_count': count
            })

        conn.close()
        return hotspots

    def detect_filename_patterns(self) -> dict:
        """Analyze filename patterns for classification improvement"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT file_name, doc_type
            FROM documents
            LIMIT 1000
        """)

        # Extract common filename patterns
        type_patterns = defaultdict(list)

        for filename, doc_type in cursor.fetchall():
            # Extract patterns (simplified - real implementation would use regex)
            filename_lower = filename.lower()

            if 'invoice' in filename_lower:
                type_patterns[doc_type].append('invoice_keyword')
            if 'receipt' in filename_lower:
                type_patterns[doc_type].append('receipt_keyword')
            if any(year in filename_lower for year in ['2023', '2024', '2025']):
                type_patterns[doc_type].append('year_in_name')
            if filename.startswith('['):
                type_patterns[doc_type].append('bracketed_prefix')

        # Find strongest correlations
        correlations = []
        for doc_type, patterns in type_patterns.items():
            pattern_counts = Counter(patterns)
            for pattern, count in pattern_counts.most_common(3):
                if count >= 5:
                    correlations.append({
                        'doc_type': doc_type,
                        'pattern': pattern,
                        'frequency': count
                    })

        conn.close()
        return correlations

    def detect_temporal_patterns(self) -> dict:
        """Detect time-based classification patterns"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                strftime('%H', created_at) as hour,
                doc_type,
                COUNT(*) as count
            FROM documents
            WHERE datetime(created_at) > datetime('now', '-7 days')
            GROUP BY hour, doc_type
            ORDER BY hour, count DESC
        """)

        hourly_patterns = defaultdict(list)

        for hour, doc_type, count in cursor.fetchall():
            hourly_patterns[hour].append((doc_type, count))

        # Find peak hours for each type
        peak_hours = {}
        for doc_type in set(row[1] for row in cursor.fetchall()):
            type_hours = []
            for hour, types in hourly_patterns.items():
                for t, count in types:
                    if t == doc_type:
                        type_hours.append((hour, count))

            if type_hours:
                peak_hour = max(type_hours, key=lambda x: x[1])
                peak_hours[doc_type] = peak_hour[0]

        conn.close()
        return peak_hours

    def generate_report(self) -> str:
        """Generate comprehensive pattern analysis report"""
        report = []
        report.append("=" * 60)
        report.append("IFMOS PATTERN DETECTION REPORT")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("=" * 60)
        report.append("")

        # Classification drift
        drift = self.detect_classification_drift()
        report.append("## Classification Drift Analysis")
        if drift:
            for item in drift:
                report.append(f"  • {item['type']}: {item['change_pct']:+.1f}% change")
                report.append(f"    (Recent: {item['recent']}, Previous: {item['previous']})")
        else:
            report.append("  No significant drift detected")
        report.append("")

        # Low confidence
        low_conf = self.detect_low_confidence_patterns()
        report.append("## Low Confidence Classifications")
        if low_conf:
            for item in low_conf[:5]:
                report.append(f"  • {item['type']}: {item['count']} docs @ {item['avg_confidence']:.2f} avg confidence")
        else:
            report.append("  All classifications have good confidence")
        report.append("")

        # Misclassification hotspots
        hotspots = self.detect_misclassification_hotspots()
        report.append("## Misclassification Hotspots")
        if hotspots:
            for item in hotspots[:5]:
                report.append(f"  • {item['predicted_type']} → {item['correct_type']}: {item['error_count']} errors")
        else:
            report.append("  No significant misclassification patterns")
        report.append("")

        # Filename patterns
        patterns = self.detect_filename_patterns()
        report.append("## Filename Pattern Correlations")
        if patterns:
            for item in patterns[:10]:
                report.append(f"  • {item['doc_type']} ← {item['pattern']} ({item['frequency']} occurrences)")
        else:
            report.append("  No strong filename patterns detected")
        report.append("")

        report.append("=" * 60)
        return "\n".join(report)


def main():
    """CLI entry point"""
    db_path = PROJECT_ROOT / "ifmos" / "data" / "training" / "ifmos_ml.db"

    detector = PatternDetector(str(db_path))
    report = detector.generate_report()

    print(report)

    # Save report
    report_path = PROJECT_ROOT / "reports" / f"pattern_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    report_path.parent.mkdir(exist_ok=True)
    report_path.write_text(report)

    logger.info(f"Report saved to: {report_path}")


if __name__ == "__main__":
    main()
