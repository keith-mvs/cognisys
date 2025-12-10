# CogniSys Document Processing Workflow

**Version:** 2.0.0
**Last Updated:** 2024-12-09

Technical reference for the CogniSys document processing pipeline.

> For general usage, see the [User Guide](USER_GUIDE.md).
> For system architecture, see the [Architecture Overview](../architecture/OVERVIEW.md).

---

## Overview

CogniSys manages a **distributed source library** spanning multiple machines, devices, and cloud storage providers, feeding into a unified classification and organization pipeline.

```
+==============================================================================+
|                           SOURCE LIBRARY                                      |
+==============================================================================+
|  LOCAL             NETWORK            CLOUD (Mounted)      CLOUD (API)        |
|  - Downloads       - NAS/SMB          - OneDrive Sync      - OneDrive API     |
|  - Documents       - Server shares    - Google Drive       - Google Drive API |
|  - Desktop         - Archive drives   - iCloud             - Proton Drive     |
+==============================================================================+
                                    |
                                    v
+------------------+     +------------------+     +------------------+     +------------------+
|                  |     |                  |     |                  |     |                  |
|  Multi-Source    | --> |    Register      | --> |    Classify      | --> |    Organize      |
|    Scanner       |     |   (Hash + DB)    |     |    (ML/Rules)    |     |  (Canonical)     |
|                  |     |                  |     |                  |     |                  |
+------------------+     +------------------+     +------------------+     +------------------+
        |                       |                       |                       |
        v                       v                       v                       v
   source_id             content_hash           document_type            canonical_path
   source_path           file_id                confidence               Two-Way Sync
                         dedup check            method                   back to cloud
```

## Detailed Flow

### Stage 1: DROP (User Action)
```
User --> 00_Inbox/
         |-- new_document.pdf
         |-- invoice_2024.pdf
         |-- photo.jpg
         +-- ...
```

**Input:** Any file dropped into the inbox directory
**Output:** Raw files awaiting processing
**Location:** `C:\Users\kjfle\00_Inbox`

### Stage 2: REGISTER (cognisys register)
```
00_Inbox/            file_registry.db
    |                     |
    +--[scan files]-->    +--[INSERT]-->  file_id: 12345
    |                     |               original_path: C:/Users/.../doc.pdf
    +--[compute hash]-->  +--[CHECK]-->   content_hash: abc123...
    |                     |               file_size: 1048576
    +--[detect dupes]-->  +--[MARK]-->    is_duplicate: 0|1
                                          canonical_state: pending
```

**Process:**
1. Scan all files in drop directory (excludes `.venv`, `__pycache__`, etc.)
2. Compute SHA-256 hash for each file
3. Check hash against existing registry entries
4. If duplicate: mark with `is_duplicate=1`, link to original
5. If new: insert with `canonical_state='pending'`

**Database Fields Set:**
- `file_id` (auto-increment)
- `original_path`
- `content_hash`
- `file_size`
- `drop_timestamp`
- `canonical_state='pending'`

### Stage 3: CLASSIFY (cognisys classify)
```
Pending Files                    Classification Pipeline
     |                                    |
     +--[filename features]-->  TF-IDF Vectorizer
     |                                    |
     +--[ML inference]-------->  RandomForest/DistilBERT (96.7% accuracy)
     |                                    |
     +--[pattern matching]--->  Regex Rules (fallback if confidence < 70%)
     |                                    |
     v                                    v
document_type: financial_invoice    confidence: 0.95
method: ml_model                    requires_review: 0
                                    canonical_state: classified
```

**Classification Methods (Priority Order):**
1. **ML Model** - DistilBERT v2 trained on 50 document types
2. **Pattern Matching** - Regex rules for known file patterns
3. **Extension Mapping** - File type based on extension
4. **Fallback** - `general_document` if all else fails

**Document Types (50 categories):**
- Financial: `financial_invoice`, `financial_statement`, `financial_receipt`
- Technical: `technical_script`, `technical_config`, `technical_documentation`
- Personal: `personal_career`, `personal_journal`, `personal_note`
- Business: `business_spreadsheet`, `business_presentation`
- Media: `media_screenshot`, `media_graphic`, `media_video`
- And 40+ more...

**Database Fields Updated:**
- `document_type`
- `confidence`
- `classification_method`
- `requires_review` (1 if confidence < 70%)
- `canonical_state='classified'`

