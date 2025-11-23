# Multi-Directory & Cross-Directory Analysis Feature Plan

**Version**: 1.0
**Date**: 2025-11-20
**Status**: Proposal

---

## Executive Summary

This proposal extends IFMOS to support comprehensive multi-directory scanning with cross-directory comparison and analysis capabilities. While the current system can scan multiple roots, it lacks the ability to track which root each file belongs to and perform comparative analysis across directories.

### Key Capabilities to Add:
1. **Source Root Tracking** - Know which directory each file came from
2. **Cross-Directory Duplicate Detection** - Find duplicates across different backup sets
3. **Directory Comparison Analysis** - Compare backup sets to identify unique/shared files
4. **Comparative Reporting** - Visual comparisons and Venn diagram analytics
5. **Intelligent Merge Planning** - Recommend optimal file consolidation strategies

---

## Use Cases

### UC1: Compare Multiple Backup Sets
**Scenario**: User has 3 OneDrive backups from different dates
```bash
ifmos scan --roots "D:\Backup-2024-01" --roots "D:\Backup-2024-06" --roots "D:\Backup-2024-11"
ifmos compare-dirs --session <id>
```

**Expected Output**:
- Files unique to each backup
- Files present in all backups (with version comparison)
- Files that appeared/disappeared between backups
- Size evolution over time

### UC2: Merge Multiple Photo Libraries
**Scenario**: User has photos scattered across external drives, phone backups, and cloud downloads

```bash
ifmos scan --roots "E:\iPhone-Backup" --roots "F:\Camera-SD-Card" --roots "C:\Downloads\GooglePhotos"
ifmos analyze --session <id> --cross-directory
ifmos report --session <id> --format html --comparison-view
```

**Expected Output**:
- Exact duplicates across all sources (keep best quality)
- Near-duplicates (edited versions, different formats)
- Unique photos from each source
- Recommended canonical locations

### UC3: Audit Document Sync Issues
**Scenario**: Check if OneDrive, Dropbox, and local copies are in sync

```bash
ifmos scan --roots "C:\OneDrive" --roots "C:\Dropbox" --roots "D:\LocalDocs"
ifmos audit-sync --session <id>
```

**Expected Output**:
- Files out of sync (different modification dates)
- Missing files in each directory
- Conflicted copies
- Synchronization health score

---

## Current Limitations

### Architecture Analysis

**Current Behavior** (scanner.py:60-88):
```python
def scan_roots(self, root_paths: List[str]) -> str:
    self.session_id = self.db.create_session(root_paths, self.config)

    # Scans each root sequentially
    for root in root_paths:
        self._scan_directory_tree(root_path)  # ❌ No tracking of which root
```

**Database Schema** (database.py:30-57):
```sql
CREATE TABLE files (
    file_id TEXT PRIMARY KEY,
    path TEXT NOT NULL,
    -- ... other fields ...
    scan_session_id TEXT NOT NULL  -- ✅ Has session
    -- ❌ MISSING: source_root_id field
)

CREATE TABLE scan_sessions (
    session_id TEXT PRIMARY KEY,
    root_paths TEXT  -- ✅ JSON array of all roots
    -- ❌ MISSING: Individual root metadata
)
```

**Limitations**:
1. ❌ Cannot identify which root a file belongs to
2. ❌ Cannot compare files across specific directories
3. ❌ Cannot generate per-directory statistics
4. ❌ Cannot track directory-specific duplicates
5. ❌ Cannot prioritize files by source directory quality

---

## Proposed Solution

### Phase 1: Database Schema Enhancements

#### 1.1 New Table: `scan_roots`
Track individual roots within a session:

```sql
CREATE TABLE scan_roots (
    root_id TEXT PRIMARY KEY,           -- UUID for this root
    session_id TEXT NOT NULL,           -- Parent session
    root_path TEXT NOT NULL,            -- Absolute path
    root_label TEXT,                    -- User-friendly name (e.g., "Backup-2024-11")
    root_priority INTEGER DEFAULT 50,   -- For canonical selection (0-100)
    root_type TEXT,                     -- 'backup', 'primary', 'archive', 'cloud'
    scan_order INTEGER,                 -- Order scanned within session
    files_found INTEGER,                -- Stats per root
    total_size INTEGER,
    scan_started DATETIME,
    scan_completed DATETIME,
    FOREIGN KEY (session_id) REFERENCES scan_sessions(session_id)
);

CREATE INDEX idx_root_session ON scan_roots(session_id);
CREATE INDEX idx_root_path ON scan_roots(root_path);
```

#### 1.2 Modify Table: `files`
Add source root tracking:

```sql
ALTER TABLE files ADD COLUMN source_root_id TEXT;
ALTER TABLE files ADD COLUMN relative_path TEXT;  -- Path relative to root

CREATE INDEX idx_file_root ON files(source_root_id);
CREATE INDEX idx_relative_path ON files(relative_path);

-- Add foreign key (SQLite requires table recreation for FK)
-- FOREIGN KEY (source_root_id) REFERENCES scan_roots(root_id)
```

**Benefits**:
- `source_root_id`: Know which directory the file came from
- `relative_path`: Enable cross-directory path matching (e.g., `Photos/2024/IMG_001.jpg` in multiple backups)

