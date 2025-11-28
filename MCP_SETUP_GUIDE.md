# IFMOS MCP Server Setup Guide

## ✅ Configuration Complete

All MCP servers have been configured and tested successfully!

---

## 🔌 Installed MCP Servers

### 1. **Filesystem MCP** (`@modelcontextprotocol/server-filesystem`)
**Access**: Project directory, inbox, documents folder
**Tools**:
- `read_file` - Read file contents
- `write_file` - Create/modify files
- `list_directory` - List directory contents
- `search_files` - Search for files by name/pattern
- `get_file_info` - Get file metadata

**Use cases**:
- Read classified documents
- Write organized files to new locations
- Search inbox for unprocessed files
- Check file metadata before classification

### 2. **SQLite MCP** (`@modelcontextprotocol/server-sqlite`)
**Access**: IFMOS ML training database
**Tools**:
- `read_query` - Execute SELECT queries
- `write_query` - Execute INSERT/UPDATE/DELETE
- `describe_table` - Get table schema
- `list_tables` - List all database tables

**Use cases**:
- Query classified documents by type/date/confidence
- Update file paths after organization
- Generate classification statistics
- Analyze classification trends

### 3. **Git MCP** (`@modelcontextprotocol/server-git`)
**Access**: IFMOS repository
**Tools**:
- `git_status` - Check repository status
- `git_diff` - View changes
- `git_log` - View commit history
- `git_commit` - Create commits
- `git_branch` - Branch operations

**Use cases**:
- Track code changes
- Create commits for enhancements
- View development history
- Branch management

### 4. **Brave Search MCP** (`@modelcontextprotocol/server-brave-search`)
**Access**: Web search API
**Tools**:
- `brave_web_search` - Search the web

**Use cases**:
- Look up file format specifications
- Search for classification patterns
- Find documentation for dependencies
- Troubleshoot errors

