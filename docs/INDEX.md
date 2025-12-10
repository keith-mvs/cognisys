# CogniSys Documentation

**Version:** 3.0.0
**Last Updated:** 2024-12-09

Comprehensive documentation for CogniSys - the Cognitive File Organization System.

---

## Quick Links

| Document | Description |
|----------|-------------|
| [Quick Start](getting-started/QUICKSTART.md) | Get up and running in 5 minutes |
| [Setup Guide](getting-started/SETUP_GUIDE.md) | Complete installation and configuration |
| [User Guide](guides/USER_GUIDE.md) | Comprehensive usage documentation |
| [Architecture Overview](architecture/OVERVIEW.md) | System design and components |
| [CLI Reference](reference/CLI_COMMANDS.md) | Complete command reference |

---

## Documentation Structure

```
docs/
├── INDEX.md                              # This file - Documentation hub
│
├── getting-started/
│   ├── QUICKSTART.md                     # 5-minute getting started
│   └── SETUP_GUIDE.md                    # Complete setup and configuration
│
├── architecture/
│   ├── OVERVIEW.md                       # System architecture and design
│   └── REDESIGN_V2.md                    # Drop-to-canonical pipeline
│
├── guides/
│   ├── USER_GUIDE.md                     # Complete user documentation
│   ├── WORKFLOW.md                       # Document processing workflow
│   ├── ML_WORKFLOW.md                    # ML training and classification
│   └── IMPLEMENTATION_PHASES.md          # Phase 3-5 implementation
│
├── reference/
│   ├── CLI_COMMANDS.md                   # Full CLI command reference
│   ├── MCP_INTEGRATION.md                # MCP servers and protocol
│   ├── WEB_SEARCH_EVALUATION.md          # Web search analysis
│   └── BRAVE_SEARCH_SETUP.md             # Brave Search MCP setup
│
└── sessions/
    └── *.md                              # Development session logs
```

---

## Getting Started

### For New Users

1. **[Quick Start Guide](getting-started/QUICKSTART.md)** - Install and run your first scan in 5 minutes
2. **[Setup Guide](getting-started/SETUP_GUIDE.md)** - Complete installation, configuration, and verification
3. **[User Guide](guides/USER_GUIDE.md)** - Learn all features and workflows

### Installation

```bash
# Clone and install
git clone https://github.com/FleithFeming/cognisys-core.git
cd cognisys-core
pip install -r requirements.txt
pip install -e .

# Optional: Cloud storage support
pip install msal keyring cryptography

# Optional: ML model support
pip install torch transformers

# Verify
cognisys --help
```

### Basic Workflow

```
1. Scan     → Index files with metadata and hashes
2. Analyze  → Detect duplicates and patterns
3. Classify → ML-powered document categorization
4. Report   → Generate insights and recommendations
5. Plan     → Create migration strategy
6. Execute  → Apply changes safely with rollback
```

**Quick Commands:**

```bash
cognisys scan --roots "C:\Users\Documents"
cognisys analyze --session <session-id>
cognisys report --session <session-id> --format html
cognisys plan --session <session-id>
cognisys dry-run --plan <plan-id>
cognisys execute --plan <plan-id>
```

---

## Key Features

### Multi-Source File Library

Manage files across local drives, network shares, and cloud storage through a unified interface.

- **Local sources**: Local filesystem directories
- **Network sources**: SMB/NFS network shares
- **Cloud sources**: OneDrive, Google Drive, iCloud, Proton Drive

