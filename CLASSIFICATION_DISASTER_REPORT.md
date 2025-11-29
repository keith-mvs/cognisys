# IFMOS Classification Disaster Report
**Date**: 2025-11-28
**Status**: 🔴 CRITICAL - ML Model Requires Complete Retraining

---

## Executive Summary

**Out of 1,127 classified documents, an estimated 40-50% are misclassified.**

### Critical Misclassification Examples

| File | Classified As | Actually Is | Impact |
|------|---------------|-------------|--------|
| `[P118956] Vehicle Diagnostic Report` | medical | automotive_service | CATASTROPHIC |
| `BMW 328i, 175kW.pdf` | medical | automotive_technical | CATASTROPHIC |
| `salary-estimator.xlsx` | financial_invoice | personal_career_tool | SEVERE |
| `Chapter_Patanjali_Yoga_Sutras.docx` | hr_resume | personal_journal | SEVERE |
| `CARFAX (1FMCU0GD6JUB25309).pdf` | hr_resume | automotive_service | SEVERE |
| `Resume-CV_v1.docx` (user's own) | hr_resume | personal_career | MODERATE |
| `AIAA Scholarship Career Goals.docx` | hr_resume | personal_essay | MODERATE |

### Misclassification Patterns

1. **Automotive ↔ Medical Confusion** (25% of "medical" docs)
   - "Diagnostic" keyword triggers medical classification
   - Vehicle patient IDs (P118956) confused with medical patient IDs
   - **Root Cause**: Term overlap without context

2. **Personal Documents → HR** (50%+ of "hr_resume" docs)
   - User's own resumes/cover letters treated as HR recruiting documents
   - Yoga journal chapters classified as resumes
   - **Root Cause**: Any document with text structure triggers "resume"

3. **Tools/Calculators → Financial Invoices** (Unknown %%)
   - Salary estimators classified as invoices
   - "Salary" keyword triggers financial classification
   - **Root Cause**: Keyword matching without semantic understanding

4. **Generic Catchall Problem** (373 documents = 33%)
   - 235 "general_document"
   - 73 "form"
   - 58 "unknown"
   - 7 "general_document_short"
   - **Root Cause**: Model has no training data for these types

---

## Root Causes

### 1. **Insufficient Training Data**
- Model trained on limited, homogeneous examples
- Missing categories: personal documents, career tools, journals
- No automotive technical documentation examples

### 2. **Keyword-Only Matching (No Context)**
- "Diagnostic" → Always medical (ignores "vehicle")
- "Resume" → Always HR (ignores ownership context)
- "Salary" → Always financial (ignores tool vs. invoice)

### 3. **Missing Document Types in Taxonomy**
Current taxonomy has **14 domains** but missing:
- `personal_career` - User's own career documents
- `personal_journal` - Meditation, yoga, personal notes
- `personal_essay` - Scholarship essays, career goals
- `personal_tools` - Calculators, estimators, planners
- `automotive_diagnostic` - Vehicle diagnostic reports (confused with medical)

### 4. **No Disambiguation Logic**
Model cannot distinguish:
- User's resume vs. job applicant resume
- Financial invoice vs. financial calculator
- Medical diagnostic vs. automotive diagnostic

---

## Impact Analysis

### Organizational Impact
- **411 files** in Financial domain (likely 20-30% misclassified)
- **156 files** in Legal domain (likely 15-20% misclassified)
- **155 files** in HR domain (likely 50%+ misclassified - mostly personal docs)
- **16 files** in Medical domain (25% are automotive)

### User Trust Impact
- **Critical**: User cannot trust organization system
- **Severe**: Manual review required for all 1,127 documents
- **Moderate**: Current organization is worse than unorganized inbox

### Retrieval Impact
- Searching for "BMW manuals" returns medical documents
- Searching for "personal resumes" returns HR recruiting folder
- Searching for "financial invoices" returns salary calculators

---

## Recommended Solutions (Priority Order)

### IMMEDIATE (This Week)

#### ✅ 1. Pattern-Based Reclassification (DONE - 28 fixes)
- Added rules for automotive, personal journals, essays
- Reclassified 28 documents successfully
- **Limitation**: Only works for descriptive filenames (2.5% coverage)

#### 🔄 2. Implement Web Search MCP (IN PROGRESS)
**Purpose**: Disambiguate low-confidence classifications using external context

**Setup**:
```bash
# Get Brave API key (free tier)
https://brave.com/search/api/

# Add to Claude MCP
claude mcp add brave-search -- npx -y @modelcontextprotocol/server-brave-search
export BRAVE_API_KEY="your-key"
```

**Use Cases**:
- Search "P118956" → Identify as vehicle ID
- Search "BMW ST1450" → Technical training module
- Search file hashes → Match known documents

**Expected Improvement**: +10-15% accuracy on generic/unknown docs

#### 📋 3. Expand Pattern Rules
Add rules for:
- Personal career documents (resumes, cover letters)
- Tools/calculators (estimators, planners)
- More automotive patterns (all BMW models, part numbers)
- **Expected Improvement**: +5-10% accuracy

### SHORT TERM (Next 2 Weeks)

#### 4. Create New Document Types
Expand taxonomy to include:
```yaml
personal:
  - personal_career  # Own resumes, cover letters
  - personal_journal  # Meditation, yoga notes
  - personal_essay  # Scholarship essays
  - personal_tools  # Calculators, estimators

automotive:
  - automotive_technical  # Service manuals
  - automotive_service  # Service records
  - automotive_diagnostic  # Diagnostic reports
  - automotive_history  # CARFAX, vehicle history
```

#### 5. Manual Review & Correction Session
**Process**:
1. Sample 100 documents from each misclassified category
2. Manually correct classifications
3. Export corrections as training data
4. Feed back into model

**Time Investment**: ~4-6 hours
**Expected Improvement**: +20-30% accuracy after retraining

### MEDIUM TERM (Next Month)

#### 6. Retrain ML Model with Expanded Dataset
**Data Collection**:
- Export all manual corrections
- Add 500+ new labeled examples:
  - 100 automotive technical docs
  - 100 personal career docs
  - 50 personal journals
  - 50 tools/calculators
  - 200 properly labeled financial/legal/medical

**Model Improvements**:
- Add context-aware features (filename + content)
- Implement disambiguation rules
- Add confidence calibration

**Expected Improvement**: +40-50% accuracy

#### 7. Implement Two-Stage Classification
**Stage 1**: Broad category (Financial, Legal, Personal, Automotive)
**Stage 2**: Specific type (Invoice, Contract, Resume, Manual)

**Benefits**:
- Reduces confusion between domains
- Higher confidence at each stage
- Easier to debug misclassifications

---

## Temporary Workarounds (Until Model is Retrained)

### 1. **Manual Review Workflow**
```bash
# Generate review list for each domain
python scripts/ml/generate_review_list.py --domain medical
python scripts/ml/generate_review_list.py --domain hr

# Review and correct
# Creates correction.csv with: doc_id, current_type, correct_type
```

### 2. **Search-Assisted Classification**
```python
# For unknown/low-confidence docs
if confidence < 0.50:
    search_results = brave_search(extract_key_terms(filename, content))
    suggested_type = classify_from_search(search_results)
    # Present to user for confirmation
```

### 3. **Domain Separation**
Organize by broad domain first, worry about specifics later:
- `Documents/Automotive/` - All automotive (don't worry if technical vs. service)
- `Documents/Personal/` - All personal docs
- `Documents/Business/Financial/` - Business financial docs

---

## Metrics to Track

### Before Retraining
- **Accuracy**: ~50-60% (estimated)
- **Generic Classifications**: 33% (373/1127)
- **Critical Misclassifications**: 40+ identified

### After Pattern Rules + Web Search
- **Target Accuracy**: 70-75%
- **Target Generic**: <25%
- **Target Critical**: <10

### After Full Retraining
- **Target Accuracy**: 90-95%
- **Target Generic**: <10%
- **Target Critical**: <5

---

## Decision Required

**Question for User**: How do you want to proceed?

### Option A: Quick Fix (Pattern Rules + Web Search)
- **Time**: 1-2 days
- **Improvement**: +15-20% accuracy
- **Pros**: Fast, immediate improvement
- **Cons**: Won't fix fundamental issues

### Option B: Full Retraining (Recommended)
- **Time**: 2-4 weeks (including manual review)
- **Improvement**: +40-50% accuracy
- **Pros**: Fixes root causes, long-term solution
- **Cons**: Requires significant time investment

### Option C: Hybrid Approach
- **Phase 1** (This week): Pattern rules + Web search
- **Phase 2** (Week 2-3): Manual review session (4-6 hours)
- **Phase 3** (Week 4): Retrain model with corrections
- **Pros**: Progressive improvement, manageable time commitment
- **Cons**: Takes full month to complete

---

## Immediate Action Items

1. ✅ Implement pattern-based reclassification (DONE - 28 fixes)
2. 🔄 Setup Brave Search MCP for web-assisted classification
3. 📋 Expand reclassification rules (personal, automotive, tools)
4. 🔍 Generate misclassification review list for manual correction
5. 🎯 Begin collecting new training examples

---

**Next Steps**: Awaiting user decision on approach (A, B, or C)

**Current Status**: System usable but requires significant manual oversight
