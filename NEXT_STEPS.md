# IFMOS Next Steps - Architecture Implementation

**Date**: 2025-11-28
**Status**: Ready to implement

## ✅ Completed (Phases 1-4)

1. ✅ Content-based classification (36.3% accuracy baseline)
2. ✅ GPU acceleration enabled (RTX 2080 Ti, 2-5x speedup)
3. ✅ ML model trained (88.6% test accuracy, Random Forest)
4. ✅ Template filling prototype (dry-run exposed architecture issues)

## 🏗️ Architecture Redesign (NEW)

Comprehensive redesign document created: **`docs/ARCHITECTURE_REDESIGN_V2.md`**

### Key Changes

| Old System | New System |
|------------|------------|
| `Organized/`, `Organized_V2/`, etc. | Single `Organized_Canonical/` tree |
| No provenance tracking | `.ifmos/file_registry.db` tracks every file |
| No accuracy metrics | Explicit metrics: accuracy, stability, duplication |
| Each run creates new tree | Idempotent: runs refine in-place |
| No feedback loop | Manual corrections logged, model improves |

## 🎯 Implementation Roadmap

### Phase 1: Core Infrastructure (2-3 hours)

**Goal**: Set up new `.ifmos/` structure and database schema

#### Tasks:
1. **Create `.ifmos/` directory structure**
   ```bash
   mkdir -p .ifmos/logs .ifmos/snapshots
   ```

2. **Initialize `file_registry.db`**
   - Run: `./venv/Scripts/python.exe scripts/setup/init_ifmos_db.py`
   - Creates tables: `file_registry`, `move_history`, `classification_rules`, `manual_corrections`

3. **Create `ifmos` CLI wrapper**
   - Implement: `ifmos/cli_v2.py` with subcommands:
     - `ifmos init`
     - `ifmos register`
     - `ifmos classify`
     - `ifmos organize`
     - `ifmos correct`
     - `ifmos metrics`

4. **Test with 10 files**
   - Register 10 files from `00_Inbox/`
   - Classify them
   - Organize to test tree
   - Verify database records correct

**Validation**: Database has 10 rows in `file_registry`, `move_history` shows moves

---

### Phase 2: Consolidation Migration (1-2 hours)

**Goal**: Merge `Organized/` and `Organized_V2/` into `Organized_Canonical/`

#### Tasks:
1. **Create consolidation script**
   - Script: `scripts/migrations/consolidate_to_canonical.py`
   - Detects duplicates by content hash
   - Moves unique files to canonical tree
   - Logs all operations

2. **Run dry-run**
   ```bash
   ./venv/Scripts/python.exe scripts/migrations/consolidate_to_canonical.py --dry-run
   ```
   - Review what would happen
   - Check duplicate detection works

3. **Execute consolidation**
   ```bash
   ./venv/Scripts/python.exe scripts/migrations/consolidate_to_canonical.py --execute
   ```

4. **Verify no data loss**
   ```bash
   # Count files before vs after
   find ~/Documents/Organized/ -type f | wc -l
   find ~/Documents/Organized_V2/ -type f | wc -l
   find ~/Documents/Organized_Canonical/ -type f | wc -l

   # Should be: Canonical = V1 + V2 - duplicates
   ```