#### 1.3 New Table: `cross_directory_duplicates`
Track duplicates that span multiple roots:

```sql
CREATE TABLE cross_directory_duplicates (
    xdup_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    file_hash TEXT NOT NULL,           -- Quick or full hash
    occurrence_count INTEGER,           -- How many roots have this file
    total_copies INTEGER,               -- Total copies across all roots
    roots_affected TEXT,                -- JSON array of root_ids
    relative_paths TEXT,                -- JSON array of relative paths
    recommended_canonical TEXT,         -- file_id of best version
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES scan_sessions(session_id)
);

CREATE INDEX idx_xdup_session ON cross_directory_duplicates(session_id);
CREATE INDEX idx_xdup_hash ON cross_directory_duplicates(file_hash);
```

#### 1.4 New Table: `directory_comparisons`
Store comparison analysis results:

```sql
CREATE TABLE directory_comparisons (
    comparison_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    root_a TEXT NOT NULL,              -- First root_id
    root_b TEXT NOT NULL,              -- Second root_id
    files_in_both INTEGER,             -- Intersection
    files_only_a INTEGER,              -- A - B
    files_only_b INTEGER,              -- B - A
    files_different INTEGER,           -- Same path, different content
    sync_score REAL,                   -- 0-100 similarity score
    analysis_data TEXT,                -- JSON with detailed breakdown
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES scan_sessions(session_id),
    FOREIGN KEY (root_a) REFERENCES scan_roots(root_id),
    FOREIGN KEY (root_b) REFERENCES scan_roots(root_id)
);

CREATE INDEX idx_comp_session ON directory_comparisons(session_id);
```

---

### Phase 2: Scanner Enhancements

#### 2.1 Root Registration and Metadata Collection

**New CLI Options**:
```bash
ifmos scan \
    --roots "D:\Backup-A" --root-label "Backup-2024-01" --root-priority 30 \
    --roots "D:\Backup-B" --root-label "Backup-2024-11" --root-priority 70 \
    --roots "C:\Primary"  --root-label "Primary-Live" --root-priority 100
```

**Scanner Changes** (scanner.py):

```python
class FileScanner:
    def __init__(self, database: Database, config: Dict):
        # ... existing code ...
        self.root_metadata = {}  # root_path -> root_id mapping
        self.current_root_id = None  # Track current root being scanned

    def scan_roots(self, root_configs: List[Dict]) -> str:
        """
        Scan multiple roots with metadata.

        Args:
            root_configs: List of dicts with:
                - path: str
                - label: str (optional)
                - priority: int (optional, 0-100)
                - type: str (optional)
        """
        logger.info(f"Starting multi-directory scan: {len(root_configs)} roots")

        # Create session
        root_paths = [rc['path'] for rc in root_configs]
        self.session_id = self.db.create_session(root_paths, self.config)

        # Register each root
        for i, root_config in enumerate(root_configs):
            root_id = self.db.register_scan_root(
                session_id=self.session_id,
                root_path=root_config['path'],
                root_label=root_config.get('label', f"Root-{i+1}"),
                root_priority=root_config.get('priority', 50),
                root_type=root_config.get('type', 'unknown'),
                scan_order=i
            )
            self.root_metadata[root_config['path']] = root_id
            logger.info(f"  [{i+1}] {root_config['path']} (priority: {root_config.get('priority', 50)})")

        # Scan each root
        for root_config in root_configs:
            root_path = Path(root_config['path'])
            if not root_path.exists():
                logger.warning(f"Root path does not exist: {root_path}")
                continue

            # Set current root context
            self.current_root_id = self.root_metadata[str(root_path)]

            logger.info(f"Scanning: {root_path} (root_id: {self.current_root_id[:8]}...)")
            scan_start = time.time()

            self._scan_directory_tree(root_path, root_path)  # Pass root for relative path

            # Update root stats
            elapsed = time.time() - scan_start
            self.db.update_scan_root(
                self.current_root_id,
                scan_completed=datetime.now(),
                files_found=self._count_files_for_root(self.current_root_id)
            )
            logger.info(f"  Completed in {elapsed:.1f}s")

        # ... rest of existing completion logic ...

        return self.session_id

    def _scan_directory_tree(self, current_path: Path, root_path: Path):
        """
        Enhanced to track root and relative paths.

        Args:
            current_path: Current directory being scanned
            root_path: Original root path (for relative path calculation)
        """
        # ... existing scanning logic ...

        # When indexing files, now pass root context
        for filename in filenames:
            filepath = current_path / filename
            relative_path = str(filepath.relative_to(root_path))

            file_record = {
                # ... existing fields ...
                'source_root_id': self.current_root_id,  # NEW
                'relative_path': relative_path,          # NEW
                # ...
            }
            self.db.insert_file(file_record)
```

---

### Phase 3: Analyzer Cross-Directory Features

#### 3.1 New Analyzer Methods

**Additions to analyzer.py**:

