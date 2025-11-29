#!/usr/bin/env python3
"""
Explore inbox directory and analyze file types
"""

import os
from pathlib import Path
from collections import Counter
import sys

sys.stdout.reconfigure(encoding='utf-8')

inbox_path = Path(r'C:\Users\kjfle\00_Inbox')

print("=" * 80)
print("INBOX EXPLORATION")
print("=" * 80)

# Count files
all_files = []
for root, dirs, files in os.walk(inbox_path):
    for file in files:
        all_files.append(Path(root) / file)

print(f"\nTotal files found: {len(all_files):,}")

# Analyze extensions
extensions = Counter()
sizes = []

for file_path in all_files:
    ext = file_path.suffix.lower()
    extensions[ext] += 1
    try:
        size = file_path.stat().st_size
        sizes.append(size)
    except:
        pass

# Show top extensions
print("\n" + "=" * 80)
print("TOP 30 FILE EXTENSIONS")
print("=" * 80)
for ext, count in extensions.most_common(30):
    ext_display = ext if ext else '(no extension)'
    pct = count / len(all_files) * 100
    print(f"  {ext_display:20} {count:8,} ({pct:5.1f}%)")

# Show sample filenames for each major type
print("\n" + "=" * 80)
print("SAMPLE FILENAMES BY TYPE")
print("=" * 80)

for ext, count in extensions.most_common(10):
    ext_display = ext if ext else '(no extension)'
    print(f"\n{ext_display} ({count:,} files) - Sample:")

    samples = [f for f in all_files if f.suffix.lower() == ext][:5]
    for sample in samples:
        print(f"  {sample.name[:70]}")

# Total size
total_size_gb = sum(sizes) / (1024**3)
print("\n" + "=" * 80)
print(f"Total size: {total_size_gb:.2f} GB")
print("=" * 80)
