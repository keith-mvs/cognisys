#!/usr/bin/env python3
"""
Automatic Pattern Detection for Unknown Files
Analyzes filename patterns, paths, and characteristics
"""

import sqlite3
from pathlib import Path
from collections import Counter, defaultdict
import re
import json


class UnknownPatternAnalyzer:
    """Automatically detect patterns in unknown files"""

    def __init__(self, db_path: str = '.cognisys/file_registry.db'):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self.patterns = defaultdict(list)

    def analyze_all_patterns(self):
        """Run comprehensive pattern analysis"""
        print("=" * 80)
        print("UNKNOWN FILE PATTERN ANALYSIS")
        print("=" * 80)

        # Get all unknown files
        self.cursor.execute('''
            SELECT file_id, original_path, file_size
            FROM file_registry
            WHERE document_type = 'unknown'
        ''')

        unknown_files = self.cursor.fetchall()
        total = len(unknown_files)

        print(f"\nAnalyzing {total:,} unknown files...")
        print()

        # Run analyses
        results = {
            'total': total,
            'directory_patterns': self.analyze_directory_patterns(unknown_files),
            'filename_patterns': self.analyze_filename_patterns(unknown_files),
            'extension_patterns': self.analyze_extension_patterns(unknown_files),
            'size_patterns': self.analyze_size_patterns(unknown_files),
            'character_patterns': self.analyze_character_patterns(unknown_files)
        }

        # Generate classification suggestions
        suggestions = self.generate_classification_suggestions(results)

        return results, suggestions

    def analyze_directory_patterns(self, files):
        """Detect common directory patterns"""
        dir_patterns = Counter()
        dir_samples = defaultdict(list)

        for file_id, path, size in files:
            p = Path(path)
            parent_str = str(p.parent).lower()

            # Categorize by directory keywords
            if 'node_modules' in parent_str:
                dir_patterns['node_modules'] += 1
                dir_samples['node_modules'].append(p.name)
            elif '__pycache__' in parent_str:
                dir_patterns['__pycache__'] += 1
                dir_samples['__pycache__'].append(p.name)
            elif '.git' in parent_str:
                dir_patterns['.git'] += 1
                dir_samples['.git'].append(p.name)
            elif 'venv' in parent_str or 'site-packages' in parent_str:
                dir_patterns['venv/site-packages'] += 1
                dir_samples['venv/site-packages'].append(p.name)
            elif 'build' in parent_str or 'dist' in parent_str:
                dir_patterns['build/dist'] += 1
                dir_samples['build/dist'].append(p.name)
            elif 'cache' in parent_str or 'tmp' in parent_str or 'temp' in parent_str:
                dir_patterns['cache/temp'] += 1
                dir_samples['cache/temp'].append(p.name)
            elif '.vscode' in parent_str or '.idea' in parent_str:
                dir_patterns['IDE metadata'] += 1
                dir_samples['IDE metadata'].append(p.name)
            else:
                dir_patterns['other'] += 1

        return {
            'counts': dict(dir_patterns.most_common()),
            'samples': {k: v[:5] for k, v in dir_samples.items()}
        }

    def analyze_filename_patterns(self, files):
        """Detect filename patterns"""
        patterns = {
            'uuid': [],
            'hex_hash_40': [],
            'hex_hash_32': [],
            'hex_hash_16': [],
            'numbered': [],
            'timestamp': [],
            'versioned': [],
            'no_extension': [],
            'mixed': []
        }

        for file_id, path, size in files:
            p = Path(path)
            name = p.name
            stem = p.stem

            # UUID pattern (8-4-4-4-12)
            if re.match(r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', name, re.I):
                patterns['uuid'].append(name)

            # 40-char hex (Git SHA-1)
            elif len(stem) == 40 and re.match(r'^[a-f0-9]{40}$', stem):
                patterns['hex_hash_40'].append(name)

            # 32-char hex (MD5)
            elif len(stem) == 32 and re.match(r'^[a-f0-9]{32}$', stem):
                patterns['hex_hash_32'].append(name)

            # 16-char hex + version
            elif re.match(r'^[a-f0-9]{16}@v\d+$', name):
                patterns['hex_hash_16'].append(name)

            # Purely numeric
            elif re.match(r'^\d+$', stem):
                patterns['numbered'].append(name)

            # Timestamp-like (8+ digits)
            elif re.match(r'.*\d{8,}', name):
                patterns['timestamp'].append(name)

            # Contains @v (version suffix)
            elif '@v' in name:
                patterns['versioned'].append(name)

            # No extension
            elif not p.suffix:
                patterns['no_extension'].append(name)

            else:
                patterns['mixed'].append(name)

        # Count and sample
        result = {}
        for pattern_type, files in patterns.items():
            if files:
                result[pattern_type] = {
                    'count': len(files),
                    'samples': files[:10]
                }

        return result

    def analyze_extension_patterns(self, files):
        """Analyze file extensions"""
        extensions = Counter()
        ext_samples = defaultdict(list)

        for file_id, path, size in files:
            p = Path(path)
            ext = p.suffix.lower() if p.suffix else 'no_extension'
            extensions[ext] += 1
            if len(ext_samples[ext]) < 5:
                ext_samples[ext].append(p.name)

        return {
            'counts': dict(extensions.most_common(30)),
            'samples': dict(ext_samples)
        }

    def analyze_size_patterns(self, files):
        """Analyze file size distributions"""
        sizes = {
            'empty': [],
            'tiny (< 1KB)': [],
            'small (1KB-100KB)': [],
            'medium (100KB-10MB)': [],
            'large (> 10MB)': []
        }

        for file_id, path, size in files:
            p = Path(path)
            name = p.name

            if size == 0:
                sizes['empty'].append(name)
            elif size < 1024:
                sizes['tiny (< 1KB)'].append(name)
            elif size < 100 * 1024:
                sizes['small (1KB-100KB)'].append(name)
            elif size < 10 * 1024 * 1024:
                sizes['medium (100KB-10MB)'].append(name)
            else:
                sizes['large (> 10MB)'].append(name)

        return {
            category: {
                'count': len(files),
                'samples': files[:5]
            }
            for category, files in sizes.items() if files
        }

    def analyze_character_patterns(self, files):
        """Analyze character composition"""
        patterns = {
            'all_lowercase': 0,
            'all_uppercase': 0,
            'mixed_case': 0,
            'contains_underscore': 0,
            'contains_dash': 0,
            'contains_dot': 0,
            'alphanumeric_only': 0,
            'contains_special': 0
        }

        for file_id, path, size in files:
            name = Path(path).stem  # Without extension

            if name.islower():
                patterns['all_lowercase'] += 1
            elif name.isupper():
                patterns['all_uppercase'] += 1
            else:
                patterns['mixed_case'] += 1

            if '_' in name:
                patterns['contains_underscore'] += 1
            if '-' in name:
                patterns['contains_dash'] += 1
            if '.' in name:
                patterns['contains_dot'] += 1

            if name.replace('-', '').replace('_', '').isalnum():
                patterns['alphanumeric_only'] += 1
            else:
                patterns['contains_special'] += 1

        return patterns

    def generate_classification_suggestions(self, results):
        """Generate actionable classification suggestions"""
        suggestions = []
        total = results['total']

        # Directory-based suggestions
        for dir_type, count in results['directory_patterns']['counts'].items():
            if dir_type == 'other':
                continue

            coverage = (count / total) * 100
            if coverage >= 1.0:  # Suggest if covers 1%+ of unknowns
                suggestions.append({
                    'type': 'directory_pattern',
                    'pattern': dir_type,
                    'count': count,
                    'coverage_pct': coverage,
                    'suggested_type': self._suggest_doc_type_for_directory(dir_type),
                    'confidence': 0.85,
                    'samples': results['directory_patterns']['samples'].get(dir_type, [])[:3]
                })

        # Filename pattern suggestions
        for pattern_type, data in results['filename_patterns'].items():
            count = data['count']
            coverage = (count / total) * 100

            if coverage >= 0.5:  # Suggest if covers 0.5%+ of unknowns
                suggestions.append({
                    'type': 'filename_pattern',
                    'pattern': pattern_type,
                    'count': count,
                    'coverage_pct': coverage,
                    'suggested_type': self._suggest_doc_type_for_filename(pattern_type),
                    'confidence': 0.80,
                    'samples': data['samples'][:3]
                })

        # Extension-based suggestions
        for ext, count in results['extension_patterns']['counts'].items():
            if ext == 'no_extension':
                continue

            coverage = (count / total) * 100
            if coverage >= 0.5:
                suggestions.append({
                    'type': 'extension',
                    'pattern': ext,
                    'count': count,
                    'coverage_pct': coverage,
                    'suggested_type': self._suggest_doc_type_for_extension(ext),
                    'confidence': 0.75,
                    'samples': results['extension_patterns']['samples'].get(ext, [])[:3]
                })

        # Sort by coverage
        suggestions.sort(key=lambda x: x['coverage_pct'], reverse=True)

        return suggestions

    def _suggest_doc_type_for_directory(self, dir_type):
        """Suggest document type based on directory"""
        mapping = {
            'node_modules': 'dependency_nodejs',
            '__pycache__': 'cache_python',
            '.git': 'git_internal',
            'venv/site-packages': 'dependency_python',
            'build/dist': 'build_artifact',
            'cache/temp': 'cache_temporary',
            'IDE metadata': 'ide_metadata'
        }
        return mapping.get(dir_type, 'unknown')

    def _suggest_doc_type_for_filename(self, pattern_type):
        """Suggest document type based on filename pattern"""
        mapping = {
            'uuid': 'temporary_generated',
            'hex_hash_40': 'git_object',
            'hex_hash_32': 'cache_hash',
            'hex_hash_16': 'cache_package_manager',
            'numbered': 'cache_temporary',
            'timestamp': 'temporary_generated',
            'versioned': 'cache_versioned',
            'no_extension': 'binary_unknown'
        }
        return mapping.get(pattern_type, 'unknown')

    def _suggest_doc_type_for_extension(self, ext):
        """Suggest document type based on extension"""
        # Just a few examples - extend as needed
        mapping = {
            '.tmp': 'temporary_file',
            '.bak': 'backup_file',
            '.swp': 'editor_swap',
            '.lock': 'lockfile'
        }
        return mapping.get(ext, f'file_{ext.replace(".", "")}')

    def print_report(self, results, suggestions):
        """Print comprehensive analysis report"""
        print("\n" + "=" * 80)
        print("PATTERN ANALYSIS RESULTS")
        print("=" * 80)

        # Directory patterns
        print("\nDIRECTORY PATTERNS:")
        print("-" * 80)
        for dir_type, count in results['directory_patterns']['counts'].items():
            pct = (count / results['total']) * 100
            print(f"  {dir_type:30} {count:6,} files ({pct:5.1f}%)")

        # Filename patterns
        print("\nFILENAME PATTERNS:")
        print("-" * 80)
        for pattern, data in sorted(results['filename_patterns'].items(),
                                    key=lambda x: x[1]['count'], reverse=True):
            count = data['count']
            pct = (count / results['total']) * 100
            print(f"  {pattern:30} {count:6,} files ({pct:5.1f}%)")

        # Top extensions
        print("\nTOP FILE EXTENSIONS:")
        print("-" * 80)
        for ext, count in list(results['extension_patterns']['counts'].items())[:15]:
            pct = (count / results['total']) * 100
            print(f"  {ext:30} {count:6,} files ({pct:5.1f}%)")

        # Size distribution
        print("\nSIZE DISTRIBUTION:")
        print("-" * 80)
        for category, data in results['size_patterns'].items():
            count = data['count']
            pct = (count / results['total']) * 100
            print(f"  {category:30} {count:6,} files ({pct:5.1f}%)")

        # Classification suggestions
        print("\n" + "=" * 80)
        print("CLASSIFICATION SUGGESTIONS (Top 10)")
        print("=" * 80)

        total_coverage = 0
        for i, suggestion in enumerate(suggestions[:10], 1):
            print(f"\n{i}. {suggestion['type'].upper()}: {suggestion['pattern']}")
            print(f"   Count: {suggestion['count']:,} files ({suggestion['coverage_pct']:.1f}%)")
            print(f"   Suggested type: {suggestion['suggested_type']}")
            print(f"   Confidence: {suggestion['confidence']:.0%}")
            print(f"   Samples: {', '.join(suggestion['samples'][:3])}")
            total_coverage += suggestion['coverage_pct']

        print("\n" + "=" * 80)
        print(f"Top 10 suggestions cover: {total_coverage:.1f}% of unknown files")
        print(f"Implementing these would reduce unknown from 7.39% to ~{7.39 * (1 - total_coverage/100):.2f}%")
        print("=" * 80)

    def save_report(self, results, suggestions):
        """Save analysis to JSON"""
        report = {
            'total_unknown': results['total'],
            'analysis_results': results,
            'suggestions': suggestions
        }

        filename = f"unknown_pattern_analysis_{__import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"\n[REPORT] Saved: {filename}")
        return filename

    def close(self):
        """Close database connection"""
        self.conn.close()


def main():
    print("=" * 80)
    print("AUTOMATIC PATTERN DETECTION")
    print("=" * 80)

    analyzer = UnknownPatternAnalyzer()

    try:
        # Run analysis
        results, suggestions = analyzer.analyze_all_patterns()

        # Print report
        analyzer.print_report(results, suggestions)

        # Save to file
        analyzer.save_report(results, suggestions)

        print("\n" + "=" * 80)
        print("NEXT STEPS")
        print("=" * 80)
        print("1. Review suggestions above")
        print("2. Run: python apply_pattern_classifications.py")
        print("3. Expected unknown rate: <5%")
        print("=" * 80)

    finally:
        analyzer.close()


if __name__ == '__main__':
    main()