```python
class Analyzer:
    def analyze_cross_directory(self, session_id: str) -> Dict:
        """
        Perform cross-directory duplicate detection and comparison.

        Returns comprehensive analysis of multi-directory session.
        """
        logger.info("=== Cross-Directory Analysis ===")

        # Stage 1: Identify files present in multiple roots
        cross_dir_duplicates = self._detect_cross_directory_duplicates(session_id)
        logger.info(f"  Found {len(cross_dir_duplicates)} files in multiple directories")

        # Stage 2: Find same relative paths with different content
        path_conflicts = self._detect_path_conflicts(session_id)
        logger.info(f"  Found {len(path_conflicts)} path conflicts")

        # Stage 3: Pairwise directory comparisons
        comparison_matrix = self._compare_all_directory_pairs(session_id)
        logger.info(f"  Generated {len(comparison_matrix)} pairwise comparisons")

        # Stage 4: Recommend canonical versions based on root priority
        canonical_recommendations = self._recommend_canonicals_by_root(session_id)

        return {
            'cross_directory_duplicates': cross_dir_duplicates,
            'path_conflicts': path_conflicts,
            'directory_comparisons': comparison_matrix,
            'canonical_recommendations': canonical_recommendations
        }

    def _detect_cross_directory_duplicates(self, session_id: str) -> List[Dict]:
        """
        Find files with same hash in multiple root directories.
        """
        cursor = self.db.conn.cursor()

        # Group files by hash across different roots
        cursor.execute("""
            SELECT
                hash_quick,
                COUNT(DISTINCT source_root_id) as root_count,
                COUNT(*) as total_copies,
                GROUP_CONCAT(DISTINCT source_root_id) as roots,
                GROUP_CONCAT(relative_path) as paths,
                MIN(size_bytes) as size
            FROM files
            WHERE scan_session_id = ?
              AND hash_quick IS NOT NULL
            GROUP BY hash_quick
            HAVING root_count > 1  -- Only files in multiple roots
            ORDER BY total_copies DESC, size DESC
        """, (session_id,))

        results = []
        for row in cursor.fetchall():
            # Get actual file records
            cursor.execute("""
                SELECT file_id, source_root_id, path, relative_path,
                       modified_at, size_bytes
                FROM files
                WHERE scan_session_id = ? AND hash_quick = ?
                ORDER BY modified_at DESC
            """, (session_id, row['hash_quick']))

            files = [dict(r) for r in cursor.fetchall()]

            # Determine best canonical based on root priority
            canonical = self._select_canonical_by_root_priority(files)

            xdup_id = str(uuid.uuid4())

            # Store in database
            self.db.conn.execute("""
                INSERT INTO cross_directory_duplicates
                (xdup_id, session_id, file_hash, occurrence_count, total_copies,
                 roots_affected, relative_paths, recommended_canonical)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                xdup_id,
                session_id,
                row['hash_quick'],
                row['root_count'],
                row['total_copies'],
                json.dumps(row['roots'].split(',')),
                json.dumps(row['paths'].split(',')),
                canonical['file_id']
            ))

            results.append({
                'xdup_id': xdup_id,
                'hash': row['hash_quick'],
                'root_count': row['root_count'],
                'total_copies': row['total_copies'],
                'size_bytes': row['size'],
                'files': files,
                'canonical': canonical
            })

        self.db.conn.commit()
        return results

    def _detect_path_conflicts(self, session_id: str) -> List[Dict]:
        """
        Find files with same relative path but different content across roots.

        Example:
          Root A: Photos/vacation.jpg (hash: abc123)
          Root B: Photos/vacation.jpg (hash: def456)  <- CONFLICT
        """
        cursor = self.db.conn.cursor()

        cursor.execute("""
            SELECT
                relative_path,
                COUNT(DISTINCT hash_quick) as hash_count,
                COUNT(DISTINCT source_root_id) as root_count
            FROM files
            WHERE scan_session_id = ?
              AND relative_path IS NOT NULL
            GROUP BY relative_path
            HAVING hash_count > 1 AND root_count > 1
        """, (session_id,))

        conflicts = []
        for row in cursor.fetchall():
            # Get all versions of this path
            cursor.execute("""
                SELECT file_id, source_root_id, path, hash_quick,
                       modified_at, size_bytes
                FROM files
                WHERE scan_session_id = ? AND relative_path = ?
                ORDER BY modified_at DESC
            """, (session_id, row['relative_path']))

            versions = [dict(r) for r in cursor.fetchall()]

            conflicts.append({
                'relative_path': row['relative_path'],
                'version_count': row['hash_count'],
                'root_count': row['root_count'],
                'versions': versions,
                'conflict_type': 'content_mismatch',
                'recommended_action': 'manual_review'
            })

        return conflicts

    def _compare_all_directory_pairs(self, session_id: str) -> List[Dict]:
        """
        Pairwise comparison of all roots in session.
        Generates comparison matrix (A vs B, A vs C, B vs C, etc.)
        """
        # Get all roots for this session
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT root_id, root_path, root_label
            FROM scan_roots
            WHERE session_id = ?
            ORDER BY scan_order
        """, (session_id,))

        roots = [dict(row) for row in cursor.fetchall()]
        comparisons = []

        # Compare each pair
        for i, root_a in enumerate(roots):
            for root_b in roots[i+1:]:
                comparison = self._compare_two_directories(
                    session_id, root_a, root_b
                )
                comparisons.append(comparison)

        return comparisons

    def _compare_two_directories(self, session_id: str,
                                 root_a: Dict, root_b: Dict) -> Dict:
        """
        Compare two specific directories.

        Returns:
            - Files in both (by relative path)
            - Files only in A
            - Files only in B
            - Files with same path but different content
            - Sync score (0-100)
        """
        cursor = self.db.conn.cursor()

        # Get all relative paths from each root
        cursor.execute("""
            SELECT DISTINCT relative_path, hash_quick, size_bytes, modified_at
            FROM files
            WHERE scan_session_id = ? AND source_root_id = ?
        """, (session_id, root_a['root_id']))
        files_a = {row['relative_path']: dict(row) for row in cursor.fetchall()}

        cursor.execute("""
            SELECT DISTINCT relative_path, hash_quick, size_bytes, modified_at
            FROM files
            WHERE scan_session_id = ? AND source_root_id = ?
        """, (session_id, root_b['root_id']))
        files_b = {row['relative_path']: dict(row) for row in cursor.fetchall()}

        # Calculate set operations
        paths_a = set(files_a.keys())
        paths_b = set(files_b.keys())

        in_both = paths_a & paths_b
        only_a = paths_a - paths_b
        only_b = paths_b - paths_a

        # Check for content differences in shared paths
        different_content = []
        identical_content = []
        for path in in_both:
            if files_a[path]['hash_quick'] != files_b[path]['hash_quick']:
                different_content.append({
                    'relative_path': path,
                    'root_a_hash': files_a[path]['hash_quick'],
                    'root_b_hash': files_b[path]['hash_quick'],
                    'root_a_modified': files_a[path]['modified_at'],
                    'root_b_modified': files_b[path]['modified_at']
                })
            else:
                identical_content.append(path)

        # Calculate sync score
        total_unique_files = len(paths_a | paths_b)
        sync_score = (len(identical_content) / total_unique_files * 100) if total_unique_files > 0 else 100

        # Store comparison
        comparison_id = str(uuid.uuid4())
        analysis_data = {
            'files_in_both': list(in_both),
            'files_only_a': list(only_a),
            'files_only_b': list(only_b),
            'identical_content': identical_content,
            'different_content': different_content
        }

        self.db.conn.execute("""
            INSERT INTO directory_comparisons
            (comparison_id, session_id, root_a, root_b,
             files_in_both, files_only_a, files_only_b, files_different,
             sync_score, analysis_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            comparison_id,
            session_id,
            root_a['root_id'],
            root_b['root_id'],
            len(identical_content),
            len(only_a),
            len(only_b),
            len(different_content),
            sync_score,
            json.dumps(analysis_data)
        ))
        self.db.conn.commit()

        return {
            'comparison_id': comparison_id,
            'root_a': root_a['root_label'],
            'root_b': root_b['root_label'],
            'files_in_both': len(in_both),
            'identical_files': len(identical_content),
            'files_only_a': len(only_a),
            'files_only_b': len(only_b),
            'files_different': len(different_content),
            'sync_score': round(sync_score, 2),
            'analysis_data': analysis_data
        }

    def _select_canonical_by_root_priority(self, files: List[Dict]) -> Dict:
        """
        Choose canonical file based on root priority and other factors.

        Priority order:
        1. Root priority (higher is better)
        2. Newest modification date
        3. Longest filename (more descriptive)
        """
        # Get root priorities
        root_priorities = {}
        for file in files:
            if file['source_root_id'] not in root_priorities:
                cursor = self.db.conn.cursor()
                cursor.execute("""
                    SELECT root_priority FROM scan_roots
                    WHERE root_id = ?
                """, (file['source_root_id'],))
                row = cursor.fetchone()
                root_priorities[file['source_root_id']] = row['root_priority'] if row else 50

        def score_file(f):
            priority = root_priorities.get(f['source_root_id'], 50)
            mod_time = datetime.fromisoformat(f['modified_at']).timestamp()
            name_length = len(Path(f['path']).stem)

            return (
                priority,           # Primary: root priority
                mod_time,           # Secondary: newest
                name_length         # Tertiary: most descriptive
            )

        return max(files, key=score_file)
```

