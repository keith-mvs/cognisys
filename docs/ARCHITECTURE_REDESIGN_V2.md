# IFMOS Architecture Redesign - Drop-to-Canonical Pipeline

**Author**: Claude Code
**Date**: 2025-11-28
**Status**: Design Proposal

## Executive Summary

This document redesigns IFMOS to solve three critical problems:

1. **Linking chaos**: Drop directory (inbox) → target repos lack clear mapping
2. **Duplication proliferation**: `organized/`, `organized_v1/`, `organized_v2/` pattern
3. **No accuracy measurement**: Can't measure or improve classification quality

**New Design Philosophy**:
- **Single canonical tree** - ONE organized hierarchy, not multiple versions
- **Idempotent operations** - Re-running IFMOS refines in-place, doesn't duplicate
- **Explicit accuracy tracking** - Every file move logged, metrics computed, feedback loop closed

---

## Part 1: Drop Directory → Target Repo Linking

### 1.1 Current Problem

```
C:\Users\kjfle\00_Inbox\              ← Drop zone (1,355 files)
C:\Users\kjfle\Documents\Organized\   ← Target v1?
C:\Users\kjfle\Documents\Organized_V2\← Target v2?
```

**Issues**:
- No explicit link between inbox and target
- Which "Organized" folder is canonical?
- No database tracking file provenance (where it came from, when, why)

### 1.2 New Design: Manifest-Based Linking

**Core Concept**: A lightweight SQLite database tracks **every file's journey** from drop → canonical.

#### Schema: File Provenance Tracking

```sql
-- File provenance and current state
CREATE TABLE file_registry (
    file_id INTEGER PRIMARY KEY,

    -- Provenance
    original_path TEXT NOT NULL,          -- Where file entered system
    drop_timestamp TEXT NOT NULL,         -- When it arrived
    content_hash TEXT NOT NULL,           -- SHA-256 for dedup

    -- Current canonical location
    canonical_path TEXT,                  -- Current home in organized tree
    canonical_state TEXT,                 -- 'classified', 'pending', 'review'

    -- Classification
    document_type TEXT,                   -- financial_invoice, automotive_technical, etc.
    confidence REAL,                      -- ML confidence 0.0-1.0
    classification_method TEXT,           -- 'ml_model', 'keyword', 'manual'

    -- Move history
    move_count INTEGER DEFAULT 0,         -- How many times moved (stability metric)
    last_moved TEXT,                      -- Last move timestamp

    -- Flags
    requires_review BOOLEAN DEFAULT 0,    -- Flagged for manual review
    is_duplicate BOOLEAN DEFAULT 0,       -- Duplicate of another file
    duplicate_of INTEGER,                 -- FOREIGN KEY to original file_id

    FOREIGN KEY (duplicate_of) REFERENCES file_registry(file_id)
);

-- Move history log
CREATE TABLE move_history (
    move_id INTEGER PRIMARY KEY,
    file_id INTEGER NOT NULL,
    from_path TEXT NOT NULL,
    to_path TEXT NOT NULL,
    move_timestamp TEXT NOT NULL,
    reason TEXT,                          -- 'initial_classification', 'reclassification', 'manual_override'
    rule_applied TEXT,                    -- Which rule triggered this move

    FOREIGN KEY (file_id) REFERENCES file_registry(file_id)
);

-- Classification rules (version-controlled)
CREATE TABLE classification_rules (
    rule_id INTEGER PRIMARY KEY,
    rule_name TEXT NOT NULL,
    rule_version INTEGER NOT NULL,
    rule_pattern TEXT,                    -- Regex or keyword pattern
    target_document_type TEXT,
    target_path_template TEXT,            -- e.g., "Financial/{YYYY}/{MM}/{invoice_id}_{original}"
    priority INTEGER DEFAULT 100,
    active BOOLEAN DEFAULT 1,
    created_timestamp TEXT NOT NULL,

    UNIQUE(rule_name, rule_version)
);

-- Accuracy tracking
CREATE TABLE manual_corrections (
    correction_id INTEGER PRIMARY KEY,
    file_id INTEGER NOT NULL,
    wrong_type TEXT,                      -- What IFMOS said
    correct_type TEXT,                    -- What user corrected to
    correction_timestamp TEXT NOT NULL,

    FOREIGN KEY (file_id) REFERENCES file_registry(file_id)
);
```

#### Where This Lives

```
$PROJECT_ROOT/
├── .ifmos/                              ← IFMOS state directory
│   ├── file_registry.db                 ← Main provenance database
│   ├── config.yml                       ← IFMOS configuration
│   └── logs/
│       ├── moves_2025-11-28.log         ← Daily move logs
│       └── metrics_2025-11-28.json      ← Daily metrics snapshots
│
├── drop/                                ← Inbox/preprocessed zone
│   └── 00_Inbox/                        ← User drop folder
│
└── repos/                               ← Canonical organized tree
    └── canonical/                       ← Single source of truth
        ├── Automotive/
        ├── Financial/
        ├── HR/
        └── ...
```

