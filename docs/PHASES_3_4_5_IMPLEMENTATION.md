# IFMOS Phases 3-5 Implementation Guide

**Status**: Deferred (implement after Phases 1-2 complete)
**Prerequisites**:
- ✅ Phase 1: `.ifmos/` structure and database created
- ✅ Phase 2: Files consolidated into `Organized_Canonical/`

---

## Phase 3: Classification Pipeline (1-2 hours)

**Goal**: End-to-end pipeline from inbox → canonical tree

### Tasks:

#### 3.1 Implement `ifmos register`

**File**: `ifmos/commands/register.py`

```python
def register_files_from_drop(drop_dir, db_path):
    """
    Scan drop directory and register files in database.

    - Computes SHA-256 hash
    - Detects duplicates
    - Inserts into file_registry
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    for filepath in Path(drop_dir).rglob('*'):
        if not filepath.is_file():
            continue

        # Compute hash
        content_hash = compute_sha256(filepath)

        # Check if already registered
        cursor.execute("""
            SELECT file_id, canonical_path
            FROM file_registry
            WHERE content_hash = ?
        """, (content_hash,))

        existing = cursor.fetchone()

        if existing:
            # Duplicate
            print(f"SKIP (duplicate): {filepath}")
            cursor.execute("""
                INSERT INTO file_registry
                (original_path, drop_timestamp, content_hash, file_size,
                 is_duplicate, duplicate_of, canonical_state)
                VALUES (?, datetime('now'), ?, ?, 1, ?, 'duplicate')
            """, (str(filepath), content_hash, filepath.stat().st_size, existing[0]))
        else:
            # New file
            print(f"REGISTER: {filepath}")
            cursor.execute("""
                INSERT INTO file_registry
                (original_path, drop_timestamp, content_hash, file_size, canonical_state)
                VALUES (?, datetime('now'), ?, ?, 'pending')
            """, (str(filepath), content_hash, filepath.stat().st_size))

    conn.commit()
    conn.close()
```

#### 3.2 Implement `ifmos classify`

**File**: `ifmos/commands/classify.py`

```python
def classify_pending_files(db_path, ml_model_path, confidence_threshold=0.70):
    """
    Classify files that are in 'pending' state.

    Uses:
    1. ML model (trained Random Forest)
    2. Fallback to keyword patterns if confidence low
    """
    from ifmos.ml.classifier import MLClassifier

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Load ML model
    classifier = MLClassifier(ml_model_path)

    # Get pending files
    cursor.execute("""
        SELECT file_id, original_path, canonical_path
        FROM file_registry
        WHERE canonical_state = 'pending' AND is_duplicate = 0
    """)

    pending_files = cursor.fetchall()

    for file_id, original_path, canonical_path in pending_files:
        filepath = canonical_path if canonical_path else original_path

        # Classify
        result = classifier.classify_file(filepath)

        doc_type = result['document_type']
        confidence = result['confidence']
        method = result['method']  # 'ml_model', 'keyword', 'pattern'

        # Determine state
        if confidence >= confidence_threshold:
            state = 'classified'
            requires_review = 0
        else:
            state = 'review'
            requires_review = 1

        # Update database
        cursor.execute("""
            UPDATE file_registry
            SET document_type = ?,
                confidence = ?,
                classification_method = ?,
                canonical_state = ?,
                requires_review = ?,
                updated_at = datetime('now')
            WHERE file_id = ?
        """, (doc_type, confidence, method, state, requires_review, file_id))

        print(f"[{file_id}] {doc_type} (conf: {confidence:.3f}) → {state}")

    conn.commit()
    conn.close()
```

#### 3.3 Implement `ifmos organize`

**File**: `ifmos/commands/organize.py`

