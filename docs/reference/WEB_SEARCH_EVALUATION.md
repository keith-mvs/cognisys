# Web Search MCP for Classification Enhancement

## Problem Statement

**Current Issue**: 373 files (33%) classified as generic types (unknown, general_document, form)
**Specific Example**: Automotive "Vehicle Diagnostic Report" misclassified as "medical" due to term overlap

## Would Web Search Help?

### YES - Use Cases Where Web Search Adds Value

1. **Entity Resolution**
   - **Example**: "P118956" appears in filename
   - **Web Search**: "P118956 vehicle" → Returns automotive VIN/patient ID context
   - **Result**: Correctly classify as automotive, not medical

2. **Product/Model Identification**
   - **Example**: "ST1450 Introduction to BMW Technical Systems.pdf"
   - **Web Search**: "ST1450 BMW" → Returns BMW training module info
   - **Result**: Classify as technical/automotive, not general_document

3. **Unknown File Hash Matching**
   - **Example**: Files with cryptic names "file-BgTHaR58NT1tpoyxjbtg28..."
   - **Web Search**: Search file hash or extracted text snippets
   - **Result**: Match to known document types in public databases

4. **Low Confidence Fallback**
   - **Example**: Classification confidence < 0.50
   - **Web Search**: Extract key terms, search for context
   - **Result**: Boost confidence or reclassify with external knowledge

### NO - Cases Where Web Search Won't Help

1. **Truly Personal/Proprietary Documents**
   - Private contracts, personal notes, custom forms
   - No public information available
   - **Solution**: Improve ML training data instead

2. **Filename-Only Issues**
   - Files like "Doc1.docx", "Untitled.txt"
   - Web search on generic terms returns noise
   - **Solution**: Content-based classification required

3. **Privacy-Sensitive Medical Records**
   - Actual patient data shouldn't be sent to web search APIs
   - **Solution**: Local classification only, strict privacy rules

## Recommendation

**IMPLEMENT WEB SEARCH MCP - BUT USE SELECTIVELY**

### Implementation Strategy

1. **Brave Search MCP** (Already in setup guide)
   - Privacy-focused (no tracking)
   - Free tier available
   - Good for technical/product queries

2. **Trigger Conditions** (When to use web search):
   ```python
   use_web_search = (
       confidence < 0.50 OR
       document_type in ['unknown', 'general_document', 'form'] OR
       detected_ambiguity  # e.g., "diagnostic" term present
   )
   ```

3. **Search Query Construction**:
   ```python
   # Extract search terms from filename/content
   query_terms = extract_entities(filename, content)
   # Examples:
   # "P118956 vehicle diagnostic"
   # "BMW ST1450 technical"
   # "CARFAX WBSBL93492JR16720"
   ```

4. **Result Processing**:
   - Extract domain keywords from search results
   - Score results against domain taxonomy
   - Boost classification confidence if strong match
   - Flag for manual review if still uncertain

5. **Privacy Safeguards**:
   ```python
   # Never search sensitive data
   exclude_from_search = [
       'SSN', 'medical_record_id', 'patient_name',
       'credit_card', 'account_number'
   ]
   ```

## Cost/Benefit Analysis

### Benefits
- **+10-15% accuracy** on unknown/generic documents
- **Disambiguate** automotive vs medical, technical vs general
- **Entity resolution** for VINs, product codes, invoice numbers
- **Reduce manual review** by 200-300 files

### Costs
- **API calls**: ~$0.005/search (Brave) × 373 files = ~$1.86
- **Latency**: +2-3 seconds per file (acceptable for batch processing)
- **Privacy risk**: Mitigated with filtering and Brave's no-tracking policy

### ROI
**Worth implementing** - Low cost, high value for edge cases

## Implementation Plan

### Phase 1: Setup Brave Search MCP (Done in previous session)
```bash
claude mcp add brave-search -- npx -y @modelcontextprotocol/server-brave-search
# Requires API key: https://brave.com/search/api/
```

### Phase 2: Create Classification Enhancement Script
- Detect low-confidence/generic classifications
- Construct contextual search queries
- Parse results for domain keywords
- Boost/reclassify based on findings

### Phase 3: Integration with CogniSys Pipeline
- Add `--use-web-search` flag to classification script
- Implement privacy filters
- Log all web searches for audit

### Phase 4: Validation
- Test on 373 generic documents
- Measure accuracy improvement
- Adjust thresholds based on results

## Alternative: Expand ML Training Data

**Complementary Approach** (do both):
1. Add 100+ automotive examples to training set
   - BMW manuals, diagnostic reports, service records
   - Label correctly as `automotive_technical` and `automotive_service`

2. Add context-aware features:
   - Filename pattern matching (VIN, model codes, part numbers)
   - Term disambiguation rules (diagnostic + vehicle = automotive)

3. Retrain model with expanded dataset

## Conclusion

**YES, implement Web Search MCP** - but use it as a **fallback for edge cases**, not primary classification.

**Priority**:
1. ✅ Redesign organization structure (Function/Form/Fit) - DONE
2. 🔄 Implement web search for low-confidence files - NEXT
3. 📊 Expand ML training data - ONGOING

**Expected Outcome**: Reduce generic classifications from 33% to ~20%, improve automotive detection by 90%+