**Configuration**: `.ifmos/config.yml`

```yaml
ifmos:
  version: "2.0"

  # Paths
  drop_directory: "C:\\Users\\kjfle\\00_Inbox"
  canonical_root: "C:\\Users\\kjfle\\Documents\\Organized_Canonical"
  database: ".ifmos/file_registry.db"

  # Behavior
  default_action: "move"                 # 'move' or 'symlink' or 'hardlink'
  duplicate_policy: "link_to_original"   # How to handle dupes
  create_backups: true
  backup_before_reorg: true

  # Classification
  ml_model_path: "ifmos/models/trained/random_forest_classifier.pkl"
  confidence_threshold: 0.70             # Below this → requires review

  # Accuracy tracking
  track_moves: true
  log_level: "INFO"
  metrics_interval: "daily"              # How often to compute metrics
```

#### Shell-Friendly API

```bash
# Initialize IFMOS in a directory
ifmos init --drop ~/00_Inbox --canonical ~/Documents/Organized_Canonical

# Register files from drop zone
ifmos register --scan-drop

# Classify and move to canonical locations
ifmos organize --dry-run               # Preview changes
ifmos organize --execute               # Actually move files

# Query file status
ifmos status <file_path>               # Show file's current state
ifmos history <file_path>              # Show move history

# Manual correction (trains accuracy metrics)
ifmos correct <file_id> --type financial_invoice --reason "wrong classification"

# Metrics
ifmos metrics --today                  # Today's accuracy metrics
ifmos metrics --report accuracy.json   # Export metrics
```

---

## Part 2: Recursive Recategorization Without Duplication

### 2.1 Current Problem

**Current pattern** (BAD):
```
Documents/
├── Organized/          ← v1 (stale)
├── Organized_V1/       ← backup? (stale)
└── Organized_V2/       ← current? (or is this stale too?)
```

**What happens on each run**:
1. IFMOS scans `Organized_V2/`
2. Applies new rules
3. Creates `Organized_V3/` with updated structure
4. **User now has 3 copies of everything**

### 2.2 New Design: In-Place Consolidation

**New pattern** (GOOD):
```
Documents/
└── Organized_Canonical/   ← Single source of truth
    ├── Automotive/
    ├── Financial/
    └── ...
```

**What happens on each run**:
1. IFMOS scans `Organized_Canonical/`
2. Compares current location vs. rules
3. **Moves files WITHIN `Organized_Canonical/`** (no new tree)
4. Logs moves in `move_history` table
5. Creates snapshot backup BEFORE any changes (optional safety)

#### Algorithm: Idempotent Reorganization

