#!/usr/bin/env python3
"""
Test NVIDIA Vision Classifier
Runs on sample unknown images/PDFs to evaluate effectiveness
"""

import os
import sqlite3
from pathlib import Path
import sys

# Add ifmos to path
sys.path.insert(0, str(Path(__file__).parent))

from cognisys.ml.vision.nvidia_vision import NVIDIAVisionClassifier


def test_nvidia_vision(sample_size=10):
    """Test NVIDIA vision on sample unknown images/PDFs"""

    print("=" * 80)
    print("NVIDIA VISION CLASSIFIER TEST")
    print("=" * 80)

    # Check API key
    api_key = os.getenv('NVIDIA_API_KEY')
    if not api_key:
        print("[ERROR] NVIDIA_API_KEY not set in environment")
        print("Run: $env:NVIDIA_API_KEY = 'your-key-here'")
        return

    print(f"API Key: {api_key[:20]}...")
    print()

    # Initialize classifier
    try:
        classifier = NVIDIAVisionClassifier(api_key=api_key)
        print("[OK] NVIDIA Vision Classifier initialized")
    except Exception as e:
        print(f"[ERROR] Failed to initialize classifier: {e}")
        return

    # Get sample unknown images/PDFs
    conn = sqlite3.connect('.ifmos/file_registry.db')
    cursor = conn.cursor()

    cursor.execute(f'''
        SELECT original_path
        FROM file_registry
        WHERE document_type = 'unknown'
          AND (
              original_path LIKE '%.jpg'
              OR original_path LIKE '%.jpeg'
              OR original_path LIKE '%.png'
              OR original_path LIKE '%.pdf'
              OR original_path LIKE '%.webp'
          )
        LIMIT {sample_size * 2}
    ''')

    sample_paths = [row[0] for row in cursor.fetchall()]
    conn.close()

    print(f"\nFound {len(sample_paths)} image/PDF candidates")
    print()

    # Test on samples
    results = []
    successful = 0
    errors = 0

    for i, path in enumerate(sample_paths[:sample_size], 1):
        filepath = Path(path)

        if not filepath.exists():
            print(f"[SKIP] {i}/{sample_size}: File not found - {filepath.name}")
            continue

        print(f"[TEST] {i}/{sample_size}: {filepath.name}")

        try:
            doc_type, confidence, method = classifier.classify_image(filepath)

            if doc_type:
                print(f"  Result: {doc_type} (confidence: {confidence:.2%})")
                results.append({
                    'filename': filepath.name,
                    'doc_type': doc_type,
                    'confidence': confidence,
                    'method': method
                })
                successful += 1
            else:
                print(f"  Result: Could not classify")
                errors += 1

        except Exception as e:
            print(f"  Error: {e}")
            errors += 1

        print()

    # Summary
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Samples tested: {sample_size}")
    print(f"Successful: {successful}")
    print(f"Errors: {errors}")

    if results:
        print("\nClassification breakdown:")
        from collections import Counter
        type_counts = Counter(r['doc_type'] for r in results)
        for doc_type, count in type_counts.most_common():
            print(f"  {doc_type}: {count}")

        avg_confidence = sum(r['confidence'] for r in results) / len(results)
        print(f"\nAverage confidence: {avg_confidence:.2%}")

    print("=" * 80)

    # Cost estimation
    if successful > 0:
        cost_per_call = 0.01  # Estimate
        total_unknown_images = 8323 * 0.3  # Estimate 30% are images/PDFs
        estimated_cost = total_unknown_images * cost_per_call

        print("\nCOST ESTIMATION")
        print("=" * 80)
        print(f"Cost per API call: ~${cost_per_call:.3f}")
        print(f"Estimated unknown images/PDFs: ~{int(total_unknown_images):,}")
        print(f"Estimated total cost: ~${estimated_cost:.2f}")
        print("=" * 80)


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Test NVIDIA Vision Classifier')
    parser.add_argument('--sample-size', type=int, default=10, help='Number of samples to test')
    args = parser.parse_args()

    test_nvidia_vision(sample_size=args.sample_size)


if __name__ == '__main__':
    main()
