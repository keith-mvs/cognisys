#!/usr/bin/env python3
"""
Classify the training sample using our hybrid system
Generate high-confidence training data for ML model improvement
"""

import sys
import pickle
from pathlib import Path
from collections import Counter
import csv

sys.stdout.reconfigure(encoding='utf-8')

# Import our reclassification logic
import re

def extract_real_filename(path):
    """Extract real filename"""
    filename = Path(path).name
    match = re.match(r'\d{4}-\d{2}-\d{2}_(?:\{[^}]+\}_)*(.+)$', filename)
    if match:
        return match.group(1)
    return filename


def classify_with_patterns(filename):
    """
    Pattern-based classification (copied from reclassify_null_files.py)
    Returns: (document_type, confidence, method) or (None, 0.0, None)
    """
    fn_lower = filename.lower()

    # Scripts & Code
    if re.search(r'\.(ps1|py|js|ts|jsx|tsx|sh|bat|cmd|vbs|rb|php|go|rs|swift|kt)$', fn_lower):
        return 'technical_script', 0.98, 'pattern_override'

    # Config files
    if re.search(r'\.(json|yml|yaml|xml|ini|conf|config|toml|properties|env|cfg|in|ch|dl)$', fn_lower):
        return 'technical_config', 0.98, 'pattern_override'

    # Compiled files
    if re.search(r'\.(pyc|pyo|class|o|obj|dll|so|dylib|pyd)$', fn_lower):
        return 'compiled_code', 0.99, 'pattern_override'

    # Header files
    if re.search(r'\.(h|hpp|hxx)$', fn_lower):
        return 'source_header', 0.99, 'pattern_override'

    # Documentation
    if re.search(r'\.(md|markdown|rst|adoc|asciidoc)$', fn_lower):
        if re.search(r'(commit|pr|pull[-_]request|git|sandbox|migration|api|readme|documentation|guide)', fn_lower):
            return 'technical_documentation', 0.95, 'pattern_override'
        if not re.search(r'(bmw|e\d{2}|f\d{2}|vehicle|axle|transmission|engine|brake|service)', fn_lower):
            return 'technical_documentation', 0.90, 'pattern_override'

    # Spreadsheets
    if re.search(r'\.(xlsx|xls|csv)$', fn_lower):
        if not re.search(r'(vehicle|bmw|car|service|repair|diagnostic)', fn_lower):
            return 'business_spreadsheet', 0.90, 'pattern_override'

    # HR/Career
    if re.search(r'(resume|cv|cover[-_]letter|job[-_]application|benefits.*guide|staff.*benefits)', fn_lower):
        return 'personal_career', 0.95, 'pattern_override'

    # Legal/Government
    if re.search(r'(contract|agreement|reporting|compliance|foreign.*contact|entry.*appearance|legal|court)', fn_lower):
        return 'legal_document', 0.90, 'pattern_override'

    # Financial
    if re.search(r'(invoice|receipt|tax|1099|w-2|statement)', fn_lower):
        return 'financial_document', 0.95, 'pattern_override'

    # Personal/Family
    if re.search(r'(family|personal|vacation|birthday|anniversary)', fn_lower):
        return 'personal_document', 0.90, 'pattern_override'

    # Images/Screenshots
    if re.search(r'(screenshot|screen.*shot|capture).*\.(png|jpg|jpeg)', fn_lower):
        return 'media_screenshot', 0.95, 'pattern_override'

    # Images general
    if re.search(r'\.(png|jpg|jpeg|gif|bmp|svg|webp)$', fn_lower):
        if re.search(r'(logo|icon|avatar)', fn_lower):
            return 'media_graphic', 0.90, 'pattern_override'
        else:
            return 'media_image', 0.85, 'pattern_override'

    # Architecture/Design
    if re.search(r'(floor.*plan|blueprint|architecture|design.*doc)', fn_lower):
        return 'design_document', 0.90, 'pattern_override'

    # Archives
    if re.search(r'\.(zip|tar|gz|7z|rar|bz2)$', fn_lower):
        if re.search(r'(tool|standard|manual)', fn_lower):
            return 'technical_archive', 0.85, 'pattern_override'

    # Executables
    if re.search(r'\.(exe|msi|dmg|pkg|deb|rpm|appimage)$', fn_lower):
        if not re.search(r'(bmw|vehicle|diagnostic|obd)', fn_lower):
            return 'software_installer', 0.90, 'pattern_override'

    # HTML files
    if re.search(r'\.html?$', fn_lower):
        if re.search(r'(bookmark|favorite|export|consolidate)', fn_lower):
            return 'web_bookmark', 0.95, 'pattern_override'
        elif re.search(r'(license|readme|doc)', fn_lower):
            return 'technical_documentation', 0.85, 'pattern_override'

    # Presentations
    if re.search(r'\.(pptx?|key|odp)$', fn_lower):
        if re.search(r'(about.*me|resume|portfolio)', fn_lower):
            return 'personal_career', 0.90, 'pattern_override'
        else:
            return 'business_presentation', 0.85, 'pattern_override'

    # Database files
    if re.search(r'\.(db|sqlite|mdb|accdb)$', fn_lower):
        return 'technical_database', 0.90, 'pattern_override'

    # CAD files
    if re.search(r'\.(dwg|dxf|skp|step|stp|iges|prt|asm)$', fn_lower):
        return 'design_cad', 0.95, 'pattern_override'

    # Video files
    if re.search(r'\.(mp4|avi|mov|wmv|flv|mkv|webm)$', fn_lower):
        return 'media_video', 0.95, 'pattern_override'

    # Audio files
    if re.search(r'\.(mp3|wav|flac|aac|ogg|m4a|wma)$', fn_lower):
        return 'media_audio', 0.95, 'pattern_override'

    # PDF-specific patterns
    if re.search(r'\.pdf$', fn_lower):
        if re.search(r'(invoice|receipt|order.*#|statement.*#)', fn_lower):
            return 'financial_document', 0.90, 'pattern_override'
        elif re.search(r'(chapter[-_]\d+|license|compliance|regulation)', fn_lower):
            return 'legal_document', 0.85, 'pattern_override'
        elif re.search(r'(reference.*guide|quick.*guide|user.*manual|ryzen|technical)', fn_lower):
            return 'technical_manual', 0.88, 'pattern_override'

    # Automotive patterns (let ML handle)
    if re.search(r'(bmw|e\d{2}|f\d{2}|m3|m5|vehicle|carfax|diagnostic|axle|transmission|engine|brake|service.*record|repair)', fn_lower):
        return None, 0.0, None

    # Default: Let ML decide
    return None, 0.0, None


