# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

IFMOS (Intelligent File Management and Organization System) is a Python-based CLI tool for scanning, analyzing, deduplicating, and reorganizing large file repositories. The system uses SQLite for persistence and follows a session-based workflow architecture.

## Essential Commands

### Installation & Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Install in development mode
pip install -e .

# Verify installation
ifmos --help
```

### Testing
```bash
# Run tests (when implemented)
pytest tests/

# Run with coverage
pytest --cov=ifmos tests/
```

### Development Workflow
```bash
# Try the example script
python example_usage.py

# Test a command directly
ifmos scan --roots "C:\TestDir" --db "db/test.db"
ifmos analyze --session <session-id> --db "db/test.db"
ifmos report --session <session-id> --format html --db "db/test.db"
```

### Common CLI Operations
```bash
# Full workflow
ifmos scan --roots <path1> --roots <path2>
ifmos analyze --session <session-id>
ifmos report --session <session-id> --format html --format json
ifmos plan --session <session-id> --structure ifmos/config/new_structure.yml
ifmos dry-run --plan <plan-id>
ifmos approve --plan <plan-id>
ifmos execute --plan <plan-id>

# List all sessions
ifmos list-sessions
```

## Architecture Overview

### Core Components
```
CLI (cli.py)
  ├─ FileScanner (core/scanner.py)    - Multi-threaded file traversal & indexing
  ├─ Analyzer (core/analyzer.py)      - 4-stage deduplication pipeline
  ├─ Reporter (core/reporter.py)      - HTML/JSON/CSV report generation
  └─ Migrator (core/migrator.py)      - Safe file reorganization with rollback
      ├─ MigrationPlanner             - Create action plans
      └─ MigrationExecutor            - Execute plans with checkpoints
```

### Data Flow Pattern
```
Session-Based Workflow:
  scan_roots() → creates Session ID
  → Files indexed in SQLite
  → analyze_session() → creates Duplicate Groups
  → generate_report() → HTML/JSON/CSV outputs
  → create_plan() → Migration Plan + Actions
  → execute_plan() → Updates files with rollback capability
```

### Database Schema (SQLite)
- **files**: File metadata, hashes (quick + full), categorization, flags
- **folders**: Hierarchy and statistics
- **duplicate_groups**: Canonical file selection with members
- **duplicate_members**: Priority scoring for canonicals
- **scan_sessions**: Session metadata and configuration snapshots
- **migration_plans**: Reorganization plans with approval status
- **migration_actions**: Individual file operations with rollback data

All tables indexed on critical fields (paths, hashes, sizes, timestamps).

### Configuration System (4 Layers)
1. **default_config.yml**: Base defaults (exclusions, threads, thresholds)
2. **scan_config.yml**: Scanning parameters (roots, exclusions, threading)
3. **analysis_rules.yml**: Deduplication rules (thresholds, canonical priorities)
4. **new_structure.yml**: Target repository structure (classification, naming templates)

Configs are YAML-based and loaded at runtime. Edit these files to customize behavior without code changes.

## Key Design Patterns

### Progressive Hashing
- **Quick hash** (SHA-256 of first 1MB): Fast pre-filter
- **Full hash** (entire file): Only calculated on matches
- Small files (<1MB) use full hash directly
- Adaptive strategy balances speed vs accuracy

### 4-Stage Deduplication Pipeline
1. Pre-filter: Group by size + extension
2. Quick hash: Match first 1MB
3. Full hash: Verify exact duplicates
4. Fuzzy match: Similarity scoring on normalized filenames

### Canonical Selection (Weighted Scoring)
Priority-based system considering:
- Modification date (newest +10)
- Preferred paths (+20 bonus)
- Path depth (shorter +10)
- Filename quality (+5 for descriptive)
- Access frequency (+15 max)

Highest score becomes canonical; others marked as duplicates.

### Session-Based Architecture
Every scan creates a unique `session_id` (format: `YYYYMMDD-HHMMSS-xxxx`). All downstream operations reference this session, enabling:
- Resumable workflows
- Incremental updates
- Audit trails
- Multiple concurrent analyses

### Checkpoint-Based Rollback
Before migration execution:
- Creates JSON checkpoint with rollback data
- Stores in `migration_actions.rollback_data` (database)
- Enables recovery if issues occur
- Lightweight vs full filesystem snapshots

## Code Organization

### Entry Point
- `ifmos/cli.py`: Click-based CLI with all commands (scan, analyze, report, plan, execute)
- Entry point defined in `setup.py`: `ifmos=ifmos.cli:main`

### Core Engines (~1500 lines)
- `core/scanner.py` (285 lines): ThreadPoolExecutor-based scanning, metadata extraction
- `core/analyzer.py` (322 lines): Multi-stage deduplication, pattern detection
- `core/reporter.py` (398 lines): Report generation with insights
- `core/migrator.py` (499 lines): Planning and execution with safety mechanisms

### Data Layer
- `models/database.py` (395 lines): SQLite schema, CRUD operations, session management

### Utilities
- `utils/hashing.py`: `calculate_quick_hash()`, `calculate_full_hash()`, `calculate_adaptive_hash()`
- `utils/naming.py`: `normalize_filename()`, `apply_naming_convention()`, `sanitize_name()`
- `utils/logging_config.py`: Structured logging setup

## Working with Components

### Adding New File Categories
1. Edit `ifmos/config/new_structure.yml` → add to `classification:` section
2. Update `FileScanner._categorize_file()` if custom logic needed
3. Add target path template with variables like `{YYYY}`, `{ProjectName}`

### Custom Deduplication Rules
1. Implement detector method in `Analyzer` class
2. Add configuration to `analysis_rules.yml`
3. Integrate into multi-stage pipeline in `analyze_session()`

### New Report Formats
1. Add method to `Reporter` class (e.g., `_generate_xml()`)
2. Implement format-specific output
3. Register in CLI: `@click.option('--format', type=click.Choice([..., 'xml']))`

### Programmatic Usage
```python
from ifmos.models.database import Database
from ifmos.core.scanner import FileScanner
from ifmos.core.analyzer import Analyzer
import yaml

