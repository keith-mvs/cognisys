"""
Merge synthetic training data with existing training data.
"""

import pandas as pd
from pathlib import Path


def merge_training_data(
    existing_csv: str = ".ifmos/training_data.csv",
    synthetic_csv: str = "synthetic_training_data.csv",
    output_csv: str = ".ifmos/training_data_expanded.csv"
):
    """
    Merge synthetic and existing training data.

    Args:
        existing_csv: Path to existing training data
        synthetic_csv: Path to synthetic training data
        output_csv: Path to merged output CSV
    """
    print("Merging training data...")

    # Load existing data
    print(f"\nLoading existing data: {existing_csv}")
    df_existing = pd.read_csv(existing_csv)
    print(f"  Existing samples: {len(df_existing)}")
    print(f"  Categories: {df_existing['document_type'].nunique()}")

    # Load synthetic data
    print(f"\nLoading synthetic data: {synthetic_csv}")
    df_synthetic = pd.read_csv(synthetic_csv)
    print(f"  Synthetic samples: {len(df_synthetic)}")
    print(f"  Categories: {df_synthetic['document_type'].nunique()}")

    # Ensure same columns
    required_cols = ['file_path', 'document_type', 'confidence', 'method']

    for col in required_cols:
        if col not in df_existing.columns:
            df_existing[col] = None
        if col not in df_synthetic.columns:
            df_synthetic[col] = None

    # Standardize confidence and method
    if 'confidence' not in df_existing.columns or df_existing['confidence'].isna().all():
        df_existing['confidence'] = 1.0
    if 'method' not in df_existing.columns or df_existing['method'].isna().all():
        df_existing['method'] = 'manual'

    # Select only required columns
    df_existing = df_existing[required_cols]
    df_synthetic = df_synthetic[required_cols]

    # Merge
    df_merged = pd.concat([df_existing, df_synthetic], ignore_index=True)

    print(f"\nMerged dataset:")
    print(f"  Total samples: {len(df_merged)}")
    print(f"  Categories: {df_merged['document_type'].nunique()}")

    # Class distribution
    print(f"\nClass distribution:")
    class_counts = df_merged['document_type'].value_counts()
    print(f"  Min: {class_counts.min()} samples")
    print(f"  Max: {class_counts.max()} samples")
    print(f"  Mean: {class_counts.mean():.1f} samples")
    print(f"  Median: {class_counts.median():.1f} samples")

    # Top and bottom classes
    print(f"\nTop 5 classes:")
    for cat, count in class_counts.head(5).items():
        print(f"  {cat}: {count}")

    print(f"\nBottom 5 classes:")
    for cat, count in class_counts.tail(5).items():
        print(f"  {cat}: {count}")

    # Method distribution
    print(f"\nMethod distribution:")
    method_counts = df_merged['method'].value_counts()
    for method, count in method_counts.items():
        print(f"  {method}: {count} ({count/len(df_merged)*100:.1f}%)")

    # Save merged data
    output_path = Path(output_csv)
    output_path.parent.mkdir(exist_ok=True, parents=True)

    df_merged.to_csv(output_csv, index=False)
    print(f"\nMerged data saved to: {output_csv}")

    return df_merged


def analyze_balance_improvement(
    original_csv: str = ".ifmos/training_data.csv",
    expanded_csv: str = ".ifmos/training_data_expanded.csv"
):
    """Analyze how synthetic data improved class balance."""
    print("\n" + "="*60)
    print("CLASS BALANCE IMPROVEMENT ANALYSIS")
    print("="*60)

    df_orig = pd.read_csv(original_csv)
    df_exp = pd.read_csv(expanded_csv)

    orig_counts = df_orig['document_type'].value_counts()
    exp_counts = df_exp['document_type'].value_counts()

    # Calculate improvement
    improvements = []
    for cat in orig_counts.index:
        orig_count = orig_counts[cat]
        exp_count = exp_counts.get(cat, orig_count)
        improvement = exp_count - orig_count
        pct_increase = (improvement / orig_count) * 100
        improvements.append({
            'category': cat,
            'original': orig_count,
            'expanded': exp_count,
            'added': improvement,
            'pct_increase': pct_increase
        })

    df_imp = pd.DataFrame(improvements).sort_values('pct_increase', ascending=False)

    print("\nCategories with most improvement:")
    print(f"{'Category':<30} {'Original':>10} {'Expanded':>10} {'Added':>8} {'Increase':>10}")
    print("-"*75)
    for _, row in df_imp.head(10).iterrows():
        print(f"{row['category']:<30} {row['original']:>10} {row['expanded']:>10} "
              f"{row['added']:>8} {row['pct_increase']:>9.1f}%")

    # Overall imbalance ratio
    orig_ratio = orig_counts.max() / orig_counts.min()
    exp_ratio = exp_counts.max() / exp_counts.min()

    print(f"\nClass imbalance ratio (max/min):")
    print(f"  Original: {orig_ratio:.1f}:1")
    print(f"  Expanded: {exp_ratio:.1f}:1")
    print(f"  Improvement: {((orig_ratio - exp_ratio) / orig_ratio * 100):.1f}% reduction")

    # Coefficient of variation
    orig_cv = orig_counts.std() / orig_counts.mean()
    exp_cv = exp_counts.std() / exp_counts.mean()

    print(f"\nCoefficient of variation (lower = better balance):")
    print(f"  Original: {orig_cv:.3f}")
    print(f"  Expanded: {exp_cv:.3f}")
    print(f"  Improvement: {((orig_cv - exp_cv) / orig_cv * 100):.1f}% reduction")


def main():
    """Merge and analyze training data."""
    # Merge data
    df_merged = merge_training_data()

    # Analyze improvement
    analyze_balance_improvement()

    print("\n" + "="*60)
    print("MERGE COMPLETE")
    print("="*60)
    print("\nNext steps:")
    print("1. Retrain ensemble model: python train_ensemble.py --csv .ifmos/training_data_expanded.csv")
    print("2. Retrain DistilBERT: python train_distilbert_v2.py --csv .ifmos/training_data_expanded.csv")
    print("3. Compare performance with original models")


if __name__ == '__main__':
    main()
