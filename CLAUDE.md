# CLAUDE.md

This file provides guidance to Claude Code when working with the IFMOS codebase.

## Overview

IFMOS (Intelligent File Management and Organization System) is a Python-based CLI tool for scanning, analyzing, deduplicating, and reorganizing large file repositories. The system uses SQLite for persistence and follows a session-based workflow architecture.

## Quick Start

```bash
# Install
pip install -e .

# Basic workflow
ifmos scan --roots <path>
ifmos analyze --session <session-id>
ifmos report --session <session-id> --format html

# See README.md for full command reference
```

## Architecture Overview

### Core Components
```
CLI (cli.py)
  ├─ FileScanner (core/scanner.py)    - Multi-threaded file traversal & indexing
  ├─ Analyzer (core/analyzer.py)      - 4-stage deduplication pipeline
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
- `ifmos/cli.py`: Click-based CLI with all commands
- Defined in `setup.py`: `ifmos=ifmos.cli:main`

### Core Engines (~1500 lines)
- `core/scanner.py` (285 lines): ThreadPoolExecutor-based scanning
- `core/analyzer.py` (322 lines): Multi-stage deduplication
- `core/reporter.py` (398 lines): Report generation
- `core/migrator.py` (499 lines): Planning and execution

### Data Layer
- `models/database.py` (395 lines): SQLite schema and CRUD operations

### Utilities
- `utils/hashing.py`: Hash calculation functions
- `utils/naming.py`: Filename normalization
- `utils/logging_config.py`: Structured logging

## Development Workflow

### Adding New File Categories
1. Edit `ifmos/config/new_structure.yml` → add to `classification:`
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
- No tests implemented yet
- CLI-only (no web UI)

## Testing

Testing framework not yet implemented. When adding tests:
```
tests/
  unit/         - Component-level tests
  integration/  - End-to-end workflows
  fixtures/     - Sample files and configs
```

Key areas: Progressive hashing, canonical selection, rollback recovery, config validation.

## Future Enhancements

See README.md for planned features:
- Web dashboard
- Cloud storage integration
- ML-based classification
- Distributed scanning
- Real-time monitoring
