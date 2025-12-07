#!/usr/bin/env python3
"""
Setup Claude Desktop MCP Configuration
Creates/updates claude_desktop_config.json with CogniSys MCP servers
"""

import json
import os
from pathlib import Path

def setup_mcp_config():
    """Create Claude Desktop MCP configuration"""

    # Get AppData path
    appdata = os.getenv('APPDATA')
    if not appdata:
        print("ERROR: APPDATA environment variable not found")
        return False

    # Create Claude directory if it doesn't exist
    claude_dir = Path(appdata) / 'Claude'
    claude_dir.mkdir(parents=True, exist_ok=True)

    config_path = claude_dir / 'claude_desktop_config.json'

    # Get project paths
    project_root = Path(__file__).parent.parent.parent.absolute()
    db_path = project_root / 'cognisys' / 'data' / 'training' / 'cognisys_ml.db'
    git_dir = project_root / '.git'

    # Build configuration
    config = {
        "mcpServers": {
            "sqlite": {
                "command": "npx",
                "args": [
                    "-y",
                    "@modelcontextprotocol/server-sqlite",
                    "--db-path",
                    str(db_path).replace('\\', '/')
                ]
            },
            "memory": {
                "command": "npx",
                "args": [
                    "-y",
                    "@modelcontextprotocol/server-memory"
                ]
            },
            "git": {
                "command": "npx",
                "args": [
                    "-y",
                    "@modelcontextprotocol/server-git"
                ],
                "env": {
                    "GIT_DIR": str(git_dir).replace('\\', '/')
                }
            },
            "brave-search": {
                "command": "npx",
                "args": [
                    "-y",
                    "@modelcontextprotocol/server-brave-search"
                ],
                "env": {
                    "BRAVE_API_KEY": ""
                }
            },
            "filesystem": {
                "command": "npx",
                "args": [
                    "-y",
                    "@modelcontextprotocol/server-filesystem",
                    "C:/Users/kjfle/Projects/intelligent-file-management-system",
                    "C:/Users/kjfle/Documents/Organized_V2",
                    "C:/Users/kjfle/00_Inbox",
                    "C:/Users/kjfle/Pictures",
                    "C:/Users/kjfle/Videos"
                ]
            }
        }
    }

    # Write configuration
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)

    print("=" * 80)
    print("MCP CONFIGURATION SETUP COMPLETE")
    print("=" * 80)
    print(f"Configuration written to: {config_path}")
    print("")
    print("Configured MCP Servers:")
    print("  ✓ SQLite - Query CogniSys database directly")
    print("  ✓ Memory - Learn from your decisions")
    print("  ✓ Git - Track configuration changes")
    print("  ✓ Brave Search - Web search for disambiguation")
    print("  ✓ Filesystem - File operations and watching")
    print("")
    print("NEXT STEPS:")
    print("  1. Restart Claude Desktop to load new configuration")
    print("  2. Test SQLite: Ask 'Query the documents table'")
    print("  3. Test Memory: Say 'Remember that BMW files are automotive'")
    print("  4. Setup Brave API key (optional):")
    print(f"     Edit: {config_path}")
    print("     Add your BRAVE_API_KEY to brave-search.env")
    print("")
    print("=" * 80)

    return True


if __name__ == "__main__":
    success = setup_mcp_config()
    exit(0 if success else 1)
