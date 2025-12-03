"""
Evaluate ensemble classifier and compare with DistilBERT.
Run comprehensive comparison for publication.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json
from datetime import datetime
import time
from tqdm import tqdm

from ifmos.ml.classification import (
    create_ensemble_classifier,
    create_distilbert_classifier,
    create_cascade
)
from ifmos.ml.content_extraction import ContentExtractor


def load_test_data(csv_path: str = ".ifmos/training_data.csv", test_size: int = 500):
    """Load random test samples."""
    print(f"Loading test data from: {csv_path}")

    df = pd.read_csv(csv_path)

    # Sample random test set
    test_df = df.sample(n=min(test_size, len(df)), random_state=42)

    print(f"  Test samples: {len(test_df)}")
    print(f"  Unique categories: {test_df['document_type'].nunique()}")

    return test_df


def evaluate_model(model, test_df, model_name: str, extractor):
    """Evaluate a single model."""
    print(f"\n{'='*60}")
    print(f"EVALUATING: {model_name}")
    print(f"{'='*60}")

    results = []
    correct = 0
    total = 0
    latencies = []

    for idx, row in tqdm(test_df.iterrows(), total=len(test_df), desc=f"{model_name}"):
        file_path = row['file_path']
        true_label = row['document_type']

        # Extract content
        try:
            path = Path(file_path)
            if not path.exists():
                continue

            content_result = extractor.extract(path)
            content = content_result.get('content', '')

            if not content:
                content = path.name

        except Exception as e:
            continue

        # Classify
        try:
            start = time.time()
            pred = model.predict(content)
            latency = (time.time() - start) * 1000  # ms

            if pred.get('success'):
                predicted = pred['predicted_category']
                confidence = pred.get('confidence', 0)

                is_correct = (predicted == true_label)
                if is_correct:
                    correct += 1
                total += 1

                latencies.append(latency)

                results.append({
                    'file_path': file_path,
                    'true_label': true_label,
                    'predicted': predicted,
                    'confidence': confidence,
                    'correct': is_correct,
                    'latency_ms': latency
                })

        except Exception as e:
            print(f"Error classifying {file_path}: {e}")
            continue

    # Calculate metrics
    accuracy = correct / total if total > 0 else 0
    avg_latency = np.mean(latencies) if latencies else 0
    throughput = 1000 / avg_latency if avg_latency > 0 else 0

    print(f"\n{'='*60}")
    print(f"RESULTS: {model_name}")
    print(f"{'='*60}")
    print(f"Accuracy: {accuracy:.4f} ({correct}/{total})")
    print(f"Avg Latency: {avg_latency:.2f} ms")
    print(f"Throughput: {throughput:.1f} files/sec")
    print(f"{'='*60}")

    return {
        'model_name': model_name,
        'accuracy': accuracy,
        'correct': correct,
        'total': total,
        'avg_latency_ms': avg_latency,
        'throughput': throughput,
        'results': results
    }


def compare_models(results_list):
    """Generate comparison table."""
    print(f"\n{'='*60}")
    print(f"MODEL COMPARISON")
    print(f"{'='*60}")

    print(f"\n{'Model':<20} {'Accuracy':>10} {'Latency':>12} {'Throughput':>15}")
    print(f"{'-'*60}")

    for result in results_list:
        name = result['model_name']
        acc = f"{result['accuracy']*100:.2f}%"
        lat = f"{result['avg_latency_ms']:.2f} ms"
        thr = f"{result['throughput']:.1f} f/s"
        print(f"{name:<20} {acc:>10} {lat:>12} {thr:>15}")

    print(f"{'-'*60}")

    # Find best
    best_acc = max(results_list, key=lambda x: x['accuracy'])
    fastest = min(results_list, key=lambda x: x['avg_latency_ms'])

    print(f"\nBest Accuracy: {best_acc['model_name']} ({best_acc['accuracy']*100:.2f}%)")
    print(f"Fastest: {fastest['model_name']} ({fastest['avg_latency_ms']:.2f} ms)")


def per_class_analysis(results_list):
    """Analyze per-class performance."""
    print(f"\n{'='*60}")
    print(f"PER-CLASS ANALYSIS")
    print(f"{'='*60}")

    for result in results_list:
        model_name = result['model_name']
        df = pd.DataFrame(result['results'])

        if df.empty:
            continue

        # Group by true label
        class_acc = df.groupby('true_label').agg({
            'correct': ['sum', 'count'],
            'confidence': 'mean'
        })

        class_acc.columns = ['correct', 'total', 'avg_confidence']
        class_acc['accuracy'] = class_acc['correct'] / class_acc['total']
        class_acc = class_acc.sort_values('accuracy', ascending=False)

        print(f"\n{model_name} - Top 10 Classes:")
        print(f"{'Category':<30} {'Accuracy':>10} {'Samples':>10}")
        print(f"{'-'*50}")

        for idx, (cat, row) in enumerate(class_acc.head(10).iterrows()):
            acc = f"{row['accuracy']*100:.1f}%"
            samples = int(row['total'])
            print(f"{cat:<30} {acc:>10} {samples:>10}")


def save_results(results_list, output_file: str = "ensemble_evaluation_results.json"):
    """Save results to JSON."""
    print(f"\nSaving results to: {output_file}")

    # Prepare for JSON serialization
    output = {
        'timestamp': datetime.now().isoformat(),
        'models': []
    }

    for result in results_list:
        model_data = {
            'model_name': result['model_name'],
            'accuracy': result['accuracy'],
            'correct': result['correct'],
            'total': result['total'],
            'avg_latency_ms': result['avg_latency_ms'],
            'throughput': result['throughput']
        }
        output['models'].append(model_data)

    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"Results saved!")


def main():
    """Run comprehensive evaluation."""
    print("="*60)
    print("COMPREHENSIVE MODEL EVALUATION")
    print("="*60)

    # Load test data
    test_df = load_test_data(test_size=500)

    # Initialize extractor
    extractor = ContentExtractor(max_chars=2000)

    # Initialize models
    print("\nInitializing models...")

    models = [
        ('Ensemble RF', create_ensemble_classifier()),
        ('DistilBERT v2', create_distilbert_classifier('v2')),
        ('Cascade (fast)', create_cascade('fast')),
        ('Cascade (local_only)', create_cascade('local_only')),
    ]

    # Evaluate each model
    results_list = []

    for model_name, model in models:
        try:
            result = evaluate_model(model, test_df, model_name, extractor)
            results_list.append(result)
        except Exception as e:
            print(f"Error evaluating {model_name}: {e}")
            continue

    # Generate comparisons
    if results_list:
        compare_models(results_list)
        per_class_analysis(results_list)
        save_results(results_list)

    print(f"\n{'='*60}")
    print(f"EVALUATION COMPLETE")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
