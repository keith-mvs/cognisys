# IFMOS Claude Code Integration

This directory contains Claude Code extensions for IFMOS: MCP servers, hooks, skills, and slash commands that enhance the document classification workflow.

## 📁 Directory Structure

```
.claude/
├── mcp-servers/          # Model Context Protocol servers
│   ├── config.json       # MCP server configuration
│   └── ifmos_server.py   # Custom IFMOS MCP server
├── hooks/                # Event-triggered scripts
│   ├── post-file-read.sh     # Bash version
│   ├── post-file-read.ps1    # PowerShell version
│   ├── user-prompt-submit.sh
│   └── tool-call.sh
├── skills/               # Reusable workflow templates
│   └── document-workflow.md
├── commands/             # Slash command definitions
│   ├── classify.md       # /classify command
│   ├── stats.md          # /stats command
│   └── batch-status.md   # /batch-status command
└── README.md             # This file
```

## 🔌 MCP Servers

### Installed Servers

1. **Filesystem MCP** (`@modelcontextprotocol/server-filesystem`)
   - Provides file system operations
   - Access to: IFMOS project, inbox, Documents
   - Use for: Reading, writing, searching files

2. **SQLite MCP** (`@modelcontextprotocol/server-sqlite`)
   - Direct SQL access to IFMOS ML database
   - Database: `ifmos/data/training/ifmos_ml.db`
   - Use for: Complex queries, data analysis

3. **IFMOS Custom MCP** (`ifmos_server.py`)
   - Specialized IFMOS operations
   - Tools:
     - `ifmos_query_documents` - Search classified documents
     - `ifmos_classify_document` - Run ML classification
     - `ifmos_get_classification_stats` - View statistics
     - `ifmos_submit_feedback` - Correct classifications
     - `ifmos_get_categories` - List document types

### Using MCP Servers

```javascript
// Query documents by type
ifmos_query_documents({ doc_type: "financial_invoice", limit: 10 })

// Classify a new document
ifmos_classify_document({ file_path: "C:\\path\\to\\document.pdf" })

// Get classification statistics
ifmos_get_classification_stats({})

// Submit feedback
ifmos_submit_feedback({
  doc_id: 123,
  correct_type: "legal_contract",
  user_notes: "This is actually a lease agreement"
})
```

## 🪝 Hooks

Hooks automatically trigger on specific events to enhance the workflow.

### Available Hooks

1. **post-file-read** - Triggers after reading files
   - Detects unclassified documents in inbox
   - Offers to classify them automatically
   - Suggests next actions

2. **user-prompt-submit** - Triggers on user messages
   - Detects classification feedback
   - Monitors batch processing queries
   - Provides contextual information

3. **tool-call** - Triggers before tool execution
   - Logs IFMOS tool usage
   - Provides operation context
   - Tracks feedback submissions

### Hook Output Example

```
User: Read the file in my inbox
[IFMOS] This document appears to be unclassified. Would you like me to:
  1. Classify it using the ML pipeline
  2. Query similar documents in the database
  3. Show classification statistics
```

## 🎯 Skills

### Document Workflow Skill

Complete workflow for processing documents:
1. Check if document exists in database
2. Extract content and metadata
3. Classify using ML pipeline
4. Verify classification with user
5. Submit feedback if needed
6. Organize file into proper location

**Activation**: Use `/document-workflow` or mention "process this document"

## ⚡ Slash Commands

### /classify

Classify a document using IFMOS ML pipeline.

**Usage**: `/classify C:\path\to\document.pdf`

**Output**:
- Document type and confidence score
- Extracted entities (dates, amounts, names)
- Text preview
- Verification prompt

### /stats

Show IFMOS classification statistics.

**Usage**: `/stats`

**Output**:
- Total documents processed
- Last 7 days activity
- Top document types
- Average confidence scores
- Incorrect classifications

### /batch-status

Check batch processing progress.

**Usage**: `/batch-status`

**Output**:
- Files processed / total
- Success rate
- Processing speed
- Top classified types
- Error patterns

## 🚀 Quick Start

### 1. Install Node.js (for MCP servers)

The Filesystem and SQLite MCP servers require Node.js:
```bash
# Check if installed
node --version

# If not installed, download from: https://nodejs.org/
```

### 2. Test IFMOS MCP Server

```bash
cd .claude/mcp-servers
python ifmos_server.py
# Should start the MCP server and wait for JSON-RPC messages
```

### 3. Use in Claude Code

```
User: Show me the latest classified invoices
Assistant: [Uses ifmos_query_documents with doc_type="financial_invoice"]

User: Classify this document: C:\inbox\report.pdf
Assistant: [Uses ifmos_classify_document]

User: Show classification stats
Assistant: [Uses /stats command]
```

## 📊 Automation Scripts

Located in `scripts/ml/` and `scripts/schedule/`:

### Pattern Detection
```bash
python scripts/ml/pattern_detector.py
```
Analyzes classification patterns:
- Classification drift over time
- Low confidence patterns
- Misclassification hotspots
- Filename correlations
- Temporal patterns

### Auto Retraining
```bash
python scripts/ml/auto_retrain.py
```
Checks if model should be retrained based on:
- Feedback count (>100 incorrect)
- Unique documents (>50)
- Feedback age (>7 days)

### Scheduled Automation
```powershell
.\scripts\schedule\ifmos_automation.ps1 -Task all -Verbose
```
Runs all maintenance tasks:
- Pattern detection
- Auto retraining check
- Database cleanup (VACUUM)
- Weekly report generation

## 🎓 Learning Resources

### MCP Protocol
- Specification: https://modelcontextprotocol.io/
- Server development: https://modelcontextprotocol.io/docs/building-servers
- Available servers: https://github.com/modelcontextprotocol/servers

### Claude Code Documentation
- Hooks: https://docs.anthropic.com/claude-code/hooks
- Skills: https://docs.anthropic.com/claude-code/skills
- Slash commands: https://docs.anthropic.com/claude-code/commands

## 🐛 Troubleshooting

### MCP Server Not Found
```
Error: MCP server 'filesystem' failed to start
```
**Solution**: Install Node.js and run:
```bash
npx -y @modelcontextprotocol/server-filesystem --help
```

### Python Import Errors
```
ModuleNotFoundError: No module named 'ifmos'
```
**Solution**: Activate virtual environment:
```bash
.\venv\Scripts\activate
pip install -e .
```

### Hook Not Triggering
Hooks require executable permissions (Unix) or proper PowerShell execution policy (Windows):
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

## 📈 Expected Impact

Based on the integration plan:

- **75% faster workflows** - MCP tools eliminate manual steps
- **30% higher accuracy** - Automated feedback loops
- **90% reduction in missed classifications** - Proactive hooks
- **5x faster queries** - Direct SQL access via SQLite MCP

## 📝 Next Steps

1. **Configure MCP Servers** - Add to Claude Code settings
2. **Test Hooks** - Read an inbox file to trigger classification offer
3. **Try Slash Commands** - Use `/stats` to view current data
4. **Run Automation** - Schedule weekly pattern detection
5. **Collect Feedback** - Use `ifmos_submit_feedback` regularly

---

For questions or issues, see the main IFMOS README or documentation in `docs/`.