```python
def reorganize_canonical_tree(dry_run=False):
    """
    Reorganize files in-place within canonical tree.
    Idempotent: running multiple times converges to same state.
    """

    # Step 1: Scan canonical tree and sync with database
    canonical_root = Path(config['canonical_root'])
    files_on_disk = scan_directory_recursive(canonical_root)
    files_in_db = load_file_registry()

    sync_database_with_filesystem(files_on_disk, files_in_db)

    # Step 2: For each file, compute CURRENT vs. TARGET location
    moves_required = []

    for file_record in files_in_db:
        current_path = Path(file_record['canonical_path'])

        # Apply classification rules to determine target
        target_path = compute_target_path(
            file_record['document_type'],
            file_record['metadata'],
            classification_rules
        )

        if current_path != target_path:
            # File needs to move
            moves_required.append({
                'file_id': file_record['file_id'],
                'from': current_path,
                'to': target_path,
                'reason': 'rule_update' if file_record['move_count'] > 0 else 'initial',
                'rule': get_matching_rule(file_record['document_type'])
            })

    # Step 3: Group moves to detect collisions
    collision_check(moves_required)  # Detect if two files target same path

    # Step 4: Execute moves (or dry-run report)
    if dry_run:
        print_move_report(moves_required)
    else:
        # Create backup snapshot
        if config['backup_before_reorg']:
            create_snapshot(canonical_root)

        # Execute moves
        for move in moves_required:
            execute_move(move)
            log_move_to_database(move)
            log_move_to_file(move)

    # Step 5: Clean up empty directories
    cleanup_empty_directories(canonical_root)

    return moves_required


def sync_database_with_filesystem(files_on_disk, files_in_db):
    """
    Sync database with filesystem reality.

    Handles:
    - Files on disk but not in DB → add to DB
    - Files in DB but not on disk → mark as missing
    - Files that moved externally → detect and log
    """

    # Hash lookup for fast comparison
    db_by_hash = {f['content_hash']: f for f in files_in_db}
    disk_by_hash = {compute_hash(p): p for p in files_on_disk}

    # Find files on disk not in DB
    new_files = [p for h, p in disk_by_hash.items() if h not in db_by_hash]

    for file_path in new_files:
        register_file_in_database(file_path, state='discovered')

    # Find files in DB not on disk
    missing_files = [f for h, f in db_by_hash.items() if h not in disk_by_hash]

    for file_record in missing_files:
        mark_file_missing(file_record['file_id'])

    # Detect files that moved externally (same hash, different path)
    for hash_val in (db_by_hash.keys() & disk_by_hash.keys()):
        db_record = db_by_hash[hash_val]
        disk_path = disk_by_hash[hash_val]

        if db_record['canonical_path'] != str(disk_path):
            log_external_move(db_record['file_id'], disk_path)
            update_canonical_path(db_record['file_id'], disk_path)


def cleanup_empty_directories(root_path):
    """
    Remove empty directories after reorganization.
    Prevents accumulation of stale category folders.
    """
    for dirpath, dirnames, filenames in os.walk(root_path, topdown=False):
        if not dirnames and not filenames:
            # Empty directory
            if is_safe_to_delete(dirpath):
                os.rmdir(dirpath)
                log_directory_cleanup(dirpath)


def create_snapshot(canonical_root):
    """
    Create lightweight snapshot before reorganization.

    Options:
    1. Hard link snapshot (instant, space-efficient)
    2. Symlink snapshot (instant, but less safe)
    3. Metadata-only snapshot (JSON file listing, no file copies)
    """
    snapshot_dir = Path('.ifmos/snapshots') / datetime.now().strftime('%Y%m%d_%H%M%S')
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    # Option 3: Metadata snapshot (recommended for large repos)
    snapshot_metadata = {
        'timestamp': datetime.now().isoformat(),
        'canonical_root': str(canonical_root),
        'files': []
    }

    for file_record in load_file_registry():
        snapshot_metadata['files'].append({
            'file_id': file_record['file_id'],
            'path': file_record['canonical_path'],
            'hash': file_record['content_hash'],
            'document_type': file_record['document_type']
        })

    with open(snapshot_dir / 'snapshot.json', 'w') as f:
        json.dump(snapshot_metadata, f, indent=2)

    return snapshot_dir
```

#### Consolidation Migration Strategy

**Problem**: You have `Organized/` and `Organized_V2/` right now. How to consolidate?

**Migration Script**:

```bash
#!/bin/bash
# migrate_to_canonical.sh
# Consolidates Organized/ and Organized_V2/ into Organized_Canonical/

set -e

SOURCE_V1="$HOME/Documents/Organized"
SOURCE_V2="$HOME/Documents/Organized_V2"
TARGET_CANONICAL="$HOME/Documents/Organized_Canonical"
IFMOS_DB=".ifmos/file_registry.db"

echo "=== IFMOS Consolidation Migration ==="
echo "This will consolidate:"
echo "  - $SOURCE_V1"
echo "  - $SOURCE_V2"
echo "Into:"
echo "  - $TARGET_CANONICAL"
echo ""
read -p "Continue? [y/N] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
fi

# Step 1: Initialize canonical tree
mkdir -p "$TARGET_CANONICAL"
ifmos init --drop ~/00_Inbox --canonical "$TARGET_CANONICAL"

# Step 2: Register all files from V1 and V2
echo "Registering files from Organized_V2 (newer)..."
ifmos register --scan-dir "$SOURCE_V2" --priority high

echo "Registering files from Organized (older)..."
ifmos register --scan-dir "$SOURCE_V1" --priority low

# Step 3: Detect duplicates (same content hash)
echo "Detecting duplicates..."
sqlite3 "$IFMOS_DB" <<SQL
UPDATE file_registry
SET is_duplicate = 1,
    duplicate_of = (
        SELECT fr2.file_id
        FROM file_registry fr2
        WHERE fr2.content_hash = file_registry.content_hash
          AND fr2.file_id < file_registry.file_id
        LIMIT 1
    )
WHERE content_hash IN (
    SELECT content_hash
    FROM file_registry
    GROUP BY content_hash
    HAVING COUNT(*) > 1
);
SQL

# Step 4: Move non-duplicate files to canonical
echo "Moving files to canonical tree..."
ifmos organize --consolidate --dry-run  # Preview
read -p "Looks good? Execute? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    ifmos organize --consolidate --execute
fi

# Step 5: Report duplicates
echo ""
echo "=== Duplicate Files (NOT moved) ==="
sqlite3 "$IFMOS_DB" -column <<SQL
SELECT
    fr1.original_path AS duplicate,
    fr2.canonical_path AS original
FROM file_registry fr1
JOIN file_registry fr2 ON fr1.duplicate_of = fr2.file_id
WHERE fr1.is_duplicate = 1;
SQL

echo ""
echo "=== Migration Complete ==="
echo "Canonical tree: $TARGET_CANONICAL"
echo "Old trees can be deleted after verification:"
echo "  rm -rf \"$SOURCE_V1\""
echo "  rm -rf \"$SOURCE_V2\""
echo ""
echo "Verify first:"
echo "  ifmos metrics --report migration_report.json"
```

