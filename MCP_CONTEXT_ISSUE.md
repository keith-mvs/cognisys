# MCP Context Health Issue

## Issue Summary
Context metrics show unhealthy status across all projects due to high context usage (98-99% capacity).

## Evidence from `~/.claude/logs/context-metrics.jsonl`

```json
{
  "OverallHealthy": false,
  "BaselineHealthy": false,
  "IFMOSHealthy": false,
  "ImageEngineHealthy": false,
  "ContextCapacityPct": 99.47,
  "IFMOSCapacityPct": 98.58,
  "ImageEngineCapacityPct": 98.57,
  "IFMOSMCPServers": [1,1,1,1],
  "GlobalMCPServers": 1,
  "GlobalMCPServerNames": "brave-search"
}
```

## Key Observations

1. **High Context Usage**: All projects running at 98-99% context capacity
2. **Multiple MCP Server Instances**: `IFMOSMCPServers: [1,1,1,1]` shows 4 registered instances
3. **Global MCP Server**: Only `brave-search` registered globally
4. **Context Scoping**: `MCPScopingHealthy: true` but overall health is false

## Potential Causes

1. **Context Bloat**: Large configuration files (CLAUDE.md, REFERENCE.md) loaded for every project
2. **Multiple MCP Registrations**: 4 MCP server instances for IFMOS may be redundant
3. **Baseline Context**: Baseline using 2,111 tokens consistently
4. **Project-Specific Context**: Each project loading 1,800+ tokens

## Impact

- Context exhaustion warnings during sessions
- Reduced available context for actual work
- Potential MCP server initialization failures

## Recommendations

1. **Reduce Baseline Context**:
   - Consolidate CLAUDE.md and REFERENCE.md
   - Move rarely-used config to separate files
   - Use conditional loading

2. **Fix MCP Server Registration**:
   - Investigate why IFMOS has 4 instances
   - Ensure MCP servers register once per project

3. **Optimize Project Context**:
   - Split large CLAUDE.md files into sections
   - Load only relevant sections based on task
   - Use symbolic links for shared config

4. **Monitor Context Usage**:
   - Set alerts at 80% capacity
   - Regular context cleanup
   - Session summaries before 200k limit

## Status

- Documented: 2025-12-01
- Severity: Medium (affects all projects)
- Action Required: Context optimization sprint