def classify_sample():
    """Classify the training sample"""

    sample_dir = Path('.cognisys/training_sample')

    if not sample_dir.exists():
        print("Error: Training sample directory not found")
        print("Run sample_inbox_for_training.py first")
        return

    print("=" * 80)
    print("CLASSIFYING TRAINING SAMPLE")
    print("=" * 80)

    # Collect all files
    files = []
    for file_path in sample_dir.rglob('*'):
        if file_path.is_file():
            files.append(file_path)

    print(f"\nFiles to classify: {len(files):,}\n")

    # Classify
    classifications = []
    stats = Counter()
    pattern_stats = Counter()

    for i, file_path in enumerate(files):
        filename = file_path.name

        # Classify
        doc_type, confidence, method = classify_with_patterns(filename)

        if doc_type:
            stats[doc_type] += 1
            pattern_stats[method] += 1
            classifications.append({
                'filename': filename,
                'path': str(file_path),
                'doc_type': doc_type,
                'confidence': confidence,
                'method': method
            })

        if (i + 1) % 100 == 0:
            print(f"  Classified {i+1}/{len(files)}...", end='\r')

    print(f"\n\n✓ Classified {len(classifications):,} files")

    # Show statistics
    print("\n" + "=" * 80)
    print("CLASSIFICATION RESULTS")
    print("=" * 80)
    print(f"\nClassified: {len(classifications):,} ({len(classifications)/len(files)*100:.1f}%)")
    print(f"Unclassified: {len(files) - len(classifications):,} ({(len(files) - len(classifications))/len(files)*100:.1f}%)")

    print("\nTop 20 categories:")
    for doc_type, count in stats.most_common(20):
        pct = count / len(classifications) * 100
        print(f"  {doc_type:35} {count:6,} ({pct:5.1f}%)")

    print("\nBy method:")
    for method, count in pattern_stats.most_common():
        pct = count / len(classifications) * 100
        print(f"  {method:35} {count:6,} ({pct:5.1f}%)")

    # Save training data (high confidence only)
    high_conf = [c for c in classifications if c['confidence'] >= 0.90]

    print(f"\nHigh-confidence classifications (≥0.90): {len(high_conf):,}")

    # Save to CSV
    with open('.cognisys/training_data.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['filename', 'path', 'doc_type', 'confidence', 'method'])
        writer.writeheader()
        writer.writerows(high_conf)

    print(f"✓ Training data saved to .cognisys/training_data.csv")
    print("=" * 80)


if __name__ == '__main__':
    classify_sample()