---

## Part 3: Accuracy Logic & Measurement

### 3.1 Defining "Accuracy" for IFMOS

**Accuracy = "The file is in the right place according to my rules"**

More formally:

```python
def file_is_accurate(file_record, current_rules):
    """
    A file is "accurate" if:
    1. Its current location matches where current rules would place it
    2. It has not required manual correction
    3. It is not flagged for review
    """

    # Compute where rules say it should be
    target_path = compute_target_path(
        file_record['document_type'],
        file_record['metadata'],
        current_rules
    )

    # Compare to current location
    location_correct = (file_record['canonical_path'] == target_path)

    # Check if manually corrected
    was_corrected = has_manual_corrections(file_record['file_id'])

    # Check if flagged
    flagged = file_record['requires_review']

    return location_correct and not was_corrected and not flagged
```

### 3.2 Concrete Metrics

```python
class IFMOSMetrics:
    """Compute and track IFMOS accuracy metrics"""

    def __init__(self, db_path):
        self.db = sqlite3.connect(db_path)

    def auto_classification_accuracy(self):
        """
        % of files that IFMOS classified correctly without manual intervention.

        Metric: (files never corrected) / (total files)
        """
        cursor = self.db.cursor()

        # Total files
        cursor.execute("SELECT COUNT(*) FROM file_registry")
        total = cursor.fetchone()[0]

        # Files with manual corrections
        cursor.execute("""
            SELECT COUNT(DISTINCT file_id)
            FROM manual_corrections
        """)
        corrected = cursor.fetchone()[0]

        return {
            'metric': 'auto_classification_accuracy',
            'value': (total - corrected) / total if total > 0 else 0.0,
            'total_files': total,
            'corrected_files': corrected,
            'uncorrected_files': total - corrected
        }

    def classification_by_confidence(self):
        """
        Distribution of classification confidence levels.
        Shows if model is confident or uncertain.
        """
        cursor = self.db.cursor()

        cursor.execute("""
            SELECT
                CASE
                    WHEN confidence >= 0.90 THEN 'high'
                    WHEN confidence >= 0.70 THEN 'medium'
                    WHEN confidence >= 0.50 THEN 'low'
                    ELSE 'very_low'
                END as confidence_bucket,
                COUNT(*) as count
            FROM file_registry
            WHERE classification_method = 'ml_model'
            GROUP BY confidence_bucket
        """)

        return dict(cursor.fetchall())

    def stability_metric(self):
        """
        How stable are file locations? Low churn = good.

        Metric: Average moves per file, % files moved >1 time
        """
        cursor = self.db.cursor()

        cursor.execute("""
            SELECT
                AVG(move_count) as avg_moves,
                SUM(CASE WHEN move_count > 1 THEN 1 ELSE 0 END) as multi_move_count,
                COUNT(*) as total_files
            FROM file_registry
        """)

        row = cursor.fetchone()
        avg_moves, multi_move, total = row

        return {
            'metric': 'stability',
            'avg_moves_per_file': avg_moves or 0.0,
            'files_moved_multiple_times': multi_move or 0,
            'percent_unstable': (multi_move / total * 100) if total > 0 else 0.0
        }

    def duplicate_rate(self):
        """
        % of files that are duplicates.
        Low = good (minimal clutter).
        """
        cursor = self.db.cursor()

        cursor.execute("""
            SELECT
                SUM(CASE WHEN is_duplicate = 1 THEN 1 ELSE 0 END) as dupes,
                COUNT(*) as total
            FROM file_registry
        """)

        dupes, total = cursor.fetchone()

        return {
            'metric': 'duplication',
            'duplicate_files': dupes or 0,
            'total_files': total,
            'duplicate_rate': (dupes / total * 100) if total > 0 else 0.0
        }

    def category_accuracy(self):
        """
        Accuracy per document type.
        Identifies which categories need rule improvements.
        """
        cursor = self.db.cursor()

        cursor.execute("""
            SELECT
                fr.document_type,
                COUNT(fr.file_id) as total_files,
                SUM(CASE WHEN mc.correction_id IS NULL THEN 1 ELSE 0 END) as correct_files,
                AVG(fr.confidence) as avg_confidence
            FROM file_registry fr
            LEFT JOIN manual_corrections mc ON fr.file_id = mc.file_id
            WHERE fr.document_type IS NOT NULL
            GROUP BY fr.document_type
            ORDER BY total_files DESC
        """)

        results = []
        for row in cursor.fetchall():
            doc_type, total, correct, avg_conf = row
            results.append({
                'document_type': doc_type,
                'total_files': total,
                'correct_files': correct,
                'accuracy': (correct / total * 100) if total > 0 else 0.0,
                'avg_confidence': avg_conf or 0.0
            })

        return results

    def generate_report(self, output_path=None):
        """
        Generate comprehensive accuracy report.
        """
        report = {
            'timestamp': datetime.now().isoformat(),
            'metrics': {
                'auto_classification_accuracy': self.auto_classification_accuracy(),
                'confidence_distribution': self.classification_by_confidence(),
                'stability': self.stability_metric(),
                'duplication': self.duplicate_rate(),
                'category_accuracy': self.category_accuracy()
            }
        }

        if output_path:
            with open(output_path, 'w') as f:
                json.dump(report, f, indent=2)

        return report
```

