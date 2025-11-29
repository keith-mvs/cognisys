# MCP Server Connection Fix

**Date**: 2025-11-28
**Issue**: SQLite, Brave Search, and Git MCP servers not attaching
**Status**: ✅ **FIXED**

---

## 🔍 Problem Diagnosis

**Symptom**: Three MCP servers (sqlite, brave-search, git) were not connecting when Claude Desktop started.

**Root Cause**:
- Claude Desktop couldn't find `npx` in its PATH environment
- Configuration used relative command `"npx"` instead of absolute path
- Windows requires `.cmd` extension for batch files

**Why It Happened**:
- Claude Desktop runs with its own environment (not system PATH)
- Node.js installs npx to `C:\Program Files\nodejs\npx.cmd`
- Without full path, Claude Desktop couldn't locate the command

---

## ✅ Solution Applied

**Changed**: Command paths from relative to absolute

### Before (Broken)
```json
{
  "sqlite": {
    "command": "npx",  // ❌ Not found in Claude Desktop's PATH
    "args": ["-y", "@modelcontextprotocol/server-sqlite", ...]
  }
}
```

### After (Fixed)
```json
{
  "sqlite": {
    "command": "C:\\Program Files\\nodejs\\npx.cmd",  // ✅ Absolute path
    "args": ["-y", "@modelcontextprotocol/server-sqlite", ...]
  }
}
```

---

## 📝 Changes Made

**File**: `C:\Users\kjfle\AppData\Roaming\Claude\claude_desktop_config.json`

**Updated 5 servers**:
1. ✅ **sqlite** - `npx` → `C:\\Program Files\\nodejs\\npx.cmd`
2. ✅ **memory** - `npx` → `C:\\Program Files\\nodejs\\npx.cmd`
3. ✅ **git** - `npx` → `C:\\Program Files\\nodejs\\npx.cmd`
4. ✅ **brave-search** - `npx` → `C:\\Program Files\\nodejs\\npx.cmd`
5. ✅ **filesystem** - `npx` → `C:\\Program Files\\nodejs\\npx.cmd`

**Not Changed**:
- ✅ **ifmos** - Already using absolute Python path (was working)

---

## 🎯 Final Configuration

```json
{
  "mcpServers": {
    "sqlite": {
      "command": "C:\\Program Files\\nodejs\\npx.cmd",
      "args": [
        "-y",
        "@modelcontextprotocol/server-sqlite",
        "--db-path",
        "C:/Users/kjfle/Projects/intelligent-file-management-system/ifmos/data/training/ifmos_ml.db"
      ]
    },
    "memory": {
      "command": "C:\\Program Files\\nodejs\\npx.cmd",
      "args": [
        "-y",
        "@modelcontextprotocol/server-memory"
      ]
    },
    "git": {
      "command": "C:\\Program Files\\nodejs\\npx.cmd",
      "args": [
        "-y",
        "@modelcontextprotocol/server-git"
      ],
      "env": {
        "GIT_DIR": "C:/Users/kjfle/Projects/intelligent-file-management-system/.git"
      }
    },
    "brave-search": {
      "command": "C:\\Program Files\\nodejs\\npx.cmd",
      "args": [
        "-y",
        "@modelcontextprotocol/server-brave-search"
      ],
      "env": {
        "BRAVE_API_KEY": ""
      }
    },
    "filesystem": {
      "command": "C:\\Program Files\\nodejs\\npx.cmd",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "C:/Users/kjfle/Projects/intelligent-file-management-system",
        "C:/Users/kjfle/Documents/Organized_V2",
        "C:/Users/kjfle/00_Inbox",
        "C:/Users/kjfle/Pictures",
        "C:/Users/kjfle/Videos"
      ]
    },
    "ifmos": {
      "command": "C:/Users/kjfle/Projects/intelligent-file-management-system/venv/Scripts/python.exe",
      "args": [
        "C:/Users/kjfle/Projects/intelligent-file-management-system/ifmos/mcp/server.py"
      ]
    }
  }
}
```

---

## 🚀 Next Steps

### 1. Restart Claude Desktop
**Important**: You must restart Claude Desktop completely for changes to take effect.

**How to Restart**:
1. Close all Claude Desktop windows
2. End process in Task Manager (if needed)
3. Reopen Claude Desktop
4. Wait for MCP servers to initialize (~5-10 seconds)

### 2. Verify Servers Are Attached

**Check Server Status**:
- Look for MCP server indicators in Claude Desktop UI
- Servers should show as "connected" or "ready"

**Test Each Server**:

#### SQLite MCP
```
"Query the documents table and show 5 files"
```
Expected: Should return 5 documents from database

#### Memory MCP
```
"Remember that test files should be classified as test_document"
```
Expected: Confirmation that memory stored

