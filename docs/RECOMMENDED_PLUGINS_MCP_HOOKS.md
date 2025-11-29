# IFMOS Recommended Plugins, MCP Servers & Hooks

## Executive Summary

Based on IFMOS architecture and current workflows, here are high-value integrations ranked by priority.

---

## 🔥 HIGH PRIORITY (Immediate Value)

### 1. **SQLite MCP Server** ⭐⭐⭐⭐⭐
**Why Critical**: Direct database querying without writing Python scripts

**Use Cases**:
- Query classification statistics on-the-fly
- Find all files of a specific type instantly
- Analyze confidence scores across domains
- Debug misclassifications quickly

**Setup**:
```bash
# Install
npm install -g @modelcontextprotocol/server-sqlite

# Add to Claude Desktop config
{
  "mcpServers": {
    "sqlite": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-sqlite",
               "--db-path", "C:/Users/kjfle/Projects/intelligent-file-management-system/ifmos/data/training/ifmos_ml.db"]
    }
  }
}
```

**Example Queries**:
```sql
-- Find all low-confidence classifications
SELECT file_name, document_type, confidence
FROM documents
WHERE confidence < 0.60
ORDER BY confidence ASC;

-- Count files per domain
SELECT document_type, COUNT(*) as count
FROM documents
GROUP BY document_type
ORDER BY count DESC;

-- Find misclassified automotive files
SELECT file_name, document_type
FROM documents
WHERE document_type = 'medical'
AND file_name LIKE '%BMW%';
```

**Impact**: 🚀 Instant insights, no scripting needed

---

### 2. **Filesystem MCP Server** (Already Available) ⭐⭐⭐⭐
**Status**: ✅ Already working (1/5 in MCP_STATUS.md)

**Current Capabilities**:
- Read files directly
- List directory contents
- Check file existence
- Get file metadata

**Enhancement Opportunities**:
- Watch directories for new files
- Detect file changes
- Trigger auto-classification on new files

**Hook Integration** (Recommended):
```yaml
# .claude/hooks/on-file-added.yml
on:
  filesystem.file_created:
    paths:
      - "C:/Users/kjfle/00_Inbox/**"
    actions:
      - classify: true
      - organize: true
      - notify: true
```

**Impact**: 🎯 Real-time file management

---

### 3. **Memory MCP Server** ⭐⭐⭐⭐
**Why Important**: Remember your classification decisions and preferences

**Use Cases**:
- Remember manual corrections you've made
- Learn from your review sessions
- Store domain-specific rules you create
- Remember vendor names, project names, etc.

**Setup**:
```bash
# Install
npm install -g @modelcontextprotocol/server-memory

# Add to Claude Desktop config
{
  "mcpServers": {
    "memory": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-memory"]
    }
  }
}
```

**Example Usage**:
```
Store: "All files from 'ECS Tuning' should be classified as automotive_service"
Store: "Files with 'yoga' or 'meditation' in name are personal_journal, not hr_resume"
Store: "User prefers vendor names in format: 'VendorName' not 'Vendor_Name'"
```

**Impact**: 🧠 Learns your preferences over time

---

### 4. **Git MCP Server** ⭐⭐⭐
**Why Useful**: Version control for IFMOS configuration and rules

**Use Cases**:
- Track changes to classification rules
- Revert bad configuration changes
- Document why rules were added
- Collaborate if multiple users

**Setup**:
```bash
# Already have git, just add MCP
{
  "mcpServers": {
    "git": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-git"],
      "env": {
        "GIT_DIR": "C:/Users/kjfle/Projects/intelligent-file-management-system/.git"
      }
    }
  }
}
```

**Auto-commit Hook**:
```yaml
# .claude/hooks/on-classification-update.yml
on:
  reclassification.complete:
    actions:
      - git.commit:
          message: "Updated classification rules - {date}"
          files:
            - "scripts/ml/*.py"
            - "ifmos/config/*.yml"
```

**Impact**: 📚 Configuration history and safety

---

## 🎯 MEDIUM PRIORITY (High Value, Moderate Effort)

### 5. **Puppeteer MCP Server** ⭐⭐⭐⭐
**Why Valuable**: Web scraping for document metadata enrichment

**Use Cases**:
- Look up VINs on CARFAX/vehicle databases
- Search invoice numbers on vendor websites
- Verify product codes on manufacturer sites
- Extract data from web portals

**Setup**:
```bash
npm install -g @modelcontextprotocol/server-puppeteer

{
  "mcpServers": {
    "puppeteer": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-puppeteer"]
    }
  }
}
```

**Example Usage**:
```javascript
// Look up VIN on CARFAX
await page.goto('https://www.carfax.com/vehicle/' + vin);
await page.waitForSelector('.vehicle-info');
const vehicleInfo = await page.evaluate(() => {
  return document.querySelector('.vehicle-info').textContent;
});
```

**Impact**: 🔍 Rich metadata from web sources

---

### 6. **Google Drive MCP Server** ⭐⭐⭐
**Why Important**: Sync with cloud storage

**Use Cases**:
- Scan Google Drive for new documents
- Classify and organize cloud files
- Backup organized files to Drive
- Share review lists via Drive