### 3.3 Logging & Feedback Loop

**Daily Move Log Format** (`.ifmos/logs/moves_YYYY-MM-DD.log`):

```
2025-11-28T07:30:15|MOVE|file_id=12345|from=/canonical/General/doc.pdf|to=/canonical/Financial/Invoices/2025/11/doc.pdf|reason=reclassification|rule=financial_keyword_v2|confidence=0.92
2025-11-28T07:30:16|MOVE|file_id=12346|from=/canonical/Unknown/file.pdf|to=/canonical/Automotive/Technical/BMW/file.pdf|reason=initial_classification|rule=automotive_ml_model|confidence=0.88
2025-11-28T07:35:42|CORRECT|file_id=12345|wrong_type=financial_invoice|correct_type=personal_receipt|user_reason=personal expense not business
```

**Metrics Snapshot** (`.ifmos/logs/metrics_YYYY-MM-DD.json`):

```json
{
  "date": "2025-11-28",
  "metrics": {
    "auto_classification_accuracy": {
      "value": 0.913,
      "total_files": 2482,
      "corrected_files": 216,
      "uncorrected_files": 2266
    },
    "confidence_distribution": {
      "high": 1845,
      "medium": 423,
      "low": 178,
      "very_low": 36
    },
    "stability": {
      "avg_moves_per_file": 1.2,
      "files_moved_multiple_times": 312,
      "percent_unstable": 12.6
    },
    "duplication": {
      "duplicate_files": 45,
      "total_files": 2482,
      "duplicate_rate": 1.8
    }
  }
}
```

**Feedback Loop Script**:

```bash
#!/bin/bash
# ifmos_daily_metrics.sh
# Run this daily to track accuracy trends

IFMOS_DB=".ifmos/file_registry.db"
TODAY=$(date +%Y-%m-%d)
METRICS_FILE=".ifmos/logs/metrics_$TODAY.json"

# Generate today's metrics
./venv/Scripts/python.exe -c "
from ifmos.metrics import IFMOSMetrics
metrics = IFMOSMetrics('$IFMOS_DB')
metrics.generate_report('$METRICS_FILE')
print('Metrics saved to $METRICS_FILE')
"

# Print summary to console
cat "$METRICS_FILE" | python -c "
import sys, json
data = json.load(sys.stdin)
m = data['metrics']

print('\n=== IFMOS Daily Metrics ===')
print(f\"Date: {data['date']}\")
print(f\"Auto-Classification Accuracy: {m['auto_classification_accuracy']['value']*100:.1f}%\")
print(f\"High Confidence Files: {m['confidence_distribution'].get('high', 0)}\")
print(f\"Files Needing Review: {m['confidence_distribution'].get('very_low', 0)}\")
print(f\"Duplicate Rate: {m['duplication']['duplicate_rate']:.1f}%\")
print(f\"Stability (avg moves): {m['stability']['avg_moves_per_file']:.2f}\")
print()

# Show worst-performing categories
print('Categories Needing Improvement:')
for cat in m['category_accuracy'][:3]:
    if cat['accuracy'] < 80:
        print(f\"  - {cat['document_type']}: {cat['accuracy']:.1f}% ({cat['total_files']} files)\")
"
```

---

## Part 4: Putting It All Together - Redesigned Workflow

### Workflow: Drop → Classify → Organize → Refine

