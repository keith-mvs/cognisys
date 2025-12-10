# CogniSys Quick Start Guide

**Version:** 2.0.0
**Last Updated:** 2024-12-09

Get started with CogniSys in 5 minutes!

> For detailed setup instructions, see the [Setup Guide](SETUP_GUIDE.md).
> For complete usage documentation, see the [User Guide](../guides/USER_GUIDE.md).

## Installation

```bash
# Clone and navigate to project directory
git clone https://github.com/FleithFeming/cognisys-core.git
cd cognisys-core

# Install dependencies
pip install -r requirements.txt

# Install CogniSys in development mode
pip install -e .

# Optional: Cloud storage support
pip install msal keyring cryptography

# Verify installation
cognisys --help
```

## Your First Workflow

### Step 1: Scan a Directory

```bash
# Scan your Downloads folder
cognisys scan --roots "C:\Users\YourName\Downloads"

# Or scan multiple directories
cognisys scan --roots "C:\Users\YourName\Documents" --roots "C:\Users\YourName\Downloads"
```

**Output:** You'll get a session ID like `20251120-143022-a8f3`

### Step 2: Analyze for Duplicates

```bash
# Replace SESSION_ID with your actual session ID
cognisys analyze --session SESSION_ID
```

**Output:** Shows how many duplicate groups and wasted space found

### Step 3: Generate Report

```bash
# Generate HTML, JSON, and CSV reports
cognisys report --session SESSION_ID --format html --format json --format csv

# Open the HTML report in your browser
# reports/SESSION_ID_report.html
```

### Step 4: Review the Report

Open `reports/SESSION_ID_report.html` in your browser to see:
- Storage distribution by file type
- Largest files and folders
- Duplicate analysis
- Actionable recommendations

### Step 5: Create Migration Plan (Optional)

If you want to reorganize files:

```bash
# Edit cognisys/config/new_structure.yml first to define your target structure
# Then create the plan
cognisys plan --session SESSION_ID --structure cognisys/config/new_structure.yml
```

### Step 6: Preview Changes

```bash
# Dry run to see what would happen (no actual changes)
cognisys dry-run --plan PLAN_ID
```

### Step 7: Execute (If Satisfied)

```bash
# Approve the plan
cognisys approve --plan PLAN_ID

# Execute migration
cognisys execute --plan PLAN_ID
```

## Cloud Integration

### Detect Cloud Folders

```bash
# Find mounted OneDrive, Google Drive, iCloud folders
cognisys cloud detect

# Add detected folders as sources
cognisys cloud detect --add
```

### Manage Sources

```bash
# List all configured sources
cognisys source list

# Add a local source
cognisys source add my_docs --type local --path "C:\Users\Documents"

# Show source status
cognisys source status
```

### File Reclassification

```bash
# Show classification statistics
cognisys reclassify stats

# Reclassify unknown files (dry run)
cognisys reclassify unknown

# Apply reclassification
cognisys reclassify unknown --execute
```

## Configuration Tips

### Customize What Gets Scanned

Edit `cognisys/config/scan_config.yml`:

```yaml
scanning:
  roots:
    - path: "C:\\Your\\Path"
      recursive: true

  exclusions:
    patterns:
      - "*.tmp"
      - "node_modules"
    folders:
      - ".git"
      - "__pycache__"
```

### Customize Duplicate Detection

Edit `cognisys/config/analysis_rules.yml`:

```yaml
deduplication:
  fuzzy_filename:
    similarity_threshold: 0.85  # 0.0 to 1.0 (higher = stricter)

  canonical_selection:
    preferred_paths:
      - "C:\\Important\\Files"  # Files here are kept as canonical
```

### Customize Target Structure

Edit `cognisys/config/new_structure.yml`:

```yaml
repository_root: "C:\\MyOrganizedFiles"

classification:
  documents:
    extensions: [".pdf", ".docx"]
    target: "Active/Documents/{YYYY}"
```

## Common Commands

```bash
# List all scan sessions
cognisys list-sessions

# Get help for any command
cognisys scan --help
cognisys analyze --help
cognisys reclassify --help

# Specify custom database location
cognisys scan --roots "C:\Path" --db "custom/path/db.sqlite"
```

## Programmatic Usage

Use CogniSys in your Python scripts:

```python
from cognisys.models.database import Database
from cognisys.core.scanner import FileScanner
import yaml

# Load config
with open('cognisys/config/scan_config.yml') as f:
    config = yaml.safe_load(f)

# Scan
db = Database('db/mydb.db')
scanner = FileScanner(db, config)
session_id = scanner.scan_roots(['C:\\MyFiles'])

print(f"Scanned {scanner.get_stats()['files_scanned']} files")
```

## Troubleshooting

### Permission Errors

Run with administrator privileges or skip system folders:

```yaml
# In scan_config.yml
exclusions:
  folders:
    - "$RECYCLE.BIN"
    - "System Volume Information"
```

### Large Directories Taking Too Long

Increase thread count:

```yaml
# In scan_config.yml
performance:
  threads: 16  # Increase from default 8
```

### Out of Memory

Reduce batch size:

```yaml
# In scan_config.yml
performance:
  batch_size: 500  # Reduce from default 1000
```

## What's Next?

- **[Setup Guide](SETUP_GUIDE.md)** - Detailed installation and configuration
- **[User Guide](../guides/USER_GUIDE.md)** - Complete feature documentation
- **[Architecture Overview](../architecture/OVERVIEW.md)** - System design and components
- **[CLI Reference](../reference/CLI_COMMANDS.md)** - All commands with examples
- **[MCP Integration](../reference/MCP_INTEGRATION.md)** - AI assistant integration

## Troubleshooting

For common issues, see the [Troubleshooting section](SETUP_GUIDE.md#troubleshooting) in the Setup Guide.

Quick checks:
- Verify configuration files are valid YAML
- Check logs in `logs/` directory
- Review reports in `reports/` directory

## Support

- [Documentation Index](../INDEX.md) - All documentation
- [Main README](../../README.md) - Project overview
- Create an issue in the repository for bugs or features

---

*CogniSys - Bringing order to digital chaos.*
