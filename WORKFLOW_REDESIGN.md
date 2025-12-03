# IFMOS Workflow Refinement - Inbox to Current with Rollback

## Current State Analysis

### Existing Workflow
1. **Scan** → Index files into database
2. **Analyze** → Detect duplicates, categorize
3. **Plan** → Create migration plan
4. **Execute** → Move files according to plan
5. **Checkpoint** → Save JSON for rollback

### Limitations
1. **No staging area**: Files go directly from source to destination
2. **Limited preview**: Can't easily visualize impact before execution
3. **Coarse rollback**: All-or-nothing checkpoint recovery
4. **Manual approval**: No automated validation
5. **No versioning**: Can't track multiple organization attempts
6. **No conflict resolution**: Overwrites without asking

## Refined Workflow Design

### Three-Stage Pipeline

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌──────────┐
│  Inbox  │ ──> │ Staging │ ──> │ Current │ ──> │ Archive  │
│ (Raw)   │     │(Preview)│     │(Active) │     │(History) │
└─────────┘     └─────────┘     └─────────┘     └──────────┘
                     │                │
                     └────────────────┴──> Rollback
```

### Stage Definitions

#### 1. Inbox (Raw)
- **Purpose**: Unsorted incoming files
- **Location**: `~/Inbox` or `~/00_Inbox`
- **Characteristics**:
  - No organization
  - Possibly duplicates
  - Unknown quality
  - Temporary storage

#### 2. Staging (Preview)
- **Purpose**: Organized preview before commit
- **Location**: `~/.ifmos/staging/<plan_id>/`
- **Characteristics**:
  - Organized structure
  - Symbolic links or copies (configurable)
  - Fully reversible
  - Validation checks

#### 3. Current (Active)
- **Purpose**: Production organized files
- **Location**: `~/Organized` or custom
- **Characteristics**:
  - Canonical file locations
  - ML-classified categories
  - Deduplication applied
  - Versioned snapshots

#### 4. Archive (History)
- **Purpose**: Previous organization states
- **Location**: `~/.ifmos/archive/<timestamp>/`
- **Characteristics**:
  - Complete snapshots
  - Rollback checkpoints
  - Metadata preserved
  - Space-efficient (hardlinks)

## Enhanced Features

### 1. Staging System

**Workflow**:
```bash
# Scan inbox
ifmos scan --roots ~/Inbox --tag inbox

# Create staging plan
ifmos stage create --session <id> --output ~/Organized

# Preview staging (opens in file explorer)
ifmos stage preview --plan <plan-id>

# Validate staging
ifmos stage validate --plan <plan-id>

# Commit to Current
ifmos stage commit --plan <plan-id>

# Or discard
ifmos stage discard --plan <plan-id>
```

**Implementation**:
- Uses symlinks on Unix, junction points on Windows
- Validates file accessibility
- Checks for conflicts
- Estimates disk usage
- Provides diff view

### 2. Granular Rollback

**Rollback Levels**:
1. **File-level**: Undo single file moves
2. **Category-level**: Undo all files in a category
3. **Plan-level**: Undo entire migration plan
4. **Snapshot-level**: Restore to specific point in time

**Workflow**:
```bash
# List rollback points
ifmos rollback list

# Show what would be rolled back
ifmos rollback preview --plan <plan-id>

# Rollback specific plan
ifmos rollback execute --plan <plan-id>

# Rollback to timestamp
ifmos rollback restore --timestamp 2024-12-03T10:00:00

# Rollback specific files
ifmos rollback files --ids file1,file2,file3
```

**Implementation**:
- Transaction log in SQLite
- Before/after state tracking
- Hardlink-based snapshots (space-efficient)
- Incremental rollback support
- Conflict detection

### 3. Conflict Resolution

**Conflict Types**:
1. **Name collision**: Target path already exists
2. **Duplicate content**: Same file hash
3. **Version conflict**: Multiple versions of same file
4. **Permission issue**: Can't read/write

**Resolution Strategies**:
```python
class ConflictStrategy(Enum):
    ASK = "ask"              # Prompt user
    SKIP = "skip"            # Skip conflicting file
    RENAME = "rename"        # Add suffix (_1, _2, etc)
    REPLACE = "replace"      # Overwrite existing
    KEEP_NEWEST = "newest"   # Keep file with latest mtime
    KEEP_LARGEST = "largest" # Keep largest file
```

**Workflow**:
```bash
# Set default strategy
ifmos config set conflict_strategy=rename

# Interactive resolution
ifmos stage resolve --plan <plan-id> --interactive

