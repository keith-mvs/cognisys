# ML Document Classifier Trade-off Study

Generated: 2025-12-03 00:19:39

Dataset: 427 test samples

## Model Performance Summary

| Model | Accuracy | Latency (ms) | Throughput (files/s) |
|-------|----------|--------------|---------------------|
| distilbert_v2 | 82.90% | 9.11 | 109.8 |
| rule_based | 6.79% | 0.05 | 19721.5 |
| cascade_local_only | 66.74% | 8.94 | 111.9 |
| cascade_fast | 66.74% | 8.87 | 112.7 |

## Key Findings

### Best Accuracy
- **distilbert_v2**: 82.90% accuracy

### Fastest Inference
- **rule_based**: 0.05ms average latency

### Best Throughput
- **rule_based**: 19721.5 files/sec


## Files Generated

- `table_model_comparison.tex` - Main performance comparison table
- `table_cascade_usage.tex` - Cascade model usage breakdown
- `table_category_performance.tex` - Per-category results
- `model_comparison.csv` - Raw data in CSV format
- `accuracy_latency_tradeoff.png` - Visualization of trade-offs