```python
def organize_classified_files(db_path, canonical_root, domain_mapping, dry_run=False):
    """
    Move classified files to their canonical locations.

    - Reads classification from database
    - Applies path templates
    - Moves files
    - Logs moves to move_history
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get classified files ready to organize
    cursor.execute("""
        SELECT file_id, original_path, canonical_path, document_type, extracted_metadata
        FROM file_registry
        WHERE canonical_state = 'classified' AND is_duplicate = 0
    """)

    classified_files = cursor.fetchall()

    for file_id, original_path, canonical_path, doc_type, metadata_json in classified_files:
        # Determine source path
        source_path = Path(canonical_path if canonical_path else original_path)

        if not source_path.exists():
            print(f"SKIP (missing): {source_path}")
            continue

        # Parse metadata
        metadata = json.loads(metadata_json) if metadata_json else {}

        # Compute target path using template
        target_path = compute_target_path(
            canonical_root,
            doc_type,
            source_path.name,
            metadata,
            domain_mapping
        )

        if source_path == target_path:
            print(f"SKIP (already in place): {source_path}")
            continue

        print(f"MOVE: {source_path} → {target_path}")

        if not dry_run:
            # Create target directory
            target_path.parent.mkdir(parents=True, exist_ok=True)

            # Move file
            shutil.move(str(source_path), str(target_path))

            # Update database
            cursor.execute("""
                UPDATE file_registry
                SET canonical_path = ?,
                    canonical_state = 'organized',
                    last_moved = datetime('now'),
                    move_count = move_count + 1,
                    updated_at = datetime('now')
                WHERE file_id = ?
            """, (str(target_path), file_id))

            # Log move
            cursor.execute("""
                INSERT INTO move_history
                (file_id, from_path, to_path, reason, rule_applied)
                VALUES (?, ?, ?, 'initial_classification', ?)
            """, (file_id, str(source_path), str(target_path), doc_type))

    if not dry_run:
        conn.commit()
    conn.close()
```

#### 3.4 Test Complete Pipeline

```bash
# Put test files in inbox
cp test_files/*.pdf ~/00_Inbox/

# Run pipeline
ifmos register --scan-drop
ifmos classify --confidence-threshold 0.70
ifmos organize --dry-run      # Preview
ifmos organize --execute      # Actually move

# Verify
ifmos status <file_path>      # Show file's journey
sqlite3 .ifmos/file_registry.db "SELECT * FROM move_history LIMIT 5"
```

---

## Phase 4: Accuracy Tracking (1 hour)

**Goal**: Implement metrics and feedback loop

### Tasks:

#### 4.1 Implement `ifmos correct`

**File**: `ifmos/commands/correct.py`

```python
def correct_file_classification(db_path, file_path, correct_type, reason):
    """
    User corrects a misclassification.

    - Logs to manual_corrections table
    - Updates file's document_type
    - Decrements accuracy metrics
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Find file by path
    cursor.execute("""
        SELECT file_id, document_type
        FROM file_registry
        WHERE canonical_path = ? OR original_path = ?
    """, (file_path, file_path))

    result = cursor.fetchone()
    if not result:
        print(f"✗ File not found: {file_path}")
        return

    file_id, wrong_type = result

    # Log correction
    cursor.execute("""
        INSERT INTO manual_corrections
        (file_id, wrong_type, correct_type, correction_reason)
        VALUES (?, ?, ?, ?)
    """, (file_id, wrong_type, correct_type, reason))

    # Update file's document_type
    cursor.execute("""
        UPDATE file_registry
        SET document_type = ?,
            classification_method = 'manual',
            updated_at = datetime('now')
        WHERE file_id = ?
    """, (correct_type, file_id))

    conn.commit()
    conn.close()

    print(f"✓ Correction logged: {wrong_type} → {correct_type}")
    print(f"  Reason: {reason}")
```

#### 4.2 Implement `ifmos metrics`

**File**: `ifmos/metrics.py`

```python
class IFMOSMetrics:
    """Compute and track IFMOS accuracy metrics"""

    def __init__(self, db_path):
        self.db = sqlite3.connect(db_path)

    def auto_classification_accuracy(self):
        """
        % of files that IFMOS classified correctly without manual intervention.
        """
        cursor = self.db.cursor()

        # Total files
        cursor.execute("SELECT COUNT(*) FROM file_registry WHERE is_duplicate = 0")
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

    def stability_metric(self):
        """How stable are file locations?"""
        cursor = self.db.cursor()

        cursor.execute("""
            SELECT
                AVG(move_count) as avg_moves,
                SUM(CASE WHEN move_count > 1 THEN 1 ELSE 0 END) as multi_move_count,
                COUNT(*) as total_files
            FROM file_registry
            WHERE is_duplicate = 0
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
        """% of files that are duplicates"""
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

    def generate_report(self, output_path=None):
        """Generate comprehensive accuracy report"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'metrics': {
                'auto_classification_accuracy': self.auto_classification_accuracy(),
                'stability': self.stability_metric(),
                'duplication': self.duplicate_rate()
            }
        }

        if output_path:
            with open(output_path, 'w') as f:
                json.dump(report, f, indent=2)

        return report
```