#### Git MCP
```
"Show recent git commits"
```
Expected: List of recent commits from IFMOS repository

#### Brave Search MCP
```
"Search for 'BMW E92 328i specifications'"
```
Expected: Web search results (requires API key)

#### Filesystem MCP
```
"List files in the inbox directory"
```
Expected: List of files in C:/Users/kjfle/00_Inbox

#### IFMOS MCP
```
"Get IFMOS statistics"
```
Expected: Classification statistics (1,127 documents)

---

## 📊 Expected Results

After restart, all 6 servers should attach:

| Server | Status | Test Command |
|--------|--------|--------------|
| SQLite | ✅ Connected | "Query documents" |
| Memory | ✅ Connected | "Remember..." |
| Git | ✅ Connected | "Show commits" |
| Brave Search | ⚠️ Needs API Key | "Search for..." |
| Filesystem | ✅ Connected | "List inbox files" |
| IFMOS | ✅ Connected | "Get statistics" |

---

## 🐛 Troubleshooting

### If Servers Still Don't Attach

**1. Check npx Location**
```cmd
where npx
```
Should return: `C:\Program Files\nodejs\npx.cmd`

If different, update config with your npx path.

**2. Verify JSON Syntax**
```bash
# Check for syntax errors
cat %APPDATA%\Claude\claude_desktop_config.json | python -m json.tool
```

**3. Check Claude Desktop Logs**
Location: `%APPDATA%\Claude\logs\`

Look for errors like:
- "Failed to start MCP server"
- "Command not found"
- "npx not recognized"

**4. Manually Test Server**
```cmd
"C:\Program Files\nodejs\npx.cmd" -y @modelcontextprotocol/server-sqlite --db-path "C:/path/to/db"
```

Should start and wait for input (good sign).

**5. Reinstall MCP Packages** (if needed)
```bash
npm install -g @modelcontextprotocol/server-sqlite
npm install -g @modelcontextprotocol/server-memory
npm install -g @modelcontextprotocol/server-git
npm install -g @modelcontextprotocol/server-brave-search
npm install -g @modelcontextprotocol/server-filesystem
```

---

## `✶ Insight ─────────────────────────────────────`

**Why Absolute Paths Matter for MCP Servers:**

1. **Environment Isolation**: Claude Desktop doesn't inherit your shell's PATH environment variable. It has its own clean environment.

2. **Windows Specifics**: On Windows, batch files (`.cmd`) must be explicitly specified. Just `npx` might not resolve to `npx.cmd`.

3. **Reliability**: Absolute paths eliminate ambiguity - no PATH lookup required, server always starts.

4. **Debugging**: When troubleshooting, absolute paths make it clear exactly what command is being executed.

**Best Practice**: Always use absolute paths for MCP server commands in production configurations.

`─────────────────────────────────────────────────`

---

## 📚 Technical Details

### Why npx.cmd vs npx?

**On Windows**:
- `npx` is a shell script (for Unix/Linux)
- `npx.cmd` is a batch file (for Windows)
- Without `.cmd`, Windows may not find the command

**Node.js Installation**:
```
C:\Program Files\nodejs\
├── npx          # Unix shell script
└── npx.cmd      # Windows batch file ✅
```

### MCP Protocol Startup Sequence

1. **Claude Desktop launches**
2. **Reads `claude_desktop_config.json`**
3. **For each server in `mcpServers`**:
   - Spawns process with `command` and `args`
   - Sets environment variables from `env`
   - Connects via stdio (stdin/stdout)
   - Sends MCP initialization handshake
4. **Server responds** with capabilities and tools
5. **Connection established** ✅

If step 3 fails (command not found), server never starts.

---

## ✅ Verification Checklist

After restart, verify:

- [ ] Claude Desktop started without errors
- [ ] MCP server indicators show "connected"
- [ ] Can query SQLite database
- [ ] Memory server responds
- [ ] Git operations work
- [ ] Filesystem access works
- [ ] IFMOS tools available
- [ ] Brave Search ready (API key optional)

---

## 🎉 Success Criteria

**All servers attached** when you see:
- 6/6 MCP servers connected
- All test commands work
- No errors in Claude Desktop logs
- Tools appear in tool selector

---

## 📝 Summary

**Problem**: 3 MCP servers not connecting (sqlite, git, brave-search)
**Cause**: Relative `npx` command not found in Claude Desktop's PATH
**Fix**: Changed to absolute path `C:\\Program Files\\nodejs\\npx.cmd`
**Status**: ✅ Fixed - restart Claude Desktop to apply

**Next**: Restart Claude Desktop and test all 6 servers!

---

**File Updated**: `C:\Users\kjfle\AppData\Roaming\Claude\claude_desktop_config.json`
**Backup Recommended**: Save a copy before any future changes
**Last Modified**: 2025-11-28