# Batch resolution
ifmos stage resolve --plan <plan-id> --strategy rename
```

### 4. Validation System

**Pre-commit Checks**:
1. ✓ All source files readable
2. ✓ Target paths writable
3. ✓ No circular dependencies
4. ✓ Sufficient disk space
5. ✓ No path length violations (Windows 260 char limit)
6. ✓ Valid characters in filenames
7. ✓ ML classification confidence > threshold
8. ✓ Duplicate handling rules applied

**Workflow**:
```bash
# Validate staging plan
ifmos stage validate --plan <plan-id>

# Output validation report
ifmos stage validate --plan <plan-id> --report validation.json

# Fix issues automatically
ifmos stage fix --plan <plan-id> --auto
```

### 5. Versioned Organization

**Version Tracking**:
- Each migration creates a version
- Versions are immutable snapshots
- Can compare versions
- Can cherry-pick files between versions

**Workflow**:
```bash
# List organization versions
ifmos versions list

# Compare two versions
ifmos versions diff --from v1 --to v2

# Restore from version
ifmos versions restore --version v1

# Cherry-pick files
ifmos versions cherry-pick --version v2 --paths "path/to/file.pdf"
```

## Implementation Plan

### Phase 1: Staging System (Priority 1)

**Files to create**:
1. `ifmos/core/staging.py` - Staging manager
2. `ifmos/core/validation.py` - Validation engine
3. `ifmos/cli.py` - Add `stage` command group

**Database changes**:
```sql
CREATE TABLE staging_plans (
    plan_id TEXT PRIMARY KEY,
    created_at TIMESTAMP,
    session_id TEXT,
    staging_root TEXT,
    target_root TEXT,
    status TEXT, -- draft, staged, validated, committed, discarded
    method TEXT  -- symlink, copy, hardlink
);

CREATE TABLE staging_actions (
    action_id INTEGER PRIMARY KEY,
    plan_id TEXT,
    source_path TEXT,
    staging_path TEXT,
    target_path TEXT,
    action_type TEXT,
    status TEXT, -- pending, staged, validated, committed, failed
    validation_errors TEXT,
    conflict_type TEXT,
    resolution_strategy TEXT
);

CREATE TABLE conflict_resolutions (
    resolution_id INTEGER PRIMARY KEY,
    action_id INTEGER,
    conflict_type TEXT,
    strategy TEXT,
    resolved_path TEXT,
    resolved_at TIMESTAMP
);
```

### Phase 2: Enhanced Rollback (Priority 2)

**Files to create**:
1. `ifmos/core/rollback.py` - Rollback manager
2. `ifmos/core/snapshots.py` - Snapshot manager

**Database changes**:
```sql
CREATE TABLE rollback_log (
    log_id INTEGER PRIMARY KEY,
    plan_id TEXT,
    action_id INTEGER,
    before_state TEXT,  -- JSON with file metadata
    after_state TEXT,   -- JSON with file metadata
    rolled_back INTEGER DEFAULT 0,
    rollback_timestamp TIMESTAMP
);

CREATE TABLE snapshots (
    snapshot_id TEXT PRIMARY KEY,
    created_at TIMESTAMP,
    snapshot_type TEXT, -- before_migration, after_migration, scheduled
    plan_id TEXT,
    root_path TEXT,
    file_count INTEGER,
    total_size INTEGER,
    manifest_path TEXT  -- JSON file with complete state
);
```

### Phase 3: Conflict Resolution (Priority 3)

**Files to update**:
1. `ifmos/core/staging.py` - Add conflict detection
2. `ifmos/core/conflict_resolver.py` - NEW: Conflict resolution engine
3. `ifmos/cli.py` - Add `resolve` subcommand

### Phase 4: Validation Engine (Priority 4)

**Files to create**:
1. `ifmos/core/validation.py` - Complete validation system
2. `ifmos/core/validators/` - Individual validators
   - `path_validator.py`
   - `permission_validator.py`
   - `space_validator.py`
   - `classification_validator.py`

## CLI Enhancements

### New Commands

```bash
# Staging workflow
ifmos stage create --session <id> --output ~/Organized [--method symlink]
ifmos stage preview --plan <plan-id> [--open]
ifmos stage validate --plan <plan-id> [--report output.json]
ifmos stage resolve --plan <plan-id> [--interactive] [--strategy rename]
ifmos stage commit --plan <plan-id> [--snapshot]
ifmos stage discard --plan <plan-id>

