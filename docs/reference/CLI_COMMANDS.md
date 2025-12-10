# CogniSys CLI Command Reference

**Version:** 2.0.0
**Last Updated:** 2024-12-09

Complete reference for all CogniSys command-line interface commands.

> For usage examples and workflows, see the [User Guide](../guides/USER_GUIDE.md).
> For installation, see the [Setup Guide](../getting-started/SETUP_GUIDE.md).

## Table of Contents

- [Scanning](#scanning)
- [Analysis](#analysis)
- [Reporting](#reporting)
- [Migration Planning](#migration-planning)
- [Execution](#execution)
- [Source Management](#source-management)
- [Cloud Integration](#cloud-integration)
- [File Reclassification](#file-reclassification)
- [Utilities](#utilities)

---

## Scanning

Index files with metadata and hashes.

```bash
cognisys scan --roots <path1> --roots <path2> [options]

Options:
  --config PATH        Scan configuration file
  --db PATH           Database path (default: db/cognisys.db)
  --session-id TEXT   Custom session ID
```

**Example:**
```bash
cognisys scan --roots "C:\Users\Documents" --roots "C:\Projects"
```

**Output:**
```
[SUCCESS] Scan completed!
  Session ID: 20251120-143022-a8f3
  Files scanned: 12,453
  Folders scanned: 1,234
  Total size: 45.20 GB
```

---

## Analysis

Run deduplication pipeline and identify patterns.

```bash
cognisys analyze --session <session-id> [options]

Options:
  --rules PATH        Analysis rules file
  --db PATH           Database path
```

**Example:**
```bash
cognisys analyze --session 20251120-143022-a8f3
```

**Output:**
```
[SUCCESS] Analysis complete!
  Duplicate groups: 1,048
  Duplicate files: 6,219
  Wasted space: 28.40 GB
```

---

## Reporting

Generate comprehensive reports in multiple formats.

```bash
cognisys report --session <session-id> [options]

Options:
  --output PATH       Output directory (default: reports)
  --format FORMAT     Output format(s): html, json, csv (multiple allowed)
  --db PATH           Database path
```

**Example:**
```bash
cognisys report --session 20251120-143022-a8f3 --format html --format json --format csv
```

**Outputs:**
- `reports/20251120-143022-a8f3_report.html` - Interactive dashboard
- `reports/20251120-143022-a8f3_report.json` - Machine-readable data
- `reports/files_inventory.csv` - Full file listing

---

## Migration Planning

Create migration plans based on target structure.

```bash
cognisys plan --session <session-id> [options]

Options:
  --structure PATH    Target structure config
  --output TEXT       Plan ID (auto-generated if not provided)
  --db PATH           Database path
```

**Example:**
```bash
cognisys plan --session 20251120-143022-a8f3 --structure cognisys/config/new_structure.yml
```

**Output:**
```
[SUCCESS] Migration plan created!
  Plan ID: plan-20251120-150000-x9a2

Actions by type:
  move: 38,456 files (120.50 GB)
  archive: 2,345 files (3.20 GB)
```

---

## Execution

Preview, approve, and execute migration plans.

### Dry Run

```bash
cognisys dry-run --plan <plan-id>

Options:
  --db PATH           Database path
```

**Example:**
```bash
cognisys dry-run --plan plan-20251120-150000-x9a2
```

### Approve

```bash
cognisys approve --plan <plan-id>

Options:
  --db PATH           Database path
```

### Execute

```bash
cognisys execute --plan <plan-id>

Options:
  --db PATH           Database path
```

**Example:**
```bash
cognisys approve --plan plan-20251120-150000-x9a2
cognisys execute --plan plan-20251120-150000-x9a2
```

---

## Source Management

Manage multi-source file library.

### List Sources

```bash
cognisys source list
```

### Add Source

```bash
# Add a local source
cognisys source add my_docs --type local --path "C:\Users\Documents"

# Add a cloud API source (requires authentication)
cognisys source add onedrive_docs --type cloud_api --provider onedrive --path /Documents
```

### Detect Cloud Folders

```bash
# Detect mounted cloud folders
cognisys source detect

# Add detected folders as sources
cognisys source detect --add
```

### Show Status

```bash
cognisys source status
```

---

## Cloud Integration

Manage cloud storage connections.

### Detect Cloud Folders

```bash
cognisys cloud detect
```

**Supported Providers:**
- OneDrive
- Google Drive
- iCloud
- Proton Drive

### Authenticate

```bash
# Standard OAuth flow
cognisys cloud auth --provider onedrive --client-id <your-client-id>

# Device code flow (for headless environments)
cognisys cloud auth --provider onedrive --device-code
```

### Check Status

```bash
cognisys cloud status
```

### Sync Files

```bash
# Pull from cloud
cognisys cloud sync <source_name> --direction pull

# Push to cloud
cognisys cloud sync <source_name> --direction push

# Dry run (preview only)
cognisys cloud sync <source_name> --dry-run
```

### Logout

```bash
cognisys cloud logout
```

---

## File Reclassification

Reclassify files using patterns and ML models.

### Show Statistics

```bash
cognisys reclassify stats
```

### Reclassify Unknown Files

```bash
# Dry run (preview)
cognisys reclassify unknown

# Execute changes
cognisys reclassify unknown --execute

# Verbose output
cognisys reclassify unknown --verbose
```

### Reclassify NULL Files

```bash
# Dry run with patterns and ML
cognisys reclassify null

# Execute changes
cognisys reclassify null --execute

# Patterns only (no ML)
cognisys reclassify null --no-ml

# Higher confidence threshold
cognisys reclassify null --confidence 0.80
```

### Full Reclassification

```bash
# Re-evaluate all files (requires confirmation)
cognisys reclassify all --execute
```

### Low Confidence Files

```bash
# Show files with low confidence
cognisys reclassify low-confidence --threshold 0.5 --limit 100
```

### Common Options

```bash
Options:
  --db PATH           Database path (default: .cognisys/file_registry.db)
  --execute           Apply changes (default is dry-run)
  --confidence FLOAT  Confidence threshold (default: 0.70)
  --use-ml/--no-ml    Enable/disable ML model fallback
  --batch-size INT    Batch size for updates (default: 100)
  --verbose, -v       Show detailed output
```

---

## Utilities

### List Sessions

```bash
cognisys list-sessions
```

### Help

```bash
# General help
cognisys --help

# Command-specific help
cognisys <command> --help
```

---

## Configuration Files

| File | Purpose |
|------|---------|
| `cognisys/config/scan_config.yml` | Scanning parameters |
| `cognisys/config/analysis_rules.yml` | Deduplication rules |
| `cognisys/config/new_structure.yml` | Target structure templates |

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `ONEDRIVE_CLIENT_ID` | Azure AD client ID for OneDrive auth |
| `BRAVE_API_KEY` | Brave Search API key (optional) |

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Configuration error |
| 3 | Database error |

---

## Related Documentation

- [User Guide](../guides/USER_GUIDE.md) - Complete usage documentation
- [Setup Guide](../getting-started/SETUP_GUIDE.md) - Installation and configuration
- [Architecture Overview](../architecture/OVERVIEW.md) - System design
- [MCP Integration](MCP_INTEGRATION.md) - AI assistant integration

---

*CogniSys - Bringing order to digital chaos.*
