# Context Management for IFMOS Sessions

**Last Updated**: 2025-12-01
**Current Token Usage**: 85,834/200,000 (42%)

---

## Overview

Claude Code has a 200k token context limit. For large projects like IFMOS, proactive context management prevents hitting the limit mid-session.

---

## Current Approach: Session Exports

### Structure
```
.sessions/
├── CONTEXT_MANAGEMENT.md           # This file
├── session_YYYYMMDD_description.md # Session exports
└── session_index.md                 # Index of all sessions
```

### When to Export
1. **Before hitting 150k tokens** (75% of limit)
2. **At completion of major feature**
3. **When switching to different task/feature**
4. **Before long-running operations** (e.g., training)

### What to Include
- **Objectives**: What was the goal?
- **Completed work**: Files created/modified
- **Technical decisions**: Why certain approaches were chosen
- **Issues encountered**: Problems and solutions
- **Next steps**: What comes after
- **Key insights**: Learnings and patterns discovered

---

## Recommended Workflow

### 1. Start of Session
```
User: "Continue work on [feature], reference session_20251201_distilbert_training.md"
Claude: Reads session export, understands context, continues work
```

### 2. During Session
- Monitor token usage
- Export at milestones (feature complete, before training, etc.)
- Commit session exports to git

### 3. End of Session
- Create comprehensive session export
- Commit all code changes
- Push to remote
- User can start fresh session with reference

---

## Session Export Template

```markdown
# Session: [Feature Name]
**Date**: YYYY-MM-DD
**Status**: [In Progress/Complete/Blocked]
**Tokens**: X/200,000 (Y%)

---

## Session Objectives
[What are we trying to accomplish?]

---

## Completed Work
[What was done in this session?]

### Files Created
- `file1.py` - Description
- `file2.py` - Description

### Files Modified
- `file3.py` - What changed

---

## Technical Decisions
[Why certain approaches were chosen]

---

## Issues Encountered
[Problems and how they were solved]

---

## Next Steps
[What comes after this session]

---

## Key Insights
[Learnings and patterns discovered]
```

---

## Token Budget Guidelines

| Token Range | Action |
|-------------|--------|
| 0-50k | Normal operation |
| 50-100k | Consider exporting at next milestone |
| 100-150k | Export soon, plan session end |
| 150-175k | **URGENT**: Export and prepare to wrap up |
| 175-200k | **CRITICAL**: Complete current task, export immediately |

---

## Session Types

### 1. Feature Implementation
- One session per major feature
- Export when feature complete
- Name: `session_YYYYMMDD_feature_name.md`

### 2. Bug Investigation
- One session per bug (or related bug cluster)
- Export when resolved or blocked
- Name: `session_YYYYMMDD_bug_description.md`

### 3. Exploration/Research
- One session per research area
- Export findings and recommendations
- Name: `session_YYYYMMDD_research_topic.md`

### 4. Training/Long Operations
- Export before starting long operation
- Include progress monitoring commands
- Update when operation completes
- Name: `session_YYYYMMDD_operation_name.md`

---

## Example Session Timeline

### Session 1: DistilBERT Training (Current)
```
Start:     0k tokens
Work:      Export data, create training script, optimize
Export:    85k tokens → session_20251201_distilbert_training.md
Commit:    Git commit with session export
Continue:  Training runs in background
```

### Session 2: DistilBERT Integration (Next)
```
Start:     Reference session_20251201_distilbert_training.md
Work:      Integrate trained model into IFMOS
Export:    When integration complete
Commit:    Git commit
```

---

## Automated Export Script (Future Enhancement)

```python
#!/usr/bin/env python3
"""Auto-export session when approaching token limit"""

import anthropic
from datetime import datetime

def should_export(token_usage: int) -> bool:
    """Check if session should be exported"""
    return token_usage > 150_000  # 75% of limit

def export_session(conversation_history: list, feature_name: str):
    """Export session to markdown"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f".sessions/session_{timestamp}_{feature_name}.md"

    # Generate summary using Claude
    # Extract key information
    # Write to file
    # Return filename

# Usage in workflow
if should_export(current_tokens):
    export_session(history, "distilbert_training")
    print(f"Session exported. Start fresh conversation.")
```

---

## Git Integration

### Session Exports as Git History
- Each session export is committed to git
- Provides timeline of project development
- Easy to reference past decisions

### Commit Message Format
```
Add session: [Feature Name]

Session export with:
- Implementation details
- Technical decisions
- Issues and solutions
- Next steps

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

---

## Context Compaction Strategies

### What NOT to Repeat
- Full file contents (reference file paths instead)
- Progress bar output (use summary stats)
- Verbose error messages (include key errors only)
- Redundant explanations

### What TO Keep
- Technical decisions and rationale
- Issue resolutions
- Key insights
- File paths and line numbers
- Commands for reproduction

---

## Session Index

Track all sessions in `.sessions/session_index.md`:

```markdown
# IFMOS Session Index

## 2025-12-01
- `session_20251201_distilbert_training.md` - PyTorch DistilBERT training with CPU/GPU optimizations

## 2025-11-30
- [Previous sessions...]
```

---

## Best Practices

1. **Export early and often** - Better to have multiple small exports than one giant one
2. **Use descriptive names** - Make sessions easy to find
3. **Link related sessions** - Reference prerequisite or continuation sessions
4. **Commit with code** - Session exports live alongside code changes
5. **Keep it concise** - Focus on decisions and outcomes, not play-by-play
6. **Update when complete** - Add final metrics, results, learnings

---

## Recovery from Context Overflow

If session hits 200k tokens:

1. **Immediately export current state** (even if incomplete)
2. **Commit all code changes**
3. **Start fresh session** with reference to export
4. **Continue from last checkpoint**

---

## Future Enhancements

### 1. Automated Monitoring
- Script to monitor token usage
- Auto-alert at 150k tokens
- Suggest export points

### 2. Session Templates
- Pre-filled templates for common session types
- Consistent structure across all sessions

### 3. Session Linking
- YAML frontmatter with metadata
- `prerequisite_sessions: [...]`
- `continuation_of: session_X.md`

### 4. Search/Index
- Full-text search across all sessions
- Tag-based organization
- Timeline visualization

---

**Current Status**: Manual session exports with git commits
**Next Step**: Implement automated export at 150k tokens