# Rollback
ifmos rollback list [--limit 10]
ifmos rollback preview --plan <plan-id>
ifmos rollback execute --plan <plan-id> [--dry-run]
ifmos rollback restore --snapshot <snapshot-id>
ifmos rollback files --ids <file-id>,<file-id>

# Validation
ifmos validate path --path "~/Organized/Documents/file.pdf"
ifmos validate plan --plan <plan-id> [--fix-auto]
ifmos validate session --session <session-id>

# Versioning
ifmos versions list
ifmos versions diff --from v1 --to v2
ifmos versions restore --version v1
ifmos versions snapshot --name "before-cleanup"

# Configuration
ifmos config set conflict_strategy=rename
ifmos config set staging_method=symlink
ifmos config set validation_level=strict
ifmos config set auto_snapshot=true
```

## User Experience Flow

### Typical Workflow

```bash
# 1. Scan inbox
$ ifmos scan --roots ~/00_Inbox
Session: 20241203-140530-abc1

# 2. Classify with ML
$ ifmos classify --session 20241203-140530-abc1 --cascade local_only
Classified 1,245 files (avg confidence: 87.3%)

# 3. Create staging plan
$ ifmos stage create --session 20241203-140530-abc1 --output ~/Organized
Staging plan created: stage-20241203-140531-xyz2
  - 1,245 files to organize
  - 342 duplicates detected
  - 12 conflicts found

# 4. Preview staging (opens file explorer)
$ ifmos stage preview --plan stage-20241203-140531-xyz2 --open
Opening staging directory in file explorer...

# 5. Validate staging
$ ifmos stage validate --plan stage-20241203-140531-xyz2
Validation results:
  ✓ All source files readable
  ✓ Target paths writable
  ✓ Sufficient disk space (1.2 GB required, 150 GB available)
  ✗ 3 path length violations (Windows 260 char limit)
  ✗ 5 invalid filename characters
  ℹ 12 conflicts requiring resolution

# 6. Fix validation issues
$ ifmos stage fix --plan stage-20241203-140531-xyz2 --auto
Fixed 8 validation issues:
  - Shortened 3 long paths
  - Sanitized 5 filenames

12 conflicts still require resolution

# 7. Resolve conflicts interactively
$ ifmos stage resolve --plan stage-20241203-140531-xyz2 --interactive
Conflict 1/12:
  Source: ~/00_Inbox/report.pdf
  Target: ~/Organized/Documents/Work/report.pdf
  Issue: Target already exists (different content)

  Options:
    [1] Rename new file (report_1.pdf)
    [2] Replace existing
    [3] Keep both (ask for names)
    [4] Skip this file

  Choice: 1

  [Conflict resolved: rename]

[... continues for all conflicts ...]

# 8. Final validation
$ ifmos stage validate --plan stage-20241203-140531-xyz2
✓ All validation checks passed
Ready to commit 1,245 files

# 9. Commit staging (creates snapshot)
$ ifmos stage commit --plan stage-20241203-140531-xyz2 --snapshot
Creating snapshot before commit...
Snapshot created: snap-20241203-140545-def3

Committing 1,245 files...
Progress: [████████████████████████████████] 100% (1245/1245)

✓ Migration complete
  - 1,245 files organized
  - 342 duplicates quarantined
  - Snapshot: snap-20241203-140545-def3

To rollback: ifmos rollback execute --plan stage-20241203-140531-xyz2

# 10. Verify organization
$ ifmos report --session 20241203-140530-abc1 --format html
Report generated: reports/report-20241203-140546.html

# If needed: Rollback
$ ifmos rollback preview --plan stage-20241203-140531-xyz2
Rollback would restore 1,245 files to inbox

$ ifmos rollback execute --plan stage-20241203-140531-xyz2
Rolling back...
✓ Restored 1,245 files to original locations
✓ Removed organized structure
```

## Benefits

1. **Safety**: Preview before commit, easy rollback
2. **Flexibility**: Multiple resolution strategies
3. **Confidence**: Validation catches issues early
4. **Reversibility**: Granular rollback at any level
5. **Transparency**: Clear visibility into what will happen
6. **Space-efficient**: Hardlinks for snapshots
7. **Fast**: Symlinks for staging (no copies)
8. **Professional**: Production-grade workflow

## Next Steps

1. Implement staging system (Phase 1)
2. Add enhanced rollback (Phase 2)
3. Build conflict resolution (Phase 3)
4. Complete validation engine (Phase 4)
5. Test with real-world inbox scenarios
6. Document user workflows
7. Create tutorial videos