---

### Phase 4: Reporter Enhancements

#### 4.1 Comparative Visualizations

**New Report Sections**:

1. **Directory Comparison Matrix**
   - Heatmap showing sync scores between all directory pairs
   - Venn diagrams for 2-3 directory comparisons
   - Timeline showing file changes across backups

2. **Cross-Directory Duplicate Dashboard**
   - Files present in all roots
   - Files present in some roots
   - Space savings per root if duplicates removed

3. **Per-Root Statistics**
   - Individual directory breakdowns
   - Side-by-side comparison table

**HTML Template Addition** (reporter.py):

```python
def _generate_html_comparison_view(self, session_id: str) -> str:
    """Generate comparative HTML view for multi-directory scans."""

    # Get all roots
    cursor = self.db.conn.cursor()
    cursor.execute("""
        SELECT * FROM scan_roots WHERE session_id = ?
        ORDER BY scan_order
    """, (session_id,))
    roots = [dict(row) for row in cursor.fetchall()]

    if len(roots) <= 1:
        return "<p>Single directory scan - no comparison available</p>"

    # Get comparison data
    cursor.execute("""
        SELECT * FROM directory_comparisons
        WHERE session_id = ?
    """, (session_id,))
    comparisons = [dict(row) for row in cursor.fetchall()]

    # Get cross-directory duplicates
    cursor.execute("""
        SELECT * FROM cross_directory_duplicates
        WHERE session_id = ?
        ORDER BY total_copies DESC, occurrence_count DESC
        LIMIT 100
    """, (session_id,))
    xdups = [dict(row) for row in cursor.fetchall()]

    html = f"""
    <section id="comparison-view">
        <h2>📊 Multi-Directory Comparison</h2>

        <div class="comparison-summary">
            <h3>Scanned Directories</h3>
            <table class="styled-table">
                <thead>
                    <tr>
                        <th>Label</th>
                        <th>Path</th>
                        <th>Priority</th>
                        <th>Files</th>
                        <th>Size</th>
                    </tr>
                </thead>
                <tbody>
    """

    for root in roots:
        size_gb = (root.get('total_size', 0) or 0) / 1e9
        html += f"""
                    <tr>
                        <td><strong>{root['root_label']}</strong></td>
                        <td><code>{root['root_path']}</code></td>
                        <td>{root['root_priority']}</td>
                        <td>{root.get('files_found', 0):,}</td>
                        <td>{size_gb:.2f} GB</td>
                    </tr>
        """

    html += """
                </tbody>
            </table>
        </div>

        <div class="comparison-matrix">
            <h3>Pairwise Comparison Matrix</h3>
            <table class="styled-table">
                <thead>
                    <tr>
                        <th>Directory A</th>
                        <th>Directory B</th>
                        <th>Sync Score</th>
                        <th>In Both</th>
                        <th>Only in A</th>
                        <th>Only in B</th>
                        <th>Different</th>
                    </tr>
                </thead>
                <tbody>
    """

    for comp in comparisons:
        # Get root labels
        root_a = next(r for r in roots if r['root_id'] == comp['root_a'])
        root_b = next(r for r in roots if r['root_id'] == comp['root_b'])

        score = comp['sync_score']
        score_class = 'high' if score > 80 else ('medium' if score > 50 else 'low')

        html += f"""
                    <tr>
                        <td>{root_a['root_label']}</td>
                        <td>{root_b['root_label']}</td>
                        <td class="sync-{score_class}">{score:.1f}%</td>
                        <td>{comp['files_in_both']:,}</td>
                        <td>{comp['files_only_a']:,}</td>
                        <td>{comp['files_only_b']:,}</td>
                        <td>{comp['files_different']:,}</td>
                    </tr>
        """

    html += """
                </tbody>
            </table>
        </div>

        <div class="cross-directory-duplicates">
            <h3>Cross-Directory Duplicates</h3>
            <p>Files found in multiple directories (top 100 by copies)</p>
            <table class="styled-table">
                <thead>
                    <tr>
                        <th>File Hash</th>
                        <th>Directories</th>
                        <th>Total Copies</th>
                        <th>Wasted Space</th>
                    </tr>
                </thead>
                <tbody>
    """

    for xdup in xdups:
        roots_affected = json.loads(xdup['roots_affected'])
        wasted_space = (xdup['total_copies'] - 1) * (
            # Estimate size from first file
            cursor.execute("""
                SELECT size_bytes FROM files
                WHERE hash_quick = ? LIMIT 1
            """, (xdup['file_hash'],)).fetchone()['size_bytes']
        )

        html += f"""
                    <tr>
                        <td><code>{xdup['file_hash'][:16]}...</code></td>
                        <td>{len(roots_affected)} directories</td>
                        <td>{xdup['total_copies']:,} copies</td>
                        <td>{wasted_space / 1e6:.2f} MB</td>
                    </tr>
        """

    html += """
                </tbody>
            </table>
        </div>

        <div class="venn-diagram">
            <h3>File Distribution Visualization</h3>
            <canvas id="vennChart" width="800" height="400"></canvas>
        </div>

    </section>

    <style>
        .sync-high { background-color: #28a745; color: white; font-weight: bold; }
        .sync-medium { background-color: #ffc107; color: black; font-weight: bold; }
        .sync-low { background-color: #dc3545; color: white; font-weight: bold; }
    </style>

    <script>
        // Venn diagram visualization using Chart.js
        // (Implementation would use Chart.js bubble chart to approximate Venn)
        const vennCtx = document.getElementById('vennChart').getContext('2d');
        // ... Chart.js configuration ...
    </script>
    """

    return html
```

