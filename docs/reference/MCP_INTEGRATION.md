# CogniSys MCP Integration Guide

**Version:** 2.0.0
**Last Updated:** 2024-12-09

Comprehensive documentation for Model Context Protocol (MCP) integration with CogniSys, including the custom CogniSys MCP server and recommended third-party servers.

---

## Table of Contents

1. [Introduction](#introduction)
2. [CogniSys MCP Server](#cognisys-mcp-server)
   - [Overview](#overview)
   - [Installation](#installation)
   - [Tool Reference](#tool-reference)
   - [Configuration](#configuration)
   - [Usage Examples](#usage-examples)
3. [Third-Party MCP Servers](#third-party-mcp-servers)
   - [High Priority Integrations](#high-priority-integrations)
   - [Medium Priority Integrations](#medium-priority-integrations)
   - [Optional Integrations](#optional-integrations)
4. [Hooks and Automation](#hooks-and-automation)
5. [Integration Patterns](#integration-patterns)
6. [Troubleshooting](#troubleshooting)

---

## Introduction

### What is MCP?

The **Model Context Protocol (MCP)** is an open standard that enables AI assistants to interact with external tools, databases, and services through a unified interface. MCP servers expose capabilities as "tools" that AI assistants can invoke programmatically.

### Why MCP for CogniSys?

MCP integration provides:

- **Direct Database Access**: Query classification data without writing scripts
- **Real-time Classification**: Classify files through conversational AI
- **Workflow Automation**: Trigger CogniSys operations from AI assistants
- **Cross-tool Integration**: Connect CogniSys with other MCP-enabled services
- **Enhanced Debugging**: Inspect and modify classifications interactively

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        AI Assistant                              │
│                   (Claude Desktop, IDE)                          │
└─────────────────────────────────┬───────────────────────────────┘
                                  │ MCP Protocol
                                  │ (JSON-RPC over stdio)
                    ┌─────────────┴─────────────┐
                    │                           │
        ┌───────────▼───────────┐   ┌───────────▼───────────┐
        │   CogniSys MCP Server │   │  Third-Party Servers  │
        │                       │   │   (SQLite, Memory,    │
        │  - classify_file      │   │    Git, Brave, etc.)  │
        │  - get_statistics     │   │                       │
        │  - query_documents    │   └───────────────────────┘
        │  - reclassify_file    │
        │  - get_review_cands   │
        │  - get_doc_details    │
        └───────────┬───────────┘
                    │
        ┌───────────▼───────────┐
        │   CogniSys Database   │
        │   (SQLite Registry)   │
        └───────────────────────┘
```

---

## CogniSys MCP Server

### Overview

The CogniSys MCP Server exposes core file classification and organization operations through the MCP protocol. It provides six specialized tools for interacting with the CogniSys classification system.

**Source Location:** `cognisys/mcp/server.py`

**Server Name:** `cognisys`

**Protocol:** JSON-RPC over stdio (standard MCP transport)

### Installation

#### Prerequisites

```bash
# Python MCP SDK
pip install mcp

# Ensure CogniSys is installed
pip install -e .
```

#### Adding to Claude Desktop

Edit your Claude Desktop configuration file:

**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "cognisys": {
      "command": "python",
      "args": ["-m", "cognisys.mcp.server"],
      "env": {
        "COGNISYS_DB_PATH": "C:/Users/kjfle/Workspace/cognisys/.cognisys/file_registry.db"
      }
    }
  }
}
```

#### Running Standalone

```bash
# Direct execution
python -m cognisys.mcp.server

# Or via the module
python cognisys/mcp/server.py
```

### Tool Reference

The CogniSys MCP server exposes six tools:

#### 1. `classify_file`

Classify a file using the CogniSys ML pipeline.

**Purpose:** Submit a file for classification and receive document type with confidence score.

**Input Schema:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file_path` | string | Yes | Absolute path to the file to classify |

**Response:** Document type, confidence score, and classification details.

**Example:**

```json
{
  "tool": "classify_file",
  "arguments": {
    "file_path": "C:/Users/kjfle/Documents/invoice_2024.pdf"
  }
}
```

**Response:**

```
File Classification Request
==================================================

File: C:/Users/kjfle/Documents/invoice_2024.pdf
Status: Classification pipeline integration pending

Note: This tool will be connected to the CogniSys ML pipeline
to provide real-time file classification.
```

---

#### 2. `get_statistics`

Retrieve classification statistics from the CogniSys database.

**Purpose:** Get aggregate metrics including document counts, confidence distribution, and domain breakdown.

**Input Schema:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `detailed` | boolean | No | false | Include extended breakdown by document type |

**Response:** Formatted statistics report.

**Example:**

```json
{
  "tool": "get_statistics",
  "arguments": {
    "detailed": true
  }
}
```

**Response:**

```
CogniSys Classification Statistics
==================================================

Total Documents: 77,482
Average Confidence: 87.34%

Confidence Distribution:
  Very High (>=90%)           45,231 ( 58.4%)
  High (75-90%)               18,742 ( 24.2%)
  Medium (50-75%)              9,856 ( 12.7%)
  Low (25-50%)                 2,841 (  3.7%)
  Very Low (<25%)                812 (  1.0%)

Document Types (Top 15):
  financial_invoice                8,234 ( 10.6%)
  automotive_technical             6,521 (  8.4%)
  personal_journal                 5,892 (  7.6%)
  ...
```

---

#### 3. `query_documents`

Query the CogniSys database with filters.

**Purpose:** Search documents by type, confidence range, or filename pattern.

**Input Schema:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `document_type` | string | No | - | Filter by document type (e.g., 'financial_invoice') |
| `min_confidence` | number | No | - | Minimum confidence score (0.0 to 1.0) |
| `max_confidence` | number | No | - | Maximum confidence score (0.0 to 1.0) |
| `filename_pattern` | string | No | - | SQL LIKE pattern (e.g., '%BMW%', '%.pdf') |
| `limit` | integer | No | 50 | Maximum results to return |

**Response:** List of matching documents with metadata.

**Example - Find low-confidence files:**

```json
{
  "tool": "query_documents",
  "arguments": {
    "max_confidence": 0.5,
    "limit": 10
  }
}
```

**Example - Search by pattern:**

```json
{
  "tool": "query_documents",
  "arguments": {
    "filename_pattern": "%invoice%",
    "document_type": "financial_invoice"
  }
}
```

**Response:**

```
Found 10 document(s):

[1234] Invoice_2024-03-15.pdf
  Type: financial_invoice
  Confidence: 92.45%
  Path: C:/Users/kjfle/Documents/Organized/Financial/Invoices/...

[1235] vendor_invoice_march.pdf
  Type: financial_invoice
  Confidence: 88.21%
  Path: C:/Users/kjfle/Documents/Organized/Financial/Invoices/...
```

---

#### 4. `reclassify_file`

Manually reclassify a file to a new document type.

**Purpose:** Override automatic classification with manual correction. Updates database and prepares file for reorganization.

**Input Schema:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `file_id` | integer | Yes | - | Database ID of the file |
| `new_type` | string | Yes | - | New document type to assign |
| `confidence` | number | No | 1.0 | Confidence score (0.0 to 1.0) |

**Response:** Confirmation with old/new classification details.

**Example:**

```json
{
  "tool": "reclassify_file",
  "arguments": {
    "file_id": 1234,
    "new_type": "automotive_service",
    "confidence": 1.0
  }
}
```

**Response:**

```
File Reclassified Successfully
==================================================

File ID: 1234
Filename: diagnostic_report.pdf
Old Type: medical_record
New Type: automotive_service
Confidence: 100.00%

Note: File will be moved to new location on next reorganization run.
Run: cognisys reclassify execute --plan <plan-id>
```

---

#### 5. `get_review_candidates`

Retrieve files that need manual review.

**Purpose:** Identify files with low confidence or ambiguous classifications for human review.

**Input Schema:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `priority` | string | No | "critical" | Priority level: "critical", "high", or "all" |
| `limit` | integer | No | 20 | Maximum candidates to return |

**Priority Levels:**

- **critical**: Confidence < 50% OR document_type = 'unknown'
- **high**: Confidence < 75% OR type in ('unknown', 'general_document')
- **all**: Confidence < 75% OR type in ('unknown', 'general_document', 'form')

**Example:**

```json
{
  "tool": "get_review_candidates",
  "arguments": {
    "priority": "high",
    "limit": 10
  }
}
```

**Response:**

```
Review Candidates (HIGH priority) - 10 file(s):

[5678] ambiguous_document.pdf
  Current Type: unknown
  Confidence: 23.45%
  Action: Review and reclassify if needed

[5679] diagnostic_report_march.pdf
  Current Type: medical_record
  Confidence: 48.12%
  Action: Review and reclassify if needed
```

---

#### 6. `get_document_details`

Get comprehensive information about a specific document.

**Purpose:** Retrieve full metadata, classification details, and file location for inspection.

**Input Schema:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file_id` | integer | Yes | Database ID of the file |

**Response:** Complete document metadata including file existence check.

**Example:**

```json
{
  "tool": "get_document_details",
  "arguments": {
    "file_id": 1234
  }
}
```

**Response:**

```
Document Details
==================================================

ID: 1234
Filename: Invoice_2024-03-15.pdf
Document Type: financial_invoice
Confidence: 92.45%
Created: 2024-03-15 10:30:22

File Location:
  Path: C:/Users/kjfle/Documents/Organized/Financial/Invoices/Invoice_2024-03-15.pdf
  Exists: Yes

Actions:
  - Reclassify: reclassify_file(file_id=1234, new_type="...")
  - Query similar: query_documents(document_type="financial_invoice")
```

---

### Configuration

#### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `COGNISYS_DB_PATH` | Path to SQLite database | `cognisys/data/training/cognisys_ml.db` |
| `COGNISYS_ORGANIZED_ROOT` | Root directory for organized files | `C:/Users/kjfle/Documents/Organized_V2` |

#### Database Path Configuration

The server reads the database path from:

1. `COGNISYS_DB_PATH` environment variable
2. Default path: `cognisys/data/training/cognisys_ml.db`

### Usage Examples

#### Workflow: Review and Correct Misclassifications

```
1. Get review candidates
   → get_review_candidates(priority="critical", limit=20)

2. Inspect suspicious file
   → get_document_details(file_id=5678)

3. Search for similar files
   → query_documents(filename_pattern="%diagnostic%")

4. Correct classification
   → reclassify_file(file_id=5678, new_type="automotive_service", confidence=1.0)

5. Verify statistics
   → get_statistics(detailed=true)
```

#### Workflow: Classify New Files

```
1. Classify incoming file
   → classify_file(file_path="C:/Users/kjfle/00_Inbox/new_document.pdf")

2. Review classification result

3. If incorrect, manually reclassify
   → reclassify_file(file_id=<new_id>, new_type="correct_type")
```

---

## Third-Party MCP Servers

### High Priority Integrations

#### SQLite MCP Server

**Purpose:** Direct SQL queries on CogniSys database.

**Why Critical:** Query classification statistics without writing Python scripts.

```bash
# Installation
npm install -g @modelcontextprotocol/server-sqlite

# Configuration
{
  "mcpServers": {
    "sqlite": {
      "command": "npx",
      "args": [
        "-y", "@modelcontextprotocol/server-sqlite",
        "--db-path", "C:/Users/kjfle/Workspace/cognisys/.cognisys/file_registry.db"
      ]
    }
  }
}
```

**Example Queries:**

```sql
-- Low confidence files
SELECT file_name, document_type, confidence
FROM file_registry
WHERE confidence < 0.60
ORDER BY confidence ASC;

-- Documents by type
SELECT document_type, COUNT(*) as count
FROM file_registry
GROUP BY document_type
ORDER BY count DESC;
```

---

#### Memory MCP Server

**Purpose:** Persistent memory for classification decisions and preferences.

**Why Important:** Remember manual corrections and learn user preferences.

```bash
# Installation
npm install -g @modelcontextprotocol/server-memory

# Configuration
{
  "mcpServers": {
    "memory": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-memory"]
    }
  }
}
```

**Usage:**

```
Store: "Files from 'ECS Tuning' should be automotive_service"
Store: "Files with 'yoga' in name are personal_journal, not hr_resume"
Store: "User prefers YYYY-MM-DD date format in filenames"
```

---

#### Filesystem MCP Server

**Purpose:** File operations and monitoring.

**Capabilities:**
- Read files directly
- List directory contents
- Check file existence
- Get file metadata

```bash
# Configuration
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": [
        "-y", "@modelcontextprotocol/server-filesystem",
        "--root", "C:/Users/kjfle"
      ]
    }
  }
}
```

---

### Medium Priority Integrations

#### Git MCP Server

**Purpose:** Version control for configuration and classification rules.

```bash
# Configuration
{
  "mcpServers": {
    "git": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-git"],
      "env": {
        "GIT_DIR": "C:/Users/kjfle/Workspace/cognisys/.git"
      }
    }
  }
}
```

---

#### Brave Search MCP Server

**Purpose:** Web search for document metadata enrichment.

```bash
# Configuration
{
  "mcpServers": {
    "brave-search": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-brave-search"],
      "env": {
        "BRAVE_API_KEY": "your-api-key"
      }
    }
  }
}
```

See [Brave Search Setup Guide](BRAVE_SEARCH_SETUP.md) for detailed configuration.

---

#### Google Drive MCP Server

**Purpose:** Cloud storage integration.

```bash
# Configuration
{
  "mcpServers": {
    "gdrive": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-gdrive"],
      "env": {
        "GOOGLE_API_KEY": "your-api-key",
        "GOOGLE_CLIENT_ID": "your-client-id"
      }
    }
  }
}
```

---

### Optional Integrations

| Server | Purpose | Use Case |
|--------|---------|----------|
| Puppeteer | Web scraping | Metadata enrichment from vendor websites |
| Sequential Thinking | Reasoning | Complex classification decisions |
| Slack | Notifications | Alert on classification events |
| Time | Scheduling | Automated processing schedules |

---

## Hooks and Automation

CogniSys supports event-driven automation through hooks. Hooks are YAML configurations that trigger actions in response to events.

### Hook Configuration

Create hooks in `.claude/hooks/` directory:

```yaml
# .claude/hooks/auto-classify-inbox.yml
trigger: "filesystem.watch"
watch:
  path: "C:/Users/kjfle/00_Inbox/**"
  events: ["create", "modify"]

actions:
  - name: "Classify New File"
    command: "cognisys classify-file --file {file_path}"

  - name: "Move to Organized"
    on_success:
      command: "cognisys reclassify execute"

  - name: "Update Review List"
    on_low_confidence:
      command: "cognisys reclassify low-confidence --add {file_path}"
```

### Pre-defined Hook Templates

#### Auto-Classify Inbox

```yaml
trigger: "filesystem.watch"
watch:
  path: "C:/Users/kjfle/00_Inbox/**"
  events: ["create"]
actions:
  - name: "Classify"
    command: "cognisys classify-file --file {file_path}"
```

#### Weekly Statistics Report

```yaml
trigger: "schedule.weekly"
schedule: "0 9 * * MON"
actions:
  - name: "Generate Stats"
    command: "cognisys reclassify stats > reports/weekly_{date}.txt"
```

#### Low Confidence Alert

```yaml
trigger: "classification.complete"
conditions:
  - confidence < 0.50
  - document_type == "unknown"
actions:
  - name: "Notify"
    notification:
      title: "Low Confidence Classification"
      message: "{file_name}: {document_type} ({confidence}%)"
```

---

## Integration Patterns

### Pattern 1: Interactive Review Workflow

```
User: "Show me files needing review"
Assistant: → get_review_candidates(priority="critical")

User: "Tell me more about file 5678"
Assistant: → get_document_details(file_id=5678)

User: "That should be automotive, not medical"
Assistant: → reclassify_file(file_id=5678, new_type="automotive_service")

User: "How many automotive files do we have now?"
Assistant: → query_documents(document_type="automotive_service")
```

### Pattern 2: Batch Analysis

```
User: "Analyze all files with less than 60% confidence"
Assistant: → query_documents(max_confidence=0.6, limit=100)

User: "Find all BMW-related documents"
Assistant: → query_documents(filename_pattern="%BMW%")

User: "What's our overall confidence distribution?"
Assistant: → get_statistics(detailed=true)
```

### Pattern 3: Automated Pipeline

```
1. Filesystem hook detects new file in inbox
2. classify_file() invoked automatically
3. If confidence < 50%, add to review queue
4. User reviews via get_review_candidates()
5. User corrects via reclassify_file()
6. Statistics updated via get_statistics()
```

---

## Troubleshooting

### Common Issues

#### Server Not Starting

```
Error: Cannot connect to MCP server 'cognisys'
```

**Solution:**
1. Verify Python environment: `python -c "import mcp; print('OK')"`
2. Check database path exists
3. Review Claude Desktop logs

#### Database Connection Error

```
Error: sqlite3.OperationalError: unable to open database file
```

**Solution:**
1. Verify `COGNISYS_DB_PATH` environment variable
2. Check file permissions
3. Ensure parent directory exists

#### Tool Not Found

```
Error: Unknown tool: classify_files (typo)
```

**Solution:**
- Use exact tool names: `classify_file` (singular)
- Check `list_tools()` output for available tools

### Debugging

Enable verbose logging:

```bash
# Set environment variable
export MCP_DEBUG=1

# Run server with debug output
python -m cognisys.mcp.server --debug
```

### Testing Tools

```bash
# Test server startup
echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | python -m cognisys.mcp.server

# Test specific tool
echo '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"get_statistics","arguments":{}},"id":2}' | python -m cognisys.mcp.server
```

---

## Additional Resources

### MCP Protocol Documentation
- [MCP Specification](https://modelcontextprotocol.io/docs)
- [MCP Server Registry](https://github.com/modelcontextprotocol/servers)

### CogniSys Documentation
- [Architecture Overview](../architecture/OVERVIEW.md)
- [CLI Commands](CLI_COMMANDS.md)
- [Quick Start Guide](../getting-started/QUICKSTART.md)

### SDK References
- [Python MCP SDK](https://github.com/modelcontextprotocol/python-sdk)
- [TypeScript MCP SDK](https://github.com/modelcontextprotocol/typescript-sdk)

---

*CogniSys MCP Integration - Bringing AI-powered file management to your workflow.*