#### 4.3 Set Up Daily Metrics

**File**: `scripts/cron/daily_metrics.sh`

```bash
#!/bin/bash
# Run daily at 11:59 PM via cron or Task Scheduler

cd ~/Projects/intelligent-file-management-system

TODAY=$(date +%Y-%m-%d)
METRICS_FILE=".ifmos/logs/metrics_$TODAY.json"

# Generate today's metrics
./venv/Scripts/python.exe -c "
from ifmos.metrics import IFMOSMetrics
metrics = IFMOSMetrics('.ifmos/file_registry.db')
metrics.generate_report('$METRICS_FILE')
print('✓ Metrics saved to $METRICS_FILE')
"

# Print summary
cat "$METRICS_FILE" | python -c "
import sys, json
data = json.load(sys.stdin)
m = data['metrics']

print('\n=== IFMOS Daily Metrics ===')
print(f\"Date: {data['timestamp'][:10]}\")
print(f\"Auto-Classification Accuracy: {m['auto_classification_accuracy']['value']*100:.1f}%\")
print(f\"Stability (avg moves): {m['stability']['avg_moves_per_file']:.2f}\")
print(f\"Duplicate Rate: {m['duplication']['duplicate_rate']:.1f}%\")
"
```

---

## Phase 5: Idempotent Reorganization (1 hour)

**Goal**: Re-run classification on existing canonical tree without duplication

### Tasks:

#### 5.1 Implement `ifmos reorg`

**File**: `ifmos/commands/reorg.py`

```python
def reorganize_canonical_tree(db_path, canonical_root, domain_mapping, dry_run=False):
    """
    Reorganize files in-place within canonical tree.
    Idempotent: running multiple times converges to same state.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Step 1: Sync database with filesystem
    sync_database_with_filesystem(conn, canonical_root)

    # Step 2: For each file, compute CURRENT vs. TARGET location
    cursor.execute("""
        SELECT file_id, canonical_path, document_type, extracted_metadata
        FROM file_registry
        WHERE canonical_state = 'organized' AND is_duplicate = 0
    """)

    moves_required = []

    for file_id, current_path, doc_type, metadata_json in cursor.fetchall():
        current_path = Path(current_path)

        if not current_path.exists():
            continue

        # Parse metadata
        metadata = json.loads(metadata_json) if metadata_json else {}

        # Compute target path
        target_path = compute_target_path(
            canonical_root,
            doc_type,
            current_path.name,
            metadata,
            domain_mapping
        )

        if current_path != target_path:
            moves_required.append({
                'file_id': file_id,
                'from': current_path,
                'to': target_path,
                'reason': 'rule_update'
            })

    # Step 3: Execute moves
    if moves_required:
        print(f"{'DRY RUN: ' if dry_run else ''}Reorganizing {len(moves_required)} files...")

        for move in moves_required:
            print(f"  {move['from']} → {move['to']}")

            if not dry_run:
                # Create target directory
                move['to'].parent.mkdir(parents=True, exist_ok=True)

                # Move file
                shutil.move(str(move['from']), str(move['to']))

                # Update database
                cursor.execute("""
                    UPDATE file_registry
                    SET canonical_path = ?,
                        last_moved = datetime('now'),
                        move_count = move_count + 1,
                        updated_at = datetime('now')
                    WHERE file_id = ?
                """, (str(move['to']), move['file_id']))

                # Log move
                cursor.execute("""
                    INSERT INTO move_history
                    (file_id, from_path, to_path, reason)
                    VALUES (?, ?, ?, ?)
                """, (move['file_id'], str(move['from']), str(move['to']), move['reason']))

        if not dry_run:
            conn.commit()
    else:
        print("✓ No changes needed (already organized correctly)")

    # Step 4: Clean up empty directories
    if not dry_run:
        cleanup_empty_directories(canonical_root)

    conn.close()


def sync_database_with_filesystem(conn, canonical_root):
    """
    Sync database with filesystem reality.

    - Files on disk but not in DB → add to DB
    - Files in DB but not on disk → mark as missing
    """
    cursor = conn.cursor()

    # Get all files from database
    cursor.execute("""
        SELECT file_id, canonical_path, content_hash
        FROM file_registry
        WHERE canonical_state = 'organized' AND canonical_path IS NOT NULL
    """)

    db_files = {row[1]: (row[0], row[2]) for row in cursor.fetchall()}

    # Get all files from disk
    disk_files = {}
    for filepath in Path(canonical_root).rglob('*'):
        if filepath.is_file():
            disk_files[str(filepath)] = compute_sha256(filepath)

    # Find files on disk but not in DB
    new_files = set(disk_files.keys()) - set(db_files.keys())
    for filepath in new_files:
        print(f"DISCOVERED: {filepath}")
        cursor.execute("""
            INSERT INTO file_registry
            (original_path, canonical_path, drop_timestamp, content_hash,
             file_size, canonical_state)
            VALUES (?, ?, datetime('now'), ?, ?, 'organized')
        """, (filepath, filepath, disk_files[filepath],
              Path(filepath).stat().st_size))

    # Find files in DB but not on disk
    missing_files = set(db_files.keys()) - set(disk_files.keys())
    for filepath in missing_files:
        file_id = db_files[filepath][0]
        print(f"MISSING: {filepath}")
        cursor.execute("""
            UPDATE file_registry
            SET is_missing = 1, updated_at = datetime('now')
            WHERE file_id = ?
        """, (file_id,))

    conn.commit()


def cleanup_empty_directories(root_path):
    """Remove empty directories after reorganization"""
    for dirpath, dirnames, filenames in os.walk(root_path, topdown=False):
        if not dirnames and not filenames:
            # Empty directory
            if dirpath != str(root_path):  # Don't delete root
                print(f"CLEANUP: Removing empty directory: {dirpath}")
                os.rmdir(dirpath)
```

