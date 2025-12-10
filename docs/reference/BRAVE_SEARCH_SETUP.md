# Brave Search MCP Setup Guide

## Purpose

Brave Search MCP enhances CogniSys classification by using web search to disambiguate low-confidence and ambiguous classifications.

**Use Cases:**
- Identify cryptic filenames (e.g., "file-BgTHaR58NT1...")
- Resolve vehicle IDs (e.g., "P118956" → automotive, not medical)
- Look up product codes (e.g., "ST1450 BMW" → training module)
- Disambiguate terms (e.g., "diagnostic" + "vehicle" vs "diagnostic" + "patient")

---

## Step 1: Get Brave Search API Key

### Free Tier Available
- **URL**: https://brave.com/search/api/
- **Free Tier**: 2,000 queries/month (sufficient for CogniSys)
- **Rate Limit**: 1 query/second
- **No tracking**: Privacy-focused search

### Sign Up Process
1. Go to https://brave.com/search/api/
2. Click "Get Started" or "Sign Up"
3. Create account (email + password)
4. Navigate to API dashboard
5. Generate API key
6. Copy key (format: `BSA...` - keep secure!)

---

## Step 2: Install Brave Search MCP Server

### Option A: Claude Desktop (Recommended)

Add to Claude Desktop MCP configuration:

**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "brave-search": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-brave-search"],
      "env": {
        "BRAVE_API_KEY": "YOUR_API_KEY_HERE"
      }
    }
  }
}
```

### Option B: Environment Variable

Set globally for all sessions:

**Windows (PowerShell):**
```powershell
[System.Environment]::SetEnvironmentVariable('BRAVE_API_KEY', 'YOUR_API_KEY_HERE', 'User')
```

**Windows (CMD):**
```cmd
setx BRAVE_API_KEY "YOUR_API_KEY_HERE"
```

---

## Step 3: Verify Installation

### Test via Claude Code

In Claude Code, try:
```
Search for "BMW ST1450 training module"
```

If MCP is working, you'll see web search results.

### Test via Python Script

```python
import os
import subprocess
import json

# Check if Brave API key is set
api_key = os.getenv('BRAVE_API_KEY')
if api_key:
    print(f"✓ API key found: {api_key[:10]}...")
else:
    print("✗ API key not found")

# Test MCP server
try:
    result = subprocess.run(
        ['npx', '-y', '@modelcontextprotocol/server-brave-search'],
        capture_output=True,
        timeout=5
    )
    print("✓ MCP server installed")
except Exception as e:
    print(f"✗ MCP server error: {e}")
```

---

## Step 4: Integration with CogniSys

### Classification Enhancement Workflow

1. **Low Confidence Detection**
   ```python
   if confidence < 0.50 or doc_type in ['unknown', 'general_document']:
       # Use web search
   ```

2. **Search Query Construction**
   ```python
   # Extract key terms
   query_terms = extract_entities(filename, content_snippet)

   # Examples:
   # - "P118956 vehicle diagnostic" → automotive
   # - "BMW ST1450 technical" → automotive technical
   # - "CARFAX WBSBL93492JR16720" → automotive service
   ```

3. **Result Processing**
   ```python
   # Parse search results
   domain_keywords = extract_keywords(search_results)

   # Score against taxonomy
   scores = {
       'automotive': keyword_match_score(domain_keywords, automotive_terms),
       'medical': keyword_match_score(domain_keywords, medical_terms),
       # ...
   }

   # Reclassify if strong match
   if max(scores.values()) > 0.75:
       suggested_type = max(scores, key=scores.get)
   ```

---

## Step 5: CogniSys Integration Script

Created: `scripts/ml/web_search_classifier.py`

**Usage:**
```bash
# Process unknown files
python scripts/ml/web_search_classifier.py --priority critical

# Process with confidence threshold
python scripts/ml/web_search_classifier.py --confidence 0.50

# Dry run (preview)
python scripts/ml/web_search_classifier.py --priority critical

# Execute
python scripts/ml/web_search_classifier.py --priority critical --execute
```

**How It Works:**
1. Queries database for low-confidence files
2. Extracts key terms from filename/content
3. Searches Brave for context
4. Analyzes results for domain keywords
5. Suggests reclassification if confident
6. Updates database and moves files

---

## Privacy & Security

### What Gets Searched
- ✅ Product codes (ST1450, BMW 328i)
- ✅ VINs and vehicle IDs
- ✅ Generic document identifiers
- ✅ Company/vendor names

### What NEVER Gets Searched
- ❌ SSNs, patient IDs, account numbers
- ❌ Medical record content
- ❌ Financial account details
- ❌ Personal identifying information

### Privacy Filters
Built into `web_search_classifier.py`:
```python
SENSITIVE_PATTERNS = [
    r'\b\d{3}-\d{2}-\d{4}\b',  # SSN
    r'\b\d{16}\b',  # Credit card
    r'patient[_\s]?id',  # Medical
    # ... more filters
]
```

---

## Cost Analysis

### Free Tier Limits
- **Queries**: 2,000/month
- **CogniSys Usage**: ~150-200 queries (for 150 unknown files)
- **Result**: Well within free tier

### Paid Tier (if needed)
- **$5/month**: 20,000 queries
- **$20/month**: 100,000 queries

**Recommendation**: Start with free tier

---

## Troubleshooting

### Issue: "API key not found"
**Solution**:
1. Check environment variable: `echo %BRAVE_API_KEY%`
2. Restart terminal/IDE after setting
3. Verify key format (starts with "BSA")

### Issue: "Rate limit exceeded"
**Solution**:
- Free tier: 1 query/second
- Add delay: `time.sleep(1)` between queries
- Script automatically handles this

### Issue: "MCP server not responding"
**Solution**:
1. Update npx: `npm install -g npm`
2. Clear cache: `npm cache clean --force`
3. Reinstall: `npx -y @modelcontextprotocol/server-brave-search`

### Issue: "No search results returned"
**Solution**:
- Check internet connection
- Verify API key is valid
- Try simpler search query

---

## Expected Results

### Before Web Search
- **Unknown files**: 52 (confidence: 0%)
- **General documents**: 226 (confidence: 20-70%)

### After Web Search Enhancement
- **Expected improvement**: +15-20% accuracy
- **Unknown files**: ~20-30 (reduced by 40-50%)
- **General documents**: ~150-180 (reduced by 30%)

### Success Metrics
- VIN lookup: 95%+ success rate
- Product codes: 90%+ success rate
- Generic IDs: 60-70% success rate
- Cryptic filenames: 40-50% success rate

---

## Next Steps

1. ✅ Get Brave API key: https://brave.com/search/api/
2. ✅ Set environment variable or configure MCP
3. ✅ Test with sample query
4. ✅ Run web search classifier on unknown files
5. ✅ Review suggestions
6. ✅ Apply corrections

---

## Alternative: DuckDuckGo MCP

If Brave Search is unavailable:

```json
{
  "mcpServers": {
    "duckduckgo": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-duckduckgo"]
    }
  }
}
```

**Note**: DuckDuckGo has more restrictive rate limits

---

## Status

- [x] Setup guide created
- [ ] Brave API key obtained (user action required)
- [ ] MCP configured in Claude Desktop
- [ ] Integration script created
- [ ] Testing on unknown files
- [ ] Results validated

**Ready to proceed after API key is obtained!**