---

### Phase 5: CLI Enhancements

#### 5.1 Enhanced `scan` Command

```python
@cli.command()
@click.option('--roots', '-r', 'root_paths', multiple=True, required=True,
              help='Root directories to scan')
@click.option('--root-labels', multiple=True,
              help='Human-readable labels for roots (same order as --roots)')
@click.option('--root-priorities', multiple=True, type=int,
              help='Priority values 0-100 for canonical selection (same order)')
@click.option('--root-types', multiple=True,
              help='Type labels: backup, primary, archive, cloud (same order)')
@click.option('--db', default='db/ifmos.db', help='Database path')
def scan(ctx, root_paths, root_labels, root_priorities, root_types, db):
    """Scan one or more root directories."""

    # Build root configs
    root_configs = []
    for i, path in enumerate(root_paths):
        config = {'path': path}

        if root_labels and i < len(root_labels):
            config['label'] = root_labels[i]
        else:
            config['label'] = f"Root-{i+1}"

        if root_priorities and i < len(root_priorities):
            config['priority'] = root_priorities[i]
        else:
            config['priority'] = 50

        if root_types and i < len(root_types):
            config['type'] = root_types[i]

        root_configs.append(config)

    # Display scan plan
    click.echo("\n[INFO] Multi-Directory Scan Plan:")
    for i, rc in enumerate(root_configs):
        click.echo(f"  [{i+1}] {rc['label']}: {rc['path']}")
        click.echo(f"      Priority: {rc['priority']} | Type: {rc.get('type', 'unknown')}")
    click.echo()

    # Execute scan
    database = Database(db)
    scanner = FileScanner(database, ctx.obj.get('config', {}))

    session_id = scanner.scan_roots(root_configs)

    click.echo(f"\n[SUCCESS] Scan completed: {session_id}")
    click.echo(f"\n[NEXT] Run cross-directory analysis:")
    click.echo(f"  ifmos compare-dirs --session {session_id}")
```