```
┌─────────────────┐
│  00_Inbox/      │ ← Files arrive here
│  (drop zone)    │
└────────┬────────┘
         │
         │ 1. ifmos register --scan-drop
         ▼
┌─────────────────────────────────────────┐
│  .ifmos/file_registry.db                │
│  - Register files                       │
│  - Compute content hash                 │
│  - Extract metadata                     │
└─────────────────┬───────────────────────┘
                  │
                  │ 2. ifmos classify
                  ▼
         ┌────────────────┐
         │  ML Classifier  │
         │  + Rules Engine │
         └────────┬────────┘
                  │
                  │ 3. ifmos organize --execute
                  ▼
┌─────────────────────────────────────────┐
│  Organized_Canonical/                   │ ← Single source of truth
│  ├── Automotive/                        │
│  ├── Financial/                         │
│  └── ...                                │
└─────────────────┬───────────────────────┘
                  │
                  │ 4. User reviews, corrects
                  ▼
┌─────────────────────────────────────────┐
│  ifmos correct <file> --type <new_type>│
│  → Logs correction to database          │
│  → Retrains model (optional)            │
└─────────────────┬───────────────────────┘
                  │
                  │ 5. ifmos reorg (idempotent)
                  ▼
         (Files move within
         Organized_Canonical/
         no duplication)
```

### Example Session

```bash
# Day 1: Initial setup
cd ~/Projects/ifmos
ifmos init --drop ~/00_Inbox --canonical ~/Documents/Organized_Canonical

# Day 2: New files arrive in inbox
# ... user copies 50 new PDFs to ~/00_Inbox ...

# Register new files
ifmos register --scan-drop
# Output: Registered 50 new files (3 duplicates detected)

# Classify them
ifmos classify --confidence-threshold 0.70
# Output: Classified 47 files (3 low confidence, flagged for review)

# Review classification
ifmos list --flagged
# Shows 3 files needing manual review

# Organize into canonical tree
ifmos organize --dry-run  # Preview
ifmos organize --execute  # Actually move

# Check metrics
ifmos metrics --today
# Output:
#   Auto-Classification Accuracy: 94.0%
#   High Confidence: 44 files
#   Flagged for Review: 3 files
#   Duplicates: 3 files

# Day 3: User notices a misclassification
# File was classified as "financial_invoice" but should be "personal_receipt"

ifmos correct ~/Documents/Organized_Canonical/Financial/Invoices/2025/11/receipt.pdf \
    --type personal_receipt \
    --reason "personal expense, not business"

# System logs this correction, updates metrics

# Day 7: Rules updated, time to reorganize
# ... edit .ifmos/config.yml to refine rules ...

ifmos reorg --dry-run      # See what would move
ifmos reorg --execute      # Moves files in-place, no duplication

# Generate weekly report
ifmos metrics --report weekly_report_2025-11-28.json

# View accuracy trends
ifmos metrics --trend --days 7
# Shows accuracy improving from 91.3% → 94.0% over the week
```

---

## Part 5: Shell Implementation Examples

### Script 1: `ifmos register` - Register Files from Drop Zone

```bash
#!/bin/bash
# ifmos-register.sh

IFMOS_DB=".ifmos/file_registry.db"
DROP_DIR=$(yq eval '.ifmos.drop_directory' .ifmos/config.yml)

echo "Registering files from: $DROP_DIR"

# Find all files in drop zone
find "$DROP_DIR" -type f | while read filepath; do
    # Compute hash
    hash=$(sha256sum "$filepath" | awk '{print $1}')

    # Check if already registered
    existing=$(sqlite3 "$IFMOS_DB" "SELECT file_id FROM file_registry WHERE content_hash='$hash'")

    if [ -n "$existing" ]; then
        echo "SKIP (duplicate): $filepath"

        # Mark as duplicate
        sqlite3 "$IFMOS_DB" <<SQL
UPDATE file_registry
SET is_duplicate = 1, duplicate_of = $existing
WHERE content_hash = '$hash' AND file_id != $existing;
SQL
    else
        echo "REGISTER: $filepath"

        # Insert into registry
        sqlite3 "$IFMOS_DB" <<SQL
INSERT INTO file_registry (
    original_path,
    drop_timestamp,
    content_hash,
    canonical_state
) VALUES (
    '$filepath',
    datetime('now'),
    '$hash',
    'pending'
);
SQL
    fi
done

echo "Registration complete."
```

### Script 2: `ifmos classify` - Run ML Classification

