# CogniSys Installation Guide

Complete installation instructions for CogniSys (Cognitive File Organization System) with ML capabilities and cloud storage integration.

## System Requirements

### Hardware
- **CPU**: Multi-core processor (4+ cores recommended)
- **RAM**: 8 GB minimum, 16 GB+ recommended for ML features
- **GPU** (Optional, for ML): NVIDIA GPU with CUDA 12.1+ support
  - Recommended: RTX 2060 or better
  - Minimum: GTX 1060 (6GB VRAM)
- **Storage**: 20 GB free space (including ML models and dependencies)

### Software
- **Python**: 3.10 or higher
- **Git**: For version control and updates
- **Windows**: Windows 10/11 (primary), or Linux/macOS with adaptations

### For GPU Acceleration (ML Features)
- **NVIDIA CUDA Toolkit**: 12.1 or higher
- **cuDNN**: Compatible version for CUDA 12.1
- **NVIDIA GPU Drivers**: Latest recommended

---

## Installation

### Step 1: Clone or Download Repository

```bash
cd C:\Users\<YourUsername>\Projects
git clone <repository-url> intelligent-file-management-system
cd intelligent-file-management-system
```

### Step 2: Create Virtual Environment

#### Option A: Core CogniSys Only (No ML)

```powershell
# Create virtual environment
python -m venv venv

# Activate
.\venv\Scripts\Activate.ps1

# Install core dependencies
pip install -r requirements.txt

# Install CogniSys in development mode
pip install -e .
```

#### Option B: Full Installation with ML (Recommended)

```powershell
# Create virtual environment
python -m venv venv

# Activate
.\venv\Scripts\Activate.ps1

# Install core dependencies first
pip install -r requirements.txt

# Install PyTorch with CUDA support (IMPORTANT: Do this BEFORE requirements-ml.txt)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Install ML dependencies
pip install -r requirements-ml.txt

# Download spaCy language model
python -m spacy download en_core_web_sm

# Install CogniSys in development mode
pip install -e .
```

**Note**: The PyTorch installation step is critical and must be done before `requirements-ml.txt` to ensure CUDA-enabled builds.

### Step 3: Verify Installation

```powershell
# Check CogniSys CLI
cognisys --help

# Verify GPU detection (if using ML features)
python -c "import torch; print(f'CUDA Available: {torch.cuda.is_available()}'); print(f'GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"None\"}')"
```

Expected output for GPU systems:
```
CUDA Available: True
GPU: NVIDIA GeForce RTX 2080 Ti
```

### Step 4: Initialize Databases

```powershell
# The database will be created automatically on first run
# Optionally, you can create it manually:
python -c "from cognisys.models.database import Database; db = Database('.cognisys/file_registry.db')"
```

### Step 5: Detect Cloud Storage (Optional)

```powershell
# Auto-detect mounted cloud folders (OneDrive, Google Drive, iCloud)
cognisys cloud detect

# Add detected folders as sources
cognisys cloud detect --add

# Authenticate with OneDrive API (requires Azure AD client ID)
cognisys cloud auth --provider onedrive --client-id <your-client-id>
```

---

## Configuration

### Basic Configuration

Edit configuration files in `cognisys/config/`:

1. **scan_config.yml** - Scanning behavior
2. **analysis_rules.yml** - Deduplication rules
3. **new_structure.yml** - Target organization structure

### ML Configuration (if using ML features)

1. **Database path**: Default is `db/ml_training.db`
2. **Model storage**: Models saved to `data/models/current/`
3. **Training data**: Stored in `data/training/`

---

## Quick Start

### Core CogniSys Workflow

```bash
# 1. Scan your file system
cognisys scan --roots "C:\Users\Documents" --roots "C:\Projects"

# 2. Analyze for duplicates
cognisys analyze --session <session-id-from-step-1>

# 3. Generate reports
cognisys report --session <session-id> --format html --format json

# 4. Create migration plan
cognisys plan --session <session-id> --structure cognisys/config/new_structure.yml

# 5. Preview and execute
cognisys dry-run --plan <plan-id>
cognisys approve --plan <plan-id>
cognisys execute --plan <plan-id>
```

### Cloud Storage Workflow

```bash
# 1. Detect and add cloud sources
cognisys cloud detect --add

# 2. Configure additional sources
cognisys source add my_nas --type network --path "\\\\NAS\\files"
cognisys source list

# 3. Scan all sources
cognisys scan --source onedrive_mounted
cognisys scan --all  # Scan all configured sources

# 4. Sync organized files back to cloud
cognisys cloud sync onedrive_docs --direction push
```

### ML Document Classification Workflow

```powershell
# Navigate to PowerShell scripts
cd scripts\powershell

# 1. Check ML server health
.\utilities\check_health.ps1

# 2. Run complete ML workflow
.\workflows\cognisys_ml_workflow.ps1 -Stage Complete
```

This will:
- Process documents from your inbox
- Collect feedback interactively
- Train the classifier
- Enable predictions

---

## Troubleshooting

### Import Errors After Installation

**Problem**: `ModuleNotFoundError: No module named 'cognisys'`

**Solution**:
```powershell
# Ensure you're in the project root
cd C:\Users\<YourUsername>\Projects\intelligent-file-management-system

# Reinstall in development mode
pip install -e .
```

### GPU Not Detected

**Problem**: `CUDA Available: False`

**Solution**:
1. Verify NVIDIA drivers are installed: `nvidia-smi`
2. Reinstall PyTorch with CUDA:
   ```powershell
   pip uninstall torch torchvision torchaudio
   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
   ```
3. Check CUDA compatibility: `nvcc --version`

### PowerShell Execution Policy Error

**Problem**: `cannot be loaded because running scripts is disabled`

**Solution**:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### ML Server Won't Start

**Problem**: Flask server fails to start

**Solution**:
1. Check if port 5000 is in use:
   ```powershell
   netstat -ano | findstr :5000
   ```
2. Verify all ML dependencies are installed:
   ```powershell
   pip list | Select-String -Pattern "torch|flask|spacy|easyocr"
   ```
3. Check server logs in `logs/` directory

---

## Updating CogniSys

```bash
# Pull latest changes
git pull origin main

# Update dependencies
pip install -r requirements.txt
pip install -r requirements-ml.txt  # If using ML features

# Reinstall
pip install -e .
```

---

## Uninstallation

```powershell
# Deactivate virtual environment
deactivate

# Remove virtual environment
Remove-Item -Recurse -Force venv

# Optionally remove databases and models (if you want a clean slate)
Remove-Item -Recurse -Force db, data, logs, reports
```

---

## Next Steps

- **Core CogniSys**: Read [QUICKSTART.md](docs/QUICKSTART.md) for usage examples
- **ML Features**: Read [ML_WORKFLOW_GUIDE.md](docs/ML_WORKFLOW_GUIDE.md) for ML training workflow
- **Architecture**: See [ARCHITECTURE.md](docs/ARCHITECTURE.md) for system design

---

## Getting Help

- **Documentation**: Check `docs/` folder
- **Issues**: Report problems via GitHub Issues
- **Logs**: Check `logs/` directory for detailed error messages

---

**Version**: 2.0.0
**Last Updated**: 2025-11-27
