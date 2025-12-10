# CogniSys ML Workflow Guide

Complete guide for training and deploying the CogniSys ML document classification system.

## 📋 Quick Start

```powershell
# Check system status
.\CogniSys_ml_workflow.ps1

# Run complete workflow (all stages)
.\CogniSys_ml_workflow.ps1 -Stage Complete
```

## 🔄 Workflow Stages

### Stage 1: Setup
**Purpose**: Initialize categories and verify server

```powershell
.\CogniSys_ml_workflow.ps1 -Stage Setup
```

**What it does**:
- Checks if ML server is running
- Creates 10 document categories based on inbox analysis
- Verifies database connection

**Output**: 10 categories created (Legal_CCO, Healthcare_Medical, etc.)

---

### Stage 2: Process
**Purpose**: Batch process all inbox documents

```powershell
.\CogniSys_ml_workflow.ps1 -Stage Process
```

**What it does**:
- Processes all 97 files in `C:\Users\kjfle\00_Inbox\To_Review`
- Extracts content (PDF, Word, Excel, Text)
- Performs NLP analysis (entities, keywords)
- Stores results in database
- Saves individual JSON results

**Duration**: ~10-15 minutes (97 files @ ~6-10 seconds each)

**Output**:
- `C:\Users\kjfle\ml_batch_results\batch_results.json` (summary)
- `C:\Users\kjfle\ml_batch_results\doc_*.json` (individual results)
- `C:\Users\kjfle\ml_batch_results\processing_summary.txt`

---

### Stage 3: Collect
**Purpose**: Interactive feedback collection for training

```powershell
.\CogniSys_ml_workflow.ps1 -Stage Collect
```

**What it does**:
- Reviews each processed document
- Shows auto-suggested categories (based on filename patterns)
- Collects user feedback for correct categorization
- Submits feedback to ML database

**Features**:
- **Auto-suggest mode**: Automatically suggests categories based on filename patterns
- **Batch auto mode**: Press 'A' to auto-categorize all remaining documents
- **Skip option**: Press 'S' to skip documents
- **Progress saving**: Saves every 10 reviews

**Duration**: ~30-60 minutes for 97 files (with auto-suggest)

**Output**: `C:\Users\kjfle\ml_feedback.json`

---

### Stage 4: Train
**Purpose**: Train the ensemble classifier

```powershell
# Check if ready
.\CogniSys_ml_workflow.ps1 -Stage Train

# Or use direct script
.\train_classifier.ps1 -CheckReadiness
.\train_classifier.ps1
```

**What it does**:
- Loads labeled documents from database
- Extracts features (TF-IDF + structural features)
- Trains ensemble model:
  - Random Forest (100 trees)
  - XGBoost (GPU-accelerated)
  - LightGBM (GPU-accelerated)
- Evaluates accuracy with cross-validation
- Saves trained model

**Requirements**:
- Minimum: 10 labeled documents
- Recommended: 100+ labeled documents
- At least 2 samples per category

**Duration**: ~5-15 minutes depending on dataset size

**Output**:
- Trained model saved to `models/current/`
- Training metrics and classification report
- Database training session record

---

## 📁 Script Reference

### Main Workflow Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `CogniSys_ml_workflow.ps1` | Master workflow manager | `.\CogniSys_ml_workflow.ps1 -Stage <Stage>` |
| `batch_process_inbox.ps1` | Batch process documents | `.\batch_process_inbox.ps1` |
| `collect_feedback.ps1` | Interactive feedback collection | `.\collect_feedback.ps1 -AutoSuggest` |
| `train_classifier.ps1` | Train ML classifier | `.\train_classifier.ps1` |

### Analysis & Setup Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `analyze_inbox_categories.ps1` | Analyze inbox and suggest categories | Auto-generated during workflow |
| `create_categories.ps1` | Create ML categories | Auto-generated and executed |
| `check_health.ps1` | Check ML server health | `.\check_health.ps1` |
| `get_stats.ps1` | Get ML system statistics | `.\get_stats.ps1` |

### Test Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `test_document_processing.ps1` | Test single document | `.\test_document_processing.ps1` |
| `test_multiple_formats.ps1` | Test multi-format support | `.\test_multiple_formats.ps1` |

---

## 🎯 Categories Created

Based on inbox analysis, 10 categories were automatically created:

| Category | Description | Sample Count |
|----------|-------------|--------------|
| Legal_CCO | CCO legal documents | 78 files |
| Healthcare_Medical | Medical and healthcare documents | 1 file |
| Legal_PropertyTax | Property tax and legal code documents | 1 file |
| Real_Estate | Real estate and property documents | 1 file |
| Education | Education-related documents | 1 file |
| Technology | Technology and account documents | 2 files |
| Financial_General | General financial documents | 1 file |
| Personal_Letters | Personal correspondence | 1 file |
| Personal_Documents | Personal identification documents | 1 file |
| Work_Documents | General work documents | 6 files |

---

## 💡 Workflow Tips

### For Best Accuracy

