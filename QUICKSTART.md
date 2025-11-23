# IFMOS Quick Start Guide

Get started with IFMOS in 5 minutes!

## Installation

```bash
# Clone and navigate to project directory
git clone https://github.com/FleithFeming/IFMOS.git
cd IFMOS

# Install dependencies
pip install -r requirements.txt

# Install IFMOS in development mode
pip install -e .

# Verify installation
ifmos --help
```

## Your First Workflow

### Step 1: Scan a Directory

```bash
# Scan your Downloads folder
ifmos scan --roots "C:\Users\YourName\Downloads"

# Or scan multiple directories
ifmos scan --roots "C:\Users\YourName\Documents" --roots "C:\Users\YourName\Downloads"
```

**Output:** You'll get a session ID like `20251120-143022-a8f3`

### Step 2: Analyze for Duplicates

```bash
# Replace SESSION_ID with your actual session ID
ifmos analyze --session SESSION_ID
```

**Output:** Shows how many duplicate groups and wasted space found

### Step 3: Generate Report

```bash
# Generate HTML, JSON, and CSV reports
ifmos report --session SESSION_ID --format html --format json --format csv

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
# Edit ifmos/config/new_structure.yml first to define your target structure
# Then create the plan
ifmos plan --session SESSION_ID --structure ifmos/config/new_structure.yml
```

### Step 6: Preview Changes

```bash
# Dry run to see what would happen (no actual changes)
ifmos dry-run --plan PLAN_ID
```

### Step 7: Execute (If Satisfied)

```bash
# Approve the plan
ifmos approve --plan PLAN_ID

# Execute migration
ifmos execute --plan PLAN_ID
```

## Configuration Tips

### Customize What Gets Scanned

Edit `ifmos/config/scan_config.yml`:

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

Edit `ifmos/config/analysis_rules.yml`:

```yaml
deduplication:
  fuzzy_filename:
    similarity_threshold: 0.85  # 0.0 to 1.0 (higher = stricter)

  canonical_selection:
    preferred_paths:
      - "C:\\Important\\Files"  # Files here are kept as canonical
```

### Customize Target Structure

Edit `ifmos/config/new_structure.yml`:

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
ifmos list-sessions

# Get help for any command
ifmos scan --help
ifmos analyze --help

# Specify custom database location
ifmos scan --roots "C:\Path" --db "custom/path/db.sqlite"
```

## Programmatic Usage

Use IFMOS in your Python scripts:

```python
from ifmos.models.database import Database
from ifmos.core.scanner import FileScanner
import yaml

# Load config
with open('ifmos/config/scan_config.yml') as f:
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
- Customize configurations in `ifmos/config/`
- Check logs in `logs/` directory if issues occur

## Support

- Check existing reports in `reports/` directory
- Review logs in `logs/` directory
- Ensure configuration files are valid YAML

---

**Happy organizing!** 🎉
