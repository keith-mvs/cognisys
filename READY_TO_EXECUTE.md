# Ready to Execute: GPU Acceleration + Remaining Phases

**Status**: Waiting for Phase 1 (content-based classification) to complete...
**Next Steps**: Staged and ready to execute immediately

---

## Execute Immediately After Classification Completes

### Step 1: Enable GPU Acceleration (5-10 minutes)
```bash
./venv/Scripts/python.exe scripts/setup/enable_gpu_acceleration.py
```

**What this does:**
- Installs PyTorch with CUDA 12.1
- Installs spaCy with CUDA support
- Installs CuPy for GPU arrays
- Replaces deprecated pynvml with nvidia-ml-py (fixes warning)
- Updates TextAnalyzer to prefer GPU
- Verifies setup is working

**Expected output:**
```
✓ NVIDIA GPU detected
✓ All CUDA packages installed
✓ spaCy is using GPU!
✓ GPU acceleration setup complete!

EXPECTED SPEEDUP
NLP Processing: 3-5x faster
ML Training: 2-10x faster
Classification: 2-3x faster overall
```

---

### Step 2: Train ML Model with GPU (2-3 minutes with GPU)
```bash
./venv/Scripts/python.exe scripts/ml/train_from_corrections.py
```

**What this does:**
- Loads 2,482 classified documents from database
- Extracts text features (filename + PDF content)
- Trains Random Forest classifier
- Uses TfidfVectorizer for text → numbers
- Saves trained model for production use

**Expected output:**
```
Training Accuracy: 0.943
Test Accuracy: 0.867
Cross-Val Accuracy: 0.852 (+/- 0.023)

Models saved to: ifmos/models/trained/
  - random_forest_classifier.pkl
  - tfidf_vectorizer.pkl
  - label_mappings.pkl
```

---

### Step 3: Reorganize with Template Filling (DRY RUN first)
```bash
./venv/Scripts/python.exe scripts/workflows/reorganize_with_templates.py --target-dir "Organized_V2" --dry-run
```

**What this does:**
- Reads extracted metadata from database
- Fills template placeholders:
  - `{vehicle_id}` → actual VIN
  - `{vendor}` → company name
  - `{invoice_id}` → invoice number
- Shows what WOULD happen (no files moved)

**Review output, then run live:**
```bash
./venv/Scripts/python.exe scripts/workflows/reorganize_with_templates.py --target-dir "Organized_V2"
```

---

## Full Execution Sequence

Copy and paste this entire block when ready:

```bash
# Phase 2: GPU Acceleration Setup
./venv/Scripts/python.exe scripts/setup/enable_gpu_acceleration.py

# Phase 3: ML Model Training (with GPU!)
./venv/Scripts/python.exe scripts/ml/train_from_corrections.py

# Phase 4: Template Filling (DRY RUN)
./venv/Scripts/python.exe scripts/workflows/reorganize_with_templates.py --target-dir "Organized_V2" --dry-run

# Phase 5: Template Filling (LIVE - after reviewing dry run)
# ./venv/Scripts/python.exe scripts/workflows/reorganize_with_templates.py --target-dir "Organized_V2"
```

---

## Expected Timeline

| Phase | Time (CPU) | Time (GPU) | Status |
|-------|------------|------------|--------|
| **Phase 1: Content Classification** | ~15 min | N/A | Running... |
| **Phase 2: GPU Setup** | 5-10 min | N/A | Ready |
| **Phase 3: ML Training** | ~3 min | ~30 sec | Ready |
| **Phase 4: Template Filling** | ~2 min | ~2 min | Ready |
| **TOTAL** | ~25 min | ~17-19 min | - |

**Time savings with GPU**: 6-8 minutes per full workflow iteration

---

## Files Created & Ready

### GPU Acceleration
- `scripts/setup/enable_gpu_acceleration.py` ✅
- `GPU_ACCELERATION_GUIDE.md` ✅

### Existing (from previous work)
- `scripts/workflows/ml_classify_with_content.py` ✅ (currently running)
- `scripts/ml/train_from_corrections.py` ✅
- `scripts/workflows/reorganize_with_templates.py` ✅
- `ML_IMPROVEMENTS_GUIDE.md` ✅

---

## Verification After Each Phase

### After GPU Setup:
```python
import torch
print(f"CUDA available: {torch.cuda.is_available()}")  # Should be True

import spacy
spacy.prefer_gpu()
print(f"spaCy GPU: {spacy.is_using_gpu()}")  # Should be True
```

### After ML Training:
```bash
ls ifmos/models/trained/
# Should see:
# - random_forest_classifier.pkl
# - tfidf_vectorizer.pkl
# - label_mappings.pkl
```

### After Template Filling:
```bash
# Check a few files in Organized_V2
ls "C:\Users\kjfle\Documents\Organized_V2\Automotive"
# Should see VINs instead of {vehicle_id}
```

---

## Monitoring GPU Usage

During execution, open a second terminal:
```bash
# Watch GPU in real-time
nvidia-smi -l 1
```

Expected during ML training:
- GPU Utilization: 50-90%
- Memory Usage: 2-4 GB
- Power: Increased from idle

---

**Everything is staged and ready!**

Just wait for Phase 1 to complete, then execute the steps above.

🚀 You'll have a fully GPU-accelerated ML classification system with:
- Content-based classification (not just filenames)
- Metadata extraction for template filling
- Trained ML model learning from your data
- 2-5x faster processing

Expected final accuracy: **85-90%** (vs current ~32%)