#### 5.2 New `compare-dirs` Command

```python
@cli.command('compare-dirs')
@click.option('--session', required=True, help='Session ID to analyze')
@click.option('--db', default='db/ifmos.db', help='Database path')
def compare_dirs(ctx, session, db):
    """Perform cross-directory comparison and analysis."""

    click.echo(f"[INFO] Analyzing multi-directory session: {session}")

    database = Database(db)

    # Check if session has multiple roots
    cursor = database.conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) as root_count FROM scan_roots
        WHERE session_id = ?
    """, (session,))
    root_count = cursor.fetchone()['root_count']

    if root_count < 2:
        click.echo("[ERROR] Session has only one root directory. Comparison requires 2+ roots.")
        raise click.Abort()

    click.echo(f"  Found {root_count} directories to compare")

    # Load analysis rules
    with open('ifmos/config/analysis_rules.yml') as f:
        rules = yaml.safe_load(f)

    analyzer = Analyzer(database, rules)

    # Run cross-directory analysis
    results = analyzer.analyze_cross_directory(session)

    # Display summary
    click.echo("\n[RESULTS] Cross-Directory Analysis:")
    click.echo(f"  Cross-directory duplicates: {len(results['cross_directory_duplicates']):,}")
    click.echo(f"  Path conflicts: {len(results['path_conflicts']):,}")
    click.echo(f"  Directory comparisons: {len(results['directory_comparisons'])}")

    # Show top duplicates
    click.echo("\n[TOP DUPLICATES] Files in Multiple Directories:")
    for i, xdup in enumerate(results['cross_directory_duplicates'][:10], 1):
        size_mb = xdup['size_bytes'] / 1e6
        wasted = (xdup['total_copies'] - 1) * size_mb
        click.echo(f"  {i}. {xdup['root_count']} dirs × {xdup['total_copies']} copies = {wasted:.1f} MB wasted")

    # Show comparison matrix
    click.echo("\n[COMPARISON MATRIX]:")
    for comp in results['directory_comparisons']:
        click.echo(f"  {comp['root_a']} ↔ {comp['root_b']}: "
                  f"Sync score {comp['sync_score']:.1f}% "
                  f"({comp['identical_files']:,} identical, "
                  f"{comp['files_different']:,} conflicts)")

    click.echo(f"\n[NEXT] Generate comparison report:")
    click.echo(f"  ifmos report --session {session} --format html --comparison-view")
```

#### 5.3 New `audit-sync` Command

```python
@cli.command('audit-sync')
@click.option('--session', required=True, help='Session ID to audit')
@click.option('--threshold', type=float, default=95.0,
              help='Sync score threshold for warnings (default: 95%)')
@click.option('--db', default='db/ifmos.db', help='Database path')
def audit_sync(ctx, session, threshold, db):
    """
    Audit synchronization health across multiple directories.
    Reports missing files, conflicts, and out-of-date copies.
    """

    click.echo(f"[INFO] Auditing sync health for session: {session}")
    click.echo(f"  Warning threshold: {threshold:.1f}%")

    database = Database(db)
    cursor = database.conn.cursor()

    # Get comparisons
    cursor.execute("""
        SELECT * FROM directory_comparisons
        WHERE session_id = ?
        ORDER BY sync_score ASC
    """, (session,))
    comparisons = [dict(row) for row in cursor.fetchall()]

    # Identify issues
    issues = []
    for comp in comparisons:
        if comp['sync_score'] < threshold:
            analysis = json.loads(comp['analysis_data'])
            issues.append({
                'comparison': comp,
                'severity': 'critical' if comp['sync_score'] < 50 else 'warning',
                'missing_files': len(analysis['files_only_a']) + len(analysis['files_only_b']),
                'conflicts': len(analysis['different_content'])
            })

    # Report
    if not issues:
        click.echo("\n✅ [PASS] All directories in sync (above threshold)")
    else:
        click.echo(f"\n⚠️  [WARNING] Found {len(issues)} sync issues:")
        for i, issue in enumerate(issues, 1):
            comp = issue['comparison']
            click.echo(f"\n  {i}. {comp['root_a']} ↔ {comp['root_b']}")
            click.echo(f"     Sync score: {comp['sync_score']:.1f}% ({'🔴 CRITICAL' if issue['severity'] == 'critical' else '🟡 WARNING'})")
            click.echo(f"     Missing files: {issue['missing_files']:,}")
            click.echo(f"     Conflicts: {issue['conflicts']:,}")

    click.echo(f"\n[NEXT] Review detailed report:")
    click.echo(f"  ifmos report --session {session} --format html --comparison-view")
```

