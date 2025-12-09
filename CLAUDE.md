# CLAUDE.md

This file provides guidance to Claude Code when working with the CogniSys codebase.

## Overview

CogniSys (formerly IFMOS - Intelligent File Management and Organization System) is a Python-based CLI tool for scanning, analyzing, deduplicating, and reorganizing large file repositories. The system uses SQLite for persistence and follows a session-based workflow architecture.

## Quick Start

```bash
# Install
pip install -e .
pip install msal keyring cryptography  # For cloud support

# Basic workflow
cognisys scan --roots <path>
cognisys analyze --session <session-id>
cognisys report --session <session-id> --format html

# Cloud integration
cognisys cloud detect                    # Find mounted cloud folders
cognisys source list                     # List configured sources
cognisys cloud auth --provider onedrive  # Authenticate (requires client ID)

# See README.md for full command reference
```

## Architecture Overview

### Core Components
```
CLI (cli.py)
  ├─ Storage Layer (storage/)
  │     ├─ interfaces.py              - FileSource/FileDestination ABCs
  │     ├─ local.py                   - LocalFileSource implementation
  │     └─ onedrive.py                - OneDriveSource (Microsoft Graph API)
  ├─ Cloud Integration (cloud/)
  │     ├─ detection.py               - Auto-detect mounted cloud folders
  │     ├─ sync.py                    - Two-way SyncManager
  │     └─ auth/                      - OAuth authentication
  │           ├─ token_storage.py     - Encrypted token storage (keyring)
  │           └─ onedrive_auth.py     - OneDrive OAuth via MSAL
  ├─ FileScanner (core/scanner.py)    - Multi-threaded file traversal & indexing
  ├─ Analyzer (core/analyzer.py)      - 4-stage deduplication pipeline
  ├─ ML Classifier (ml/)              - DistilBERT document classification
  ├─ Reporter (core/reporter.py)      - HTML/JSON/CSV report generation
  └─ Migrator (core/migrator.py)      - Safe file reorganization with rollback
```

### Session-Based Workflow
Every scan creates a unique `session_id` (format: `YYYYMMDD-HHMMSS-xxxx`):
```
scan_roots() → Session ID
  → Files indexed in SQLite
  → analyze_session() → Duplicate Groups
  → generate_report() → Outputs
  → create_plan() → Migration Plan
  → execute_plan() → Safe execution with rollback
```

### Database Schema (SQLite)
- **files**: File metadata, hashes (quick + full), categorization
- **folders**: Hierarchy and statistics
- **sources**: Configured source library (local, network, cloud)
- **cloud_providers**: Authenticated cloud provider credentials
- **scan_history**: Per-source scan tracking
- **duplicate_groups**: Canonical file selection
- **duplicate_members**: Priority scoring
- **scan_sessions**: Session metadata
- **migration_plans**: Reorganization plans
- **migration_actions**: File operations with rollback data

### Configuration System (4 Layers)
1. `default_config.yml`: Base defaults
2. `scan_config.yml`: Scanning parameters
3. `analysis_rules.yml`: Deduplication rules
4. `new_structure.yml`: Target structure templates

Edit YAML files to customize behavior without code changes.

## Key Design Patterns

### Progressive Hashing
- **Quick hash** (SHA-256 of first 1MB): Fast pre-filter
- **Full hash** (entire file): Only on matches
- Small files (<1MB): Full hash directly
- Balances speed vs accuracy

### 4-Stage Deduplication Pipeline
1. Pre-filter: Group by size + extension
2. Quick hash: Match first 1MB
3. Full hash: Verify exact duplicates
4. Fuzzy match: Similarity scoring

### Canonical Selection
Weighted scoring system:
- Modification date (newest +10)
- Preferred paths (+20)
- Path depth (shorter +10)
- Filename quality (+5)
- Access frequency (+15 max)

Highest score becomes canonical.

### Checkpoint-Based Rollback
- Creates JSON checkpoint before migration
- Stores in `migration_actions.rollback_data`
- Enables recovery on failure
- Lightweight vs full snapshots

## Code Organization

