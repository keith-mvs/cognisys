# IFMOS Architecture Documentation

This document provides a detailed architectural overview of the Intelligent File Management and Organization System (IFMOS).

## Table of Contents

1. [System Overview](#system-overview)
2. [Component Architecture](#component-architecture)
3. [Data Model](#data-model)
4. [Workflow Patterns](#workflow-patterns)
5. [Design Decisions](#design-decisions)
6. [Extensibility](#extensibility)

## System Overview

IFMOS is designed as a modular, pipeline-based system for large-scale file management with the following principles:

- **Safety First:** Non-destructive operations, dry-run previews, rollback capability
- **Performance:** Multi-threaded scanning, progressive hashing, batch processing
- **Flexibility:** Template-based configuration, rule-driven classification
- **Auditability:** Comprehensive logging, audit trails, checkpoint system

### High-Level Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     IFMOS Architecture                        │
└──────────────────────────────────────────────────────────────┘

┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│   Scanning   │─────▶│   Analysis   │─────▶│  Reporting   │
│    Engine    │      │    Engine    │      │    Engine    │
└──────────────┘      └──────────────┘      └──────────────┘
       │                     │                      │
       ▼                     ▼                      ▼
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│  File Index  │      │  Rules &     │      │   Report     │
│  Database    │      │  Policies    │      │   Outputs    │
└──────────────┘      └──────────────┘      └──────────────┘
       │                     │
       └──────────┬──────────┘
                  ▼
           ┌──────────────┐
           │  Migration   │
           │    Engine    │
           └──────────────┘
                  │
                  ▼
           ┌──────────────┐
           │  New Repo    │
           │  Structure   │
           └──────────────┘
```

## Component Architecture

### 1. Scanning Engine (`core/scanner.py`)

**Responsibility:** Traverse file systems and build comprehensive index.

**Key Features:**
- Multi-threaded directory traversal
- Configurable exclusion patterns
- Progressive hashing (quick hash → full hash on demand)
- Metadata extraction (size, timestamps, MIME types)
- Incremental scanning support

**Design Pattern:** Producer-Consumer with thread pool

```python
ThreadPoolExecutor
    └─ Worker threads process files in parallel
    └─ Main thread coordinates and checkpoints
    └─ Lock-protected statistics aggregation
```

### 2. Analysis Engine (`core/analyzer.py`)

**Responsibility:** Detect duplicates and identify patterns.

**Multi-Stage Pipeline:**

```
Stage 1: Pre-filter
    └─ Group by (size + extension)
    └─ Filter candidates

Stage 2: Quick Hash
    └─ Calculate first 1MB hash
    └─ Narrow candidate groups

Stage 3: Full Hash
    └─ Verify exact duplicates
    └─ Create duplicate groups

Stage 4: Fuzzy Matching
    └─ Normalize filenames
    └─ Calculate similarity scores
    └─ Identify near-duplicates
```

**Canonical Selection:**
Priority-based scoring system considering:
- Modification date (newest preferred)
- Path location (preferred paths get bonus)
- Path depth (shorter paths preferred)
- Filename quality (avoid "copy", "backup", etc.)
- Access frequency (more accessed = higher priority)

### 3. Reporting Engine (`core/reporter.py`)

**Responsibility:** Generate insights and visualizations.

**Report Types:**
- **HTML:** Interactive dashboard with charts and tables
- **JSON:** Machine-readable data for automation
- **CSV:** Raw data exports for analysis

**Insight Generation:**
- Automatic pattern detection
- Storage concentration analysis
- Duplication impact assessment
- Actionable recommendations

### 4. Migration Engine (`core/migrator.py`)

**Responsibility:** Plan and execute file reorganization.

**Components:**

**MigrationPlanner:**
- Reads target structure configuration
- Applies classification rules
- Generates action list (move/copy/delete)
- Creates migration plan in database

**MigrationExecutor:**
- Validates plan approval
- Creates checkpoint for rollback
- Executes actions in batches
- Handles conflicts and errors
- Updates audit trail

**Safety Mechanisms:**
- Dry-run preview
- Explicit approval required
- Checkpoint-based rollback
- Conflict resolution
- Error recovery

## Data Model

### Core Entities

#### Files
- Metadata: path, name, size, timestamps
- Content: hashes (quick + full)
- Classification: category, MIME type
- Flags: is_duplicate, is_orphaned, is_temp
- Relationships: parent folder, duplicate group

#### Folders
- Hierarchy: path, parent, depth
- Statistics: total size, file count
- Metadata: timestamps, type

#### Duplicate Groups
- Canonical file selection
- Member list with priority scores
- Detection method and rules

#### Migration Plans
- Action list (source → target)
- Approval status
- Execution tracking
- Rollback data

### Database Schema Design

**SQLite** chosen for:
- Serverless deployment
- ACID compliance
- Complex query support
- Portability

**Indexes** on:
- File paths (for lookups)
- Hashes (for duplicate detection)
- Sizes (for pre-filtering)
- Timestamps (for lifecycle rules)

## Workflow Patterns

### Pattern 1: Scan → Analyze → Report

**Use Case:** Initial assessment

```
1. Scan file system
2. Detect duplicates
3. Generate insights
```

### Pattern 2: Scan → Analyze → Plan → Execute

**Use Case:** Full reorganization

```
1. Scan file system
2. Detect duplicates
3. Create migration plan
4. Dry-run preview
5. Approve plan
6. Execute migration
```

### Pattern 3: Incremental Updates

**Use Case:** Periodic maintenance

```
1. Load previous session
2. Incremental scan (only changed files)
3. Update analysis
4. Generate delta report
```

## Design Decisions

### 1. Progressive Hashing

**Decision:** Calculate quick hash (1MB) first, full hash only on matches

**Rationale:**
- Quick hash filters 99% of non-duplicates fast
- Full hash only for ~1% candidates
- Massive performance improvement for large files

### 2. Quarantine vs Delete

**Decision:** Move duplicates to quarantine folder

**Rationale:**
- User can review before permanent deletion
- Accidental misclassification is recoverable
- Audit trail preserved

### 3. SQLite over NoSQL

**Decision:** Use SQLite for structured storage

**Rationale:**
- Complex queries needed (JOINs, aggregations)
- ACID compliance for migration safety
- No server setup required
- Excellent Python integration

### 4. Checkpoint-based Rollback

**Decision:** JSON checkpoints vs full filesystem snapshots

**Rationale:**
- Lightweight and fast
- Sufficient for undo operations
- No disk space overhead
- Easy to inspect and debug

### 5. Template-based Structure

**Decision:** YAML configuration with variable templates

**Rationale:**
- User-customizable without code changes
- Supports diverse organizational schemes
- Version-controllable configuration
- Readable and maintainable

## Extensibility

### Adding New File Categories

1. Update `classification` in `new_structure.yml`
2. Add extensions and target path template
3. Optionally add category-specific logic in scanner

### Custom Deduplication Rules

1. Implement detector in `Analyzer` class
2. Add configuration in `analysis_rules.yml`
3. Create duplicate groups with custom type

### New Report Formats

1. Add method to `Reporter` class
2. Implement format-specific output
3. Register in CLI command

### Integration Points

**Database Access:**
```python
from ifmos.models.database import Database
db = Database('path/to/db.db')
```

**Programmatic Usage:**
```python
from ifmos.core import FileScanner, Analyzer
scanner = FileScanner(db, config)
session_id = scanner.scan_roots(paths)
```

**Custom Pipelines:**
Combine components in custom workflows using Python scripts.

## Performance Considerations

### Scanning
- **Bottleneck:** Disk I/O
- **Optimization:** Multi-threading (4-8 threads optimal)
- **Scaling:** Distribute across multiple machines for network drives

### Hashing
- **Bottleneck:** CPU for large files
- **Optimization:** Skip very large files, use quick hash
- **Scaling:** GPU acceleration possible for advanced use cases

### Analysis
- **Bottleneck:** Database queries for large datasets
- **Optimization:** Proper indexing, batch processing
- **Scaling:** Database partitioning or sharding

### Migration
- **Bottleneck:** File system operations
- **Optimization:** Batch moves, efficient conflict resolution
- **Scaling:** Parallel execution with coordination

## Security Considerations

1. **Permission Handling:** Graceful degradation on access errors
2. **Path Injection:** Sanitization of user-provided paths
3. **Symlink Attacks:** Configurable symlink following
4. **Data Privacy:** Local-only processing, no external calls

## Testing Strategy

- **Unit Tests:** Individual component testing
- **Integration Tests:** End-to-end workflow validation
- **Performance Tests:** Benchmarking on large datasets
- **Safety Tests:** Rollback and error recovery verification

## Future Enhancements

1. **Web Dashboard:** Browser-based UI for reports and control
2. **Cloud Integration:** Direct S3/Azure/GCP scanning
3. **ML Classification:** Smart categorization using machine learning
4. **Distributed Scanning:** Multi-node scanning for enterprise scale
5. **Real-time Monitoring:** Continuous file system watching

---

**Version:** 1.0.0
**Last Updated:** 2025-11-20