# Load config
with open('ifmos/config/scan_config.yml') as f:
    config = yaml.safe_load(f)

# Initialize
db = Database('db/mydb.db')
scanner = FileScanner(db, config)

# Scan
session_id = scanner.scan_roots(['C:\\MyFiles'])
stats = scanner.get_stats()

# Analyze
analyzer = Analyzer(db, analysis_rules)
analysis_stats = analyzer.analyze_session(session_id)

# Query results directly
cursor = db.conn.cursor()
cursor.execute("SELECT * FROM duplicate_groups WHERE session_id = ?", (session_id,))
```

## Important Implementation Notes

### Threading in Scanner
- Uses `ThreadPoolExecutor` with configurable worker count (default: 8)
- Main thread coordinates; workers process files in parallel
- Lock-protected statistics (`self.stats_lock`)
- Graceful error handling per file (doesn't crash on permission errors)

### Database Transactions
- Scanner uses batch inserts every 100 files for performance
- Analyzer wraps pipeline stages in transactions
- Migrator uses transactions per action batch
- Always commit/rollback explicitly

### Configuration Loading
All engines expect pre-loaded YAML dicts. Pattern:
```python
with open(config_path) as f:
    config = yaml.safe_load(f)
engine = Engine(db, config)
```

### Path Handling
- Uses `pathlib.Path` for cross-platform compatibility
- Converts to strings for database storage
- Windows paths: Handle drive letters correctly
- Always resolve absolute paths

### Error Handling Philosophy
- **Scanner**: Log errors, continue scanning (graceful degradation)
- **Analyzer**: Strict - halt on database errors
- **Reporter**: Best-effort - generate partial reports if needed
- **Migrator**: Strict - rollback on any execution error

## Testing Strategy (To Be Implemented)

Recommended structure:
```
tests/
  unit/         - Component-level tests (scanner, analyzer, etc.)
  integration/  - End-to-end workflow tests
  fixtures/     - Sample files and configs for testing
```

Key areas to test:
- Progressive hashing correctness
- Canonical selection scoring
- Migration rollback recovery
- Configuration loading and validation
- Database schema integrity

## Known Limitations

- **Single-machine**: No distributed scanning (network drives mounted only)
- **No real-time monitoring**: Batch-oriented workflows only
- **Memory scaling**: Large file systems (>100k files) may need batch size tuning
- **No tests**: Testing framework not yet implemented
- **CLI-only**: No web UI (documented as future enhancement)

## Future Enhancement Areas

See `README.md` for planned features:
- Web dashboard UI
- Cloud storage integration (S3, Azure, GCP)
- ML-based classification
- Distributed scanning for enterprise scale
- Real-time monitoring