#### 5.2 Test Idempotency

```bash
# Run reorganization
ifmos reorg --dry-run
ifmos reorg --execute

# Run again - should show "No changes needed"
ifmos reorg --dry-run

# Verify stability metric
ifmos metrics --stability
```

#### 5.3 Test Rule Changes

```bash
# Edit classification rules
vim .ifmos/config.yml  # Change a path template

# See what would move
ifmos reorg --dry-run

# Execute
ifmos reorg --execute

# Verify files moved correctly
ifmos metrics --today
```

---

## Success Criteria

### Phase 3 Complete:
- [ ] `ifmos register` scans drop directory and registers files
- [ ] `ifmos classify` uses ML model with 88.6% accuracy
- [ ] `ifmos organize` moves files to canonical locations
- [ ] Database has complete audit trail (move_history populated)

### Phase 4 Complete:
- [ ] `ifmos correct` logs manual corrections
- [ ] `ifmos metrics` generates accuracy report
- [ ] Metrics show >85% accuracy
- [ ] Daily metrics automated (cron/Task Scheduler)

### Phase 5 Complete:
- [ ] `ifmos reorg` works idempotently (run twice, no changes second time)
- [ ] Rule changes trigger appropriate moves
- [ ] Stability metric shows low churn (<15%)
- [ ] Empty directories cleaned up automatically

---

## Quick Reference Commands

```bash
# Phase 3: Classification Pipeline
ifmos register --scan-drop
ifmos classify --confidence-threshold 0.70
ifmos organize --dry-run
ifmos organize --execute

# Phase 4: Accuracy Tracking
ifmos correct <file_path> --type <doc_type> --reason "..."
ifmos metrics --today
ifmos metrics --report .ifmos/logs/metrics_$(date +%Y-%m-%d).json

# Phase 5: Idempotent Reorganization
ifmos reorg --dry-run
ifmos reorg --execute
ifmos metrics --stability
```

---

## Implementation Order

Implement in this order for logical progression:

1. **Phase 3.1**: `ifmos register` (files enter system)
2. **Phase 3.2**: `ifmos classify` (ML classification)
3. **Phase 3.3**: `ifmos organize` (move to canonical)
4. **Phase 4.1**: `ifmos correct` (user feedback)
5. **Phase 4.2**: `ifmos metrics` (accuracy measurement)
6. **Phase 5.1**: `ifmos reorg` (idempotent refinement)

Each phase builds on the previous, creating a complete feedback loop.