### Entry Point
- `cognisys/cli.py`: Click-based CLI with all commands
- `cognisys/commands/source.py`: Source management commands
- `cognisys/commands/cloud.py`: Cloud integration commands
- Defined in `setup.py`: `cognisys=cognisys.cli:main`

### Storage Layer
- `storage/interfaces.py`: FileSource, FileDestination, SyncableSource ABCs
- `storage/local.py`: LocalFileSource for filesystem operations
- `storage/onedrive.py`: OneDriveSource with Microsoft Graph API

### Cloud Integration
- `cloud/detection.py`: CloudFolderDetector for OneDrive, Google Drive, iCloud, Proton
- `cloud/ondemand.py`: Windows Files On-Demand handling
- `cloud/sync.py`: SyncManager for bidirectional cloud sync
- `cloud/auth/token_storage.py`: Secure token storage (keyring + Fernet)
- `cloud/auth/onedrive_auth.py`: OneDrive OAuth via MSAL

### Core Engines
- `core/scanner.py`: ThreadPoolExecutor-based scanning
- `core/analyzer.py`: Multi-stage deduplication
- `core/reporter.py`: Report generation
- `core/migrator.py`: Planning and execution

### ML Classification
- `ml/classifier.py`: DistilBERT-based document classifier
- `ml/training/`: Model training scripts
- Models stored in `~/.cognisys/models/`

### Data Layer
- `models/database.py`: SQLite schema and CRUD operations
- `models/migrations/`: Database migrations

### Utilities
- `utils/hashing.py`: Hash calculation functions
- `utils/naming.py`: Filename normalization
- `utils/logging_config.py`: Structured logging

## Development Workflow

### Adding New File Categories
1. Edit `cognisys/config/new_structure.yml` → add to `classification:`
2. Update `FileScanner._categorize_file()` if custom logic needed
3. Add target path template with variables: `{YYYY}`, `{ProjectName}`

### Custom Deduplication Rules
1. Implement detector in `Analyzer` class
2. Add configuration to `analysis_rules.yml`
3. Integrate into pipeline in `analyze_session()`

### New Report Formats
1. Add method to `Reporter` class
2. Implement format-specific output
3. Register in CLI options

## Important Implementation Details

### Threading
- Uses `ThreadPoolExecutor` (default: 8 workers)
- Lock-protected statistics
- Graceful error handling per file

### Database Transactions
- Scanner: Batch inserts every 100 files
- Analyzer: Wraps pipeline stages in transactions
- Migrator: Transactions per action batch
- Always commit/rollback explicitly

### Path Handling
- Uses `pathlib.Path` for cross-platform compatibility
- Converts to strings for database storage
- Always resolve absolute paths

### Error Handling Philosophy
- **Scanner**: Log and continue (graceful degradation)
- **Analyzer**: Halt on database errors
- **Reporter**: Best-effort partial reports
- **Migrator**: Rollback on any error

## Known Limitations

- Single-machine only (no distributed scanning)
- Batch-oriented (no real-time monitoring)
- Memory scaling: Large file systems (>100k files) may need tuning
- CLI-only (no web UI)
- OneDrive API requires Azure AD app registration

## Testing

Testing framework not yet implemented. When adding tests:
```
tests/
  unit/         - Component-level tests
  integration/  - End-to-end workflows
  fixtures/     - Sample files and configs
```

Key areas: Progressive hashing, canonical selection, rollback recovery, config validation, cloud sync.

## Recent Enhancements (Dec 2024)

- **Cloud Storage Integration**: OneDrive, Google Drive, iCloud, Proton Drive detection
- **Multi-Source Library**: Configure sources across local, network, and cloud storage
- **OneDrive Native API**: Direct integration via Microsoft Graph API
- **Two-Way Sync**: Pull from cloud, classify, push organized files back
- **ML Classification**: DistilBERT v2 with 96.7% accuracy on 77k+ files
- **Secure Auth**: OAuth 2.0 with encrypted token storage

## Future Enhancements

See README.md for planned features:
- Web dashboard
- Google Drive native API support
- Additional cloud providers (S3, Azure Blob)
- Distributed scanning
- Real-time monitoring