```bash
#!/bin/bash
# ifmos-classify.sh

IFMOS_DB=".ifmos/file_registry.db"
ML_MODEL=$(yq eval '.ifmos.ml_model_path' .ifmos/config.yml)
THRESHOLD=$(yq eval '.ifmos.confidence_threshold' .ifmos/config.yml)

echo "Classifying pending files (threshold: $THRESHOLD)..."

# Get files pending classification
sqlite3 -separator $'\t' "$IFMOS_DB" \
    "SELECT file_id, original_path FROM file_registry WHERE canonical_state='pending'" |
while IFS=$'\t' read file_id filepath; do

    # Run Python classifier
    result=$(./venv/Scripts/python.exe -c "
from ifmos.classifiers import MLClassifier
classifier = MLClassifier('$ML_MODEL')
result = classifier.classify_file('$filepath')
print(f\"{result['document_type']}|{result['confidence']:.3f}\")
")

    doc_type=$(echo "$result" | cut -d'|' -f1)
    confidence=$(echo "$result" | cut -d'|' -f2)

    # Update database
    if (( $(echo "$confidence >= $THRESHOLD" | bc -l) )); then
        state="classified"
    else
        state="review"
    fi

    sqlite3 "$IFMOS_DB" <<SQL
UPDATE file_registry
SET document_type = '$doc_type',
    confidence = $confidence,
    classification_method = 'ml_model',
    canonical_state = '$state',
    requires_review = CASE WHEN $confidence < $THRESHOLD THEN 1 ELSE 0 END
WHERE file_id = $file_id;
SQL

    echo "[$file_id] $doc_type (conf: $confidence) → $state"
done

echo "Classification complete."
```

### Script 3: `ifmos organize` - Move Files to Canonical

```bash
#!/bin/bash
# ifmos-organize.sh

IFMOS_DB=".ifmos/file_registry.db"
CANONICAL_ROOT=$(yq eval '.ifmos.canonical_root' .ifmos/config.yml)
DRY_RUN=false

if [ "$1" = "--dry-run" ]; then
    DRY_RUN=true
fi

echo "Organizing files to: $CANONICAL_ROOT"
[ "$DRY_RUN" = true ] && echo "(DRY RUN MODE)"

# Get classified files ready to organize
sqlite3 -separator $'\t' "$IFMOS_DB" \
    "SELECT file_id, original_path, document_type FROM file_registry WHERE canonical_state='classified'" |
while IFS=$'\t' read file_id filepath doc_type; do

    # Compute target path based on document type
    # (In real implementation, use Python to apply templates)
    case "$doc_type" in
        financial_invoice)
            year=$(date +%Y)
            month=$(date +%m)
            target_dir="$CANONICAL_ROOT/Financial/Invoices/$year/$month"
            ;;
        automotive_technical)
            target_dir="$CANONICAL_ROOT/Automotive/Technical"
            ;;
        hr_resume)
            target_dir="$CANONICAL_ROOT/HR/Resumes"
            ;;
        *)
            target_dir="$CANONICAL_ROOT/Uncategorized"
            ;;
    esac

    filename=$(basename "$filepath")
    target_path="$target_dir/$filename"

    echo "MOVE: $filepath → $target_path"

    if [ "$DRY_RUN" = false ]; then
        # Create target directory
        mkdir -p "$target_dir"

        # Move file
        mv "$filepath" "$target_path"

        # Update database
        sqlite3 "$IFMOS_DB" <<SQL
UPDATE file_registry
SET canonical_path = '$target_path',
    canonical_state = 'organized',
    last_moved = datetime('now'),
    move_count = move_count + 1
WHERE file_id = $file_id;

INSERT INTO move_history (file_id, from_path, to_path, move_timestamp, reason)
VALUES ($file_id, '$filepath', '$target_path', datetime('now'), 'initial_classification');
SQL

        # Log to daily log file
        echo "$(date -Iseconds)|MOVE|file_id=$file_id|from=$filepath|to=$target_path|reason=initial|doc_type=$doc_type" \
            >> ".ifmos/logs/moves_$(date +%Y-%m-%d).log"
    fi
done

echo "Organization complete."
```

### Script 4: `ifmos metrics` - Compute Accuracy Metrics