**Note**: Requires Brave API key (set in config or get free at https://brave.com/search/api/)

### 5. **IFMOS Custom MCP** (`.claude/mcp-servers/ifmos_server.py`)
**Access**: IFMOS ML pipeline and classification system
**Tools**:
- `ifmos_query_documents` - Search classified docs
- `ifmos_classify_document` - Run ML classification
- `ifmos_get_classification_stats` - View statistics
- `ifmos_submit_feedback` - Correct classifications
- `ifmos_get_categories` - List document types

**Use cases**:
- Classify new documents
- Query similar documents
- Submit correction feedback
- Monitor classification accuracy

---

## 🪝 Configured Hooks

### 1. **post-file-read Hook**
**Triggers**: After reading any file
**Action**: Detects unclassified documents in inbox/To_Review
**Offers**:
- Auto-classification option
- Similar document search
- Classification statistics

### 2. **user-prompt-submit Hook**
**Triggers**: When user sends a message
**Detects**:
- Classification feedback ("should be classified as...")
- Batch processing queries ("how many classified?")
- Organization requests ("organize files")

**Actions**:
- Captures feedback for model improvement
- Shows batch processing status
- Suggests /organize command

---

## 📋 Available Commands

### `/classify <file_path>`
Classify a document using IFMOS ML pipeline
- Shows: Type, confidence, entities, preview
- Prompts: Verification and feedback option

### `/stats`
View IFMOS classification statistics
- Total documents processed
- Last 7 days activity
- Top document types by count
- Average confidence scores
- Error rates

### `/batch-status`
Check batch processing progress
- Files processed / total
- Success rate
- Processing speed (files/minute)
- Top classified types
- Error patterns

### `/organize`
Organize classified documents into domain folders
- Shows sample organization plan
- Dry-run option (recommended first)
- Batch or selective organization
- Updates database with new paths

---

## 🚀 Quick Start

### Using MCP Tools in Claude Code

```plaintext
User: Query all financial invoices from last month

Claude: [Uses SQLite MCP]
SELECT file_name, file_path, confidence, processing_timestamp
FROM documents
WHERE document_type = 'financial_invoice'
  AND datetime(processing_timestamp) > datetime('now', '-30 days')
ORDER BY processing_timestamp DESC

Results: 24 invoices found...
```

```plaintext
User: Classify this document: C:\Users\kjfle\00_Inbox\invoice.pdf

Claude: [Uses ifmos_classify_document]
Classification Result:
  Type: financial_invoice
  Confidence: 89%
  Entities: Invoice #12345, $1,250.00, Due: 2025-01-15

Is this correct? [yes/no]
```

```plaintext
User: Show me the latest automotive documents

Claude: [Uses ifmos_query_documents]
Found 8 automotive documents:
  1. Parts_Diagram_Engine.pdf (automotive_technical, 92%)
  2. Service_Manual.pdf (automotive_service, 87%)
  ...
```

### Using File Organization

```bash
# Dry run (recommended first)
python scripts/workflows/auto_organize.py --dry-run --max-files 50

# Organize all classified documents
python scripts/workflows/auto_organize.py

# Organize specific document
python -m ifmos.core.file_organizer --doc-id 1127
```

---

## 📊 File Organization Structure

After classification, files are automatically organized into domain-based folders:

```
C:\Users\kjfle\Documents\Organized\
├── Financial\
│   ├── financial_invoice\
│   │   └── 2025\
│   │       └── 11\
│   │           └── 2025-11-28_vendor_12345_invoice.pdf
│   └── financial_statement\
├── Legal\
│   └── legal_contract\
│       └── 2025\
│           └── 2025-11-28_party_contract_type_agreement.pdf
├── Medical\
│   └── patient_name\
│       └── 2025\
│           └── 2025-11-28_provider_visit_record.pdf
├── Automotive\
│   └── vehicle_id\
│       └── automotive_technical\
│           └── parts_diagram.pdf
├── Technical\
│   └── technical_documentation\
│       └── project_name\
│           └── 2025-11-28_product_v1_0_manual.pdf
└── General\
    └── 2025\
        └── 11\
            └── 2025-11-28_document.pdf
```

**Features**:
- Domain-based organization (Financial, Legal, Medical, etc.)
- Chronological sorting (YYYY/MM folders)
- Intelligent naming with extracted metadata
- Automatic conflict resolution (adds `_1`, `_2` suffixes)
- Backup before moving (optional, enabled by default)
- Rollback capability

---

## 🔧 Testing Your Setup

Run the test script to verify everything:

```powershell
.\scripts\setup\test_mcp_servers.ps1
```

Expected output:
```
[SUCCESS] All MCP servers configured correctly!
You can now use MCP tools in Claude Code.

filesystem : OK
sqlite : OK
git : OK
brave-search : OK
ifmos : OK
```

---

## 🎯 Recommended Workflow

### 1. **Classification Phase**
```
1. Files land in: C:\Users\kjfle\00_Inbox\To_Review\
2. Run batch processing: .\scripts\powershell\workflows\batch_process_inbox.ps1
3. Check stats: /stats
4. Review classifications in database
```

### 2. **Feedback Phase**
```
1. Review misclassifications
2. Use /classify to reclassify
3. Submit feedback: ifmos_submit_feedback
4. Feedback stored for model retraining
```

### 3. **Organization Phase**
```
1. Check what's ready: "How many documents need organization?"
2. Run dry-run: python scripts/workflows/auto_organize.py --dry-run
3. Review organization plan
4. Execute: python scripts/workflows/auto_organize.py
5. Files moved to domain folders with intelligent naming
```

### 4. **Maintenance Phase**
```
1. Pattern detection: python scripts/ml/pattern_detector.py
2. Auto-retraining check: python scripts/ml/auto_retrain.py
3. Database cleanup: .\scripts\schedule\ifmos_automation.ps1 -Task cleanup
4. Weekly reports: .\scripts\schedule\ifmos_automation.ps1 -Task report
```

---

## 🎓 Advanced Usage

### Custom Queries via SQLite MCP

```sql
-- Find high-confidence classifications
SELECT document_type, COUNT(*), AVG(confidence)
FROM documents
WHERE confidence > 0.9
GROUP BY document_type
ORDER BY COUNT(*) DESC;

-- Find documents needing review (low confidence)
SELECT file_name, document_type, confidence
FROM documents
WHERE confidence < 0.7
ORDER BY confidence ASC
LIMIT 20;

-- Classification trends by date
SELECT DATE(processing_timestamp) as date,
       document_type,
       COUNT(*) as count
FROM documents
WHERE processing_timestamp > date('now', '-7 days')
GROUP BY date, document_type
ORDER BY date DESC;
```

### Batch Operations via File Organizer

```python
from ifmos.core.file_organizer import FileOrganizer

# Initialize
organizer = FileOrganizer(
    'ifmos/config/domain_mapping.yml',
    'ifmos/data/training/ifmos_ml.db'
)

# Organize specific documents
doc_ids = [1127, 1126, 1125]
result = organizer.organize_batch(doc_ids, dry_run=True)

# Check results
print(f"Success: {result['successful']}/{result['total']}")
```

---

## 🔐 Security Notes

- **Medical documents**: Marked as sensitive in domain_mapping.yml
- **Backups**: Created before moving files (location: C:\Users\kjfle\Documents\IFMOS_Backups)
- **Legal retention**: Configured retention periods (7 years for legal/tax, 10 years for medical/insurance)
- **Database access**: SQLite MCP has read/write access - use carefully
- **Filesystem MCP**: Limited to specified directories only

---

## 🐛 Troubleshooting

### MCP Server Not Found
```
Error: MCP server 'filesystem' failed to start
```
**Solution**: Ensure Node.js is installed and in PATH
```bash
node --version  # Should show v25.0.0 or higher
npx @modelcontextprotocol/server-filesystem --help
```

### Python MCP Server Fails
```
Error: IFMOS MCP server failed to start
```
**Solution**: Check Python virtual environment
```bash
.\venv\Scripts\activate
python .claude\mcp-servers\ifmos_server.py
```

### Hook Not Triggering
**Solution**: Check PowerShell execution policy
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

### Database Lock Error
```
Error: database is locked
```
**Solution**: Close other connections to the database
```bash
# Check what's using the DB
lsof ifmos/data/training/ifmos_ml.db  # Unix
```

---

## 📚 Additional Resources

- **MCP Protocol**: https://modelcontextprotocol.io/
- **Claude Code Docs**: https://docs.claude.com/claude-code
- **IFMOS README**: README.md
- **Integration Guide**: .claude/README.md
- **Domain Mapping**: ifmos/config/domain_mapping.yml

---

## ✅ Configuration Files

All configuration files created:
- `~/.claude/config.json` - MCP servers
- `~/.claude/hooks.json` - Hook configuration
- `ifmos/config/domain_mapping.yml` - File organization rules
- `.claude/mcp-servers/ifmos_server.py` - Custom MCP server
- `.claude/hooks/*.ps1` - Hook scripts

---

**🎉 Setup Complete! You can now use all MCP servers and hooks in Claude Code.**

To verify, run `/mcp` in Claude Code - you should see all 5 servers listed.
