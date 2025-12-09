#!/usr/bin/env python3
"""Quick training status checker for v1 and v2"""
import json
from pathlib import Path

def check_version(version_dir, name):
    """Check status of a training version"""
    label_mapping = version_dir / "label_mapping.json"
    training_history = version_dir / "training_history.json"
    best_model = version_dir / "best_model"

    print(f"\n=== {name} ===")

    if not label_mapping.exists():
        print("Status: Not started")
        return

    if not training_history.exists():
        if best_model.exists():
            print("Status: Training complete (best model saved)")
        else:
            print("Status: Content extraction or training in progress")
        return

    with open(training_history) as f:
        history = json.load(f)

    last = history[-1]
    print(f"Epochs completed: {len(history)}")
    print(f"Train Acc: {last['train_accuracy']:.2%}")
    print(f"Val Acc:   {last['val_accuracy']:.2%}")
    print(f"Gap:       {(last['train_accuracy'] - last['val_accuracy'])*100:.1f}pp")

    if best_model.exists():
        print("Best model: SAVED")

# Check v1
check_version(Path("cognisys/models/distilbert"), "v1 (Original - Overfitted)")

# Check v2
check_version(Path("cognisys/models/distilbert_v2"), "v2 (With Fixes)")

print("\n" + "=" * 35)