```bash
#!/bin/bash
# ifmos-metrics.sh

IFMOS_DB=".ifmos/file_registry.db"

echo "=== IFMOS Accuracy Metrics ==="
echo "Date: $(date +%Y-%m-%d)"
echo ""

# Auto-classification accuracy
echo "Auto-Classification Accuracy:"
sqlite3 "$IFMOS_DB" <<SQL
SELECT
    printf('  Total Files: %d', COUNT(*)) AS total,
    printf('  Corrected: %d',
        (SELECT COUNT(DISTINCT file_id) FROM manual_corrections)) AS corrected,
    printf('  Uncorrected: %d',
        COUNT(*) - (SELECT COUNT(DISTINCT file_id) FROM manual_corrections)) AS uncorrected,
    printf('  Accuracy: %.1f%%',
        (COUNT(*) - (SELECT COUNT(DISTINCT file_id) FROM manual_corrections)) * 100.0 / COUNT(*)) AS accuracy
FROM file_registry;
SQL
echo ""

# Confidence distribution
echo "Confidence Distribution:"
sqlite3 "$IFMOS_DB" <<SQL
SELECT
    CASE
        WHEN confidence >= 0.90 THEN '  High (>=0.90)'
        WHEN confidence >= 0.70 THEN '  Medium (>=0.70)'
        WHEN confidence >= 0.50 THEN '  Low (>=0.50)'
        ELSE '  Very Low (<0.50)'
    END || ': ' || COUNT(*) || ' files'
FROM file_registry
WHERE classification_method = 'ml_model'
GROUP BY
    CASE
        WHEN confidence >= 0.90 THEN 1
        WHEN confidence >= 0.70 THEN 2
        WHEN confidence >= 0.50 THEN 3
        ELSE 4
    END
ORDER BY 1;
SQL
echo ""

# Stability
echo "Stability:"
sqlite3 "$IFMOS_DB" <<SQL
SELECT
    printf('  Avg moves per file: %.2f', AVG(move_count)) AS avg_moves,
    printf('  Files moved >1 time: %d (%.1f%%)',
        SUM(CASE WHEN move_count > 1 THEN 1 ELSE 0 END),
        SUM(CASE WHEN move_count > 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*)) AS multi_moves
FROM file_registry;
SQL
echo ""

# Duplication
echo "Duplication:"
sqlite3 "$IFMOS_DB" <<SQL
SELECT
    printf('  Duplicate files: %d (%.1f%%)',
        SUM(CASE WHEN is_duplicate = 1 THEN 1 ELSE 0 END),
        SUM(CASE WHEN is_duplicate = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*)) AS dupes
FROM file_registry;
SQL
echo ""

# Category accuracy
echo "Category Accuracy (top 5):"
sqlite3 -column "$IFMOS_DB" <<SQL
SELECT
    '  ' || document_type AS Category,
    printf('%d files', COUNT(fr.file_id)) AS Total,
    printf('%.1f%%',
        SUM(CASE WHEN mc.correction_id IS NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(fr.file_id)) AS Accuracy
FROM file_registry fr
LEFT JOIN manual_corrections mc ON fr.file_id = mc.file_id
WHERE fr.document_type IS NOT NULL
GROUP BY fr.document_type
ORDER BY COUNT(fr.file_id) DESC
LIMIT 5;
SQL
```

---

## Part 6: Migration Roadmap

### Phase 1: Setup New Architecture (Week 1)

- [ ] Initialize `.ifmos/` directory structure
- [ ] Create `file_registry.db` with schema
- [ ] Write `ifmos init` command
- [ ] Write `ifmos register` command
- [ ] Test with small subset (100 files)

### Phase 2: Consolidation (Week 2)

- [ ] Run consolidation migration script
- [ ] Merge `Organized/` + `Organized_V2/` → `Organized_Canonical/`
- [ ] Verify no data loss (hash checks)
- [ ] Archive old folders (don't delete yet)

### Phase 3: Classification & Organization (Week 3)

- [ ] Implement `ifmos classify` with ML model
- [ ] Implement `ifmos organize` with templates
- [ ] Test idempotent reorganization
- [ ] Validate template filling works

### Phase 4: Accuracy Tracking (Week 4)

- [ ] Implement `ifmos correct` for manual corrections
- [ ] Implement `ifmos metrics` reporter
- [ ] Set up daily metrics cron job
- [ ] Create accuracy dashboard (optional web UI)

### Phase 5: Production & Iteration (Ongoing)

- [ ] Use IFMOS daily for new files
- [ ] Review weekly metrics
- [ ] Refine rules based on correction data
- [ ] Re-run idempotent reorg after rule changes

---

## Summary

### What This Redesign Solves

| Problem | Solution |
|---------|----------|
| **Drop → Target linking unclear** | `.ifmos/file_registry.db` tracks every file's journey |
| **Multiple "Organized" versions** | Single `Organized_Canonical/` tree, idempotent reorg |
| **No accuracy measurement** | Explicit metrics: classification accuracy, stability, duplication rate |
| **Template placeholders not filled** | Metadata extraction + template engine |
| **Can't improve over time** | Manual corrections logged, feedback loop to retrain model |

### Key Design Principles

1. **Single Source of Truth**: One canonical tree, not multiple versions
2. **Idempotency**: Re-running operations converges to same state
3. **Explicit Tracking**: Database records provenance, moves, corrections
4. **Shell-Friendly**: All operations accessible via CLI, scriptable
5. **Measurable**: Concrete metrics, logged daily, trends visible

### Next Steps

1. Review this design and confirm it matches your vision
2. I'll implement the core scripts (`ifmos init`, `register`, `classify`, `organize`, `metrics`)
3. Run consolidation migration to merge existing trees
4. Set up daily metrics tracking
5. Iterate based on accuracy feedback

This architecture transforms IFMOS from a one-shot organizer into a **measurable, improvable system** with clear accuracy tracking and zero duplication cruft.