**Setup**:
```bash
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

**Integration**:
```python
# Auto-backup organized files
if document_organized:
    upload_to_gdrive(file_path, folder='IFMOS_Organized')
```

**Impact**: ☁️ Cloud backup and sharing

---

### 7. **Sequential Thinking MCP** ⭐⭐⭐
**Why Useful**: Break down complex classification decisions

**Use Cases**:
- Analyze ambiguous documents step-by-step
- Reason through edge cases
- Explain classification decisions
- Debug misclassifications

**Setup**:
```bash
{
  "mcpServers": {
    "sequential-thinking": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"]
    }
  }
}
```

**Example**:
```
Step 1: Analyze filename: "Diagnostic Report 20250319.pdf"
Step 2: Check for automotive keywords: None found
Step 3: Check for medical keywords: "Diagnostic" found
Step 4: WARNING - "Diagnostic" is ambiguous!
Step 5: Read content for context...
Step 6: Found "vehicle" and "engine" - classify as automotive_service
```

**Impact**: 🤔 Better edge case handling

---

## 💡 NICE TO HAVE (Specialized Use Cases)

### 8. **Slack MCP Server** ⭐⭐
**Why**: Notifications and collaboration

**Use Cases**:
- Notify when batch processing complete
- Alert on classification errors
- Share review lists with team
- Log file organization events

**Setup**:
```bash
{
  "mcpServers": {
    "slack": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-slack"],
      "env": {
        "SLACK_TOKEN": "your-slack-token"
      }
    }
  }
}
```

---

### 9. **Time MCP Server** ⭐⭐
**Why**: Scheduling and automation

**Use Cases**:
- Schedule daily inbox processing
- Auto-organize files at 2 AM
- Weekly classification accuracy reports
- Monthly backup reminders

---

### 10. **EverArt MCP Server** ⭐⭐
**Why**: Image analysis and metadata

**Use Cases**:
- Extract EXIF data from photos
- Detect duplicate images
- OCR text from scanned documents
- Categorize image types

---

## 🔧 CUSTOM HOOKS (Recommended)

### Hook 1: Auto-Classify Inbox
```yaml
# .claude/hooks/auto-classify-inbox.yml
trigger: "filesystem.watch"
watch:
  path: "C:/Users/kjfle/00_Inbox/**"
  events: ["create", "modify"]

actions:
  - name: "Classify New File"
    command: "python scripts/workflows/auto_organize.py --file {file_path}"

  - name: "Move to Organized"
    on_success:
      command: "python scripts/workflows/reorganize_function_form.py"

  - name: "Update Review List"
    on_low_confidence:
      command: "python scripts/ml/generate_review_list.py --add {file_path}"
```

---

### Hook 2: Pre-Commit Classification Rules
```yaml
# .claude/hooks/pre-commit.yml
trigger: "git.pre_commit"

actions:
  - name: "Validate Classification Rules"
    command: "python scripts/validation/validate_rules.py"

  - name: "Run Tests"
    command: "pytest tests/test_classification.py"

  - name: "Update Documentation"
    command: "python scripts/docs/generate_rule_docs.py"
```

---

### Hook 3: Weekly Stats Report
```yaml
# .claude/hooks/weekly-report.yml
trigger: "schedule.weekly"
schedule: "0 9 * * MON"  # Every Monday at 9 AM

actions:
  - name: "Generate Stats"
    command: "python scripts/reporting/weekly_stats.py"

  - name: "Export Report"
    output: "C:/Users/kjfle/Documents/IFMOS_Reports/weekly_{date}.html"

  - name: "Email Report"
    email:
      to: "your-email@example.com"
      subject: "IFMOS Weekly Report - {date}"
      body: "{report_html}"
```

---

### Hook 4: Low Confidence Alert
```yaml
# .claude/hooks/low-confidence-alert.yml
trigger: "classification.complete"

conditions:
  - confidence < 0.50
  - document_type == "unknown"

actions:
  - name: "Add to Review List"
    command: "python scripts/ml/generate_review_list.py --add {file_path}"

  - name: "Notify User"
    notification:
      title: "Low Confidence Classification"
      message: "{file_name} classified as {document_type} ({confidence}%)"
      urgency: "normal"
