"""
Generate publication-ready tables and figures for ML classifier trade-off study.
Outputs LaTeX tables, CSV data, and summary statistics.
"""

import json
import pandas as pd
from pathlib import Path
import matplotlib.pyplot as plt
from datetime import datetime


class PublicationGenerator:
    """Generate publication materials from evaluation results."""

    def __init__(self, eval_report_path: str = "evaluation_report.json"):
        self.eval_path = Path(eval_report_path)

        if not self.eval_path.exists():
            raise FileNotFoundError(f"Evaluation report not found: {eval_report_path}")

        with open(self.eval_path) as f:
            self.data = json.load(f)

        # Convert to standardized format
        self.models = self._normalize_format()

        print(f"Loaded evaluation report: {eval_report_path}")
        print(f"Models evaluated: {len(self.models)}")

    def _normalize_format(self):
        """Normalize evaluation report format."""
        models = []

        summary = self.data.get('summary', {})
        detailed = self.data.get('detailed_results', [])

        for model_name, stats in summary.items():
            # Find detailed results
            detailed_result = None
            for result in detailed:
                if result['model'] == model_name:
                    detailed_result = result
                    break

            model_entry = {
                'model_name': model_name,
                'accuracy': stats['accuracy'],
                'avg_latency_ms': stats['latency_ms'],
                'throughput_files_per_sec': 1000.0 / stats['latency_ms'] if stats['latency_ms'] > 0 else 0,
                'total_samples': stats['samples']
            }

            # Add class accuracy if available
            if detailed_result and 'class_accuracy' in detailed_result:
                class_acc = detailed_result['class_accuracy']
                worst_classes = sorted(
                    [{'category': k, 'accuracy': v, 'support': 1}
                     for k, v in class_acc.items()],
                    key=lambda x: x['accuracy']
                )
                model_entry['worst_classes'] = worst_classes

            # Add model usage for cascades
            if 'cascade' in model_name and detailed_result and 'model_usage' in detailed_result:
                model_entry['model_usage'] = detailed_result.get('model_usage', {})

            models.append(model_entry)

        return models

    def generate_latex_table(self) -> str:
        """Generate LaTeX table for model comparison."""
        models = self.models

        latex = []
        latex.append(r"\begin{table}[htbp]")
        latex.append(r"\centering")
        latex.append(r"\caption{Document Classification Model Performance Comparison}")
        latex.append(r"\label{tab:model_comparison}")
        latex.append(r"\begin{tabular}{lrrrr}")
        latex.append(r"\toprule")
        latex.append(r"Model & Accuracy (\%) & Latency (ms) & Throughput (files/s) & Memory (MB) \\")
        latex.append(r"\midrule")

        for model in models:
            name = model['model_name'].replace('_', r'\_')
            acc = model['accuracy'] * 100
            latency = model['avg_latency_ms']
            throughput = model['throughput_files_per_sec']

            # Estimate memory (placeholder)
            memory = 0
            if 'distilbert' in model['model_name']:
                memory = 266  # DistilBERT model size
            elif 'rule_based' in model['model_name']:
                memory = 1
            elif 'cascade' in model['model_name']:
                memory = 267

            latex.append(f"{name} & {acc:.2f} & {latency:.2f} & {throughput:.1f} & {memory} \\\\")

        latex.append(r"\bottomrule")
        latex.append(r"\end{tabular}")
        latex.append(r"\end{table}")

        return '\n'.join(latex)

    def generate_csv_summary(self) -> pd.DataFrame:
        """Generate CSV summary of results."""
        models = self.models

        rows = []
        for model in models:
            row = {
                'Model': model['model_name'],
                'Accuracy': f"{model['accuracy']*100:.2f}%",
                'Latency (ms)': f"{model['avg_latency_ms']:.2f}",
                'Throughput (files/sec)': f"{model['throughput_files_per_sec']:.1f}",
                'Test Samples': model['total_samples']
            }
            rows.append(row)

        df = pd.DataFrame(rows)
        return df

    def generate_cascade_analysis(self) -> str:
        """Generate cascade model usage analysis."""
        models = self.models

        latex = []
        latex.append(r"\begin{table}[htbp]")
        latex.append(r"\centering")
        latex.append(r"\caption{Cascade Classifier Model Usage Distribution}")
        latex.append(r"\label{tab:cascade_usage}")
        latex.append(r"\begin{tabular}{lrr}")
        latex.append(r"\toprule")
        latex.append(r"Cascade Preset & Model Used & Usage (\%) \\")
        latex.append(r"\midrule")

        for model in models:
            if 'cascade' not in model['model_name']:
                continue

            if 'model_usage' in model:
                preset = model['model_name'].replace('cascade_', '').replace('_', r'\_')

                for model_name, count in model['model_usage'].items():
                    pct = (count / model['total_samples']) * 100
                    model_clean = model_name.replace('_', r'\_')
                    latex.append(f"{preset} & {model_clean} & {pct:.1f} \\\\")

        latex.append(r"\bottomrule")
        latex.append(r"\end{tabular}")
        latex.append(r"\end{table}")

        return '\n'.join(latex)

    def generate_accuracy_latency_plot(self, output_path: str = "accuracy_latency_tradeoff.png"):
        """Generate accuracy vs latency scatter plot."""
        models = self.models

        # Extract data
        names = [m['model_name'] for m in models]
        accuracies = [m['accuracy'] * 100 for m in models]
        latencies = [m['avg_latency_ms'] for m in models]

        # Create plot
        plt.figure(figsize=(10, 6))
        plt.scatter(latencies, accuracies, s=200, alpha=0.6, c=range(len(names)), cmap='viridis')

        # Annotate points
        for i, name in enumerate(names):
            plt.annotate(
                name.replace('_', ' ').title(),
                (latencies[i], accuracies[i]),
                textcoords="offset points",
                xytext=(10, 5),
                ha='left',
                fontsize=9
            )

        plt.xlabel('Average Latency (ms)', fontsize=12)
        plt.ylabel('Accuracy (%)', fontsize=12)
        plt.title('Classification Model Trade-off: Accuracy vs Latency', fontsize=14)
        plt.grid(True, alpha=0.3)
        plt.tight_layout()

        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Saved plot: {output_path}")

        return output_path

    def generate_category_performance(self) -> str:
        """Generate per-category performance table."""
        models = self.models

        # Find DistilBERT model for detailed analysis
        distilbert_model = None
        for model in models:
            if model['model_name'] == 'distilbert_v2':
                distilbert_model = model
                break

        if not distilbert_model or 'worst_classes' not in distilbert_model:
            return "% No detailed category performance available\n"

        latex = []
        latex.append(r"\begin{table}[htbp]")
        latex.append(r"\centering")
        latex.append(r"\caption{Worst Performing Document Categories (DistilBERT v2)}")
        latex.append(r"\label{tab:worst_categories}")
        latex.append(r"\begin{tabular}{lrr}")
        latex.append(r"\toprule")
        latex.append(r"Category & Accuracy (\%) & Samples \\")
        latex.append(r"\midrule")

        for cat in distilbert_model['worst_classes'][:10]:
            name = cat['category'].replace('_', r'\_')
            acc = cat['accuracy'] * 100
            support = cat['support']
            latex.append(f"{name} & {acc:.1f} & {support} \\\\")

        latex.append(r"\bottomrule")
        latex.append(r"\end{tabular}")
        latex.append(r"\end{table}")

        return '\n'.join(latex)

    def generate_all(self, output_dir: str = "publication_materials"):
        """Generate all publication materials."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        print(f"\nGenerating publication materials in: {output_path}")

        # LaTeX tables
        print("\n1. Generating LaTeX tables...")

        main_table = self.generate_latex_table()
        with open(output_path / "table_model_comparison.tex", 'w') as f:
            f.write(main_table)
        print(f"   Saved: table_model_comparison.tex")

        cascade_table = self.generate_cascade_analysis()
        with open(output_path / "table_cascade_usage.tex", 'w') as f:
            f.write(cascade_table)
        print(f"   Saved: table_cascade_usage.tex")

        category_table = self.generate_category_performance()
        with open(output_path / "table_category_performance.tex", 'w') as f:
            f.write(category_table)
        print(f"   Saved: table_category_performance.tex")

        # CSV summary
        print("\n2. Generating CSV summary...")
        csv_df = self.generate_csv_summary()
        csv_path = output_path / "model_comparison.csv"
        csv_df.to_csv(csv_path, index=False)
        print(f"   Saved: model_comparison.csv")
        print(f"\n{csv_df.to_string(index=False)}")

        # Plots
        print("\n3. Generating plots...")
        plot_path = output_path / "accuracy_latency_tradeoff.png"
        self.generate_accuracy_latency_plot(str(plot_path))

        # Summary report
        print("\n4. Generating summary report...")
        self._generate_summary_report(output_path)

        print(f"\n{'='*60}")
        print(f"PUBLICATION MATERIALS GENERATED")
        print(f"Output directory: {output_path}")
        print(f"{'='*60}")

    def _generate_summary_report(self, output_path: Path):
        """Generate markdown summary report."""
        models = self.models

        md = []
        md.append("# ML Document Classifier Trade-off Study")
        md.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Get test samples from first model
        if models:
            test_samples = models[0]['total_samples']
            md.append(f"\nDataset: {test_samples} test samples")

        md.append("\n## Model Performance Summary\n")
        md.append("| Model | Accuracy | Latency (ms) | Throughput (files/s) |")
        md.append("|-------|----------|--------------|---------------------|")

        for model in models:
            name = model['model_name']
            acc = f"{model['accuracy']*100:.2f}%"
            latency = f"{model['avg_latency_ms']:.2f}"
            throughput = f"{model['throughput_files_per_sec']:.1f}"
            md.append(f"| {name} | {acc} | {latency} | {throughput} |")

        md.append("\n## Key Findings\n")
        md.append("### Best Accuracy")
        best_acc = max(models, key=lambda x: x['accuracy'])
        md.append(f"- **{best_acc['model_name']}**: {best_acc['accuracy']*100:.2f}% accuracy\n")

        md.append("### Fastest Inference")
        fastest = min(models, key=lambda x: x['avg_latency_ms'])
        md.append(f"- **{fastest['model_name']}**: {fastest['avg_latency_ms']:.2f}ms average latency\n")

        md.append("### Best Throughput")
        highest_throughput = max(models, key=lambda x: x['throughput_files_per_sec'])
        md.append(f"- **{highest_throughput['model_name']}**: {highest_throughput['throughput_files_per_sec']:.1f} files/sec\n")

        md.append("\n## Files Generated\n")
        md.append("- `table_model_comparison.tex` - Main performance comparison table")
        md.append("- `table_cascade_usage.tex` - Cascade model usage breakdown")
        md.append("- `table_category_performance.tex` - Per-category results")
        md.append("- `model_comparison.csv` - Raw data in CSV format")
        md.append("- `accuracy_latency_tradeoff.png` - Visualization of trade-offs")

        with open(output_path / "README.md", 'w') as f:
            f.write('\n'.join(md))

        print(f"   Saved: README.md")


def main():
    """Generate all publication materials."""
    print("="*60)
    print("PUBLICATION MATERIALS GENERATOR")
    print("="*60)

    generator = PublicationGenerator("evaluation_report.json")
    generator.generate_all("publication_materials")


if __name__ == "__main__":
    main()
