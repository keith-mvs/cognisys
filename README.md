# IFMOS - Intelligent File Management and Organization System

A comprehensive, automation-friendly system for analyzing, deduplicating, and reorganizing large-scale file repositories with minimal human intervention and maximum safety.

## Features

### 🔍 Comprehensive File Analysis
- Multi-threaded scanning of local, network, and cloud-mounted drives
- Rich metadata extraction (size, timestamps, MIME types, access patterns)
- Progressive hashing strategy (quick hash for pre-filtering, full hash for verification)
- SQLite-based indexing for fast queries and analysis

### 🔄 Smart Deduplication
- **Multi-stage detection pipeline:**
  1. Fast pre-filtering by size and extension
  2. Quick hash matching (first 1MB)
  3. Full content verification (SHA-256)
  4. Fuzzy filename matching for near-duplicates
- Intelligent canonical file selection based on configurable priorities
- Safe quarantine approach (move to staging area, not immediate deletion)

### 📊 Detailed Reporting
- Interactive HTML reports with statistics and insights
- JSON exports for automation and integration
- CSV exports for spreadsheet analysis
- Automatic insight generation and recommendations
- Visualizations of storage distribution, duplicates, and trends

### 🗂️ Repository Optimization
- Template-based target structure design
- Flexible classification rules by file type
- Standardized naming conventions
- Lifecycle management (active → archive → cold storage)
- Backward compatibility with optional symlinks

### 🚀 Safe Migration
- Dry-run preview before execution
- Batch processing with progress tracking
- Checkpoint-based rollback capability
- Full audit trail with detailed logging
- Conflict resolution and error handling

## Installation

### Requirements
- Python 3.10 or higher
- Windows, macOS, or Linux

### Install from source

```bash
git clone https://github.com/FleithFeming/IFMOS.git
cd IFMOS
pip install -r requirements.txt
pip install -e .
```

### Verify installation

```bash
ifmos --help
```

## Quick Start

### 1. Scan Your File System

```bash
ifmos scan --roots "C:\Users\Documents" --roots "C:\Projects"
```

This creates a session and indexes all files with metadata and hashes.

**Output:**
```
[SUCCESS] Scan completed!
  Session ID: 20251120-143022-a8f3
  Files scanned: 12,453
  Folders scanned: 1,234
  Total size: 45.20 GB
```

### 2. Analyze for Duplicates

```bash
ifmos analyze --session 20251120-143022-a8f3
```

Runs the deduplication pipeline and identifies patterns.

**Output:**
```
[SUCCESS] Analysis complete!
  Duplicate groups: 1,048
  Duplicate files: 6,219
  Wasted space: 28.40 GB
```

### 3. Generate Reports

```bash
ifmos report --session 20251120-143022-a8f3 --format html --format json --format csv
```

Creates comprehensive reports in multiple formats.

**Outputs:**
- `reports/20251120-143022-a8f3_report.html` - Interactive dashboard
- `reports/20251120-143022-a8f3_report.json` - Machine-readable data
- `reports/files_inventory.csv` - Full file listing

### 4. Create Migration Plan

```bash
ifmos plan --session 20251120-143022-a8f3 --structure ifmos/config/new_structure.yml
```

Generates a migration plan based on target structure.

**Output:**
```
[SUCCESS] Migration plan created!
  Plan ID: plan-20251120-150000-x9a2

Actions by type:
  move: 38,456 files (120.50 GB)
  archive: 2,345 files (3.20 GB)
```

### 5. Preview Changes (Dry Run)

```bash
ifmos dry-run --plan plan-20251120-150000-x9a2
```

Shows sample actions without making any changes.

**Output:**
```
[PREVIEW] Sample actions:

1. MOVE: C:\Users\Documents\Report (1).docx
   TO: C:\Repository\Quarantine\Duplicates_2025-11-20\Report (1).docx
   REASON: Duplicate (group dup-a8f3c1d2)

2. MOVE: C:\Users\Downloads\client_data.xlsx
   TO: C:\Repository\Active\Projects\ProjectA\Data\2025-10-20_ProjectA_ClientData_v01.xlsx
   REASON: Reorganize to code structure

[INFO] Total actions: 40,801
[INFO] Total data: 123.70 GB
```

### 6. Approve and Execute

```bash
# Approve the plan
ifmos approve --plan plan-20251120-150000-x9a2

# Execute the migration
ifmos execute --plan plan-20251120-150000-x9a2
```

Executes the migration with full audit logging and rollback capability.

## Configuration

### Scan Configuration

Edit `ifmos/config/scan_config.yml` to customize:

- Root paths to scan
- Exclusion patterns (e.g., `*.tmp`, `node_modules`)
- Threading and performance settings
- Hashing strategy
- Access tracking options

### Analysis Rules

Edit `ifmos/config/analysis_rules.yml` to configure:

- Duplicate detection thresholds
- Canonical file selection priorities
- Orphaned file criteria
- Preferred paths for keeping files

### Target Structure

Edit `ifmos/config/new_structure.yml` to define:

