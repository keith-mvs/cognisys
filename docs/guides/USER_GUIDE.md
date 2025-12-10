# CogniSys User Guide

**Version:** 1.0.0
**Last Updated:** 2024-12-09

A complete guide to using CogniSys for intelligent file management, organization, and classification.

---

## Table of Contents

1. [Introduction](#introduction)
2. [System Capabilities](#system-capabilities)
3. [Getting Started](#getting-started)
4. [Core Workflows](#core-workflows)
   - [Basic Workflow](#basic-workflow)
   - [Classification Workflow](#classification-workflow)
   - [Cloud Sync Workflow](#cloud-sync-workflow)
5. [Feature Deep Dives](#feature-deep-dives)
   - [Multi-Source File Library](#multi-source-file-library)
   - [Intelligent Classification](#intelligent-classification)
   - [Deduplication System](#deduplication-system)
   - [Migration and Organization](#migration-and-organization)
6. [Common Use Cases](#common-use-cases)
7. [Best Practices](#best-practices)
8. [Frequently Asked Questions](#frequently-asked-questions)

---

## Introduction

### What is CogniSys?

**CogniSys** (Cognitive File Organization System) is an intelligent file management system that automatically scans, classifies, deduplicates, and organizes files across local drives, network shares, and cloud storage. It combines machine learning classification with rule-based patterns to bring order to digital file collections.

### Who is CogniSys For?

- **Individuals** managing personal document collections
- **Professionals** organizing work files across multiple devices
- **Developers** maintaining code repositories and assets
- **Organizations** standardizing file structures across teams
- **Digital archivists** preserving and categorizing content

### Key Benefits

| Benefit | Description |
|---------|-------------|
| **Automatic Classification** | ML-powered categorization with 96.7% accuracy |
| **Cross-Platform Sources** | Unified management across local, network, and cloud storage |
| **Space Recovery** | Intelligent deduplication finds wasted space |
| **Safe Operations** | Dry-run previews and rollback capability |
| **Customizable Rules** | Configure classification and organization to your needs |

---

## System Capabilities

### Overview

```
┌────────────────────────────────────────────────────────────────┐
│                     CogniSys Capabilities                       │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  SCAN          ANALYZE         CLASSIFY        ORGANIZE         │
│  ─────         ───────         ────────        ────────         │
│  - Local       - Duplicates    - ML Model      - Move Files     │
│  - Network     - Patterns      - Patterns      - Archive        │
│  - Cloud       - Statistics    - Extensions    - Rename         │
│                                                                 │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  REPORT        MIGRATE         SYNC            REVIEW           │
│  ──────        ───────         ────            ──────           │
│  - HTML        - Dry Run       - Pull          - Low Conf       │
│  - JSON        - Execute       - Push          - Unknown        │
│  - CSV         - Rollback      - Bidirect      - Reclassify     │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

### Capability Matrix

| Capability | Description | Commands |
|------------|-------------|----------|
| **File Scanning** | Index files with metadata and hashes | `cognisys scan` |
| **Duplicate Detection** | 4-stage pipeline for finding duplicates | `cognisys analyze` |
| **ML Classification** | DistilBERT-based document categorization | `cognisys classify` |
| **Pattern Classification** | Rule-based classification with 40+ rules | `cognisys reclassify` |
| **Report Generation** | Statistics, insights, visualizations | `cognisys report` |
| **Migration Planning** | Create file reorganization plans | `cognisys plan` |
| **Safe Execution** | Dry-run preview and rollback | `cognisys execute` |
| **Cloud Integration** | OneDrive, Google Drive, iCloud support | `cognisys cloud` |
| **Source Management** | Multi-source library configuration | `cognisys source` |

---

## Getting Started

### Prerequisites

- Python 3.10 or higher
- 4GB RAM minimum (8GB recommended for large collections)
- Storage space for database (approximately 1MB per 10,000 files)

### Quick Installation

```bash
# Clone repository
git clone https://github.com/FleithFeming/cognisys-core.git
cd cognisys-core

# Install dependencies
pip install -r requirements.txt
pip install -e .

# Verify installation
cognisys --help
```

### Optional Components

```bash
# Cloud storage support
pip install msal keyring cryptography

# ML model support
pip install torch transformers

# Development tools
pip install pytest black mypy
```

### Initial Setup

1. **Create your first scan:**
   ```bash
   cognisys scan --roots "C:\Users\YourName\Documents"
   ```

2. **Analyze for duplicates:**
   ```bash
   cognisys analyze --session <session-id>
   ```

3. **Generate a report:**
   ```bash
   cognisys report --session <session-id> --format html
   ```

4. **Review results** in `reports/` directory

---

## Core Workflows

### Basic Workflow

The standard CogniSys workflow follows five stages:

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│  SCAN   │───▶│ ANALYZE │───▶│ REPORT  │───▶│  PLAN   │───▶│ EXECUTE │
└─────────┘    └─────────┘    └─────────┘    └─────────┘    └─────────┘
     │              │              │              │              │
     ▼              ▼              ▼              ▼              ▼
  Index         Detect         Generate      Create          Apply
  Files         Patterns       Insights      Migration       Changes
```

#### Step 1: Scan

Index your files with metadata and content hashes:

```bash
# Single directory
cognisys scan --roots "C:\Users\Documents"

# Multiple directories
cognisys scan --roots "C:\Users\Documents" --roots "D:\Projects"

# Custom session ID
cognisys scan --roots "C:\Data" --session-id "archive-2024"
```

**Output:**
```
[SUCCESS] Scan completed!
  Session ID: 20241209-143022-a8f3
  Files scanned: 12,453
  Folders scanned: 1,234
  Total size: 45.20 GB
```

#### Step 2: Analyze

Run the deduplication pipeline:

```bash
cognisys analyze --session 20241209-143022-a8f3
```

**Output:**
```
[SUCCESS] Analysis complete!
  Duplicate groups: 1,048
  Duplicate files: 6,219
  Wasted space: 28.40 GB
```

#### Step 3: Report

Generate comprehensive reports:

```bash
# Single format
cognisys report --session 20241209-143022-a8f3 --format html

# Multiple formats
cognisys report --session 20241209-143022-a8f3 --format html --format json --format csv
```

**Outputs:**
- `reports/<session>_report.html` - Interactive dashboard
- `reports/<session>_report.json` - Machine-readable data
- `reports/files_inventory.csv` - Full file listing

#### Step 4: Plan

Create a migration plan:

```bash
cognisys plan --session 20241209-143022-a8f3 --structure cognisys/config/new_structure.yml
```

**Output:**
```
[SUCCESS] Migration plan created!
  Plan ID: plan-20241209-150000-x9a2

Actions by type:
  move: 38,456 files (120.50 GB)
  archive: 2,345 files (3.20 GB)
```

#### Step 5: Execute

Preview and apply changes:

```bash
# Preview (dry run)
cognisys dry-run --plan plan-20241209-150000-x9a2

# Approve the plan
cognisys approve --plan plan-20241209-150000-x9a2

# Execute migration
cognisys execute --plan plan-20241209-150000-x9a2
```

---

### Classification Workflow

For ML-powered document classification:

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  STATS   │───▶│ RECLASSY │───▶│  REVIEW  │───▶│ EXECUTE  │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
     │               │               │               │
     ▼               ▼               ▼               ▼
  View           Classify        Inspect         Apply
  Metrics        Files           Results         Changes
```

#### View Classification Statistics

```bash
cognisys reclassify stats
```

**Output:**
```
Classification Statistics
========================================
Total files: 77,482
Classified: 76,891 (99.2%)
Unknown type: 423 (0.5%)
NULL type: 168 (0.2%)

By confidence:
  High (>90%): 58,234 (75.2%)
  Medium (70-90%): 14,856 (19.2%)
  Low (<70%): 4,392 (5.7%)
```

#### Reclassify Unknown Files

```bash
# Dry run (preview)
cognisys reclassify unknown --verbose

# Execute changes
cognisys reclassify unknown --execute
```

#### Reclassify NULL Type Files

```bash
# Patterns + ML (default)
cognisys reclassify null

# Patterns only (faster)
cognisys reclassify null --no-ml

# Higher confidence threshold
cognisys reclassify null --confidence 0.80 --execute
```

#### Review Low-Confidence Files

```bash
# View files needing review
cognisys reclassify low-confidence --threshold 0.5 --limit 100

# Full reclassification (careful!)
cognisys reclassify all --execute
```

---

### Cloud Sync Workflow

For managing cloud storage integration:

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  DETECT  │───▶│   AUTH   │───▶│  STATUS  │───▶│   SYNC   │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
     │               │               │               │
     ▼               ▼               ▼               ▼
  Find           Authen-         Check           Sync
  Cloud          ticate          Conn.           Files
  Folders        OAuth           Status
```

#### Detect Cloud Folders

```bash
# Auto-detect mounted cloud folders
cognisys cloud detect

# Add detected as sources
cognisys source detect --add
```

#### Authenticate with Providers

```bash
# OneDrive (requires Azure AD app)
cognisys cloud auth --provider onedrive --client-id <your-client-id>

# Device code flow (headless)
cognisys cloud auth --provider onedrive --device-code
```

#### Check Status

```bash
# Cloud connection status
cognisys cloud status

# Source status
cognisys source status
```

#### Sync Files

```bash
# Pull from cloud
cognisys cloud sync my_onedrive --direction pull

# Push to cloud
cognisys cloud sync my_onedrive --direction push

# Preview only
cognisys cloud sync my_onedrive --dry-run
```

---

## Feature Deep Dives

### Multi-Source File Library

CogniSys manages files across multiple locations through a unified source library.

#### Source Types

| Type | Description | Example |
|------|-------------|---------|
| **local** | Local filesystem | `C:\Users\Documents` |
| **network** | Network shares | `\\NAS\archive` |
| **cloud_mounted** | Mounted cloud folders | `C:\Users\OneDrive` |
| **cloud_api** | Direct cloud API | OneDrive via Graph API |

#### Managing Sources

```bash
# List all sources
cognisys source list

# Add a local source
cognisys source add my_docs --type local --path "C:\Users\Documents"

# Add a network source
cognisys source add nas_backup --type network --path "\\\\NAS\\backup"

# Add a cloud API source
cognisys source add onedrive_docs --type cloud_api --provider onedrive --path /Documents

# View source status
cognisys source status
```

#### Source Configuration

Sources are stored in `.cognisys/sources.yml`:

```yaml
sources:
  my_documents:
    type: local
    path: "C:/Users/kjfle/Documents"
    enabled: true
    scan_mode: scheduled

  onedrive_sync:
    type: cloud_mounted
    path: "C:/Users/kjfle/OneDrive"
    provider: onedrive
    enabled: true
    scan_mode: watch

  nas_archive:
    type: network
    path: "\\\\NAS\\archive"
    enabled: true
    scan_mode: manual
```

---

### Intelligent Classification

CogniSys uses a cascade classification system with multiple methods.

#### Classification Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                  Classification Cascade                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. Pattern Classifier (40+ rules)                           │
│     └── If match → Return type + 100% confidence             │
│                                                              │
│  2. ML Classifier (DistilBERT v2)                            │
│     └── If confidence >= 70% → Return type                   │
│                                                              │
│  3. NVIDIA NIM Fallback (optional)                           │
│     └── For low-confidence cases                             │
│                                                              │
│  4. Extension Mapping (fallback)                             │
│     └── Basic type from file extension                       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

#### Document Types (50 Categories)

**Financial:**
- `financial_invoice` - Invoices and bills
- `financial_statement` - Bank/financial statements
- `financial_receipt` - Receipts and confirmations
- `financial_tax` - Tax documents

**Technical:**
- `technical_script` - Code and scripts
- `technical_config` - Configuration files
- `technical_documentation` - Technical docs
- `technical_log` - Log files

**Personal:**
- `personal_career` - Resumes, career documents
- `personal_journal` - Personal notes, journals
- `personal_identity` - ID documents
- `personal_correspondence` - Letters, emails

**Business:**
- `business_spreadsheet` - Spreadsheets
- `business_presentation` - Presentations
- `business_contract` - Contracts, agreements
- `business_report` - Reports

**Media:**
- `media_screenshot` - Screenshots
- `media_graphic` - Graphics, images
- `media_video` - Video files
- `media_audio` - Audio files

*Plus 30+ additional categories...*

#### Pattern Rules

Pattern rules are high-confidence matches based on filename patterns:

```python
# Example rules from pattern_classifier.py
rules = [
    # Financial
    (r'invoice|rechnung|faktura', 'financial_invoice'),
    (r'receipt|quittung', 'financial_receipt'),
    (r'statement|kontoauszug', 'financial_statement'),

    # Automotive
    (r'vin[:\s_-]*[A-Z0-9]{17}', 'automotive_vehicle'),
    (r'diagnostic|dtc|obd', 'automotive_technical'),

    # Technical
    (r'\.(py|js|ts|go|rs|cpp)$', 'technical_script'),
    (r'config\.(yml|yaml|json|toml)', 'technical_config'),
]
```

---

### Deduplication System

CogniSys uses a 4-stage pipeline for accurate duplicate detection.

#### Deduplication Pipeline

```
Stage 1: Pre-Filter
├── Group by file size
├── Group by extension
└── Eliminates 80% of comparisons

Stage 2: Quick Hash
├── Hash first 1MB of file
├── Compare quick hashes
└── Fast elimination of non-duplicates

Stage 3: Full Hash
├── Full SHA-256 hash
├── Only for quick hash matches
└── Verify exact duplicates

Stage 4: Fuzzy Match (optional)
├── Filename similarity
├── Metadata comparison
└── Find near-duplicates
```

#### Canonical Selection

When duplicates are found, CogniSys selects a "canonical" (master) copy based on scoring:

| Factor | Weight | Description |
|--------|--------|-------------|
| Modification Date | +10 | Newest file preferred |
| Preferred Paths | +20 | Configured priority locations |
| Path Depth | +10 | Shorter paths preferred |
| Filename Quality | +5 | Descriptive names preferred |
| Access Frequency | +15 max | Recently accessed files |

The highest-scoring file becomes canonical; others are marked as duplicates.

---

### Migration and Organization

CogniSys organizes files into a structured hierarchy.

#### Target Structure

Default structure from `new_structure.yml`:

```
Organized/
├── Active/
│   ├── Projects/
│   ├── Work/
│   └── Personal/
├── Archive/
│   ├── 2024/
│   ├── 2023/
│   └── ...
├── Reference/
│   ├── Documentation/
│   ├── Templates/
│   └── Resources/
├── Media/
│   ├── Photos/
│   ├── Videos/
│   └── Audio/
└── Quarantine/
    └── Duplicates/
```

#### Path Templates

Files are organized using configurable templates:

```yaml
# Example from new_structure.yml
classification:
  financial_invoice:
    path_template: "Financial/Invoices/{YYYY}/{MM}/{filename}"
  personal_photo:
    path_template: "Media/Photos/{YYYY}/{filename}"
  technical_script:
    path_template: "Reference/Code/{filename}"
```

#### Migration Safety

- **Dry Run**: Preview all changes before execution
- **Checkpoints**: Rollback data saved before each batch
- **Audit Trail**: Complete logging of all operations
- **Conflict Resolution**: Automatic handling of naming collisions

---

## Common Use Cases

### Use Case 1: Clean Up Downloads Folder

**Scenario:** Downloads folder has accumulated thousands of files over years.

```bash
# 1. Scan downloads
cognisys scan --roots "C:\Users\YourName\Downloads"

# 2. Analyze for duplicates
cognisys analyze --session <session-id>

# 3. Generate report to see what's there
cognisys report --session <session-id> --format html

# 4. Create organization plan
cognisys plan --session <session-id>

# 5. Preview changes
cognisys dry-run --plan <plan-id>

# 6. Execute (after review)
cognisys approve --plan <plan-id>
cognisys execute --plan <plan-id>
```

### Use Case 2: Consolidate Multiple Drives

**Scenario:** Files scattered across C:, D:, and external drives.

```bash
# 1. Add sources
cognisys source add c_docs --type local --path "C:\Users\Documents"
cognisys source add d_projects --type local --path "D:\Projects"
cognisys source add external --type local --path "E:\Backup"

# 2. Scan all sources
cognisys scan --roots "C:\Users\Documents" --roots "D:\Projects" --roots "E:\Backup"

# 3. Find cross-drive duplicates
cognisys analyze --session <session-id>

# 4. Review and consolidate
cognisys report --session <session-id> --format html
```

### Use Case 3: Classify Unorganized Documents

**Scenario:** Thousands of documents with no organization.

```bash
# 1. Initial scan
cognisys scan --roots "C:\Users\Documents\Unsorted"

# 2. Run classification
cognisys classify --session <session-id>

# 3. Check classification quality
cognisys reclassify stats

# 4. Fix low-confidence classifications
cognisys reclassify low-confidence --threshold 0.5 --limit 100

# 5. Organize by classification
cognisys plan --session <session-id>
cognisys execute --plan <plan-id>
```

### Use Case 4: Sync with Cloud Storage

**Scenario:** Keep local organized files synchronized with OneDrive.

```bash
# 1. Detect OneDrive folder
cognisys cloud detect

# 2. Add as source
cognisys source add onedrive --type cloud_mounted --path "C:\Users\OneDrive"

# 3. Authenticate for API access
cognisys cloud auth --provider onedrive --client-id <client-id>

# 4. Pull new files from cloud
cognisys cloud sync onedrive --direction pull

# 5. Classify and organize
cognisys classify --session <session-id>
cognisys reclassify null --execute

# 6. Push organized files back
cognisys cloud sync onedrive --direction push
```

---

## Best Practices

### Scanning

1. **Start small**: Test with a single directory before scanning entire drives
2. **Exclude system folders**: Use exclusion patterns for `.venv`, `node_modules`, etc.
3. **Schedule large scans**: Run overnight for very large collections
4. **Use incremental scans**: Update existing indexes rather than full re-scans

### Classification

1. **Review low-confidence first**: Files below 70% confidence need attention
2. **Create custom patterns**: Add rules for your specific file types
3. **Retrain periodically**: Update ML model with corrections
4. **Validate before bulk reclassify**: Always preview changes

### Organization

1. **Always use dry-run first**: Preview all changes before execution
2. **Backup before migration**: Especially for first-time use
3. **Start with duplicates**: Quarantine duplicates before reorganizing
4. **Document your structure**: Keep notes on path templates and rules

### Maintenance

1. **Regular scans**: Weekly or monthly depending on file volume
2. **Monitor confidence scores**: Watch for classification drift
3. **Clean quarantine folder**: Periodically review and delete confirmed duplicates
4. **Update patterns**: Add rules as you find new file types

---

## Frequently Asked Questions

### General

**Q: How long does a scan take?**
A: Depends on file count and storage speed. Rough estimates:
- 10,000 files: 2-5 minutes
- 100,000 files: 20-40 minutes
- 1,000,000 files: 3-6 hours

**Q: How much disk space does CogniSys use?**
A: The SQLite database uses approximately 1MB per 10,000 files. ML models require additional 500MB if installed.

**Q: Can I run CogniSys on network drives?**
A: Yes, but performance depends on network speed. Consider scanning during off-hours for large network shares.

### Classification

**Q: How accurate is the ML classification?**
A: The DistilBERT v2 model achieves 96.7% accuracy on the training set. Real-world accuracy may vary based on your file types.

**Q: What if a file is misclassified?**
A: Use `cognisys reclassify` commands to correct individual files or use the MCP server for interactive corrections.

**Q: Can I add custom document types?**
A: Yes, modify `cognisys/config/new_structure.yml` to add categories and `utils/pattern_classifier.py` for matching rules.

### Migration

**Q: What happens if migration fails mid-way?**
A: CogniSys creates checkpoints before each batch. Use rollback to restore files to original locations.

**Q: Can I undo a migration?**
A: Yes, rollback data is stored in `migration_actions.rollback_data`. Run the rollback command with your plan ID.

**Q: Are original files deleted?**
A: By default, duplicates are moved to quarantine, not deleted. You must manually delete quarantined files after verification.

### Cloud Integration

**Q: Which cloud providers are supported?**
A: OneDrive (full API support), Google Drive, iCloud, and Proton Drive (mounted folder detection).

**Q: Do I need an Azure app for OneDrive?**
A: Yes, OneDrive API integration requires registering an Azure AD application.

**Q: Can CogniSys sync bidirectionally?**
A: Yes, use `--direction pull` to download and `--direction push` to upload.

---

## Additional Resources

- [Quick Start Guide](../getting-started/QUICKSTART.md) - Get started in 5 minutes
- [Architecture Overview](../architecture/OVERVIEW.md) - System design details
- [CLI Reference](../reference/CLI_COMMANDS.md) - Complete command reference
- [MCP Integration](../reference/MCP_INTEGRATION.md) - AI assistant integration
- [ML Workflow Guide](ML_WORKFLOW.md) - Training and classification details

---

*CogniSys - Bringing order to digital chaos.*
