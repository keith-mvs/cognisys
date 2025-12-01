#!/usr/bin/env python3
"""Quick training status checker"""
import json
from pathlib import Path

# Check what phase we're in
label_mapping = Path("ifmos/models/distilbert/label_mapping.json")
training_history = Path("ifmos/models/distilbert/training_history.json")
checkpoint_1 = Path("ifmos/models/distilbert/checkpoint_epoch1")
checkpoint_2 = Path("ifmos/models/distilbert/checkpoint_epoch2")
checkpoint_3 = Path("ifmos/models/distilbert/checkpoint_epoch3")

print("\n=== TRAINING STATUS ===")

if not label_mapping.exists():
    print("Status: Not started")
elif not training_history.exists():
    if checkpoint_1.exists():
        print("Status: Epoch 1 complete, working on Epoch 2")
    else:
        print("Status: Content extraction or Epoch 1 training in progress")
else:
    with open(training_history) as f:
        history = json.load(f)

    last_epoch = history[-1]
    print(f"Status: {len(history)} of 3 epochs complete")
    print(f"Epoch {last_epoch['epoch']}:")
    print(f"  Train Acc: {last_epoch['train_accuracy']:.2%}")
    print(f"  Val Acc:   {last_epoch['val_accuracy']:.2%}")

    if checkpoint_3.exists():
        print("\n✓ TRAINING COMPLETE")
    else:
        remaining = 3 - len(history)
        print(f"\n{remaining} epoch(s) remaining...")

print("=" * 25 + "\n")