1. **Label 100+ documents**: More training data = better accuracy
2. **Balanced classes**: Try to have at least 10 samples per category
3. **Consistent labeling**: Be consistent in how you categorize similar documents
4. **Use auto-suggest**: Speeds up feedback collection significantly

### Auto-Suggest Patterns

The system auto-suggests categories based on these patterns:

- **Legal_CCO**: Files matching `cco_\d+`
- **Healthcare_Medical**: Files containing `quest|billing|medical`
- **Technology**: Files containing `mozilla|recovery|onedrive`
- **Work_Documents**: Files like `text_document|doc\d+`

### Batch Processing Options

```powershell
# Process only first 20 files (for testing)
.\batch_process_inbox.ps1 -MaxFiles 20

# Skip already processed files
.\batch_process_inbox.ps1 -SkipExisting

# Custom inbox path
.\batch_process_inbox.ps1 -InboxPath "C:\Documents\Inbox"
```

### Feedback Collection Modes

```powershell
# With auto-suggestions (recommended)
.\collect_feedback.ps1 -AutoSuggest

# Without auto-suggestions
.\collect_feedback.ps1

# Resume previous session (automatically loads existing feedback)
.\collect_feedback.ps1 -AutoSuggest
```

---

## 🔍 Monitoring Progress

### Check System Status

```powershell
.\CogniSys_ml_workflow.ps1
```

Shows:
- ML server status
- GPU detection
- Database statistics
- Training readiness

### Check Specific Stats

```powershell
Import-Module .\CogniSys-ML-Bridge.psm1
Get-CogniSysMLStats | Format-List
```

### View Categories

```powershell
Get-CogniSysMLCategories | Format-Table
```

### Review Batch Results

```json
// C:\Users\kjfle\ml_batch_results\batch_results.json
[
  {
    "file_name": "2024-12-29_review_quest_billing.pdf",
    "document_id": 1,
    "extraction_method": "digital_pdf",
    "text_length": 5523,
    "document_type": "general_document",
    "entities_count": 17,
    "timestamp": "2025-11-27 20:00:33"
  }
]
```

---

## 🎓 Training Results

After training, you'll see:

```
Training Complete!
==================================
Accuracy: 0.856
Training samples: 97
Number of classes: 10

Classes trained: Legal_CCO, Healthcare_Medical, Technology, ...

Classification Report:
                    precision    recall  f1-score   support
    Legal_CCO          0.92      0.94      0.93        78
    Technology         0.78      0.72      0.75         9
    ...
```

---

## 🚀 Production Use

Once trained, process new documents:

```powershell
Import-Module .\CogniSys-ML-Bridge.psm1

# Process a single document
$result = Invoke-CogniSysMLProcess -FilePath "C:\new_doc.pdf"

# View prediction
Write-Host "Category: $($result.prediction.predicted_category)"
Write-Host "Confidence: $([Math]::Round($result.prediction.confidence * 100, 1))%"

# Submit feedback if prediction was wrong
Submit-CogniSysMLFeedback `
    -DocumentId $result.document_id `
    -CorrectCategory "Legal_CCO" `
    -WasCorrect $false
```

---

## 🔄 Continuous Improvement

1. **Process new documents** regularly
2. **Review and correct** predictions
3. **Retrain periodically** (every 50-100 new labels)

```powershell
# Retraining workflow
.\batch_process_inbox.ps1          # Process new docs
.\collect_feedback.ps1 -AutoSuggest # Collect feedback
.\train_classifier.ps1             # Retrain model
```

---

## 📊 Expected Performance

### Processing Speed
- **PDF extraction**: 2-5 seconds/file
- **Text analysis**: 1-2 seconds/file
- **Classification**: <0.5 seconds/file (after training)

### Accuracy Expectations
- **100 training samples**: 70-80% accuracy
- **200+ training samples**: 80-90% accuracy
- **500+ training samples**: 90-95% accuracy

---

## 🛠️ Troubleshooting

### Server won't start
```powershell
# Check if already running
Test-CogniSysMLServer

# Kill existing process
Get-Process python | Where-Object {$_.Path -like "*pytorch-venv*"} | Stop-Process

# Restart
Import-Module .\CogniSys-ML-Bridge.psm1
Start-CogniSysMLServer
```

### Not enough training data
```powershell
# Check current status
.\train_classifier.ps1 -CheckReadiness

# Process more documents
.\batch_process_inbox.ps1

# Collect more feedback
.\collect_feedback.ps1 -AutoSuggest
```

### GPU not detected
```powershell
# Check health
.\check_health.ps1

# Verify PyTorch CUDA
C:\...\pytorch-venv\Scripts\python.exe -c "import torch; print(torch.cuda.is_available())"
```

---

## 📝 Next Steps

1. **Run the complete workflow**: `.\CogniSys_ml_workflow.ps1 -Stage Complete`
2. **Monitor accuracy** as you collect more feedback
3. **Integrate with main CogniSys** PowerShell scripts
4. **Set up automated processing** for new inbox files

---

**Version**: 1.0.0
**Last Updated**: 2025-11-27
**Author**: CogniSys ML System
**GPU**: NVIDIA GeForce RTX 2080 Ti