- Repository organization (Active, Archive, Reference, etc.)
- File classification rules by type
- Naming conventions
- Lifecycle policies

## Command Reference

### Scanning

```bash
ifmos scan --roots <path1> --roots <path2> [options]

Options:
  --config PATH        Scan configuration file
  --db PATH           Database path (default: db/ifmos.db)
  --session-id TEXT   Custom session ID
```

### Analysis

```bash
ifmos analyze --session <session-id> [options]

Options:
  --rules PATH        Analysis rules file
  --db PATH           Database path
```

### Reporting

```bash
ifmos report --session <session-id> [options]

Options:
  --output PATH       Output directory (default: reports)
  --format FORMAT     Output format(s): html, json, csv (multiple allowed)
  --db PATH           Database path
```

### Migration Planning

```bash
ifmos plan --session <session-id> [options]

Options:
  --structure PATH    Target structure config
  --output TEXT       Plan ID (auto-generated if not provided)
  --db PATH           Database path
```

### Execution

```bash
# Preview changes
ifmos dry-run --plan <plan-id>

# Approve plan
ifmos approve --plan <plan-id>

# Execute migration
ifmos execute --plan <plan-id>

Options:
  --db PATH           Database path
```

### Utilities

```bash
# List all scan sessions
ifmos list-sessions

# Show help for any command
ifmos <command> --help
```

## Architecture

### Components

```
IFMOS
├─ Scanning Engine     → Multi-threaded file traversal and indexing
├─ Analysis Engine     → Deduplication and pattern detection
├─ Reporting Engine    → Statistics, insights, and visualizations
├─ Migration Planner   → Rule-based reorganization planning
└─ Migration Executor  → Safe execution with rollback support
```

### Data Flow

```
1. Scan → Index files with metadata and hashes
2. Analyze → Detect duplicates and patterns
3. Report → Generate insights and recommendations
4. Plan → Create migration strategy
5. Execute → Apply changes with safety checks
```

### Database Schema

SQLite database with tables for:
- **files** - File metadata and hashes
- **folders** - Folder hierarchy and stats
- **duplicate_groups** - Duplicate sets with canonical selection
- **duplicate_members** - Individual duplicates with priority scores
- **scan_sessions** - Scan metadata and configuration
- **migration_plans** - Reorganization plans
- **migration_actions** - Individual file operations

## Safety Features

### Non-Destructive by Default
- Dry-run preview before any changes
- Explicit approval required for execution
- Duplicates moved to quarantine, not deleted
- Audit trail for all operations

### Rollback Capability
- Checkpoint creation before execution
- JSON-based rollback data
- Automatic rollback on errors
- Manual rollback support

### Error Handling
- Graceful handling of permission errors
- Conflict resolution for naming collisions
- Batch processing with retry logic
- Detailed error logging

## Use Cases

### Personal File Organization
- Consolidate scattered documents and media
- Eliminate duplicate photos and downloads
- Organize by project or date
- Archive old files

### Enterprise Data Management
- Audit network drives for redundancy
- Standardize naming conventions
- Implement retention policies
- Reclaim storage space

### Digital Asset Management
- Organize media libraries
- Version control for documents
- Metadata enrichment
- Searchable archives

### Development Workflow
- Organize code repositories
- Clean up build artifacts
- Manage dependencies
- Archive legacy projects

## Advanced Features

### Extensible Classification
Add custom file categories and rules in configuration files.

### Custom Naming Conventions
Define templates with variables like `{YYYY-MM-DD}_{ProjectName}_{Version}`.

### Lifecycle Management
Automate transitions: Active → Archive → Cold Storage based on access patterns.

### Integration Ready
JSON exports and SQLite database enable integration with other tools and scripts.

## Troubleshooting

### Large File Systems
- Increase thread count in config for faster scanning
- Use incremental scans to update existing indexes
- Split very large scans across multiple sessions

### Permission Errors
- Run with appropriate privileges for network drives
- Check exclusion patterns to skip system folders
- Review error logs for specific access issues

### Memory Usage
- Adjust batch size in configuration
- Use checkpoint intervals for long-running scans
- Close and reopen database connections periodically

## Performance Tips

1. **Scanning:** Use 4-8 threads for balanced performance
2. **Hashing:** Skip very large files (>10GB) or disable full hashing
3. **Analysis:** Enable fuzzy matching only when needed (expensive)
4. **Migration:** Execute during off-peak hours for large operations

## Contributing

Contributions are welcome! Areas for enhancement:

- [ ] Web-based dashboard UI
- [ ] Cloud storage integration (S3, Azure, GCP)
- [ ] Machine learning for smarter classification
- [ ] Multi-user collaboration features
- [ ] Real-time monitoring and alerting

## License

[Add your license here]

## Support

For issues, questions, or feature requests:
- Create an issue in the repository
- Review logs in `logs/` directory
- Check configuration files for syntax errors

## Acknowledgments

Built with Python, SQLite, Click, and PyYAML.

---

**IFMOS** - Bringing order to digital chaos.
