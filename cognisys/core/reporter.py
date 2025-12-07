"""
Reporting engine for IFMOS.
Generates comprehensive reports with statistics, visualizations, and insights.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from ..models.database import Database
from ..utils.logging_config import get_logger

logger = get_logger(__name__)


class Reporter:
    """
    Generates detailed analysis reports in multiple formats.
    """

    def __init__(self, database: Database, config: Dict):
        """
        Initialize reporter with database and configuration.

        Args:
            database: Database instance
            config: Configuration dictionary
        """
        self.db = database
        self.config = config

    def generate_report(self, session_id: str, output_dir: str, formats: List[str] = None):
        """
        Generate comprehensive analysis report.

        Args:
            session_id: Scan session ID
            output_dir: Directory to save reports
            formats: List of output formats (html, json, csv)
        """
        if formats is None:
            formats = ['html', 'json']

        logger.info(f"Generating report for session {session_id}")

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Collect all metrics
        report_data = {
            'session_id': session_id,
            'generated_at': datetime.now().isoformat(),
            'overview': self._get_overview(session_id),
            'file_types': self._get_file_type_distribution(session_id),
            'subcategories': self._get_subcategory_distribution(session_id),
            'extensions': self._get_extension_distribution(session_id),
            'size_distribution': self._get_size_distribution(session_id),
            'timeline': self._get_timeline_data(session_id),
            'largest_files': self._get_largest_files(session_id),
            'largest_folders': self._get_largest_folders(session_id),
            'duplicates': self._get_duplication_metrics(session_id),
            'insights': self._generate_insights(session_id)
        }

        # Generate outputs
        if 'json' in formats:
            self._save_json(report_data, output_path / f"{session_id}_report.json")

        if 'html' in formats:
            self._save_html(report_data, output_path / f"{session_id}_report.html")

        if 'csv' in formats:
            self._save_csv_exports(session_id, output_path)

        logger.info(f"Reports saved to {output_path}")

    def _get_overview(self, session_id: str) -> Dict:
        """Get overview statistics."""
        stats = self.db.get_overview_stats(session_id)
        return {
            'total_files': stats['total_files'],
            'total_folders': stats['total_folders'],
            'total_size_gb': stats['total_size'] / 1e9 if stats['total_size'] else 0,
            'unique_extensions': stats['unique_extensions'],
            'date_range': {
                'oldest': stats['oldest'],
                'newest': stats['newest']
            }
        }

    def _get_file_type_distribution(self, session_id: str) -> List[Dict]:
        """Get file type distribution."""
        return self.db.get_file_type_distribution(session_id)

    def _get_largest_files(self, session_id: str, limit: int = 20) -> List[Dict]:
        """Get largest files."""
        files = self.db.get_largest_files(session_id, limit)
        return [
            {
                'name': f['name'],
                'path': f['path'],
                'size_mb': f['size_bytes'] / 1e6,
                'modified': f['modified_at']
            }
            for f in files
        ]

    def _get_largest_folders(self, session_id: str, limit: int = 20) -> List[Dict]:
        """Get largest folders."""
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT f.path,
                   COUNT(DISTINCT files.file_id) as file_count,
                   SUM(files.size_bytes) as total_size
            FROM folders f
            LEFT JOIN files ON files.path LIKE f.path || '%'
            WHERE f.scan_session_id = ?
            GROUP BY f.folder_id
            ORDER BY total_size DESC
            LIMIT ?
        """, (session_id, limit))

        results = []
        for row in cursor.fetchall():
            results.append({
                'path': row[0],
                'file_count': row[1],
                'size_gb': row[2] / 1e9 if row[2] else 0
            })

        return results

    def _get_duplication_metrics(self, session_id: str) -> Dict:
        """Get duplication analysis."""
        metrics = self.db.get_duplication_metrics(session_id)

        return {
            'duplicate_sets': metrics.get('duplicate_sets', 0) or 0,
            'duplicate_files': metrics.get('total_duplicate_files', 0) or 0,
            'wasted_space_gb': (metrics.get('wasted_space', 0) or 0) / 1e9,
            'by_type': metrics.get('by_type', [])
        }

    def _get_subcategory_distribution(self, session_id: str) -> List[Dict]:
        """Get file distribution by subcategory."""
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT file_category, file_subcategory,
                   COUNT(*) as count,
                   SUM(size_bytes) as total_size
            FROM files
            WHERE scan_session_id = ?
            GROUP BY file_category, file_subcategory
            ORDER BY total_size DESC
        """, (session_id,))

        results = []
        for row in cursor.fetchall():
            results.append({
                'category': row[0],
                'subcategory': row[1],
                'count': row[2],
                'total_size': row[3]
            })
        return results

    def _get_extension_distribution(self, session_id: str, limit: int = 20) -> List[Dict]:
        """Get top file extensions by count and size."""
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT extension,
                   COUNT(*) as count,
                   SUM(size_bytes) as total_size,
                   AVG(size_bytes) as avg_size
            FROM files
            WHERE scan_session_id = ? AND extension IS NOT NULL AND extension != ''
            GROUP BY extension
            ORDER BY total_size DESC
            LIMIT ?
        """, (session_id, limit))

        results = []
        for row in cursor.fetchall():
            results.append({
                'extension': row[0],
                'count': row[1],
                'total_size': row[2],
                'avg_size': row[3]
            })
        return results

    def _get_size_distribution(self, session_id: str) -> Dict:
        """Get distribution of files by size ranges."""
        cursor = self.db.conn.cursor()

        size_ranges = [
            ('tiny', 0, 10240),  # 0-10 KB
            ('small', 10240, 102400),  # 10-100 KB
            ('medium', 102400, 1048576),  # 100 KB - 1 MB
            ('large', 1048576, 10485760),  # 1-10 MB
            ('very_large', 10485760, 104857600),  # 10-100 MB
            ('huge', 104857600, float('inf'))  # 100 MB+
        ]

        distribution = {}
        for label, min_size, max_size in size_ranges:
            if max_size == float('inf'):
                cursor.execute("""
                    SELECT COUNT(*), SUM(size_bytes)
                    FROM files
                    WHERE scan_session_id = ? AND size_bytes >= ?
                """, (session_id, min_size))
            else:
                cursor.execute("""
                    SELECT COUNT(*), SUM(size_bytes)
                    FROM files
                    WHERE scan_session_id = ? AND size_bytes >= ? AND size_bytes < ?
                """, (session_id, min_size, max_size))

            count, total = cursor.fetchone()
            distribution[label] = {
                'count': count or 0,
                'total_size': total or 0,
                'range': f"{min_size/1024:.0f}KB-{max_size/1024:.0f}KB" if max_size != float('inf') else f"{min_size/1024:.0f}KB+"
            }

        return distribution

    def _get_timeline_data(self, session_id: str) -> Dict:
        """Get file creation/modification timeline."""
        cursor = self.db.conn.cursor()

        # Files created per month
        cursor.execute("""
            SELECT strftime('%Y-%m', created_at) as month,
                   COUNT(*) as count,
                   SUM(size_bytes) as size
            FROM files
            WHERE scan_session_id = ? AND created_at IS NOT NULL
            GROUP BY month
            ORDER BY month DESC
            LIMIT 12
        """, (session_id,))

        creation_timeline = []
        for row in cursor.fetchall():
            creation_timeline.append({
                'month': row[0],
                'count': row[1],
                'size': row[2]
            })

        # Files modified per month
        cursor.execute("""
            SELECT strftime('%Y-%m', modified_at) as month,
                   COUNT(*) as count
            FROM files
            WHERE scan_session_id = ? AND modified_at IS NOT NULL
            GROUP BY month
            ORDER BY month DESC
            LIMIT 12
        """, (session_id,))

        modification_timeline = []
        for row in cursor.fetchall():
            modification_timeline.append({
                'month': row[0],
                'count': row[1]
            })

        return {
            'creation': creation_timeline,
            'modification': modification_timeline
        }

    def _generate_insights(self, session_id: str) -> List[Dict]:
        """Generate narrative insights."""
        insights = []

        # Overview stats
        overview = self._get_overview(session_id)

        # Insight 1: Storage concentration
        file_types = self._get_file_type_distribution(session_id)
        if file_types:
            top_category = max(file_types, key=lambda x: x['total_size'])
            insights.append({
                'severity': 'info',
                'title': f"Storage Dominated by {top_category['file_category'].title()}",
                'description': f"{top_category['pct_of_total']}% of total storage "
                              f"({top_category['total_size']/1e9:.1f} GB) consists of "
                              f"{top_category['file_category']} files.",
                'action': 'Consider archiving or compressing old files.'
            })

        # Insight 2: Duplication
        dup_metrics = self._get_duplication_metrics(session_id)
        if dup_metrics['wasted_space_gb'] > 1:
            insights.append({
                'severity': 'warning',
                'title': f"Significant Duplication: {dup_metrics['wasted_space_gb']:.1f} GB Recoverable",
                'description': f"Found {dup_metrics['duplicate_sets']} sets of duplicate files. "
                              f"Removing duplicates could free {dup_metrics['wasted_space_gb']:.1f} GB.",
                'action': 'Review duplicate groups and approve cleanup.'
            })

        # Insight 3: Orphaned files
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT COUNT(*), SUM(size_bytes)
            FROM files
            WHERE scan_session_id = ? AND is_orphaned = 1
        """, (session_id,))
        orphan_count, orphan_size = cursor.fetchone()

        if orphan_count and orphan_count > 0:
            insights.append({
                'severity': 'suggestion',
                'title': f"{orphan_count} Orphaned Files Found",
                'description': f"Identified {orphan_size/1e9:.1f} GB of files not accessed in over a year.",
                'action': 'Archive to cold storage or external backup.'
            })

        return insights

    def _save_json(self, data: Dict, filepath: Path):
        """Save report as JSON."""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)

        logger.info(f"JSON report saved: {filepath}")

    def _save_html(self, data: Dict, filepath: Path):
        """Save report as HTML."""
        html = self._generate_html(data)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html)

        logger.info(f"HTML report saved: {filepath}")

    def _generate_html(self, data: Dict) -> str:
        """Generate enhanced HTML report with charts and visualizations."""
        # Load template
        template_path = Path(__file__).parent.parent / 'templates' / 'report_template.html'
        with open(template_path, 'r', encoding='utf-8') as f:
            template = f.read()

        # Prepare basic data
        overview = data['overview']
        total_size = overview['total_size_gb']

        # Build insights HTML
        insights_html = ""
        for insight in data['insights']:
            insights_html += f"""
            <div class="insight-card {insight['severity']}">
                <h3>{insight['title']}</h3>
                <p>{insight['description']}</p>
                <div class="action">{insight['action']}</div>
            </div>
            """

        # Build subcategory table rows
        subcategory_rows = ""
        for subcat in data['subcategories']:
            pct = (subcat['total_size'] / (total_size * 1e9)) * 100 if total_size > 0 else 0
            subcategory_rows += f"""
            <tr>
                <td><span class="badge badge-primary">{subcat['category'].title()}</span></td>
                <td>{subcat['subcategory'].replace('_', ' ').title()}</td>
                <td>{subcat['count']:,}</td>
                <td>{subcat['total_size'] / 1e9:.2f}</td>
                <td>{pct:.1f}%</td>
            </tr>
            """

        # Build largest files rows
        largest_files_rows = ""
        for file in data['largest_files'][:20]:
            largest_files_rows += f"""
            <tr>
                <td>{file['name']}</td>
                <td>{file['size_mb']:.2f}</td>
                <td>{file['modified']}</td>
            </tr>
            """

        # Build largest folders rows
        largest_folders_rows = ""
        for folder in data['largest_folders'][:20]:
            largest_folders_rows += f"""
            <tr>
                <td>{folder['path']}</td>
                <td>{folder['file_count']:,}</td>
                <td>{folder['size_gb']:.2f}</td>
            </tr>
            """

        # Generate chart data (JSON format for Chart.js)
        # Category chart
        category_labels = [ft['file_category'].title() for ft in data['file_types'][:10]]
        category_sizes = [ft['total_size'] / 1e9 for ft in data['file_types'][:10]]
        category_chart_data = f'''{{
            labels: {json.dumps(category_labels)},
            datasets: [{{
                data: {json.dumps(category_sizes)},
                backgroundColor: ['#667eea', '#764ba2', '#f093fb', '#4facfe', '#43e97b', '#fa709a', '#fee140', '#30cfd0', '#a8edea', '#fed6e3']
            }}]
        }}'''

        # Extension chart
        ext_labels = [ext['extension'] for ext in data['extensions'][:15]]
        ext_sizes = [ext['total_size'] / 1e9 for ext in data['extensions'][:15]]
        extension_chart_data = f'''{{
            labels: {json.dumps(ext_labels)},
            datasets: [{{
                label: 'Size (GB)',
                data: {json.dumps(ext_sizes)},
                backgroundColor: '#667eea'
            }}]
        }}'''

        # Size distribution chart
        size_labels = [v['range'] for v in data['size_distribution'].values()]
        size_counts = [v['count'] for v in data['size_distribution'].values()]
        size_chart_data = f'''{{
            labels: {json.dumps(size_labels)},
            datasets: [{{
                data: {json.dumps(size_counts)},
                backgroundColor: ['#667eea', '#764ba2', '#f093fb', '#4facfe', '#43e97b', '#fa709a']
            }}]
        }}'''

        # Timeline chart
        timeline_months = [t['month'] for t in data['timeline']['creation'][:12]][::-1]
        timeline_counts = [t['count'] for t in data['timeline']['creation'][:12]][::-1]
        timeline_chart_data = f'''{{
            labels: {json.dumps(timeline_months)},
            datasets: [{{
                label: 'Files Created',
                data: {json.dumps(timeline_counts)},
                borderColor: '#667eea',
                backgroundColor: 'rgba(102, 126, 234, 0.1)',
                fill: true
            }}]
        }}'''

        # Replace placeholders
        html = template
        html = html.replace('{{session_id}}', data['session_id'])
        html = html.replace('{{generated_at}}', data['generated_at'])
        html = html.replace('{{total_files}}', f"{overview['total_files']:,}")
        html = html.replace('{{total_folders}}', f"{overview['total_folders']:,}")
        html = html.replace('{{total_size_gb}}', f"{overview['total_size_gb']:.2f}")
        html = html.replace('{{unique_extensions}}', str(overview['unique_extensions']))
        html = html.replace('{{duplicate_files}}', f"{data['duplicates']['duplicate_files']:,}")
        html = html.replace('{{wasted_space_gb}}', f"{data['duplicates']['wasted_space_gb']:.2f}")

        # Date range
        oldest = overview['date_range']['oldest'][:10] if overview['date_range']['oldest'] else 'N/A'
        newest = overview['date_range']['newest'][:10] if overview['date_range']['newest'] else 'N/A'
        html = html.replace('{{date_range}}', f"{oldest} to {newest}")

        html = html.replace('{{insights_html}}', insights_html)
        html = html.replace('{{subcategory_rows}}', subcategory_rows)
        html = html.replace('{{largest_files_rows}}', largest_files_rows)
        html = html.replace('{{largest_folders_rows}}', largest_folders_rows)
        html = html.replace('{{category_chart_data}}', category_chart_data)
        html = html.replace('{{extension_chart_data}}', extension_chart_data)
        html = html.replace('{{size_chart_data}}', size_chart_data)
        html = html.replace('{{timeline_chart_data}}', timeline_chart_data)

        return html

    def _save_csv_exports(self, session_id: str, output_dir: Path):
        """Export data to CSV files."""
        import csv

        # Export files inventory
        files = self.db.get_files_by_session(session_id)
        with open(output_dir / 'files_inventory.csv', 'w', newline='', encoding='utf-8') as f:
            if files:
                writer = csv.DictWriter(f, fieldnames=files[0].keys())
                writer.writeheader()
                writer.writerows(files)

        logger.info(f"CSV exports saved to {output_dir}")
