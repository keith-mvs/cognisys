# CogniSys Architecture Documentation

A comprehensive technical reference for the CogniSys system architecture, including component design, data flows, interaction patterns, and foundational concepts.

---

## Table of Contents

1. [Introduction](#introduction)
2. [System Overview](#system-overview)
3. [Core Design Principles](#core-design-principles)
4. [Component Architecture](#component-architecture)
5. [Data Model](#data-model)
6. [Processing Pipeline](#processing-pipeline)
7. [Extension Points](#extension-points)
8. [Security Model](#security-model)
9. [Performance Characteristics](#performance-characteristics)

---

## Introduction

CogniSys (Cognitive File Organization System) is an intelligent file management platform designed to analyze, classify, deduplicate, and reorganize large-scale file repositories. The system employs a combination of rule-based heuristics and machine learning to automate document classification while maintaining strict safety guarantees through non-destructive operations and comprehensive audit trails.

### Purpose

CogniSys addresses three fundamental challenges in digital file management:

1. **Discovery**: Understanding what files exist across distributed storage locations
2. **Classification**: Automatically categorizing files by type, content, and purpose
3. **Organization**: Restructuring file hierarchies according to configurable policies

### Target Use Cases

| Use Case | Description |
|----------|-------------|
| Personal Organization | Consolidating scattered documents across local drives, cloud storage, and devices |
| Enterprise Data Management | Auditing network drives for redundancy, enforcing retention policies |
| Digital Asset Management | Organizing media libraries with version control and metadata enrichment |
| Development Workflow | Cleaning build artifacts, archiving legacy projects |

---

## System Overview

### High-Level Architecture

CogniSys employs a pipeline-based architecture where data flows through sequential processing stages:

```
                                    CogniSys System Architecture
+-------------------------------------------------------------------------------------------+
|                                                                                           |
|  +------------------+     +------------------+     +------------------+                   |
|  |   SOURCE LAYER   |     |  PROCESSING      |     |   OUTPUT LAYER   |                  |
|  |                  |     |    PIPELINE      |     |                  |                  |
|  |  Local Files     |     |                  |     |  HTML Reports    |                  |
|  |  Network Shares  |---->|  Scanner ------> |---->|  JSON Exports    |                  |
|  |  Cloud Storage   |     |  Analyzer -----> |     |  CSV Data        |                  |
|  |  (Mounted/API)   |     |  Classifier ---> |     |  Reorganized     |                  |
|  |                  |     |  Migrator        |     |    Repository    |                  |
|  +------------------+     +------------------+     +------------------+                   |
|           |                        |                        |                            |
|           v                        v                        v                            |
|  +-----------------------------------------------------------------------------------+   |
|  |                          PERSISTENCE LAYER                                        |   |
|  |                                                                                   |   |
|  |   +----------------+    +----------------+    +------------------+                |   |
|  |   | File Registry  |    | Migration      |    | Classification   |               |   |
|  |   | (SQLite)       |    | Plans/Actions  |    | Models (ML)      |               |   |
|  |   +----------------+    +----------------+    +------------------+                |   |
|  |                                                                                   |   |
|  +-----------------------------------------------------------------------------------+   |
|                                                                                           |
+-------------------------------------------------------------------------------------------+
```

### Component Interaction Flow

```
User Command                    System Response
     |                               |
     v                               |
+----------+                         |
|   CLI    |<------------------------+
+----------+
     |
     | (1) Parse options, load config
     v
+------------+
| Controller |
+------------+
     |
     | (2) Initialize components
     +----------------------------------------+
     |                |                       |
     v                v                       v
+----------+    +-----------+           +-----------+
| Scanner  |    | Analyzer  |           | Migrator  |
+----------+    +-----------+           +-----------+
     |                |                       |
     | (3) Process    | (4) Detect            | (6) Execute
     |    files       |    patterns           |    plan
     v                v                       v
+----------------------------------------------------------+
|                      Database Layer                       |
|                                                           |
|  files | folders | sources | duplicate_groups | plans    |
+----------------------------------------------------------+
                              |
                              | (5) Generate
                              v
                        +-----------+
                        | Reporter  |
                        +-----------+
```

---

## Core Design Principles

CogniSys architecture adheres to five foundational principles:

### 1. Safety First

All operations are designed to be non-destructive by default:

- **Dry-run Preview**: Every migration plan can be previewed before execution
- **Explicit Approval**: Plans require explicit user approval before execution
- **Quarantine Pattern**: Duplicates are moved to staging areas, never deleted immediately
- **Checkpoint Rollback**: JSON-based checkpoints enable recovery from failed operations
- **Audit Trail**: Every file operation is logged with timestamp, source, and reason

### 2. Progressive Processing

Operations are optimized to minimize unnecessary computation:

- **Progressive Hashing**: Quick hash (first 1MB) filters 99% of non-duplicates; full hash only on matches
- **Batch Processing**: Files are processed in configurable batches to manage memory
- **Incremental Scanning**: Only changed files are re-indexed on subsequent runs
- **Lazy Content Extraction**: Document content is extracted only when classification requires it

### 3. Configuration-Driven Behavior

All behavior is customizable without code changes:

- **YAML Configuration**: Human-readable configuration files for all settings
- **Template Variables**: Path templates support variables like `{YYYY}`, `{ProjectName}`
- **Rule Priorities**: Classification rules are ordered by priority score
- **Extension Points**: New file types, cloud providers, and report formats can be added via configuration

### 4. Multi-Source Abstraction

Unified interface across diverse storage backends:

- **Abstract Interfaces**: `FileSource` and `FileDestination` ABCs define common operations
- **Source Registry**: Central registry manages multiple configured sources
- **Provider Independence**: Processing logic is decoupled from storage implementation
- **Transparent Access**: Cloud files appear as local files to the processing pipeline

### 5. Observable Operations

All system activities are traceable and measurable:

- **Structured Logging**: JSON-formatted logs with severity levels
- **Progress Tracking**: Real-time progress updates during long operations
- **Statistics Collection**: Comprehensive metrics on classifications, confidence scores
- **Session Management**: All operations are grouped into auditable sessions

---

## Component Architecture

### Storage Layer (`cognisys/storage/`)

The storage layer abstracts file system operations across different backends.

#### Interfaces (`interfaces.py`)

```python
# Core Abstract Base Classes

class FileSource(ABC):
    """Read operations from any storage backend"""
    - source_type: str        # Identifier (e.g., 'local', 'onedrive')
    - root_path: str          # Base path for this source
    - walk()                  # os.walk compatible directory traversal
    - list_directory()        # List files/folders in path
    - get_metadata()          # Get FileMetadata for single file
    - read_stream()           # Binary stream for file content
    - read_bytes()            # Read file as bytes
    - exists(), is_file(), is_directory()

class FileDestination(ABC):
    """Write operations to any storage backend"""
    - write_stream()          # Write binary stream to file
    - write_bytes()           # Write bytes to file
    - mkdir()                 # Create directory
    - move(), copy(), delete()
    - exists()

class SyncableSource(FileSource, FileDestination):
    """Bidirectional sync operations"""
    - get_changes_since()     # Delta query for changed files
    - upload(), download()    # Transfer between local and remote
    - get_sync_token()        # Continuation token for delta queries
```

#### Data Structures

```python
@dataclass
class FileMetadata:
    """Common file information across all sources"""
    path: str                 # Full path (relative or absolute)
    name: str                 # Filename only
    size_bytes: int           # File size
    created_at: datetime      # Creation timestamp
    modified_at: datetime     # Modification timestamp
    mime_type: str            # MIME type (guessed from extension)
    source_type: str          # Source identifier
    is_placeholder: bool      # True for cloud placeholders
    content_hash: str         # Content hash if available
    extra: Dict[str, Any]     # Provider-specific metadata

@dataclass
class FolderMetadata:
    """Folder information with statistics"""
    path: str
    name: str
    depth: int                # Depth from root
    file_count: int           # Files in folder
    total_size_bytes: int     # Cumulative size

@dataclass
class ChangeRecord:
    """Record of file change for sync operations"""
    path: str
    change_type: ChangeType   # CREATED, MODIFIED, DELETED, RENAMED
    modified_at: datetime
    old_path: str             # For renames
```

#### Implementations

| Class | Module | Description |
|-------|--------|-------------|
| `LocalFileSource` | `local.py` | Local filesystem operations using `pathlib` |
| `OneDriveSource` | `onedrive.py` | Microsoft Graph API integration |
| `SourceRegistry` | `interfaces.py` | Central registry for all sources |

### Cloud Integration (`cognisys/cloud/`)

Cloud integration provides detection, authentication, and synchronization with cloud storage providers.

#### Detection (`detection.py`)

```python
class CloudFolderDetector:
    """Auto-detect mounted cloud storage folders"""

    Supported Providers:
    - OneDrive: C:\Users\{user}\OneDrive
    - Google Drive: G:\My Drive or C:\Users\{user}\Google Drive
    - iCloud: C:\Users\{user}\iCloudDrive
    - Proton Drive: C:\Users\{user}\Proton Drive

    Methods:
    - detect_all() -> List[CloudFolder]
    - detect_onedrive() -> Optional[CloudFolder]
    - detect_google_drive() -> Optional[CloudFolder]
    - detect_icloud() -> Optional[CloudFolder]
    - detect_proton_drive() -> Optional[CloudFolder]
```

#### Authentication (`auth/`)

```python
# Token Storage (token_storage.py)
class SecureTokenStorage:
    """Encrypted token storage using system keyring + Fernet"""

    Features:
    - Uses system keyring for secure storage
    - Fernet encryption for token data
    - Automatic token refresh handling

    Methods:
    - store_token(provider, token_data)
    - get_token(provider) -> Optional[dict]
    - delete_token(provider)
    - is_token_valid(provider) -> bool

# OneDrive Authentication (onedrive_auth.py)
class OneDriveAuthenticator:
    """OneDrive OAuth 2.0 via MSAL"""

    Auth Flows:
    - Interactive (browser-based)
    - Device Code (headless environments)

    Scopes:
    - Files.Read (read-only mode)
    - Files.ReadWrite (full access mode)
```

#### Synchronization (`sync.py`)

```python
class SyncManager:
    """Bidirectional sync between sources"""

    Configuration:
    @dataclass
    class SyncConfig:
        direction: SyncDirection  # PULL, PUSH, BIDIRECTIONAL
        dry_run: bool
        conflict_resolution: str  # 'newer', 'local', 'remote'
        exclude_patterns: List[str]

    Operations:
    - pull(remote_path, local_path) -> SyncStats
    - push(local_path, remote_path) -> SyncStats
    - sync(remote_path, local_path) -> SyncStats

    @dataclass
    class SyncStats:
        files_scanned: int
        files_downloaded: int
        files_uploaded: int
        files_skipped: int
        files_conflicted: int
        errors: List[str]
```

### Core Processing Engines (`cognisys/core/`)

#### Scanner (`scanner.py`)

The scanner traverses file systems and builds a comprehensive index.

```python
class FileScanner:
    """Multi-threaded file system scanner"""

    Architecture:
    - ThreadPoolExecutor with configurable worker count
    - Lock-protected statistics aggregation
    - Batch database commits (default: 100 files)

    Configuration Options:
    - threads: int (default: 8)
    - batch_size: int (default: 100)
    - exclusion_patterns: List[str]
    - max_file_size: int (skip large files)
    - follow_symlinks: bool

    Processing Pipeline:
    1. Directory Traversal (os.walk compatible)
    2. Exclusion Pattern Filtering
    3. Metadata Extraction (size, timestamps, MIME)
    4. Progressive Hashing
       - Quick hash: SHA-256 of first 1MB
       - Full hash: On-demand for duplicate candidates
    5. Database Persistence (batch inserts)

    Output:
    - Session ID: YYYYMMDD-HHMMSS-xxxx
    - Statistics: files_scanned, folders_scanned, total_size, errors
```

#### Analyzer (`analyzer.py`)

The analyzer detects duplicates and identifies patterns using a multi-stage pipeline.

```python
class Analyzer:
    """4-stage deduplication pipeline"""

    Pipeline Stages:

    Stage 1: Pre-filter
    +-------------------------------------------+
    | Group files by (size + extension)         |
    | Filter groups with only 1 file            |
    | Output: Candidate groups for hashing      |
    +-------------------------------------------+

    Stage 2: Quick Hash
    +-------------------------------------------+
    | Calculate SHA-256 of first 1MB            |
    | Group by quick hash                       |
    | Filter groups with only 1 file            |
    | Output: Probable duplicate groups         |
    +-------------------------------------------+

    Stage 3: Full Hash
    +-------------------------------------------+
    | Calculate full file SHA-256               |
    | Verify exact matches                      |
    | Create duplicate groups in database       |
    | Output: Confirmed duplicate groups        |
    +-------------------------------------------+

    Stage 4: Fuzzy Matching (optional)
    +-------------------------------------------+
    | Normalize filenames (remove (1), Copy)    |
    | Calculate Levenshtein similarity          |
    | Identify near-duplicates                  |
    | Output: Similar file suggestions          |
    +-------------------------------------------+

    Canonical Selection Algorithm:

    Each file in a duplicate group receives a priority score:
    - Modification date (newest): +10
    - Preferred path match: +20
    - Path depth (shorter): +10
    - Filename quality: +5 (avoid "copy", "backup", "(1)")
    - Access frequency: +15 (max)

    Highest scoring file becomes the canonical version.
```

#### Classifier (`classifier.py`)

The classifier categorizes files using ML models and rule-based heuristics.

```python
class MLClassifier:
    """ML-based document classification"""

    Model Options:
    - distilbert_v2: DistilBERT fine-tuned (96.7% accuracy)
    - distilbert_v1: Original DistilBERT model
    - rule_based: Pattern matching only
    - cascade_*: Multi-stage cascade classifier

    Cascade Presets:
    - default: Rule-based -> DistilBERT -> NVIDIA NIM
    - fast: Rule-based only
    - accurate: DistilBERT -> NVIDIA NIM -> Manual review
    - local_only: No external API calls

    Processing:
    1. Content Extraction (PDF, DOCX, images via OCR)
    2. Feature Engineering (TF-IDF, embeddings)
    3. Classification (category + confidence score)
    4. Low-confidence routing (manual review queue)

    Output per file:
    - document_type: str (e.g., 'financial_invoice')
    - confidence: float (0.0-1.0)
    - classification_method: str ('ml_model', 'pattern', 'manual')
```

#### Migrator (`migrator.py`)

The migrator plans and executes file reorganization with safety guarantees.

```python
class MigrationPlanner:
    """Generate migration plans from structure templates"""

    Input:
    - Session ID (scanned files)
    - Structure configuration (YAML template)

    Planning Process:
    1. Load files from session
    2. Apply classification rules
    3. Generate target paths from templates
    4. Detect conflicts (same target path)
    5. Create plan in database

    Plan Structure:
    - plan_id: Unique identifier
    - actions: List of (source, target, action_type, reason)
    - status: pending, approved, executing, completed, failed

class MigrationExecutor:
    """Execute approved migration plans"""

    Safety Mechanisms:
    - Approval check (plan.approved = True)
    - Checkpoint creation before execution
    - Batch execution with progress tracking
    - Conflict resolution (rename, overwrite, skip)
    - Automatic rollback on errors

    Execution Flow:
    1. Validate plan approval
    2. Create rollback checkpoint
    3. Execute actions in batches
    4. Update audit trail
    5. Handle errors (rollback or continue)

    Rollback Data:
    - Original path
    - New path
    - Timestamp
    - Checksum verification
```

#### Reporter (`reporter.py`)

The reporter generates insights and visualizations from analysis results.

```python
class Reporter:
    """Multi-format report generation"""

    Output Formats:

    HTML Report:
    - Interactive dashboard
    - Storage distribution charts
    - Duplicate analysis visualization
    - Searchable file table
    - Actionable recommendations

    JSON Export:
    - Machine-readable structure
    - Full metadata included
    - Suitable for automation

    CSV Export:
    - File inventory listing
    - Spreadsheet compatible
    - Custom field selection

    Generated Insights:
    - Storage concentration (top folders by size)
    - Duplication impact (wasted space)
    - File age distribution
    - Category breakdown
    - Recommended actions
```

### Machine Learning (`cognisys/ml/`)

#### Classification Pipeline

```
                        ML Classification Pipeline
+-------------------------------------------------------------------------+
|                                                                         |
|   Input File                                                            |
|       |                                                                 |
|       v                                                                 |
|   +-------------------+                                                 |
|   | Content Extractor |                                                 |
|   +-------------------+                                                 |
|       |                                                                 |
|       | Text content                                                    |
|       v                                                                 |
|   +-------------------+     +-------------------+     +---------------+ |
|   | Rule-Based        |---->| DistilBERT       |---->| NVIDIA NIM    | |
|   | Classifier        |     | Classifier        |     | (optional)    | |
|   +-------------------+     +-------------------+     +---------------+ |
|       |                          |                         |            |
|       | High confidence?         | High confidence?        |            |
|       v                          v                         v            |
|   [category, conf]          [category, conf]          [category, conf]  |
|                                                                         |
|                     Cascade Selection Logic                             |
|                     (first high-confidence wins)                        |
|                                                                         |
+-------------------------------------------------------------------------+
```

#### Model Components

| Component | Module | Description |
|-----------|--------|-------------|
| `PatternClassifier` | `utils/pattern_classifier.py` | 40+ rule-based patterns |
| `DistilBERTClassifier` | `ml/classification/distilbert_classifier.py` | Fine-tuned transformer |
| `CascadeClassifier` | `ml/classification/cascade_classifier.py` | Multi-model orchestrator |
| `NVIDIAClassifier` | `ml/classification/nvidia_classifier.py` | NVIDIA NIM API |
| `ContentExtractor` | `ml/utils/content_extractor.py` | PDF, DOCX, OCR extraction |

---

## Data Model

### Database Schema

CogniSys uses SQLite for persistence. The schema consists of interconnected tables:

```sql
-- Core file registry
CREATE TABLE file_registry (
    file_id INTEGER PRIMARY KEY,

    -- Provenance
    original_path TEXT NOT NULL,
    drop_timestamp TEXT NOT NULL,
    content_hash TEXT NOT NULL,

    -- Current location
    canonical_path TEXT,
    canonical_state TEXT,  -- 'classified', 'pending', 'review'

    -- Classification
    document_type TEXT,
    confidence REAL,
    classification_method TEXT,

    -- Tracking
    move_count INTEGER DEFAULT 0,
    last_moved TEXT,
    requires_review BOOLEAN DEFAULT 0,
    is_duplicate BOOLEAN DEFAULT 0,
    duplicate_of INTEGER REFERENCES file_registry(file_id)
);

-- Source configuration
CREATE TABLE sources (
    source_id TEXT PRIMARY KEY,
    source_name TEXT UNIQUE,
    source_type TEXT,      -- 'local', 'network', 'cloud_mounted', 'cloud_api'
    provider TEXT,         -- 'onedrive', 'google_drive', 'icloud'
    path TEXT,
    scan_mode TEXT,        -- 'auto', 'manual'
    priority INTEGER,
    is_active BOOLEAN
);

-- Authenticated cloud providers
CREATE TABLE cloud_providers (
    provider_id TEXT PRIMARY KEY,
    provider_type TEXT,
    account_name TEXT,
    account_email TEXT,
    last_auth_at TEXT,
    is_active BOOLEAN
);

-- Duplicate detection results
CREATE TABLE duplicate_groups (
    group_id TEXT PRIMARY KEY,
    canonical_file_id INTEGER REFERENCES file_registry(file_id),
    detection_method TEXT,
    member_count INTEGER,
    total_size INTEGER
);

-- Migration planning
CREATE TABLE migration_plans (
    plan_id TEXT PRIMARY KEY,
    session_id TEXT,
    created_at TEXT,
    approved BOOLEAN DEFAULT 0,
    executed_at TEXT,
    status TEXT
);

CREATE TABLE migration_actions (
    action_id INTEGER PRIMARY KEY,
    plan_id TEXT REFERENCES migration_plans(plan_id),
    source_path TEXT,
    target_path TEXT,
    action_type TEXT,      -- 'move', 'copy', 'delete', 'archive'
    reason TEXT,
    file_size INTEGER,
    status TEXT,
    rollback_data TEXT     -- JSON for undo
);
```

### Entity Relationships

```
+------------------+       +-------------------+
|   file_registry  |<----->|  duplicate_groups |
+------------------+       +-------------------+
        |
        |  belongs to
        v
+------------------+       +-------------------+
|     sources      |       | cloud_providers   |
+------------------+       +-------------------+

+------------------+       +-------------------+
| migration_plans  |<----->| migration_actions |
+------------------+       +-------------------+
```

---

## Processing Pipeline

### Standard Workflow

```
1. SCAN
   cognisys scan --roots "C:\Documents" --roots "D:\Projects"

   Output: Session ID (e.g., 20251209-140000-abc1)

2. ANALYZE
   cognisys analyze --session 20251209-140000-abc1

   Output: Duplicate groups detected

3. CLASSIFY (optional)
   cognisys classify --session 20251209-140000-abc1 --model distilbert_v2

   Output: Files categorized with confidence scores

4. REPORT
   cognisys report --session 20251209-140000-abc1 --format html

   Output: reports/20251209-140000-abc1_report.html

5. PLAN
   cognisys plan --session 20251209-140000-abc1 --structure config/new_structure.yml

   Output: Plan ID (e.g., plan-20251209-150000-xyz2)

6. PREVIEW
   cognisys dry-run --plan plan-20251209-150000-xyz2

   Output: Sample actions without modification

7. APPROVE
   cognisys approve --plan plan-20251209-150000-xyz2

8. EXECUTE
   cognisys execute --plan plan-20251209-150000-xyz2

   Output: Files reorganized, audit trail created
```

### Data Flow Diagram

```
+-------------+
| File System |
+-------------+
      |
      | (files, metadata)
      v
+-------------+     +----------------+
|   Scanner   |---->|   Database     |
+-------------+     | (file_registry)|
                    +----------------+
                           |
                           v
+-------------+     +----------------+
|  Analyzer   |<----|   Database     |
+-------------+     | (dup_groups)   |
      |             +----------------+
      v
+-------------+     +----------------+
| Classifier  |---->|   Database     |
+-------------+     | (doc_type,     |
                    |  confidence)   |
                    +----------------+
                           |
                           v
+-------------+     +----------------+
|  Reporter   |<----|   Database     |
+-------------+     +----------------+
      |
      v
+-------------+
|   Reports   |
| (HTML/JSON) |
+-------------+

+-------------+     +----------------+
|   Planner   |---->| migration_plan |
+-------------+     +----------------+
                           |
                           v
+-------------+     +----------------+
|  Executor   |<----| migration_     |
+-------------+     |    actions     |
      |             +----------------+
      v
+-------------+
| Reorganized |
| Repository  |
+-------------+
```

---

## Extension Points

### Adding New Cloud Providers

1. Implement `FileSource` interface:

```python
class NewProviderSource(FileSource):
    @property
    def source_type(self) -> str:
        return "new_provider"

    def walk(self, path: str = '') -> Iterator[Tuple[str, List[str], List[str]]]:
        # Implement directory traversal
        pass

    def get_metadata(self, path: str) -> FileMetadata:
        # Return file metadata
        pass

    # ... implement remaining methods
```

2. Add detection logic to `CloudFolderDetector`
3. Add authentication handler if needed
4. Register CLI commands in `commands/cloud.py`

### Adding New Classification Categories

1. Update `cognisys/config/new_structure.yml`:

```yaml
classification:
  new_category:
    extensions: [".xyz", ".abc"]
    target: "Documents/{category}/{YYYY}"
    priority: 100
```

2. Add patterns to `PatternClassifier` (optional):

```python
PatternRule(
    name="new_category",
    document_type="new_category",
    extension_patterns=[r"\.xyz$", r"\.abc$"],
    priority=100
)
```

3. Retrain ML model with new category examples (for ML classification)

### Adding New Report Formats

1. Add method to `Reporter` class:

```python
def generate_markdown(self, session_id: str, output_path: str):
    """Generate Markdown report"""
    # Implementation
    pass
```

2. Register format in CLI:

```python
@click.option('--format', multiple=True,
              type=click.Choice(['html', 'json', 'csv', 'markdown']))
```

---

## Security Model

### Authentication

- **OAuth 2.0**: Cloud providers use standard OAuth flows
- **Token Storage**: Encrypted via system keyring + Fernet
- **Scope Limitations**: Read-only mode available for safer operations

### Data Protection

- **Local Processing**: No data leaves the system except for explicit cloud sync
- **Path Sanitization**: User-provided paths are validated
- **Symlink Control**: Configurable symlink following to prevent attacks

### Access Control

- **Permission Handling**: Graceful degradation on access errors
- **Audit Trail**: All operations logged with user, timestamp, and reason
- **Rollback Capability**: Every change can be undone

---

## Performance Characteristics

### Scanning Performance

| Metric | Typical Value | Notes |
|--------|---------------|-------|
| Files/second | 500-2000 | Depends on disk speed |
| Optimal threads | 4-8 | Beyond 8 diminishing returns |
| Memory usage | ~100MB + 1KB/file | Linear with file count |
| Database batch size | 100 files | Configurable |

### Hashing Performance

| File Size | Quick Hash | Full Hash |
|-----------|------------|-----------|
| < 1MB | N/A | ~1ms |
| 1-10MB | ~1ms | ~10ms |
| 10-100MB | ~1ms | ~100ms |
| > 100MB | ~1ms | ~1s+ |

### Classification Performance

| Model | Speed | Accuracy | GPU Required |
|-------|-------|----------|--------------|
| Rule-based | ~10,000/s | 80% | No |
| DistilBERT | ~100/s | 96.7% | Optional |
| NVIDIA NIM | ~50/s | 98%+ | No (API) |

### Optimization Strategies

1. **For Large Repositories (>100K files)**:
   - Increase thread count to 16
   - Enable incremental scanning
   - Split into multiple sessions

2. **For Limited Memory**:
   - Reduce batch size to 50
   - Disable fuzzy matching
   - Use rule-based classification only

3. **For Slow Networks**:
   - Use mounted cloud folders instead of API
   - Enable placeholder detection
   - Schedule syncs during off-peak hours

---

## Glossary

| Term | Definition |
|------|------------|
| **Canonical File** | The authoritative version of a duplicate set |
| **Quick Hash** | SHA-256 hash of first 1MB of file |
| **Full Hash** | SHA-256 hash of entire file content |
| **Session** | A single scan operation with unique ID |
| **Plan** | A set of migration actions awaiting approval |
| **Source** | A configured storage location (local/cloud) |
| **Placeholder** | Cloud file that exists remotely but not downloaded locally |
2
---

**Version:** 3.0.0
**Last Updated:** 2024-12-09
**Maintainer:** CogniSys Development Team