### Stage 4: ORGANIZE (cognisys organize)
```
Classified Files                 Canonical Structure
     |                                    |
     +--[map doc_type]------->  domain_mapping config
     |                                    |
     +--[build path]--------->  {root}/{type}/{YYYY}/{MM}/{filename}
     |                                    |
     +--[move file]---------->  Organized_Canonical/
     |                              |-- Financial/
     |                              |   +-- Invoices/2025/01/
     |                              |-- Technical/
     |                              |   +-- Scripts/
     |                              |   +-- Archives/
     |                              +-- Personal/
     |                                    |
     v                                    v
canonical_path: .../Financial/...   canonical_state: organized
move_count: 1                       last_moved: 2025-12-07
```

**Path Templates (from config):**
```yaml
financial:
  path_template: "Financial/{doc_subtype}/{YYYY}/{MM}/{filename}"
technical:
  path_template: "Technical/{doc_subtype}/{filename}"
personal:
  path_template: "Personal/{doc_subtype}/{YYYY}/{MM}/{filename}"
```

**Database Fields Updated:**
- `canonical_path`
- `canonical_state='organized'`
- `move_count` (incremented)
- `last_moved`

## State Machine

```
                    +-- [hash match] --> DUPLICATE
                    |
PENDING --> CLASSIFIED --> ORGANIZED --> [user moves] --> RE-TRACKED
    |           |              |
    |           |              +-- [file deleted] --> MISSING
    |           |
    |           +-- [low confidence] --> REQUIRES_REVIEW
    |
    +-- [error] --> ERROR
```

**States:**
| State | Description |
|-------|-------------|
| `pending` | Registered, awaiting classification |
| `classified` | ML/pattern classification complete |
| `organized` | Moved to canonical location |
| `duplicate` | Hash match to existing file |
| `missing` | File no longer exists at path |
| `error` | Processing error occurred |

## Feedback Loop

```
User Review                     Training Data
     |                               |
     +--[incorrect?]-->  Submit correction via CLI/Web
     |                               |
     +--[store feedback]-->  feedback_log table
     |                               |
     +--[batch retrain]-->  Update ML model
                                     |
                                     v
                            Improved accuracy
```

## Current Statistics (as of 2025-12-07)

| Metric | Value |
|--------|-------|
| Total tracked | 77,497 files |
| Organized | 77,265 files |
| Duplicates | 394 files |
| ML classified | 31,437 (41%) |
| Pattern classified | 45,000+ (59%) |
| ML Accuracy | 96.7% |

## Key Directories

| Purpose | Path |
|---------|------|
| Canonical Output | `C:\Users\kjfle\Documents\Organized_Canonical` |
| Database | `.cognisys\file_registry.db` |
| Sources Config | `.cognisys\sources.yml` |
| ML Model | `cognisys\models\trained\` |
| Config | `.cognisys\config.yml` |

## Source Library (Configured in `.cognisys/sources.yml`)

| Source Type | Example Path | Scan Mode |
|-------------|--------------|-----------|
| Local | `C:\Users\kjfle\Downloads` | watch |
| Local | `C:\Users\kjfle\Documents` | scheduled |
| Network | `\\NAS\archive` | manual |
| Cloud (Mounted) | `C:\Users\kjfle\OneDrive` | watch |
| Cloud (API) | OneDrive `/Documents` | scheduled |
| Cloud (API) | Google Drive `/My Drive` | scheduled |

## CLI Commands

```bash
# Source Management
cognisys source list                    # List all configured sources
cognisys source add mynas --type network --path "\\\\NAS\\files"
cognisys source add onedrive_docs --type cloud_api --provider onedrive --path "/Documents"
cognisys source status                  # Show scan status for all sources

# Scanning
cognisys scan --source <name>           # Scan specific source
cognisys scan --all                     # Scan all active sources
cognisys scan --watch                   # Start file watcher daemon

# Classification & Organization
cognisys classify --pending             # Classify pending files
cognisys organize --classified          # Organize classified files

# Cloud Integration
cognisys cloud detect                   # Find mounted cloud folders
cognisys cloud auth --provider onedrive # Authenticate with provider
cognisys sync --source onedrive_docs    # Sync specific cloud source
cognisys sync --push-organized          # Push organized files to cloud

# Review and Feedback
cognisys review --low-confidence
cognisys feedback --file-id 12345 --correct-type financial_invoice

# Reports
cognisys stats
cognisys report --format html
```
