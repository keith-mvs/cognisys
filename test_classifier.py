"""
Quick test script for the ML classifier integration.
"""
from ifmos.ml.classification import create_distilbert_classifier
from ifmos.ml.content_extraction import ContentExtractor
from pathlib import Path

# Test single file classification
file_path = Path("README.md")
print(f"Testing classification on: {file_path}")

# Extract content
extractor = ContentExtractor(max_chars=2000)
result = extractor.extract(file_path)
content = result.get('content', file_path.name)

print(f"\nExtracted {len(content)} characters")

# Load classifier
print("\nLoading DistilBERT v2 classifier...")
classifier = create_distilbert_classifier("v2")
print("Classifier loaded")

# Classify
print("\nClassifying...")
pred = classifier.predict(content)

if pred.get('success'):
    print(f"\n[SUCCESS]")
    print(f"  Category: {pred['predicted_category']}")
    print(f"  Confidence: {pred.get('confidence', 0):.2%}")

    if 'probabilities' in pred:
        print(f"\n  Top 5 predictions:")
        sorted_probs = sorted(pred['probabilities'].items(), key=lambda x: x[1], reverse=True)
        for cat, prob in sorted_probs[:5]:
            print(f"    {cat}: {prob:.2%}")
else:
    print(f"[ERROR] {pred.get('error', 'Unknown error')}")
