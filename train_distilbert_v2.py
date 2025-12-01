#!/usr/bin/env python3
"""
DistilBERT Training Script v2 - With Overfitting Fixes

FIXES FROM v1:
1. Class weights for imbalanced data
2. Early stopping when validation loss increases
3. Weight decay (L2 regularization)
4. Lower learning rate
5. Stratified train/val split
6. Increased dropout
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict
import warnings

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torch.optim import AdamW
from torch.cuda.amp import autocast, GradScaler
from transformers import (
    DistilBertTokenizer,
    DistilBertForSequenceClassification,
    DistilBertConfig,
    get_linear_schedule_with_warmup
)
from sklearn.model_selection import train_test_split
from sklearn.utils.class_weight import compute_class_weight
from tqdm import tqdm
import numpy as np
import pandas as pd

# Suppress warnings
warnings.filterwarnings('ignore')

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project root
sys.path.insert(0, str(Path(__file__).parent))
from ifmos.ml.content_extraction import ContentExtractor


class DocumentDataset(Dataset):
    """Dataset with pre-extracted content"""

    def __init__(self, file_paths, labels, label_to_id, tokenizer, max_length=256):
        self.file_paths = file_paths
        self.labels = labels
        self.label_to_id = label_to_id
        self.tokenizer = tokenizer
        self.max_length = max_length

        # Extract content upfront
        self.extractor = ContentExtractor(max_chars=1500)
        self.contents = []

        logger.info("Extracting content from files...")
        for i, file_path in enumerate(tqdm(file_paths, desc="Extracting content")):
            if i % 1000 == 0:
                logger.info(f"Extracted {i}/{len(file_paths)} files")
            try:
                result = self.extractor.extract(Path(file_path))
                content = result.get('content', '')
                if not content:
                    content = Path(file_path).name
                self.contents.append(content[:1500])
            except:
                self.contents.append(Path(file_path).name)

        logger.info(f"Content extraction complete: {len(self.contents)} documents")

    def __len__(self):
        return len(self.contents)

    def __getitem__(self, idx):
        content = self.contents[idx]
        encoding = self.tokenizer(
            content,
            max_length=self.max_length,
            padding='max_length',
            truncation=True,
            return_tensors='pt'
        )

        return {
            'input_ids': encoding['input_ids'].squeeze(),
            'attention_mask': encoding['attention_mask'].squeeze(),
            'labels': torch.tensor(self.label_to_id[self.labels[idx]], dtype=torch.long)
        }


class DistilBERTTrainerV2:
    """Trainer with overfitting fixes"""

    def __init__(
        self,
        model_name: str = 'distilbert-base-uncased',
        max_length: int = 256,  # Reduced from 512
        batch_size: int = 32,   # Increased from 16
        num_epochs: int = 10,   # More epochs with early stopping
        learning_rate: float = 5e-6,  # Reduced from 2e-5
        weight_decay: float = 0.01,   # L2 regularization
        dropout: float = 0.3,         # Increased dropout
        patience: int = 2,            # Early stopping patience
        output_dir: str = 'ifmos/models/distilbert_v2'
    ):
        self.model_name = model_name
        self.max_length = max_length
        self.batch_size = batch_size
        self.num_epochs = num_epochs
        self.learning_rate = learning_rate
        self.weight_decay = weight_decay
        self.dropout = dropout
        self.patience = patience
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Device
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        logger.info(f"Using device: {self.device}")
        if self.device.type == 'cuda':
            logger.info(f"GPU: {torch.cuda.get_device_name(0)}")

        # Load tokenizer
        logger.info(f"Loading tokenizer: {model_name}")
        self.tokenizer = DistilBertTokenizer.from_pretrained(model_name)

        self.model = None
        self.label_to_id = None
        self.id_to_label = None

    def load_data(self, csv_path: str):
        """Load and prepare data with stratified split"""
        logger.info(f"Loading training data from: {csv_path}")
        df = pd.read_csv(csv_path)

        # Remove classes with too few examples (< 10)
        class_counts = df['document_type'].value_counts()
        valid_classes = class_counts[class_counts >= 10].index
        df = df[df['document_type'].isin(valid_classes)]

        logger.info(f"After filtering: {len(df)} examples, {len(valid_classes)} classes")

        # Create label mappings
        unique_labels = sorted(df['document_type'].unique())
        self.label_to_id = {label: i for i, label in enumerate(unique_labels)}
        self.id_to_label = {i: label for label, i in self.label_to_id.items()}

        # Save label mapping
        mapping_path = self.output_dir / 'label_mapping.json'
        with open(mapping_path, 'w') as f:
            json.dump({
                'label_to_id': self.label_to_id,
                'id_to_label': {str(k): v for k, v in self.id_to_label.items()},
                'num_labels': len(unique_labels)
            }, f, indent=2)
        logger.info(f"Saved label mapping to: {mapping_path}")

        # Stratified split
        file_paths = df['file_path'].tolist()
        labels = df['document_type'].tolist()

        train_paths, val_paths, train_labels, val_labels = train_test_split(
            file_paths, labels,
            test_size=0.15,
            stratify=labels,
            random_state=42
        )

        logger.info(f"Training: {len(train_paths)}, Validation: {len(val_paths)}")

        # Compute class weights for imbalanced data
        label_ids = [self.label_to_id[l] for l in train_labels]
        class_weights = compute_class_weight(
            class_weight='balanced',
            classes=np.unique(label_ids),
            y=label_ids
        )
        self.class_weights = torch.tensor(class_weights, dtype=torch.float32).to(self.device)
        logger.info(f"Class weights computed (range: {class_weights.min():.2f} - {class_weights.max():.2f})")

        return train_paths, val_paths, train_labels, val_labels

    def create_dataloaders(self, train_paths, val_paths, train_labels, val_labels):
        """Create dataloaders with parallel loading"""

        train_dataset = DocumentDataset(
            train_paths, train_labels, self.label_to_id,
            self.tokenizer, max_length=self.max_length
        )

        val_dataset = DocumentDataset(
            val_paths, val_labels, self.label_to_id,
            self.tokenizer, max_length=self.max_length
        )

        train_loader = DataLoader(
            train_dataset,
            batch_size=self.batch_size,
            shuffle=True,
            num_workers=4,
            pin_memory=True
        )

        val_loader = DataLoader(
            val_dataset,
            batch_size=self.batch_size,
            shuffle=False,
            num_workers=2,
            pin_memory=True
        )

        return train_loader, val_loader

    def train(self, train_loader, val_loader, num_labels: int):
        """Train with early stopping and class weights"""

        logger.info("Initializing model with increased dropout...")

        # Custom config with higher dropout
        config = DistilBertConfig.from_pretrained(
            self.model_name,
            num_labels=num_labels,
            dropout=self.dropout,
            attention_dropout=self.dropout
        )

        self.model = DistilBertForSequenceClassification.from_pretrained(
            self.model_name,
            config=config
        )
        self.model.to(self.device)

        # Optimizer with weight decay
        optimizer = AdamW(
            self.model.parameters(),
            lr=self.learning_rate,
            weight_decay=self.weight_decay
        )

        total_steps = len(train_loader) * self.num_epochs
        scheduler = get_linear_schedule_with_warmup(
            optimizer,
            num_warmup_steps=int(0.1 * total_steps),
            num_training_steps=total_steps
        )

        # Loss function with class weights
        criterion = nn.CrossEntropyLoss(weight=self.class_weights)

        # Mixed precision
        scaler = GradScaler()

        logger.info("=" * 60)
        logger.info("TRAINING CONFIG (v2 - Overfitting Fixes)")
        logger.info("=" * 60)
        logger.info(f"Epochs: {self.num_epochs} (with early stopping)")
        logger.info(f"Batch size: {self.batch_size}")
        logger.info(f"Learning rate: {self.learning_rate}")
        logger.info(f"Weight decay: {self.weight_decay}")
        logger.info(f"Dropout: {self.dropout}")
        logger.info(f"Early stopping patience: {self.patience}")
        logger.info(f"Class weights: ENABLED")
        logger.info(f"Mixed precision: ENABLED")
        logger.info("=" * 60)

        best_val_loss = float('inf')
        patience_counter = 0
        training_history = []

        for epoch in range(self.num_epochs):
            logger.info(f"\nEpoch {epoch + 1}/{self.num_epochs}")

            # Training
            self.model.train()
            train_loss = 0
            train_correct = 0
            train_total = 0

            train_pbar = tqdm(train_loader, desc=f"Train {epoch+1}")
            for batch in train_pbar:
                input_ids = batch['input_ids'].to(self.device)
                attention_mask = batch['attention_mask'].to(self.device)
                labels = batch['labels'].to(self.device)

                optimizer.zero_grad()

                with autocast():
                    outputs = self.model(
                        input_ids=input_ids,
                        attention_mask=attention_mask
                    )
                    # Use weighted loss
                    loss = criterion(outputs.logits, labels)

                scaler.scale(loss).backward()
                scaler.step(optimizer)
                scaler.update()
                scheduler.step()

                train_loss += loss.item()
                predictions = torch.argmax(outputs.logits, dim=1)
                train_correct += (predictions == labels).sum().item()
                train_total += labels.size(0)

                train_pbar.set_postfix({
                    'loss': f'{loss.item():.3f}',
                    'acc': f'{train_correct/train_total:.2%}'
                })

            avg_train_loss = train_loss / len(train_loader)
            train_acc = train_correct / train_total

            # Validation
            self.model.eval()
            val_loss = 0
            val_correct = 0
            val_total = 0

            with torch.no_grad():
                for batch in tqdm(val_loader, desc=f"Val {epoch+1}"):
                    input_ids = batch['input_ids'].to(self.device)
                    attention_mask = batch['attention_mask'].to(self.device)
                    labels = batch['labels'].to(self.device)

                    outputs = self.model(
                        input_ids=input_ids,
                        attention_mask=attention_mask
                    )
                    loss = criterion(outputs.logits, labels)

                    val_loss += loss.item()
                    predictions = torch.argmax(outputs.logits, dim=1)
                    val_correct += (predictions == labels).sum().item()
                    val_total += labels.size(0)

            avg_val_loss = val_loss / len(val_loader)
            val_acc = val_correct / val_total

            logger.info(f"Train Loss: {avg_train_loss:.4f} | Train Acc: {train_acc:.2%}")
            logger.info(f"Val Loss:   {avg_val_loss:.4f} | Val Acc:   {val_acc:.2%}")
            logger.info(f"Gap: {(train_acc - val_acc)*100:.1f} percentage points")

            training_history.append({
                'epoch': epoch + 1,
                'train_loss': avg_train_loss,
                'train_accuracy': train_acc,
                'val_loss': avg_val_loss,
                'val_accuracy': val_acc
            })

            # Early stopping check
            if avg_val_loss < best_val_loss:
                best_val_loss = avg_val_loss
                patience_counter = 0

                # Save best model
                checkpoint_path = self.output_dir / 'best_model'
                self.model.save_pretrained(checkpoint_path)
                self.tokenizer.save_pretrained(checkpoint_path)
                logger.info(f"New best model saved! Val loss: {avg_val_loss:.4f}")
            else:
                patience_counter += 1
                logger.info(f"No improvement. Patience: {patience_counter}/{self.patience}")

                if patience_counter >= self.patience:
                    logger.info("Early stopping triggered!")
                    break

        # Save training history
        history_path = self.output_dir / 'training_history.json'
        with open(history_path, 'w') as f:
            json.dump(training_history, f, indent=2)

        logger.info(f"\nTraining complete. Best val loss: {best_val_loss:.4f}")
        logger.info(f"Best model saved to: {self.output_dir / 'best_model'}")

        return training_history


def main():
    print("=" * 70)
    print("DISTILBERT v2 - OVERFITTING FIXES")
    print("=" * 70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    trainer = DistilBERTTrainerV2(
        batch_size=32,
        num_epochs=10,
        learning_rate=5e-6,
        weight_decay=0.01,
        dropout=0.3,
        patience=2
    )

    # Load data
    train_paths, val_paths, train_labels, val_labels = trainer.load_data(
        '.ifmos/training_data.csv'
    )

    # Create dataloaders
    train_loader, val_loader = trainer.create_dataloaders(
        train_paths, val_paths, train_labels, val_labels
    )

    # Train
    history = trainer.train(
        train_loader, val_loader,
        num_labels=len(trainer.label_to_id)
    )

    print("\n" + "=" * 70)
    print("TRAINING COMPLETE")
    print("=" * 70)

    final = history[-1]
    print(f"Final Train Acc: {final['train_accuracy']:.2%}")
    print(f"Final Val Acc:   {final['val_accuracy']:.2%}")
    print(f"Best model at: ifmos/models/distilbert_v2/best_model/")


if __name__ == '__main__':
    main()