---

### Phase 6: Migration Enhancements

#### 6.1 Smart Merge Planning

**New Feature**: Merge multiple directories into optimized structure

```python
@cli.command('plan-merge')
@click.option('--session', required=True, help='Multi-directory session ID')
@click.option('--target-root', required=True, help='Root to keep as primary/canonical')
@click.option('--merge-strategy',
              type=click.Choice(['keep-newest', 'keep-highest-priority', 'manual']),
              default='keep-highest-priority',
              help='Conflict resolution strategy')
@click.option('--db', default='db/ifmos.db', help='Database path')
def plan_merge(ctx, session, target_root, merge_strategy, db):
    """
    Create migration plan to merge multiple directories into one.
    Handles duplicates and conflicts intelligently.
    """

    click.echo(f"[INFO] Planning merge for session: {session}")
    click.echo(f"  Target root: {target_root}")
    click.echo(f"  Strategy: {merge_strategy}")

    database = Database(db)

    # Verify target root exists in session
    cursor = database.conn.cursor()
    cursor.execute("""
        SELECT root_id FROM scan_roots
        WHERE session_id = ? AND (root_path = ? OR root_label = ?)
    """, (session, target_root, target_root))
    target_root_record = cursor.fetchone()

    if not target_root_record:
        click.echo(f"[ERROR] Target root '{target_root}' not found in session")
        raise click.Abort()

    target_root_id = target_root_record['root_id']

    # Get all non-target roots
    cursor.execute("""
        SELECT * FROM scan_roots
        WHERE session_id = ? AND root_id != ?
    """, (session, target_root_id))
    source_roots = [dict(row) for row in cursor.fetchall()]

    click.echo(f"\n  Merging {len(source_roots)} directories into target:")
    for src in source_roots:
        click.echo(f"    - {src['root_label']}: {src['files_found']:,} files")

    # Create merge plan
    planner = MigrationPlanner(database)
    plan_id = planner.create_merge_plan(
        session_id=session,
        target_root_id=target_root_id,
        source_root_ids=[r['root_id'] for r in source_roots],
        strategy=merge_strategy
    )

    click.echo(f"\n[SUCCESS] Merge plan created: {plan_id}")
    click.echo(f"\n[NEXT] Review and execute:")
    click.echo(f"  ifmos dry-run --plan {plan_id}")
    click.echo(f"  ifmos execute --plan {plan_id}")
```

---

## Implementation Roadmap

### Phase 1: Foundation (Week 1-2)
- [ ] Database schema migrations
  - [ ] Create `scan_roots` table
  - [ ] Add `source_root_id` to `files` table
  - [ ] Create `cross_directory_duplicates` table
  - [ ] Create `directory_comparisons` table
- [ ] Update Database class with new methods
  - [ ] `register_scan_root()`
  - [ ] `update_scan_root()`
  - [ ] `get_roots_for_session()`

### Phase 2: Scanner Updates (Week 2-3)
- [ ] Modify `FileScanner.scan_roots()` to accept root configs
- [ ] Add root registration before scanning
- [ ] Track `current_root_id` during scan
- [ ] Calculate relative paths
- [ ] Update file records with root info
- [ ] Update CLI `scan` command with new options

### Phase 3: Cross-Directory Analysis (Week 3-4)
- [ ] Implement `Analyzer.analyze_cross_directory()`
- [ ] Implement `_detect_cross_directory_duplicates()`
- [ ] Implement `_detect_path_conflicts()`
- [ ] Implement `_compare_all_directory_pairs()`
- [ ] Implement `_compare_two_directories()`
- [ ] Implement `_select_canonical_by_root_priority()`
- [ ] Add new CLI commands: `compare-dirs`, `audit-sync`

### Phase 4: Reporting (Week 4-5)
- [ ] Add comparison view to HTML reporter
- [ ] Create directory comparison matrix visualization
- [ ] Add Venn diagram for 2-3 directory comparisons
- [ ] Add cross-directory duplicate section
- [ ] Per-root statistics breakdown
- [ ] Update CLI `report` command with `--comparison-view` flag

### Phase 5: Migration & Merge (Week 5-6)
- [ ] Implement `MigrationPlanner.create_merge_plan()`
- [ ] Add merge strategies (keep-newest, priority-based, manual)
- [ ] Handle conflict resolution
- [ ] Add CLI `plan-merge` command
- [ ] Test merge execution with rollback