```

---

## 📊 PRIORITY MATRIX

| Plugin/MCP | Impact | Effort | Priority |
|-----------|---------|--------|----------|
| SQLite MCP | 🔥🔥🔥🔥🔥 | ⚡ Easy | **DO NOW** |
| Memory MCP | 🔥🔥🔥🔥 | ⚡ Easy | **DO NOW** |
| Brave Search | 🔥🔥🔥🔥 | ⚡ Easy | ✅ **DONE** |
| Filesystem Watch Hook | 🔥🔥🔥🔥 | ⚡⚡ Medium | **DO NEXT** |
| Git MCP | 🔥🔥🔥 | ⚡ Easy | **DO NEXT** |
| Puppeteer MCP | 🔥🔥🔥🔥 | ⚡⚡⚡ Hard | **LATER** |
| Google Drive MCP | 🔥🔥🔥 | ⚡⚡ Medium | **LATER** |
| Sequential Thinking | 🔥🔥🔥 | ⚡ Easy | **NICE TO HAVE** |
| Slack MCP | 🔥🔥 | ⚡ Easy | **NICE TO HAVE** |
| Time/Schedule MCP | 🔥🔥 | ⚡⚡ Medium | **NICE TO HAVE** |

---

## 🎯 RECOMMENDED IMPLEMENTATION ORDER

### Phase 1: Immediate (This Week)
1. **SQLite MCP** - Instant database queries
2. **Memory MCP** - Learn preferences
3. **Auto-Classify Inbox Hook** - Real-time processing

**Time Investment**: 1-2 hours
**Expected Impact**: 🚀 Massive workflow improvement

### Phase 2: Short-Term (Next 2 Weeks)
4. **Git MCP** - Configuration version control
5. **Filesystem Watch Hook** - Auto-detect new files
6. **Weekly Stats Hook** - Automated reporting

**Time Investment**: 2-3 hours
**Expected Impact**: 📊 Better insights and automation

### Phase 3: Medium-Term (Next Month)
7. **Puppeteer MCP** - Web scraping for metadata
8. **Google Drive MCP** - Cloud sync
9. **Low Confidence Alert Hook** - Proactive review

**Time Investment**: 4-6 hours
**Expected Impact**: 🔍 Enhanced metadata and cloud integration

---

## 💎 HIDDEN GEM: Custom IFMOS MCP Server

**Consider building**: `@ifmos/mcp-server`

**Capabilities**:
- Expose IFMOS operations via MCP
- Allow other tools to query classifications
- Provide classification as a service
- Enable remote management

**Structure**:
```javascript
// ifmos-mcp-server/index.js
import { Server } from '@modelcontextprotocol/sdk/server/index.js';

const server = new Server({
  name: 'ifmos',
  version: '1.0.0',
});

// Expose classification endpoint
server.tool('classify_file', async ({ file_path }) => {
  // Call IFMOS classification
  const result = await ifmos.classify(file_path);
  return result;
});

// Expose organization endpoint
server.tool('organize_file', async ({ file_path, doc_type }) => {
  const result = await ifmos.organize(file_path, doc_type);
  return result;
});

// Query stats
server.tool('get_stats', async () => {
  const stats = await ifmos.getStats();
  return stats;
});
```

**Impact**: 🎁 IFMOS becomes reusable across projects

---

## 🚀 Quick Start Guide

### Step 1: Install Top 3 MCP Servers (15 minutes)

```bash
# SQLite
npm install -g @modelcontextprotocol/server-sqlite

# Memory
npm install -g @modelcontextprotocol/server-memory

# Git
npm install -g @modelcontextprotocol/server-git
```

### Step 2: Configure Claude Desktop

Edit: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "brave-search": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-brave-search"],
      "env": {
        "BRAVE_API_KEY": "your-key"
      }
    },
    "sqlite": {
      "command": "npx",
      "args": [
        "-y", "@modelcontextprotocol/server-sqlite",
        "--db-path", "C:/Users/kjfle/Projects/intelligent-file-management-system/ifmos/data/training/ifmos_ml.db"
      ]
    },
    "memory": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-memory"]
    },
    "git": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-git"],
      "env": {
        "GIT_DIR": "C:/Users/kjfle/Projects/intelligent-file-management-system/.git"
      }
    }
  }
}
```

### Step 3: Create First Hook (5 minutes)

```bash
# Create hooks directory
mkdir -p .claude/hooks

# Create auto-classify hook
cat > .claude/hooks/auto-classify.yml << EOF
trigger: manual
actions:
  - name: "Classify Inbox"
    command: "python scripts/workflows/auto_organize.py"
EOF
```

### Step 4: Test (2 minutes)

```bash
# Test SQLite MCP
claude query "SELECT COUNT(*) FROM documents WHERE confidence < 0.50"

# Test Memory MCP
claude remember "User prefers YYYY-MM-DD date format in filenames"

# Test Hook
claude trigger auto-classify
```

---

## 📚 Additional Resources

### MCP Registry
- https://github.com/modelcontextprotocol/servers
- Browse all available MCP servers

### Claude Code Hooks
- `.claude/hooks/` directory
- YAML-based configuration
- Event-driven automation

### Custom Development
- MCP SDK: https://github.com/modelcontextprotocol/typescript-sdk
- Python SDK: https://github.com/modelcontextprotocol/python-sdk

---

## 🎓 Conclusion

**Top 3 Recommendations for IFMOS**:
1. **SQLite MCP** - Query database directly in chat
2. **Memory MCP** - Learn from your decisions
3. **Filesystem Watch Hook** - Auto-process new files

**Expected Results**:
- 🚀 10x faster debugging and analysis
- 🧠 System learns your preferences
- ⚡ Real-time file processing
- 📊 Better insights and reporting

**Next Steps**:
1. Install SQLite + Memory MCP (15 min)
2. Test with sample queries (5 min)
3. Create auto-classify hook (10 min)
4. Enjoy automated file management! 🎉

---

**Ready to level up IFMOS?** Let me know which plugins you'd like to implement first!
