# CogniSys - Intelligent File Management and Organization System

A comprehensive, automation-friendly system for analyzing, deduplicating, and reorganizing large-scale file repositories with minimal human intervention and maximum safety.

## Features

### Comprehensive File Analysis
- Multi-threaded scanning of local, network, and cloud-mounted drives
- Rich metadata extraction (size, timestamps, MIME types, access patterns)
- Progressive hashing strategy (quick hash for pre-filtering, full hash for verification)
- SQLite-based indexing for fast queries and analysis

### Smart Deduplication
- **Multi-stage detection pipeline:**
  1. Fast pre-filtering by size and extension
  2. Quick hash matching (first 1MB)
  3. Full content verification (SHA-256)
  4. Fuzzy filename matching for near-duplicates
- Intelligent canonical file selection based on configurable priorities
- Safe quarantine approach (move to staging area, not immediate deletion)

### Detailed Reporting
- Interactive HTML reports with statistics and insights
- JSON exports for automation and integration
- CSV exports for spreadsheet analysis
- Automatic insight generation and recommendations
- Visualizations of storage distribution, duplicates, and trends

### Repository Optimization
- Template-based target structure design
- Flexible classification rules by file type
- Standardized naming conventions
- Lifecycle management (active -> archive -> cold storage)
- Backward compatibility with optional symlinks

### Safe Migration
- Dry-run preview before execution
- Batch processing with progress tracking
- Checkpoint-based rollback capability
- Full audit trail with detailed logging
- Conflict resolution and error handling

### Cloud Storage Integration
- **Multi-source library architecture:** Manage files across local drives, network shares, and cloud storage
- **Auto-detection:** Automatically find mounted OneDrive, Google Drive, iCloud, and Proton Drive folders
- **Native API support:** Direct integration with OneDrive via Microsoft Graph API
- **Two-way sync:** Pull files from cloud, classify them, push organized files back
- **Secure authentication:** OAuth 2.0 with encrypted token storage using system keyring

### ML-Powered Classification
- **DistilBERT v2 classifier:** Trained on 77k+ files with 96.7% accuracy
- **Automatic document classification:** Categorize files by content type
- **Confidence scoring:** Know when to trust automated decisions
- **Incremental learning:** Improve classification with user feedback

## Installation

### Requirements
- Python 3.10 or higher
- Windows, macOS, or Linux

### Install from source

```bash
git clone https://github.com/FleithFeming/cognisys-core.git
cd cognisys-core
pip install -r requirements.txt
pip install -e .
```

### Install cloud storage support (optional)

```bash
pip install msal keyring cryptography
```

### Verify installation

```bash
cognisys --help
```

## Quick Start

### 1. Scan Your File System

```bash
cognisys scan --roots "C:\Users\Documents" --roots "C:\Projects"
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
cognisys analyze --session 20251120-143022-a8f3
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
cognisys report --session 20251120-143022-a8f3 --format html --format json --format csv
```

Creates comprehensive reports in multiple formats.

**Outputs:**
- `reports/20251120-143022-a8f3_report.html` - Interactive dashboard
- `reports/20251120-143022-a8f3_report.json` - Machine-readable data
- `reports/files_inventory.csv` - Full file listing

### 4. Create Migration Plan

```bash
cognisys plan --session 20251120-143022-a8f3 --structure cognisys/config/new_structure.yml
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
cognisys dry-run --plan plan-20251120-150000-x9a2
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
cognisys approve --plan plan-20251120-150000-x9a2

# Execute the migration
cognisys execute --plan plan-20251120-150000-x9a2
```

Executes the migration with full audit logging and rollback capability.

## Configuration

### Scan Configuration

Edit `cognisys/config/scan_config.yml` to customize:

- Root paths to scan
- Exclusion patterns (e.g., `*.tmp`, `node_modules`)
- Threading and performance settings
- Hashing strategy
- Access tracking options

### Analysis Rules

Edit `cognisys/config/analysis_rules.yml` to configure:

- Duplicate detection thresholds
- Canonical file selection priorities
- Orphaned file criteria
- Preferred paths for keeping files

### Target Structure

Edit `cognisys/config/new_structure.yml` to define:

- Repository organization (Active, Archive, Reference, etc.)
- File classification rules by type
- Naming conventions
- Lifecycle policies

## Command Reference

### Scanning

```bash
cognisys scan --roots <path1> --roots <path2> [options]

Options:
  --config PATH        Scan configuration file
  --db PATH           Database path (default: db/cognisys.db)
  --session-id TEXT   Custom session ID
```

### Analysis

```bash
cognisys analyze --session <session-id> [options]

Options:
  --rules PATH        Analysis rules file
  --db PATH           Database path
```

### Reporting

```bash
cognisys report --session <session-id> [options]

Options:
  --output PATH       Output directory (default: reports)
  --format FORMAT     Output format(s): html, json, csv (multiple allowed)
  --db PATH           Database path
```

### Migration Planning

```bash
cognisys plan --session <session-id> [options]

Options:
  --structure PATH    Target structure config
  --output TEXT       Plan ID (auto-generated if not provided)
  --db PATH           Database path
```

### Execution

```bash
# Preview changes
cognisys dry-run --plan <plan-id>

# Approve plan
cognisys approve --plan <plan-id>

# Execute migration
cognisys execute --plan <plan-id>

Options:
  --db PATH           Database path
```

### Source Management

```bash
# List all configured sources
cognisys source list

# Add a local source
cognisys source add my_docs --type local --path "C:\Users\Documents"

# Add a cloud API source (requires authentication)
cognisys source add onedrive_docs --type cloud_api --provider onedrive --path /Documents

# Detect cloud folders automatically
cognisys source detect
cognisys source detect --add  # Add detected folders as sources

# Show source status
cognisys source status
```