See: [Architecture Overview](architecture/OVERVIEW.md#multi-source-file-library)

### Intelligent Classification

ML-powered document categorization with 96.7% accuracy:

- **Pattern Classifier**: 40+ rule-based patterns for high-confidence matches
- **ML Classifier**: DistilBERT v2 trained on 77k+ files
- **NVIDIA NIM**: Optional fallback for low-confidence cases

See: [ML Workflow Guide](guides/ML_WORKFLOW.md)

### Smart Deduplication

4-stage pipeline for accurate duplicate detection:

1. **Pre-filter**: Group by size and extension
2. **Quick hash**: First 1MB comparison
3. **Full hash**: Complete SHA-256 verification
4. **Fuzzy match**: Filename similarity scoring

See: [Architecture Overview](architecture/OVERVIEW.md#progressive-hashing-strategy)

### Safe Migration

Non-destructive file organization with safety features:

- **Dry-run preview**: See all changes before execution
- **Checkpoint rollback**: Automatic recovery on failure
- **Full audit trail**: Complete logging of operations

See: [User Guide](guides/USER_GUIDE.md#migration-and-organization)

### MCP Integration

Model Context Protocol support for AI assistant integration:

- Custom CogniSys MCP server with 6 specialized tools
- Third-party server integration (SQLite, Memory, Git, Brave Search)
- Event-driven automation through hooks

See: [MCP Integration Guide](reference/MCP_INTEGRATION.md)

---

## Documentation by Topic

### Installation & Setup

| Document | Description |
|----------|-------------|
| [Quick Start](getting-started/QUICKSTART.md) | 5-minute installation and first scan |
| [Setup Guide](getting-started/SETUP_GUIDE.md) | Detailed setup, configuration, verification |

### Usage & Workflows

| Document | Description |
|----------|-------------|
| [User Guide](guides/USER_GUIDE.md) | Complete usage documentation |
| [Workflow Guide](guides/WORKFLOW.md) | End-to-end processing workflow |
| [CLI Reference](reference/CLI_COMMANDS.md) | All CLI commands with examples |

### Architecture & Design

| Document | Description |
|----------|-------------|
| [Architecture Overview](architecture/OVERVIEW.md) | System design, components, data flow |
| [Redesign V2](architecture/REDESIGN_V2.md) | Drop-to-canonical pipeline design |

### Advanced Topics

| Document | Description |
|----------|-------------|
| [ML Workflow](guides/ML_WORKFLOW.md) | Training and classification pipeline |
| [MCP Integration](reference/MCP_INTEGRATION.md) | MCP servers and automation |
| [Implementation Phases](guides/IMPLEMENTATION_PHASES.md) | Development roadmap |

### Integration

| Document | Description |
|----------|-------------|
| [MCP Integration](reference/MCP_INTEGRATION.md) | Model Context Protocol |
| [Brave Search Setup](reference/BRAVE_SEARCH_SETUP.md) | Web search enhancement |
| [Web Search Evaluation](reference/WEB_SEARCH_EVALUATION.md) | Search provider analysis |

---

## Glossary

| Term | Definition |
|------|------------|
| **Canonical** | The designated "master" copy when duplicates are found |
| **Confidence** | ML classification certainty (0.0 to 1.0) |
| **Document Type** | Classification category (e.g., `financial_invoice`) |
| **Quick Hash** | SHA-256 hash of first 1MB for fast comparison |
| **Session** | A scan operation with unique ID (format: `YYYYMMDD-HHMMSS-xxxx`) |
| **Source** | A configured file location (local, network, or cloud) |
| **MCP** | Model Context Protocol for AI assistant integration |
| **Pattern Classifier** | Rule-based classification using filename patterns |

---

## Testing

```bash
# Run all unit tests
pytest tests/unit/ -v

# Run specific test module
pytest tests/unit/test_scanner.py

# Run with coverage
pytest tests/unit/ --cov=cognisys --cov-report=html
```

200+ unit tests covering:
- File scanning and hashing
- Duplicate detection and analysis
- Migration planning and execution
- Pattern classification
- Cloud storage interfaces

---

## Additional Resources

### Project Files

- [Main README](../README.md) - Project overview and features
- [CLAUDE.md](../CLAUDE.md) - Claude Code integration guide
- [Session Logs](sessions/) - Development history

### External Resources

- [MCP Specification](https://modelcontextprotocol.io/docs)
- [DistilBERT Documentation](https://huggingface.co/docs/transformers/model_doc/distilbert)
- [Python MCP SDK](https://github.com/modelcontextprotocol/python-sdk)

### Support

For issues, questions, or feature requests:
- Create an issue in the repository
- Review logs in `logs/` directory
- Check configuration files for syntax errors

---

*CogniSys - Bringing order to digital chaos.*
