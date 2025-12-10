# CogniSys Setup Guide

**Version:** 1.0.0
**Last Updated:** 2024-12-09

Complete installation, configuration, and verification guide for CogniSys.

---

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Installation](#installation)
   - [Standard Installation](#standard-installation)
   - [Development Installation](#development-installation)
   - [Optional Components](#optional-components)
3. [Configuration](#configuration)
   - [Directory Structure](#directory-structure)
   - [Configuration Files](#configuration-files)
   - [Environment Variables](#environment-variables)
4. [Verification](#verification)
5. [Cloud Provider Setup](#cloud-provider-setup)
   - [OneDrive Setup](#onedrive-setup)
   - [Other Providers](#other-providers)
6. [Initial Setup Workflow](#initial-setup-workflow)
7. [Upgrading](#upgrading)
8. [Uninstallation](#uninstallation)
9. [Troubleshooting](#troubleshooting)

---

## System Requirements

### Minimum Requirements

| Component | Requirement |
|-----------|-------------|
| **Operating System** | Windows 10/11, macOS 10.15+, Linux (Ubuntu 20.04+) |
| **Python** | 3.10 or higher |
| **RAM** | 4 GB |
| **Storage** | 500 MB for application + 1 MB per 10,000 indexed files |
| **Network** | Required for cloud integration (optional otherwise) |

### Recommended Requirements

| Component | Recommendation |
|-----------|----------------|
| **Python** | 3.11 or higher |
| **RAM** | 8 GB or more |
| **Storage** | SSD for database performance |
| **GPU** | NVIDIA GPU with CUDA 11+ for ML acceleration |

### Python Version Verification

```bash
# Check Python version
python --version

# Output should be 3.10 or higher
# Python 3.11.x (recommended)
```

If Python is not installed or outdated:
- **Windows:** Download from [python.org](https://www.python.org/downloads/)
- **macOS:** `brew install python@3.11`
- **Linux:** `sudo apt install python3.11 python3.11-venv`

---

## Installation

### Standard Installation

#### Step 1: Clone the Repository

```bash
# Clone CogniSys
git clone https://github.com/FleithFeming/cognisys-core.git
cd cognisys-core
```

#### Step 2: Create Virtual Environment (Recommended)

```bash
# Windows
python -m venv venv
.\venv\Scripts\Activate.ps1  # PowerShell
# or
.\venv\Scripts\activate.bat  # Command Prompt

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

#### Step 3: Install Dependencies

```bash
# Core dependencies
pip install -r requirements.txt

# Install CogniSys
pip install -e .
```

#### Step 4: Verify Installation

```bash
# Check CLI is available
cognisys --help

# Expected output: List of available commands
```

---

### Development Installation

For contributors and advanced users:

```bash
# Clone repository
git clone https://github.com/FleithFeming/cognisys-core.git
cd cognisys-core

# Create development environment
python -m venv venv
source venv/bin/activate  # or .\venv\Scripts\Activate.ps1 on Windows

# Install with development dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt  # If exists
pip install -e ".[dev]"  # If extras defined

# Install pre-commit hooks
pip install pre-commit
pre-commit install

# Run tests to verify
pytest tests/unit/ -v
```

---

### Optional Components

#### Cloud Storage Support

Required for OneDrive, Google Drive integration:

```bash
pip install msal keyring cryptography
```

**Dependencies:**
- `msal` - Microsoft Authentication Library for OneDrive
- `keyring` - Secure credential storage
- `cryptography` - Token encryption

#### ML Model Support

For DistilBERT-based classification:

```bash
pip install torch transformers
```

**Note:** GPU acceleration requires CUDA-compatible PyTorch:

```bash
# CUDA 11.8
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118

# CUDA 12.1
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

# CPU only
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
```

#### MCP Server Support

For MCP protocol integration:

```bash
pip install mcp
```

#### Development Tools

```bash
pip install pytest pytest-cov black mypy ruff
```

---

## Configuration

### Directory Structure

After installation, CogniSys uses this directory structure:

```
cognisys-core/                  # Project root
├── cognisys/                   # Source code
│   ├── cli.py                  # CLI entry point
│   ├── config/                 # Configuration templates
│   │   ├── scan_config.yml
│   │   ├── analysis_rules.yml
│   │   └── new_structure.yml
│   ├── core/                   # Core engines
│   ├── models/                 # Database models
│   ├── storage/                # Storage layer
│   ├── cloud/                  # Cloud integration
│   ├── ml/                     # ML classification
│   ├── mcp/                    # MCP server
│   └── utils/                  # Utilities
├── tests/                      # Test suite
├── docs/                       # Documentation
├── .cognisys/                  # Runtime data (created on first run)
│   ├── file_registry.db        # SQLite database
│   ├── sources.yml             # Configured sources
│   └── config.yml              # User configuration
├── reports/                    # Generated reports
└── logs/                       # Application logs
```

### Configuration Files

#### 1. Scan Configuration (`cognisys/config/scan_config.yml`)

Controls file scanning behavior:

```yaml
scanning:
  # Root directories to scan
  roots:
    - path: "C:\\Users\\YourName\\Documents"
      recursive: true
    - path: "D:\\Projects"
      recursive: true

  # Files/folders to exclude
  exclusions:
    patterns:
      - "*.tmp"
      - "*.bak"
      - "~$*"           # Office temp files
      - "Thumbs.db"
      - ".DS_Store"
    folders:
      - ".git"
      - ".svn"
      - "node_modules"
      - "__pycache__"
      - ".venv"
      - "venv"
      - "$RECYCLE.BIN"
      - "System Volume Information"

performance:
  threads: 8              # Concurrent scanning threads
  batch_size: 1000        # Files per database batch
  chunk_size: 1048576     # 1MB for quick hash

hashing:
  quick_hash: true        # Enable first-1MB pre-filter
  full_hash: true         # Enable full SHA-256
  skip_large_files: false # Skip files over max_file_size
  max_file_size: null     # null = no limit, or bytes (e.g., 10737418240 for 10GB)
```

#### 2. Analysis Rules (`cognisys/config/analysis_rules.yml`)

Controls duplicate detection and canonical selection:

```yaml
deduplication:
  # Fuzzy filename matching
  fuzzy_filename:
    enabled: true
    similarity_threshold: 0.85    # 0.0-1.0 (higher = stricter)
    min_filename_length: 5        # Skip short filenames

  # Canonical file selection weights
  canonical_selection:
    weights:
      modification_date: 10       # Newest preferred
      preferred_paths: 20         # Configured paths preferred
      path_depth: 10              # Shorter paths preferred
      filename_quality: 5         # Descriptive names preferred
      access_frequency: 15        # Recently accessed preferred

    # Paths where files should be kept as canonical
    preferred_paths:
      - "C:\\Users\\YourName\\Documents\\Important"
      - "D:\\Projects"

# Quarantine settings
quarantine:
  root: "Quarantine"
  duplicates_folder: "Duplicates_{date}"
  retention_days: 30              # Auto-delete after N days (0 = never)
```

#### 3. Target Structure (`cognisys/config/new_structure.yml`)

Defines organization hierarchy and classification mapping:

```yaml
repository_root: "C:\\Users\\YourName\\Organized"

# Top-level structure
structure:
  Active:
    description: "Current projects and work"
    subfolders:
      - Projects
      - Work
      - Personal

  Archive:
    description: "Historical files by year"
    naming: "{YYYY}"

  Reference:
    description: "Documentation and templates"
    subfolders:
      - Documentation
      - Templates
      - Resources

  Media:
    description: "Photos, videos, audio"
    subfolders:
      - Photos
      - Videos
      - Audio

  Quarantine:
    description: "Duplicates and review items"

# Classification to path mapping
classification:
  # Financial documents
  financial_invoice:
    path_template: "Active/Financial/Invoices/{YYYY}/{MM}"
  financial_statement:
    path_template: "Active/Financial/Statements/{YYYY}"
  financial_receipt:
    path_template: "Active/Financial/Receipts/{YYYY}/{MM}"

  # Technical files
  technical_script:
    path_template: "Reference/Code/{filename}"
  technical_documentation:
    path_template: "Reference/Documentation/{filename}"

  # Personal documents
  personal_photo:
    path_template: "Media/Photos/{YYYY}/{MM}"
  personal_journal:
    path_template: "Archive/{YYYY}/Personal/{filename}"

  # Default fallback
  default:
    path_template: "Active/Unsorted/{filename}"

# Naming conventions
naming:
  date_format: "YYYY-MM-DD"
  sanitize_names: true            # Remove special characters
  max_length: 200                 # Maximum filename length
  collision_handling: "increment"  # append _1, _2, etc.
```

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `COGNISYS_DB_PATH` | Override database location | `C:\data\cognisys.db` |
| `COGNISYS_CONFIG_DIR` | Override config directory | `C:\config\cognisys` |
| `COGNISYS_LOG_LEVEL` | Logging verbosity | `DEBUG`, `INFO`, `WARNING` |
| `ONEDRIVE_CLIENT_ID` | Azure AD app client ID | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| `BRAVE_API_KEY` | Brave Search API key | `BSA...` |

Set environment variables:

```bash
# Windows PowerShell
$env:COGNISYS_LOG_LEVEL = "DEBUG"

# Windows Command Prompt
set COGNISYS_LOG_LEVEL=DEBUG

# macOS/Linux
export COGNISYS_LOG_LEVEL=DEBUG
```

---

## Verification

### Basic Verification

```bash
# 1. Check CLI installation
cognisys --help

# Expected: List of commands (scan, analyze, report, plan, etc.)

# 2. Check version
cognisys --version

# 3. Create test scan
cognisys scan --roots "." --session-id "test-install"

# 4. Verify database created
# Windows: dir .cognisys
# macOS/Linux: ls -la .cognisys

# 5. Run unit tests
pytest tests/unit/ -v --tb=short
```

### Component Verification

```bash
# Check cloud support
python -c "import msal; print('MSAL OK')"
python -c "import keyring; print('Keyring OK')"

# Check ML support
python -c "import torch; print(f'PyTorch OK, CUDA: {torch.cuda.is_available()}')"
python -c "import transformers; print('Transformers OK')"

# Check MCP support
python -c "import mcp; print('MCP OK')"
```

### Database Verification

```bash
# Check database structure
python -c "
from cognisys.models.database import Database
db = Database('.cognisys/file_registry.db')
print('Tables:', db.list_tables())
"
```

---

## Cloud Provider Setup

### OneDrive Setup

OneDrive API integration requires an Azure AD application registration.

#### Step 1: Register Azure AD Application

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to **Azure Active Directory** > **App registrations**
3. Click **New registration**
4. Configure:
   - **Name:** CogniSys
   - **Supported account types:** Personal Microsoft accounts only (or as needed)
   - **Redirect URI:** `http://localhost:8080/callback`
5. Click **Register**

#### Step 2: Configure API Permissions

1. Go to **API permissions**
2. Click **Add a permission**
3. Select **Microsoft Graph**
4. Add **Delegated permissions**:
   - `Files.Read`
   - `Files.Read.All`
   - `Files.ReadWrite`
   - `Files.ReadWrite.All`
   - `User.Read`
5. Click **Grant admin consent** (if admin)

#### Step 3: Get Client ID

1. Go to **Overview**
2. Copy the **Application (client) ID**

#### Step 4: Configure CogniSys

```bash
# Set environment variable
$env:ONEDRIVE_CLIENT_ID = "your-client-id-here"

# Or authenticate directly
cognisys cloud auth --provider onedrive --client-id "your-client-id-here"

# For headless/server environments
cognisys cloud auth --provider onedrive --client-id "your-client-id-here" --device-code
```

### Other Providers

#### Google Drive

Currently supports mounted folder detection only:

```bash
# Detect mounted Google Drive folder
cognisys cloud detect

# Add as source
cognisys source add gdrive --type cloud_mounted --path "C:\Users\YourName\Google Drive"
```

#### iCloud

Mounted folder detection:

```bash
# Typically located at
# Windows: C:\Users\YourName\iCloudDrive
# macOS: ~/Library/Mobile Documents/com~apple~CloudDocs

cognisys source add icloud --type cloud_mounted --path "path/to/icloud"
```

#### Proton Drive

Mounted folder detection:

```bash
cognisys source add proton --type cloud_mounted --path "path/to/proton-drive"
```

---

## Initial Setup Workflow

Complete setup workflow for first-time users:

### Step 1: Install CogniSys

```bash
git clone https://github.com/FleithFeming/cognisys-core.git
cd cognisys-core
python -m venv venv
.\venv\Scripts\Activate.ps1  # Windows
pip install -r requirements.txt
pip install -e .
```

### Step 2: Configure Sources

```bash
# List default sources
cognisys source list

# Add your main directories
cognisys source add documents --type local --path "C:\Users\YourName\Documents"
cognisys source add downloads --type local --path "C:\Users\YourName\Downloads"

# Detect cloud folders
cognisys cloud detect --add
```

### Step 3: Customize Configuration

Edit configuration files as needed:
- `cognisys/config/scan_config.yml` - Add exclusions
- `cognisys/config/new_structure.yml` - Customize organization

### Step 4: Run Initial Scan

```bash
# Test with small directory first
cognisys scan --roots "C:\Users\YourName\Downloads" --session-id "initial-test"

# Review results
cognisys analyze --session initial-test
cognisys report --session initial-test --format html
```

### Step 5: Review and Adjust

1. Open `reports/initial-test_report.html`
2. Review file distribution and duplicates
3. Adjust configuration if needed
4. Proceed with larger scans

---

## Upgrading

### Standard Upgrade

```bash
cd cognisys-core

# Backup database (recommended)
cp .cognisys/file_registry.db .cognisys/file_registry.db.backup

# Pull latest changes
git pull origin main

# Update dependencies
pip install -r requirements.txt
pip install -e .

# Run database migrations if prompted
cognisys migrate
```

### Major Version Upgrade

For major version changes:

```bash
# Backup everything
cp -r .cognisys .cognisys.backup

# Pull and reinstall
git pull origin main
pip install -r requirements.txt
pip install -e . --force-reinstall

# Check for breaking changes in CHANGELOG.md
# Run migrations
cognisys migrate --force
```

---

## Uninstallation

### Remove CogniSys

```bash
# Uninstall package
pip uninstall cognisys

# Remove virtual environment
rm -rf venv  # or delete venv folder on Windows

# Remove runtime data (optional)
rm -rf .cognisys

# Remove project directory
cd ..
rm -rf cognisys-core
```

### Keep Data, Remove Code

```bash
# Backup data first
cp -r .cognisys ~/cognisys-backup

# Uninstall
pip uninstall cognisys
rm -rf venv
```

---

## Troubleshooting

### Installation Issues

#### Python Version Error

```
Error: Python 3.10 or higher required
```

**Solution:** Install Python 3.10+ from [python.org](https://www.python.org/downloads/)

#### Permission Denied

```
Error: Permission denied: .cognisys/file_registry.db
```

**Solution:**
- Windows: Run terminal as Administrator
- macOS/Linux: Check file permissions with `ls -la .cognisys/`

#### Module Not Found

```
ModuleNotFoundError: No module named 'cognisys'
```

**Solution:**
```bash
# Reinstall in development mode
pip install -e .

# Or check virtual environment is activated
which python  # Should show venv path
```

### Database Issues

#### Database Locked

```
sqlite3.OperationalError: database is locked
```

**Solution:**
- Close other applications accessing the database
- Check for zombie Python processes
- Wait and retry

#### Database Corrupted

```
sqlite3.DatabaseError: database disk image is malformed
```

**Solution:**
```bash
# Try to recover
sqlite3 .cognisys/file_registry.db "PRAGMA integrity_check"

# If corrupted, restore backup
cp .cognisys/file_registry.db.backup .cognisys/file_registry.db
```

### Performance Issues

#### Slow Scanning

**Solutions:**
1. Increase thread count in `scan_config.yml`
2. Add more exclusion patterns
3. Use SSD for database storage
4. Split large scans into batches

#### High Memory Usage

**Solutions:**
1. Reduce `batch_size` in configuration
2. Close other applications
3. Add more RAM
4. Use 64-bit Python

### Cloud Issues

#### OAuth Authentication Failed

**Solutions:**
1. Verify Client ID is correct
2. Check redirect URI matches configuration
3. Ensure API permissions are granted
4. Try device code flow for problematic networks

#### Cloud Sync Timeout

**Solutions:**
1. Check network connectivity
2. Reduce batch size for sync
3. Try syncing smaller folders first
4. Check cloud provider status

---

## Next Steps

After setup, continue with:

- [Quick Start Guide](QUICKSTART.md) - First workflow in 5 minutes
- [User Guide](../guides/USER_GUIDE.md) - Complete usage documentation
- [Architecture Overview](../architecture/OVERVIEW.md) - System design
- [CLI Reference](../reference/CLI_COMMANDS.md) - All commands

---

*CogniSys - Bringing order to digital chaos.*
