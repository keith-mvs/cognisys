"""
Structure Proposal Generator for IFMOS.
Analyzes scan results and generates recommended repository structure.
"""

from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple
from collections import defaultdict
import yaml

from ..models.database import Database
from ..utils.logging_config import get_logger

logger = get_logger(__name__)


class StructureProposalGenerator:
    """
    Analyzes scanned files and generates optimal repository structure proposal.
    """

    def __init__(self, database: Database):
        """
        Initialize structure proposal generator.

        Args:
            database: Database instance
        """
        self.db = database

    def generate_proposal(self, session_id: str, output_path: str = None) -> Dict:
        """
        Generate structure proposal based on scan analysis.

        Args:
            session_id: Scan session to analyze
            output_path: Optional path to save YAML proposal

        Returns:
            Structure proposal dictionary
        """
        logger.info(f"=== Generating Structure Proposal ===")
        logger.info(f"Session ID: {session_id}")

        # Analyze session data
        logger.info("[1/5] Analyzing file categories...")
        category_stats = self._analyze_categories(session_id)

        logger.info("[2/5] Analyzing file patterns...")
        pattern_stats = self._analyze_patterns(session_id)

        logger.info("[3/5] Analyzing temporal distribution...")
        temporal_stats = self._analyze_temporal_distribution(session_id)

        logger.info("[4/5] Analyzing size distribution...")
        size_stats = self._analyze_size_distribution(session_id)

        logger.info("[5/5] Building structure proposal...")
        proposal = self._build_proposal(
            category_stats,
            pattern_stats,
            temporal_stats,
            size_stats
        )

        # Save to file if requested
        if output_path:
            self._save_proposal(proposal, output_path)
            logger.info(f"[OK] Proposal saved to: {output_path}")

        logger.info(f"=== Proposal Generation Complete ===")
        return proposal

    def _analyze_categories(self, session_id: str) -> Dict:
        """Analyze file category distribution."""
        cursor = self.db.conn.cursor()

        # Get category breakdown
        cursor.execute("""
            SELECT
                file_category,
                file_subcategory,
                COUNT(*) as count,
                SUM(size_bytes) as total_size,
                AVG(size_bytes) as avg_size
            FROM files
            WHERE scan_session_id = ?
            GROUP BY file_category, file_subcategory
            ORDER BY total_size DESC
        """, (session_id,))

        categories = {}
        for row in cursor.fetchall():
            cat, subcat, count, total_size, avg_size = row
            if cat not in categories:
                categories[cat] = {
                    'total_count': 0,
                    'total_size': 0,
                    'subcategories': {}
                }
            categories[cat]['total_count'] += count
            categories[cat]['total_size'] += total_size
            categories[cat]['subcategories'][subcat] = {
                'count': count,
                'total_size': total_size,
                'avg_size': avg_size
            }

        # Get extension breakdown per category
        cursor.execute("""
            SELECT
                file_category,
                extension,
                COUNT(*) as count
            FROM files
            WHERE scan_session_id = ? AND extension IS NOT NULL
            GROUP BY file_category, extension
            ORDER BY file_category, count DESC
        """, (session_id,))

        for row in cursor.fetchall():
            cat, ext, count = row
            if cat in categories:
                if 'extensions' not in categories[cat]:
                    categories[cat]['extensions'] = []
                categories[cat]['extensions'].append((ext, count))

        logger.info(f"  -> Found {len(categories)} main categories")
        return categories

    def _analyze_patterns(self, session_id: str) -> Dict:
        """Analyze naming patterns and folder structures."""
        cursor = self.db.conn.cursor()

        # Get common folder depths
        cursor.execute("""
            SELECT
                depth,
                COUNT(*) as count
            FROM folders
            WHERE scan_session_id = ?
            GROUP BY depth
            ORDER BY count DESC
        """, (session_id,))

        depth_distribution = {row[0]: row[1] for row in cursor.fetchall()}

        # Get common path patterns (top-level folders)
        cursor.execute("""
            SELECT DISTINCT path
            FROM folders
            WHERE scan_session_id = ?
            ORDER BY path
        """, (session_id,))

        paths = [row[0] for row in cursor.fetchall()]
        top_level_folders = self._extract_top_level_folders(paths)

        return {
            'depth_distribution': depth_distribution,
            'top_level_folders': top_level_folders,
            'common_depth': max(depth_distribution, key=depth_distribution.get) if depth_distribution else 3
        }

    def _analyze_temporal_distribution(self, session_id: str) -> Dict:
        """Analyze file age and modification patterns."""
        cursor = self.db.conn.cursor()

        cursor.execute("""
            SELECT
                COUNT(*) as total,
                AVG(JULIANDAY('now') - JULIANDAY(modified_at)) as avg_age_days,
                MIN(modified_at) as oldest,
                MAX(modified_at) as newest
            FROM files
            WHERE scan_session_id = ?
        """, (session_id,))

        row = cursor.fetchone()
        total, avg_age, oldest, newest = row

        # Get age buckets
        cursor.execute("""
            SELECT
                CASE
                    WHEN JULIANDAY('now') - JULIANDAY(modified_at) < 30 THEN '0-30 days'
                    WHEN JULIANDAY('now') - JULIANDAY(modified_at) < 90 THEN '30-90 days'
                    WHEN JULIANDAY('now') - JULIANDAY(modified_at) < 180 THEN '90-180 days'
                    WHEN JULIANDAY('now') - JULIANDAY(modified_at) < 365 THEN '180-365 days'
                    ELSE '365+ days'
                END as age_bucket,
                COUNT(*) as count,
                SUM(size_bytes) as total_size
            FROM files
            WHERE scan_session_id = ?
            GROUP BY age_bucket
        """, (session_id,))

        age_distribution = {row[0]: {'count': row[1], 'size': row[2]} for row in cursor.fetchall()}

        return {
            'total_files': total,
            'avg_age_days': avg_age or 0,
            'oldest': oldest,
            'newest': newest,
            'age_distribution': age_distribution
        }

    def _analyze_size_distribution(self, session_id: str) -> Dict:
        """Analyze file size distribution."""
        cursor = self.db.conn.cursor()

        cursor.execute("""
            SELECT
                CASE
                    WHEN size_bytes < 10240 THEN 'tiny'
                    WHEN size_bytes < 1048576 THEN 'small'
                    WHEN size_bytes < 10485760 THEN 'medium'
                    WHEN size_bytes < 104857600 THEN 'large'
                    ELSE 'very_large'
                END as size_class,
                COUNT(*) as count,
                SUM(size_bytes) as total_size
            FROM files
            WHERE scan_session_id = ?
            GROUP BY size_class
        """, (session_id,))

        size_distribution = {row[0]: {'count': row[1], 'total_size': row[2]} for row in cursor.fetchall()}

        return size_distribution

    def _extract_top_level_folders(self, paths: List[str]) -> Dict[str, int]:
        """Extract and count top-level folder names."""
        top_level_counts = defaultdict(int)

        for path in paths:
            parts = Path(path).parts
            if len(parts) > 1:  # Skip root
                # Get first meaningful folder (skip drive letter on Windows)
                start_idx = 1 if len(parts[0]) == 2 and parts[0][1] == ':' else 0
                if len(parts) > start_idx:
                    top_level = parts[start_idx]
                    top_level_counts[top_level] += 1

        # Sort by frequency
        sorted_folders = sorted(top_level_counts.items(), key=lambda x: x[1], reverse=True)
        return dict(sorted_folders[:20])  # Top 20

    def _build_proposal(
        self,
        category_stats: Dict,
        pattern_stats: Dict,
        temporal_stats: Dict,
        size_stats: Dict
    ) -> Dict:
        """Build complete structure proposal."""

        # Calculate total size
        total_size = sum(cat['total_size'] for cat in category_stats.values())
        total_files = sum(cat['total_count'] for cat in category_stats.values())

        # Suggest top-level structure based on content
        top_level_folders = self._suggest_top_level(category_stats, temporal_stats)

        # Build classification rules for each significant category
        classification = {}
        for cat_name, cat_data in category_stats.items():
            # Only include categories with >1% of files or >1GB
            if cat_data['total_count'] / total_files > 0.01 or cat_data['total_size'] > 1e9:
                classification[cat_name] = self._build_category_classification(
                    cat_name,
                    cat_data,
                    top_level_folders
                )

        # Suggest lifecycle rules based on age distribution
        lifecycle = self._suggest_lifecycle_rules(temporal_stats)

        # Build proposal
        proposal = {
            'generated_at': datetime.now().isoformat(),
            'session_stats': {
                'total_files': total_files,
                'total_size_gb': round(total_size / 1e9, 2),
                'categories': len(category_stats)
            },
            'repository_root': 'C:\\Repository',  # Default, user should customize
            'structure': {
                'top_level': top_level_folders
            },
            'classification': classification,
            'naming_conventions': self._suggest_naming_conventions(),
            'lifecycle': lifecycle,
            'backward_compatibility': {
                'create_symlinks': False,
                'symlink_lifetime_days': 90
            }
        }

        return proposal

    def _suggest_top_level(self, category_stats: Dict, temporal_stats: Dict) -> List[str]:
        """Suggest top-level folder structure."""
        folders = ['Active', 'Archive']

        # Add category-specific folders for major categories
        for cat_name, cat_data in category_stats.items():
            if cat_data['total_count'] > 100:  # Significant category
                # Suggest dedicated folder for large categories
                if cat_name in ['documents', 'media', 'code']:
                    if cat_name.title() not in folders:
                        folders.append(cat_name.title())

        # Always include these
        if 'Shared' not in folders:
            folders.append('Shared')
        if 'Quarantine' not in folders:
            folders.append('Quarantine')

        return folders

    def _build_category_classification(
        self,
        cat_name: str,
        cat_data: Dict,
        top_level_folders: List[str]
    ) -> Dict:
        """Build classification rules for a category."""

        # Get top extensions
        extensions = [ext for ext, count in cat_data.get('extensions', [])[:20]]

        # Determine target path based on category
        if cat_name == 'documents':
            target = 'Active/Documents/{subcategory}/{YYYY}'
        elif cat_name == 'media':
            target = 'Active/Media/{subcategory}/{YYYY-MM}'
        elif cat_name == 'code':
            target = 'Active/Projects/{project_name}/src'
        elif cat_name == 'archives':
            target = 'Archive/Compressed/{YYYY}'
        else:
            target = f'Active/{cat_name.title()}/{{YYYY}}'

        classification = {
            'extensions': extensions,
            'target': target
        }

        # Add subcategories if available
        if 'subcategories' in cat_data and cat_data['subcategories']:
            subcats = list(cat_data['subcategories'].keys())
            if 'unknown' in subcats or 'other' in subcats:
                subcats = [s for s in subcats if s not in ['unknown', 'other']]
            if subcats:
                classification['subcategories'] = subcats[:10]  # Top 10

        # Add preserve_structure flag for code
        if cat_name == 'code':
            classification['preserve_structure'] = True

        return classification

    def _suggest_naming_conventions(self) -> Dict:
        """Suggest naming conventions."""
        return {
            'files': {
                'pattern': '{YYYY-MM-DD}_{Name}_{Type}.{ext}',
                'rules': {
                    'date_format': 'YYYY-MM-DD',
                    'separator': '_',
                    'case': 'PascalCase',
                    'version_format': 'v{NN}'
                }
            },
            'folders': {
                'case': 'PascalCase',
                'separator': '_',
                'max_depth': 5
            }
        }

    def _suggest_lifecycle_rules(self, temporal_stats: Dict) -> Dict:
        """Suggest lifecycle management rules based on age distribution."""
        age_dist = temporal_stats.get('age_distribution', {})

        # Calculate threshold for archiving (files older than 80% of dataset)
        total_files = temporal_stats.get('total_files', 0)
        avg_age = temporal_stats.get('avg_age_days', 0)

        # Suggest archiving files older than average age + 50%
        archive_threshold = int(avg_age * 1.5) if avg_age > 30 else 180

        return {
            'active_to_archive': {
                'trigger': {
                    'not_modified_days': max(180, archive_threshold),
                    'access_count': 0
                },
                'action': 'move',
                'target': 'Archive/{original_category}/{YYYY}'
            },
            'quarantine_review': {
                'trigger': {
                    'in_quarantine_days': 30
                },
                'action': 'prompt',
                'options': ['restore', 'delete', 'keep']
            }
        }

    def _save_proposal(self, proposal: Dict, output_path: str):
        """Save proposal to YAML file."""
        # Add helpful comments
        commented_proposal = {
            '# IFMOS Structure Proposal': None,
            '# Generated': proposal['generated_at'],
            '# Review and customize before using for migration': None,
            **proposal
        }

        # Remove the session_stats from YAML (keep in return value only)
        yaml_proposal = {k: v for k, v in proposal.items() if k != 'session_stats'}

        with open(output_path, 'w') as f:
            f.write(f"# IFMOS Structure Proposal\n")
            f.write(f"# Generated: {proposal['generated_at']}\n")
            f.write(f"# Based on session with {proposal['session_stats']['total_files']} files ")
            f.write(f"({proposal['session_stats']['total_size_gb']} GB)\n")
            f.write(f"# REVIEW AND CUSTOMIZE before using for migration\n\n")
            yaml.dump(yaml_proposal, f, default_flow_style=False, sort_keys=False, indent=2)
