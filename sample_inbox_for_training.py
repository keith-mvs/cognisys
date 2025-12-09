#!/usr/bin/env python3
"""
Create a stratified sample from inbox for training
- Diverse file types
- Representative of the full dataset
- Manageable size (2000 files)
"""

import os
import random
from pathlib import Path
from collections import defaultdict
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

inbox_path = Path(r'C:\Users\kjfle\00_Inbox')
sample_dir = Path('.cognisys/training_sample')
sample_size = 2000

print("=" * 80)
print("STRATIFIED INBOX SAMPLING FOR TRAINING")
print("=" * 80)
print(f"Target sample size: {sample_size:,} files")
print()

# Create sample directory
sample_dir.mkdir(parents=True, exist_ok=True)

# Group files by extension
files_by_ext = defaultdict(list)

print("Scanning inbox...")
for root, dirs, files in os.walk(inbox_path):
    for file in files:
        file_path = Path(root) / file
        ext = file_path.suffix.lower()
        files_by_ext[ext].append(file_path)

print(f"Found {len(files_by_ext)} unique extensions")

# Calculate samples per extension (stratified)
total_files = sum(len(files) for files in files_by_ext.values())
samples = []

print("\nStratified sampling:")
for ext, files in sorted(files_by_ext.items(), key=lambda x: -len(x[1]))[:20]:  # Top 20 extensions
    ext_count = len(files)
    proportion = ext_count / total_files
    sample_count = max(1, int(sample_size * proportion))  # At least 1

    # Random sample
    ext_sample = random.sample(files, min(sample_count, len(files)))
    samples.extend(ext_sample)

    ext_display = ext if ext else '(no extension)'
    print(f"  {ext_display:20} {ext_count:6,} files -> {len(ext_sample):4} sampled")

# Cap at sample_size
samples = samples[:sample_size]

print(f"\nTotal sampled: {len(samples):,} files")

# Copy to sample directory (keep structure)
print("\nCopying sample files...")
copied = 0
for file_path in samples:
    try:
        # Create relative path to preserve some structure
        rel_path = file_path.relative_to(inbox_path)
        dest_path = sample_dir / rel_path

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file_path, dest_path)
        copied += 1

        if copied % 100 == 0:
            print(f"  Copied {copied}/{len(samples)}...", end='\r')
    except Exception as e:
        print(f"\n  Warning: Could not copy {file_path.name}: {e}")

print(f"\n✓ Copied {copied} files to {sample_dir}")

# Save file list
with open('.cognisys/training_sample_files.txt', 'w', encoding='utf-8') as f:
    for file_path in samples:
        f.write(f"{file_path}\n")

print(f"✓ File list saved to .cognisys/training_sample_files.txt")
print("=" * 80)