### Phase 6: Testing & Documentation (Week 6-7)
- [ ] Unit tests for all new analyzer methods
- [ ] Integration tests for multi-directory workflows
- [ ] Update README with multi-directory examples
- [ ] Create migration guide for existing databases
- [ ] Performance testing with 5+ roots

---

## Example Workflows

### Workflow 1: Compare Three Backups

```bash
# Scan three backup directories with priorities
ifmos scan \
    --roots "D:\Backup-2024-01" --root-labels "Jan-Backup" --root-priorities 30 \
    --roots "D:\Backup-2024-06" --root-labels "Jun-Backup" --root-priorities 60 \
    --roots "D:\Backup-2024-11" --root-labels "Nov-Backup" --root-priorities 100

# Output: session-id: 20251120-120000-abcd

# Run cross-directory analysis
ifmos compare-dirs --session 20251120-120000-abcd

# Generate comparison report
ifmos report --session 20251120-120000-abcd --format html --comparison-view

# Audit sync health
ifmos audit-sync --session 20251120-120000-abcd --threshold 90
```

### Workflow 2: Merge Photo Libraries

```bash
# Scan multiple photo sources
ifmos scan \
    --roots "E:\iPhone-Photos" --root-labels "iPhone" --root-priorities 100 --root-types primary \
    --roots "F:\Camera-SD" --root-labels "Camera" --root-priorities 80 --root-types backup \
    --roots "C:\Downloads\GooglePhotos" --root-labels "Google" --root-priorities 50 --root-types cloud

# Compare and analyze
ifmos compare-dirs --session <session-id>
ifmos report --session <session-id> --format html --comparison-view

# Plan merge into iPhone library (highest priority)
ifmos plan-merge --session <session-id> --target-root "iPhone" --merge-strategy keep-highest-priority

# Review and execute
ifmos dry-run --plan <plan-id>
ifmos execute --plan <plan-id>
```

### Workflow 3: Cloud Sync Audit

```bash
# Scan local and cloud mirrors
ifmos scan \
    --roots "C:\OneDrive" --root-labels "OneDrive" --root-priorities 100 \
    --roots "C:\Dropbox" --root-labels "Dropbox" --root-priorities 95 \
    --roots "D:\LocalDocs" --root-labels "Local" --root-priorities 90

# Audit synchronization
ifmos audit-sync --session <session-id> --threshold 98

# Generate detailed report
ifmos report --session <session-id> --format html --comparison-view
```

---

## Technical Considerations

### Performance Impact

**Database Size**:
- New tables add ~5-10% overhead
- `scan_roots`: Small (<1000 rows typical)
- `cross_directory_duplicates`: Medium (proportional to duplicate count)
- `directory_comparisons`: Small (N×(N-1)/2 rows for N roots)

**Query Performance**:
- Cross-directory duplicate detection: O(n) with hash index
- Pairwise comparison: O(n×m) where n,m are file counts
- Relative path matching: Requires index on `relative_path`

**Memory**:
- Comparison matrix for 10 directories: ~45 comparisons
- Should batch process for sessions with >1M files

### Backward Compatibility

**Migration Strategy**:
1. Schema changes are additive (new tables, new columns with defaults)
2. Existing sessions continue to work (legacy mode)
3. New features only activate for multi-root sessions
4. Migration script to backfill `source_root_id` for old sessions (set to first root)

**Legacy Mode**:
- Sessions with only `scan_sessions.root_paths` (no `scan_roots` entries)
- Fall back to current behavior
- Warn user that comparison features unavailable

---

## Success Metrics

**Feature Adoption**:
- 50%+ of scans use multiple roots within 3 months
- Average of 2.5 roots per multi-directory scan

**Performance**:
- Cross-directory analysis completes in <30s for 100K files
- Comparison reports generate in <10s
- No more than 20% slowdown vs single-directory scan

**User Value**:
- Average 15-30% space savings when merging backups
- >90% sync score for properly synced directories
- <5% manual intervention needed for conflict resolution

---

## Open Questions

1. **Visualization Libraries**: Should we add a dedicated Venn diagram library (venn.js) or approximate with Chart.js?

2. **Conflict Resolution UI**: CLI-based manual conflict resolution sufficient, or need interactive TUI (textual, rich)?

3. **Scalability Limits**: What's the max number of roots to support? (Currently targeting 2-10)

4. **Relative Path Edge Cases**: How to handle:
   - Different drive letters on Windows?
   - Symlinks that point across roots?
   - Case sensitivity differences (Mac vs Linux)?

5. **Merge Strategy Defaults**: Should default be `keep-highest-priority` or `keep-newest`?

---

## Next Steps

1. **Review & Approve**: Stakeholder review of this proposal
2. **Database Migration Design**: Detailed SQLite migration script
3. **Prototype**: Build Phase 1 + Phase 2 (foundation + scanner) as MVP
4. **User Testing**: Test with real backup scenarios
5. **Iterate**: Refine based on feedback

---

**Document Status**: 📋 **DRAFT - Awaiting Review**

*This proposal outlines a comprehensive multi-directory feature set for IFMOS. Implementation will be phased over 6-7 weeks with continuous testing and user feedback integration.*
