#!/usr/bin/env python3
"""
Comprehensive Classifier Evaluation
Compare DistilBERT, Ensemble ML, and Rule-based classifiers
"""

import json
import time
import random
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import pandas as pd
from tqdm import tqdm

# Evaluation config
SAMPLE_SIZE = 500  # Files to evaluate
RANDOM_SEED = 42


def load_test_data():
    """Load test files from training data CSV."""
    df = pd.read_csv('.ifmos/training_data.csv')

    # Stratified sample
    samples = []
    for doc_type in df['document_type'].unique():
        type_files = df[df['document_type'] == doc_type]
        n_sample = min(len(type_files), max(5, SAMPLE_SIZE // len(df['document_type'].unique())))
        samples.append(type_files.sample(n=n_sample, random_state=RANDOM_SEED))

    test_df = pd.concat(samples)
    print(f"Test set: {len(test_df)} files, {len(test_df['document_type'].unique())} classes")
    return test_df


def evaluate_distilbert(test_df):
    """Evaluate DistilBERT classifier."""
    from ifmos.ml.classification import create_distilbert_classifier
    from ifmos.ml.content_extraction import ContentExtractor

    print("\n" + "="*60)
    print("EVALUATING: DistilBERT v2")
    print("="*60)

    classifier = create_distilbert_classifier("v2")
    extractor = ContentExtractor(max_chars=1500)

    correct = 0
    total = 0
    results = []
    class_correct = defaultdict(int)
    class_total = defaultdict(int)
    inference_times = []

    for _, row in tqdm(test_df.iterrows(), total=len(test_df), desc="DistilBERT"):
        file_path = row['file_path']
        true_label = row['document_type']

        try:
            # Extract content
            content_result = extractor.extract(Path(file_path))
            content = content_result.get('content', '')
            if not content:
                content = Path(file_path).name

            # Predict
            start = time.time()
            pred = classifier.predict(content)
            inference_time = time.time() - start
            inference_times.append(inference_time)

            if pred['success']:
                predicted = pred['predicted_category']
                confidence = pred['confidence']

                is_correct = predicted == true_label
                if is_correct:
                    correct += 1
                    class_correct[true_label] += 1

                total += 1
                class_total[true_label] += 1

                results.append({
                    'file_path': file_path,
                    'true_label': true_label,
                    'predicted': predicted,
                    'confidence': confidence,
                    'correct': is_correct,
                    'model': 'distilbert_v2'
                })
        except Exception as e:
            pass

    accuracy = correct / total if total > 0 else 0
    avg_time = sum(inference_times) / len(inference_times) if inference_times else 0

    print(f"\nResults:")
    print(f"  Accuracy: {accuracy:.2%} ({correct}/{total})")
    print(f"  Avg inference time: {avg_time*1000:.1f}ms")
    print(f"  Throughput: {1/avg_time:.1f} files/sec" if avg_time > 0 else "")

    # Per-class accuracy (worst 5)
    print(f"\nWorst performing classes:")
    class_acc = {k: class_correct[k]/class_total[k] for k in class_total}
    for cls, acc in sorted(class_acc.items(), key=lambda x: x[1])[:5]:
        print(f"  {cls}: {acc:.2%} ({class_correct[cls]}/{class_total[cls]})")

    return {
        'model': 'distilbert_v2',
        'accuracy': accuracy,
        'correct': correct,
        'total': total,
        'avg_inference_ms': avg_time * 1000,
        'class_accuracy': class_acc,
        'results': results
    }


def evaluate_rule_based(test_df):
    """Evaluate rule-based classifier."""
    from ifmos.ml.classification import RuleBasedClassifier
    from ifmos.ml.content_extraction import ContentExtractor

    print("\n" + "="*60)
    print("EVALUATING: Rule-Based")
    print("="*60)

    classifier = RuleBasedClassifier()
    extractor = ContentExtractor(max_chars=1500)

    correct = 0
    total = 0
    results = []
    inference_times = []

    for _, row in tqdm(test_df.iterrows(), total=len(test_df), desc="Rule-based"):
        file_path = row['file_path']
        true_label = row['document_type']

        try:
            content_result = extractor.extract(Path(file_path))
            content = content_result.get('content', '')
            if not content:
                content = Path(file_path).name

            start = time.time()
            pred = classifier.classify(content, file_path)
            inference_time = time.time() - start
            inference_times.append(inference_time)

            if pred['success']:
                predicted = pred['predicted_category']
                confidence = pred['confidence']

                is_correct = predicted == true_label
                if is_correct:
                    correct += 1
                total += 1

                results.append({
                    'file_path': file_path,
                    'true_label': true_label,
                    'predicted': predicted,
                    'confidence': confidence,
                    'correct': is_correct,
                    'model': 'rule_based'
                })
        except:
            pass

    accuracy = correct / total if total > 0 else 0
    avg_time = sum(inference_times) / len(inference_times) if inference_times else 0

    print(f"\nResults:")
    print(f"  Accuracy: {accuracy:.2%} ({correct}/{total})")
    print(f"  Avg inference time: {avg_time*1000:.2f}ms")
    print(f"  Throughput: {1/avg_time:.0f} files/sec" if avg_time > 0 else "")

    return {
        'model': 'rule_based',
        'accuracy': accuracy,
        'correct': correct,
        'total': total,
        'avg_inference_ms': avg_time * 1000,
        'results': results
    }


def evaluate_cascade(test_df, preset="local_only"):
    """Evaluate cascade classifier."""
    from ifmos.ml.classification import create_cascade
    from ifmos.ml.content_extraction import ContentExtractor

    print("\n" + "="*60)
    print(f"EVALUATING: Cascade ({preset})")
    print("="*60)

    cascade = create_cascade(preset)
    extractor = ContentExtractor(max_chars=1500)

    correct = 0
    total = 0
    results = []
    model_usage = defaultdict(int)
    inference_times = []

    for _, row in tqdm(test_df.iterrows(), total=len(test_df), desc=f"Cascade-{preset}"):
        file_path = row['file_path']
        true_label = row['document_type']

        try:
            content_result = extractor.extract(Path(file_path))
            content = content_result.get('content', '')
            if not content:
                content = Path(file_path).name

            start = time.time()
            pred = cascade.predict(content, file_path)
            inference_time = time.time() - start
            inference_times.append(inference_time)

            if pred['success']:
                predicted = pred['predicted_category']
                confidence = pred['confidence']
                model_used = pred['model_used']

                model_usage[model_used] += 1

                is_correct = predicted == true_label
                if is_correct:
                    correct += 1
                total += 1

                results.append({
                    'file_path': file_path,
                    'true_label': true_label,
                    'predicted': predicted,
                    'confidence': confidence,
                    'correct': is_correct,
                    'model': f'cascade_{preset}',
                    'model_used': model_used
                })
        except:
            pass

    accuracy = correct / total if total > 0 else 0
    avg_time = sum(inference_times) / len(inference_times) if inference_times else 0

    print(f"\nResults:")
    print(f"  Accuracy: {accuracy:.2%} ({correct}/{total})")
    print(f"  Avg inference time: {avg_time*1000:.1f}ms")
    print(f"\nModel usage:")
    for model, count in sorted(model_usage.items(), key=lambda x: -x[1]):
        print(f"  {model}: {count} ({count/total*100:.1f}%)")

    return {
        'model': f'cascade_{preset}',
        'accuracy': accuracy,
        'correct': correct,
        'total': total,
        'avg_inference_ms': avg_time * 1000,
        'model_usage': dict(model_usage),
        'results': results
    }


def generate_report(all_results):
    """Generate comparison report."""
    print("\n" + "="*70)
    print("TRADE-OFF STUDY RESULTS")
    print("="*70)

    print(f"\n{'Model':<25} {'Accuracy':>10} {'Latency (ms)':>15} {'Throughput':>12}")
    print("-" * 65)

    for result in all_results:
        model = result['model']
        acc = result['accuracy']
        latency = result['avg_inference_ms']
        throughput = 1000 / latency if latency > 0 else 0
        print(f"{model:<25} {acc:>9.2%} {latency:>14.1f} {throughput:>10.1f}/s")

    print("\n" + "="*70)

    # Save detailed results
    report = {
        'timestamp': datetime.now().isoformat(),
        'summary': {
            r['model']: {
                'accuracy': r['accuracy'],
                'latency_ms': r['avg_inference_ms'],
                'samples': r['total']
            }
            for r in all_results
        },
        'detailed_results': all_results
    }

    report_path = Path('evaluation_report.json')
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2, default=str)

    print(f"\nDetailed report saved to: {report_path}")
    return report


def main():
    print("="*70)
    print("CLASSIFIER EVALUATION SUITE")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)

    # Load test data
    test_df = load_test_data()

    all_results = []

    # Evaluate each classifier
    all_results.append(evaluate_distilbert(test_df))
    all_results.append(evaluate_rule_based(test_df))
    all_results.append(evaluate_cascade(test_df, "local_only"))
    all_results.append(evaluate_cascade(test_df, "fast"))

    # Generate report
    generate_report(all_results)

    print(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == '__main__':
    main()
