# CogniSys Quick Start Guide

Get started with CogniSys in 5 minutes!

## Installation

```bash
# Clone and navigate to project directory
git clone https://github.com/FleithFeming/cognisys-core.git
cd cognisys-core

# Install dependencies
pip install -r requirements.txt

# Install CogniSys in development mode
pip install -e .

# Install cloud storage support (optional)
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

## Cloud Storage Quick Start (Optional)

CogniSys can scan and organize files from cloud storage providers.

### Detect Mounted Cloud Folders

```bash
# Auto-detect OneDrive, Google Drive, iCloud folders
cognisys cloud detect

# Add detected folders as sources
cognisys cloud detect --add
```

### Authenticate with OneDrive API

```bash
# For direct API access (headless/server environments)
cognisys cloud auth --provider onedrive --client-id YOUR_CLIENT_ID

# Check connection status
cognisys cloud status
```

### Scan Cloud Sources

```bash
# Scan a specific cloud source
cognisys scan --source onedrive_mounted

# Scan all configured sources
cognisys scan --all
```

### Sync Files with Cloud

```bash
# Pull files from cloud
cognisys cloud sync onedrive_docs --direction pull

# Push organized files back
cognisys cloud sync onedrive_docs --direction push

# Preview without making changes
cognisys cloud sync onedrive_docs --dry-run
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

See `example_usage.py` for a complete example.

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

- Read [README.md](README.md) for detailed documentation
- Review [ARCHITECTURE.md](ARCHITECTURE.md) for system design
- Customize configurations in `cognisys/config/`
- Check logs in `logs/` directory if issues occur

## Support

- Check existing reports in `reports/` directory
- Review logs in `logs/` directory
- Ensure configuration files are valid YAML

---

**Happy organizing!** 🎉