### Cloud Integration

```bash
# Detect mounted cloud folders
cognisys cloud detect

# Authenticate with OneDrive
cognisys cloud auth --provider onedrive --client-id <your-client-id>
cognisys cloud auth --provider onedrive --device-code  # For headless environments

# Check cloud connection status
cognisys cloud status

# Sync files with cloud source
cognisys cloud sync <source_name> --direction pull
cognisys cloud sync <source_name> --direction push
cognisys cloud sync <source_name> --dry-run

# Log out from cloud providers
cognisys cloud logout
```

### File Reclassification

```bash
# Show classification statistics
cognisys reclassify stats

# Reclassify 'unknown' files using pattern matching
cognisys reclassify unknown                    # Dry run
cognisys reclassify unknown --execute          # Apply changes
cognisys reclassify unknown --verbose          # Show detailed output

# Reclassify NULL document_type files (patterns + ML)
cognisys reclassify null                       # Dry run
cognisys reclassify null --execute             # Apply changes
cognisys reclassify null --no-ml               # Patterns only
cognisys reclassify null --confidence 0.80     # Higher threshold

# Re-evaluate all files (full reclassification)
cognisys reclassify all --execute              # Requires confirmation

# Show files with low classification confidence
cognisys reclassify low-confidence --threshold 0.5 --limit 100

Options:
  --db PATH           Database path (default: .cognisys/file_registry.db)
  --execute           Apply changes (default is dry-run)
  --confidence FLOAT  Confidence threshold (default: 0.70)
  --use-ml/--no-ml    Enable/disable ML model fallback
  --batch-size INT    Batch size for updates (default: 100)
  --verbose, -v       Show detailed output
```

### Utilities

```bash
# List all scan sessions
cognisys list-sessions

# Show help for any command
cognisys <command> --help
```

## Architecture

### Components

```
CogniSys
├─ Storage Layer       -> Multi-source abstraction (local, network, cloud)
│   ├─ LocalFileSource     -> Local filesystem operations
│   ├─ OneDriveSource      -> Microsoft Graph API integration
│   └─ SyncManager         -> Two-way cloud synchronization
├─ Cloud Integration   -> Provider detection and authentication
│   ├─ CloudFolderDetector -> Auto-detect mounted cloud folders
│   └─ OAuth Authenticator -> Secure token management
├─ Scanning Engine     -> Multi-threaded file traversal and indexing
├─ Analysis Engine     -> Deduplication and pattern detection
├─ ML Classifier       -> DistilBERT-based document classification
├─ Reporting Engine    -> Statistics, insights, and visualizations
├─ Migration Planner   -> Rule-based reorganization planning
└─ Migration Executor  -> Safe execution with rollback support
```

### Multi-Source Architecture

```
+------------------------------------------------------------------+
|                      CogniSys Source Library                      |
+------------------------------------------------------------------+
|                                                                    |
|  LOCAL SOURCES              CLOUD SOURCES (Mounted)               |
|  +----------------+         +----------------+                    |
|  | Downloads      |         | OneDrive       |                    |
|  | Documents      |         | Google Drive   |                    |
|  | Projects       |         | iCloud         |                    |
|  +----------------+         +----------------+                    |
|                                                                    |
|  CLOUD SOURCES (API)        NETWORK SOURCES                       |
|  +----------------+         +----------------+                    |
|  | OneDrive API   |         | NAS/SMB        |                    |
|  | (coming soon)  |         | Network Share  |                    |
|  +----------------+         +----------------+                    |
|                                                                    |
+------------------------------------------------------------------+
                              |
                              v
                   +--------------------+
                   |  Unified Registry  |
                   |  (file_registry.db)|
                   +--------------------+
```

### Data Flow

```
1. Source Library -> Configure local, network, and cloud sources
2. Scan -> Index files with metadata and hashes from all sources
3. Analyze -> Detect duplicates and patterns across sources
4. Classify -> ML-powered document categorization
5. Report -> Generate insights and recommendations
6. Plan -> Create migration strategy
7. Execute -> Apply changes with safety checks
8. Sync -> Push organized files back to cloud (optional)
```

### Database Schema

SQLite database with tables for:
- **files** - File metadata and hashes
- **folders** - Folder hierarchy and stats
- **sources** - Configured source library (local, network, cloud)
- **cloud_providers** - Authenticated cloud provider credentials
- **scan_history** - Per-source scan tracking
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
Automate transitions: Active -> Archive -> Cold Storage based on access patterns.

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
- [x] Cloud storage integration (OneDrive, Google Drive, iCloud - mounted folder support)
- [x] Machine learning for smarter classification (DistilBERT v2 - 96.7% accuracy)
- [ ] Additional cloud providers (S3, Azure Blob, GCP)
- [ ] Multi-user collaboration features
- [ ] Real-time monitoring and alerting
- [ ] Google Drive native API support

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Documentation

Full documentation is available in the [docs/](docs/) directory:

- [Quick Start Guide](docs/getting-started/QUICKSTART.md) - Get started in 5 minutes
- [Architecture Overview](docs/architecture/OVERVIEW.md) - System design and components
- [CLI Reference](docs/reference/CLI_COMMANDS.md) - Complete command reference
- [Workflow Guide](docs/guides/WORKFLOW.md) - End-to-end processing

## Support

For issues, questions, or feature requests:
- Create an issue in the repository
- Review [documentation](docs/INDEX.md) for guides and references
- Review logs in `logs/` directory
- Check configuration files for syntax errors

## Acknowledgments

Built with Python, SQLite, Click, and PyYAML.

---

**CogniSys** - Bringing order to digital chaos.
