# Context Optimization Proposal

## Current State (From MCP_CONTEXT_ISSUE.md)
- **Baseline**: 2,111 tokens per project
- **IFMOS**: 1,802 tokens project context
- **Total**: ~4,000 tokens baseline (2% of 200k capacity)
- **MCP Servers**: 4 instances for IFMOS (should be 1)
- **Overall Health**: 98-99% capacity usage

## Optimization Strategy

### 1. Reduce Project CLAUDE.md (80% reduction)
**Before**: 140 lines, 702 words, 5,226 chars (~1,300 tokens)
**After**: 27 lines, 139 words, 1,038 chars (~260 tokens)
**Savings**: ~1,040 tokens (80%)

**Implementation**:
- Replace `CLAUDE.md` with `CLAUDE_MINIMAL.md`
- Move detailed docs to separate files:
  - `ARCHITECTURE.md` - System design (load on demand)
  - `TRAINING.md` - ML training guides (load on demand)
  - `API_REFERENCE.md` - CLI commands (load on demand)

### 2. Consolidate Home Config (50% reduction)
**Before**: ~/CLAUDE.md (68 lines, ~630 tokens)
**After**: Streamline to 30 lines (~300 tokens)
**Savings**: ~330 tokens (50%)

**Changes**:
- Remove duplicate path/env info (Claude Code knows this)
- Remove redundant tool preferences (already in Claude Code)
- Keep only project-specific overrides

### 3. Fix MCP Server Registration
**Issue**: IFMOS shows 4 MCP instances instead of 1
**Investigation**:
- Check `.claude/config.json` for duplicates
- Verify MCP server scoping
- Ensure project-local vs global separation

**Expected Savings**: Reduce redundant initialization overhead

### 4. Lazy-Load Documentation
**Pattern**: Load detailed docs only when needed
```markdown
# CLAUDE_MINIMAL.md
For detailed info:
- Architecture: See ARCHITECTURE.md
- Training: See TRAINING.md
- API: See API_REFERENCE.md
```

### 5. Session-Based Cleanup
**Pattern**: Proactive cleanup before hitting 200k
```
At 150k tokens (75%): Trigger context summary
At 175k tokens (87.5%): Force summary + cleanup
At 190k tokens (95%): Emergency compaction
```

## Expected Results

### Token Usage After Optimization
| Component | Before | After | Savings |
|-----------|--------|-------|---------|
| Project CLAUDE.md | 1,300 | 260 | 1,040 (80%) |
| Home CLAUDE.md | 630 | 300 | 330 (52%) |
| MCP Overhead | ~180 | ~45 | 135 (75%) |
| **Total Baseline** | **2,110** | **605** | **1,505 (71%)** |

### Capacity Impact
- **Before**: 2,110 / 200,000 = 1.06%
- **After**: 605 / 200,000 = 0.30%
- **Gain**: 1,505 tokens freed for actual work

## Implementation Plan

### Phase 1: Immediate (This Sprint)
1. ✅ Create CLAUDE_MINIMAL.md
2. ⏳ Test with minimal config
3. ⏳ Backup and replace CLAUDE.md
4. ⏳ Verify token reduction

### Phase 2: MCP Fix (Next Session)
1. Investigate MCP server duplication
2. Fix configuration
3. Verify single instance

### Phase 3: Documentation Restructure (Future)
1. Split CLAUDE.md into modular docs
2. Implement lazy-loading pattern
3. Add context monitoring hooks

## Migration Path

### Safe Rollback
```bash
# Backup current config
cp CLAUDE.md CLAUDE_FULL.md.bak

# Test minimal version
cp CLAUDE_MINIMAL.md CLAUDE.md

# If issues, rollback
mv CLAUDE_FULL.md.bak CLAUDE.md
```

### Validation
- Check `context-metrics.jsonl` before/after
- Verify baseline tokens reduced
- Ensure functionality intact

## Risk Assessment
- **Low Risk**: Config changes are reversible
- **Medium Impact**: Reduces baseline by 71%
- **High Value**: Frees 1,505 tokens for work

## Success Criteria
- [x] CLAUDE_MINIMAL.md created (260 tokens)
- [ ] Baseline reduced to <700 tokens
- [ ] MCP instances reduced to 1
- [ ] Context health shows "healthy" status
- [ ] No functionality regressions

## Next Steps
1. Test current session with CLAUDE_MINIMAL.md
2. Measure actual token reduction
3. Roll out if successful
4. Document best practices

---

**Created**: 2025-12-01
**Status**: Proposal (Phase 1 in progress)
**Owner**: AI/ML Development Team
