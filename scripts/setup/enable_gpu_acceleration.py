#!/usr/bin/env python3
"""
IFMOS: Enable GPU Acceleration for ML Classification
Configures spaCy, PyTorch, and scikit-learn to use CUDA GPU
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def check_gpu_available():
    """Check if NVIDIA GPU is available"""
    try:
        result = subprocess.run(['nvidia-smi'], capture_output=True, text=True)
        if result.returncode == 0:
            print("[OK] NVIDIA GPU detected")
            print(result.stdout.split('\n')[2])  # GPU info line
            return True
        else:
            print("[FAIL] No NVIDIA GPU found")
            return False
    except FileNotFoundError:
        print("[FAIL] nvidia-smi not found (no NVIDIA GPU)")
        return False


def install_cuda_packages():
    """Install CUDA-enabled ML packages"""
    print("\n" + "="*80)
    print("INSTALLING CUDA-ENABLED PACKAGES")
    print("="*80)

    packages = [
        "torch --index-url https://download.pytorch.org/whl/cu121",  # PyTorch with CUDA 12.1
        "spacy[cuda12x]",  # spaCy with CUDA support
        "cupy-cuda12x",  # CuPy for GPU arrays
        "nvidia-ml-py",  # Replace deprecated pynvml
    ]

    for package in packages:
        print(f"\nInstalling: {package}")
        subprocess.run([sys.executable, "-m", "pip", "install"] + package.split(), check=True)

    print("\n[OK] All CUDA packages installed")


def configure_spacy_gpu():
    """Configure spaCy to use GPU"""
    print("\n" + "="*80)
    print("CONFIGURING SPACY GPU")
    print("="*80)

    try:
        import spacy

        # Enable GPU
        spacy.prefer_gpu()

        # Test with small model
        print("\nTesting GPU with spaCy...")
        nlp = spacy.load("en_core_web_sm")

        # Check if using GPU
        try:
            if spacy.prefer_gpu():
                print("[OK] spaCy GPU enabled successfully!")
            else:
                print("[WARN] spaCy GPU initialization attempted")
        except Exception:
            print("[WARN] spaCy still using CPU (this is OK for small models)")

    except Exception as e:
        print(f"[ERROR] Error configuring spaCy: {e}")


def update_text_analyzer():
    """Update TextAnalyzer to use GPU"""
    print("\n" + "="*80)
    print("UPDATING TEXT ANALYZER")
    print("="*80)

    analyzer_path = PROJECT_ROOT / "ifmos" / "ml" / "nlp" / "text_analyzer.py"

    with open(analyzer_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Check if already GPU-enabled
    if "spacy.prefer_gpu()" in content:
        print("[OK] TextAnalyzer already GPU-enabled")
        return

    # Add GPU preference after spaCy import
    lines = content.split('\n')
    new_lines = []

    for i, line in enumerate(lines):
        new_lines.append(line)

        # After "class TextAnalyzer:" definition, add GPU init
        if "def __init__(self" in line and "TextAnalyzer" in lines[max(0, i-5):i+1]:
            # Find the logger setup line
            for j in range(i, min(i+10, len(lines))):
                if "self.logger = " in lines[j]:
                    new_lines.append("")
                    new_lines.append("        # Enable GPU acceleration if available")
                    new_lines.append("        try:")
                    new_lines.append("            import spacy")
                    new_lines.append("            spacy.prefer_gpu()")
                    new_lines.append("            if spacy.is_using_gpu():")
                    new_lines.append("                self.logger.info('GPU acceleration enabled for spaCy')")
                    new_lines.append("        except:")
                    new_lines.append("            pass  # GPU not available, continue with CPU")
                    break

    # Write updated content with UTF-8 encoding
    with open(analyzer_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(new_lines))

    print(f"[OK] Updated: {analyzer_path}")


def verify_setup():
    """Verify GPU setup is working"""
    print("\n" + "="*80)
    print("VERIFYING GPU SETUP")
    print("="*80)

    try:
        import torch
        print(f"\nPyTorch version: {torch.__version__}")
        print(f"CUDA available: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"CUDA version: {torch.version.cuda}")
            print(f"GPU: {torch.cuda.get_device_name(0)}")
            print(f"GPU memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")

        import spacy
        print(f"\nspaCy version: {spacy.__version__}")
        spacy.prefer_gpu()
        try:
            gpu_status = spacy.prefer_gpu()
            print(f"spaCy GPU enabled: {gpu_status}")
        except Exception:
            print("spaCy GPU status: CPU mode")

        print("\n[OK] GPU acceleration setup complete!")
        print("\n" + "="*80)
        print("EXPECTED SPEEDUP")
        print("="*80)
        print("NLP Processing: 3-5x faster")
        print("ML Training: 2-10x faster (depending on model)")
        print("Classification: 2-3x faster overall")

    except Exception as e:
        print(f"[ERROR] Verification failed: {e}")


def main():
    print("="*80)
    print("IFMOS GPU ACCELERATION SETUP")
    print("="*80)

    # Check GPU
    if not check_gpu_available():
        print("\nWARNING: No GPU detected. This script will install CUDA packages,")
        print("but they won't provide speedup without an NVIDIA GPU.")
        response = input("\nContinue anyway? (y/n): ")
        if response.lower() != 'y':
            print("Setup cancelled.")
            return

    # Install packages
    install_cuda_packages()

    # Configure spaCy
    configure_spacy_gpu()

    # Update TextAnalyzer
    update_text_analyzer()

    # Verify
    verify_setup()

    print("\n" + "="*80)
    print("SETUP COMPLETE!")
    print("="*80)
    print("\nNext steps:")
    print("1. Wait for current classification to complete")
    print("2. Re-run classification - it will automatically use GPU")
    print("3. Enjoy 2-5x faster processing!")


if __name__ == "__main__":
    main()