5. **Archive old trees** (DON'T delete yet)
   ```bash
   mv ~/Documents/Organized ~/Documents/_archived_Organized_20251128
   mv ~/Documents/Organized_V2 ~/Documents/_archived_Organized_V2_20251128
   ```

**Validation**: All files in canonical tree, database shows file provenance

---

### Phase 3: Classification Pipeline (1-2 hours)

**Goal**: End-to-end pipeline from inbox → canonical tree

#### Tasks:
1. **Implement `ifmos register`**
   - Scans drop directory (`C:\Users\kjfle\00_Inbox`)
   - Computes SHA-256 hashes
   - Detects duplicates
   - Inserts into `file_registry`

2. **Implement `ifmos classify`**
   - Loads trained ML model (`ifmos/models/trained/random_forest_classifier.pkl`)
   - Classifies pending files
   - Updates `document_type` and `confidence` fields
   - Flags low-confidence for review

3. **Implement `ifmos organize`**
   - Reads classified files from database
   - Applies path templates
   - Moves files to canonical locations
   - Logs moves to `move_history`

4. **Test complete pipeline**
   ```bash
   # Put 20 test files in inbox
   cp test_files/* ~/00_Inbox/

   # Run pipeline
   ifmos register --scan-drop
   ifmos classify --confidence-threshold 0.70
   ifmos organize --dry-run
   ifmos organize --execute

   # Verify files moved correctly
   ifmos status <file_path>  # Show file's journey
   ```

**Validation**: 20 files organized correctly, database has complete audit trail

---

### Phase 4: Accuracy Tracking (1 hour)

**Goal**: Implement metrics and feedback loop

#### Tasks:
1. **Implement `ifmos correct`**
   - User marks misclassified file
   - Logs to `manual_corrections` table
   - Updates file's `document_type`
   - Optionally triggers retraining

2. **Implement `ifmos metrics`**
   - Computes accuracy metrics (see `ARCHITECTURE_REDESIGN_V2.md` Part 3.2)
   - Generates JSON report
   - Displays summary to console

3. **Test correction flow**
   ```bash
   # Simulate user correcting a misclassification
   ifmos correct ~/Documents/Organized_Canonical/Financial/Invoices/wrong_file.pdf \
       --type personal_receipt \
       --reason "personal expense, not business"

   # Check metrics updated
   ifmos metrics --today
   ```

4. **Set up daily metrics**
   - Create cron job (or Windows Task Scheduler):
     ```bash
     # Run daily at 11:59 PM
     59 23 * * * cd ~/Projects/ifmos && ifmos metrics --report .ifmos/logs/metrics_$(date +\%Y-\%m-\%d).json
     ```

**Validation**: Metrics report shows classification accuracy, corrections tracked

---

### Phase 5: Idempotent Reorganization (1 hour)

**Goal**: Re-run classification on existing canonical tree without duplication

#### Tasks:
1. **Implement `ifmos reorg`**
   - Scans `Organized_Canonical/`
   - Syncs filesystem with database
   - Computes current vs. target paths
   - Moves files within canonical tree (no new tree)

2. **Test idempotency**
   ```bash
   # Run reorganization
   ifmos reorg --dry-run

   # Execute
   ifmos reorg --execute

   # Run again - should show "No changes needed"
   ifmos reorg --dry-run
   ```

3. **Test rule changes**
   - Edit `.ifmos/config.yml` to change a classification rule
   - Run `ifmos reorg --dry-run` to see what would move
   - Execute and verify files moved correctly

4. **Verify stability metric**
   ```bash
   # Check how many files moved multiple times
   ifmos metrics --stability
   # Should show low churn after initial organization
   ```

**Validation**: Re-running reorg is safe, no duplication, stability metric low

---

## 📊 Success Criteria

### Phase 1-2 Complete:
- [ ] `.ifmos/file_registry.db` exists with correct schema
- [ ] All files consolidated into `Organized_Canonical/`
- [ ] No duplicates (checked by hash)
- [ ] Old trees archived, not deleted

### Phase 3-4 Complete:
- [ ] End-to-end pipeline working: drop → register → classify → organize
- [ ] Database has complete audit trail (provenance, moves, corrections)
- [ ] Metrics command shows accuracy >85%

### Phase 5 Complete:
- [ ] Idempotent reorganization working (run twice, no changes second time)
- [ ] Rule changes trigger appropriate moves
- [ ] Stability metric shows low churn (<15% files moved >1 time)
- [ ] Daily metrics tracking automated

---

## 🚀 Quick Start Commands

```bash
# Phase 1: Initialize
./venv/Scripts/python.exe scripts/setup/init_ifmos_db.py
ifmos init --drop ~/00_Inbox --canonical ~/Documents/Organized_Canonical

# Phase 2: Consolidate existing trees
./venv/Scripts/python.exe scripts/migrations/consolidate_to_canonical.py --dry-run
./venv/Scripts/python.exe scripts/migrations/consolidate_to_canonical.py --execute

# Phase 3: Daily workflow
ifmos register --scan-drop       # Register new files
ifmos classify                   # Classify them
ifmos organize --execute         # Move to canonical locations

# Phase 4: Track accuracy
ifmos metrics --today            # View today's metrics
ifmos correct <file> --type X    # Correct misclassification

# Phase 5: Reorganize after rule changes
ifmos reorg --dry-run            # Preview changes
ifmos reorg --execute            # Apply changes in-place
```

---

## 📝 File Inventory

### Scripts to Create:
1. `scripts/setup/init_ifmos_db.py` - Initialize database schema
2. `scripts/migrations/consolidate_to_canonical.py` - Consolidation migration
3. `ifmos/cli_v2.py` - New CLI with all subcommands
4. `ifmos/metrics.py` - Accuracy metrics calculator
5. `scripts/cron/daily_metrics.sh` - Automated daily metrics

### Configuration Files:
1. `.ifmos/config.yml` - Main IFMOS configuration
2. `.ifmos/file_registry.db` - Provenance database (created by init script)

### Documentation:
1. ✅ `docs/ARCHITECTURE_REDESIGN_V2.md` - Complete architecture spec
2. ✅ `NEXT_STEPS.md` - This file (implementation guide)

---

## 🎯 Priority: Implement Phase 1 First

The first concrete step is to create the database initialization script. This unblocks everything else.

**Ready to proceed?** Let me know if you want me to:
1. Implement Phase 1 scripts now (`init_ifmos_db.py`, `ifmos init`)
2. Review the architecture design first
3. Something else?

The architecture is designed to be shell-friendly, measurable, and directly solves your three core problems. Let's build it!
