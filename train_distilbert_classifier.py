#!/usr/bin/env python3
"""
Train DistilBERT Document Classifier

Fine-tunes DistilBERT on high-confidence classifications from IFMOS database.
Trains on content extracted from actual files for superior accuracy.

Hardware Requirements:
- GPU: NVIDIA RTX 2080 Ti (11GB VRAM)
- CUDA: 12.1+
- Memory: 16GB+ RAM

Training Specs:
- Model: distilbert-base-uncased (66M parameters)
- Training examples: 72,422
- Document types: 45 classes
- Epochs: 3
- Batch size: 16
- Expected time: 2-4 hours
- Expected accuracy: 92-94%

Author: Claude Code
Date: 2025-12-01
"""

import csv
import json
import logging
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Dict
import warnings

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torch.optim import AdamW
from torch.cuda.amp import autocast, GradScaler
from transformers import (
    DistilBertTokenizer,
    DistilBertForSequenceClassification,
    get_linear_schedule_with_warmup
)
from tqdm import tqdm

# Import content extraction
sys.path.insert(0, str(Path(__file__).parent))
from ifmos.ml.content_extraction import ContentExtractor

# Suppress warnings
warnings.filterwarnings('ignore')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DocumentDataset(Dataset):
    """PyTorch Dataset for document classification"""

    def __init__(
        self,
        file_paths: List[str],
        labels: List[str],
        label_to_id: Dict[str, int],
        tokenizer,
        max_length: int = 512,
        max_content_chars: int = 2000
    ):
        self.file_paths = file_paths
        self.labels = labels
        self.label_to_id = label_to_id
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.extractor = ContentExtractor(max_chars=max_content_chars)

        # Pre-extract content to avoid repeated extraction
        logger.info("Extracting content from files...")
        self.contents = []
        for i, file_path in enumerate(tqdm(file_paths, desc="Extracting content")):
            if i % 1000 == 0:
                logger.info(f"Extracted {i}/{len(file_paths)} files")

            result = self.extractor.extract(Path(file_path))
            content = result.get('content', '')

            # Fallback to filename if extraction failed
            if not content or len(content.strip()) == 0:
                content = Path(file_path).name

            self.contents.append(content)

        logger.info(f"Content extraction complete: {len(self.contents)} documents")

    def __len__(self):
        return len(self.file_paths)

    def __getitem__(self, idx):
        content = self.contents[idx]
        label = self.labels[idx]
        label_id = self.label_to_id[label]

        # Tokenize
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
            'labels': torch.tensor(label_id, dtype=torch.long)
        }


class DistilBERTTrainer:
    """Train DistilBERT for document classification"""

    def __init__(
        self,
        model_name: str = 'distilbert-base-uncased',
        output_dir: str = 'ifmos/models/distilbert',
        batch_size: int = 16,
        learning_rate: float = 2e-5,
        num_epochs: int = 3,
        max_length: int = 512
    ):
        self.model_name = model_name
        self.output_dir = Path(output_dir)
        self.batch_size = batch_size
        self.learning_rate = learning_rate
        self.num_epochs = num_epochs
        self.max_length = max_length

        # Check GPU availability
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        logger.info(f"Using device: {self.device}")

        if torch.cuda.is_available():
            logger.info(f"GPU: {torch.cuda.get_device_name(0)}")
            logger.info(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize tokenizer
        logger.info(f"Loading tokenizer: {model_name}")
        self.tokenizer = DistilBertTokenizer.from_pretrained(model_name)

        # Will be set during training
        self.model = None
        self.label_to_id = None
        self.id_to_label = None

    def load_training_data(self, csv_path: str) -> Tuple[List[str], List[str], Dict]:
        """
        Load training data from CSV.

        Returns:
            Tuple of (file_paths, labels, label_to_id mapping)
        """
        logger.info(f"Loading training data from: {csv_path}")

        file_paths = []
        labels = []
        label_counts = {}

        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                file_path = row['file_path']
                label = row['document_type']

                # Only include existing files
                if Path(file_path).exists():
                    file_paths.append(file_path)
                    labels.append(label)
                    label_counts[label] = label_counts.get(label, 0) + 1

        logger.info(f"Loaded {len(file_paths)} training examples")
        logger.info(f"Unique labels: {len(label_counts)}")

        # Show label distribution
        logger.info("Label distribution (top 20):")
        for label in sorted(label_counts.keys(), key=lambda x: label_counts[x], reverse=True)[:20]:
            logger.info(f"  {label:35} : {label_counts[label]:,}")

        # Create label mapping
        unique_labels = sorted(label_counts.keys())
        label_to_id = {label: idx for idx, label in enumerate(unique_labels)}
        id_to_label = {idx: label for label, idx in label_to_id.items()}

        # Save label mapping
        mapping_path = self.output_dir / 'label_mapping.json'
        with open(mapping_path, 'w') as f:
            json.dump({
                'label_to_id': label_to_id,
                'id_to_label': id_to_label,
                'num_labels': len(unique_labels)
            }, f, indent=2)

        logger.info(f"Saved label mapping to: {mapping_path}")

        return file_paths, labels, label_to_id

    def create_dataloaders(
        self,
        file_paths: List[str],
        labels: List[str],
        label_to_id: Dict[str, int],
        train_split: float = 0.9
    ):
        """Create training and validation dataloaders"""

        # Split into train/val
        split_idx = int(len(file_paths) * train_split)
        train_paths = file_paths[:split_idx]
        train_labels = labels[:split_idx]
        val_paths = file_paths[split_idx:]
        val_labels = labels[split_idx:]

        logger.info(f"Training examples: {len(train_paths)}")
        logger.info(f"Validation examples: {len(val_paths)}")

        # Create datasets
        train_dataset = DocumentDataset(
            train_paths,
            train_labels,
            label_to_id,
            self.tokenizer,
            max_length=self.max_length
        )

        val_dataset = DocumentDataset(
            val_paths,
            val_labels,
            label_to_id,
            self.tokenizer,
            max_length=self.max_length
        )

        # Create dataloaders with parallel CPU workers
        train_loader = DataLoader(
            train_dataset,
            batch_size=self.batch_size,
            shuffle=True,
            num_workers=6,  # Parallel CPU data loading
            pin_memory=True,  # Faster CPU->GPU transfers
            persistent_workers=True  # Keep workers alive between epochs
        )

        val_loader = DataLoader(
            val_dataset,
            batch_size=self.batch_size,
            shuffle=False,
            num_workers=4,
            pin_memory=True,
            persistent_workers=True
        )

        return train_loader, val_loader

    def train(self, train_loader, val_loader, num_labels: int):
        """Train the model"""

        logger.info("Initializing model...")
        self.model = DistilBertForSequenceClassification.from_pretrained(
            self.model_name,
            num_labels=num_labels
        )
        self.model.to(self.device)

        # Optimizer and scheduler
        optimizer = AdamW(self.model.parameters(), lr=self.learning_rate)
        total_steps = len(train_loader) * self.num_epochs
        scheduler = get_linear_schedule_with_warmup(
            optimizer,
            num_warmup_steps=int(0.1 * total_steps),
            num_training_steps=total_steps
        )

        # Initialize mixed precision training
        scaler = GradScaler()

        logger.info("Starting training...")
        logger.info(f"Total steps: {total_steps}")
        logger.info(f"Epochs: {self.num_epochs}")
        logger.info(f"Batch size: {self.batch_size}")
        logger.info("Mixed precision: ENABLED")
        logger.info(f"CPU workers: 6 (parallel data loading)")

        best_val_accuracy = 0.0
        training_history = []

        for epoch in range(self.num_epochs):
            logger.info(f"\n{'='*80}")
            logger.info(f"Epoch {epoch + 1}/{self.num_epochs}")
            logger.info(f"{'='*80}")

            # Training
            self.model.train()
            train_loss = 0
            train_correct = 0
            train_total = 0

            train_pbar = tqdm(train_loader, desc=f"Training Epoch {epoch+1}")
            for batch in train_pbar:
                input_ids = batch['input_ids'].to(self.device)
                attention_mask = batch['attention_mask'].to(self.device)
                labels = batch['labels'].to(self.device)

                optimizer.zero_grad()

                # Forward pass with mixed precision
                with autocast():
                    outputs = self.model(
                        input_ids=input_ids,
                        attention_mask=attention_mask,
                        labels=labels
                    )
                    loss = outputs.loss
                    logits = outputs.logits

                # Backward pass with gradient scaling
                scaler.scale(loss).backward()
                scaler.step(optimizer)
                scaler.update()
                scheduler.step()

                # Track metrics
                train_loss += loss.item()
                predictions = torch.argmax(logits, dim=1)
                train_correct += (predictions == labels).sum().item()
                train_total += labels.size(0)

                # Update progress bar
                train_pbar.set_postfix({
                    'loss': loss.item(),
                    'acc': train_correct / train_total
                })

            avg_train_loss = train_loss / len(train_loader)
            train_accuracy = train_correct / train_total

            # Validation
            self.model.eval()
            val_loss = 0
            val_correct = 0
            val_total = 0

            with torch.no_grad():
                val_pbar = tqdm(val_loader, desc=f"Validation Epoch {epoch+1}")
                for batch in val_pbar:
                    input_ids = batch['input_ids'].to(self.device)
                    attention_mask = batch['attention_mask'].to(self.device)
                    labels = batch['labels'].to(self.device)

                    outputs = self.model(
                        input_ids=input_ids,
                        attention_mask=attention_mask,
                        labels=labels
                    )

                    val_loss += outputs.loss.item()
                    predictions = torch.argmax(outputs.logits, dim=1)
                    val_correct += (predictions == labels).sum().item()
                    val_total += labels.size(0)

                    val_pbar.set_postfix({
                        'loss': outputs.loss.item(),
                        'acc': val_correct / val_total
                    })

            avg_val_loss = val_loss / len(val_loader)
            val_accuracy = val_correct / val_total

            # Log epoch results
            logger.info(f"\nEpoch {epoch + 1} Results:")
            logger.info(f"  Train Loss: {avg_train_loss:.4f} | Train Acc: {train_accuracy:.2%}")
            logger.info(f"  Val Loss:   {avg_val_loss:.4f} | Val Acc:   {val_accuracy:.2%}")

            # Save best model
            if val_accuracy > best_val_accuracy:
                best_val_accuracy = val_accuracy
                logger.info(f"New best validation accuracy: {best_val_accuracy:.2%}")
                self.save_model(epoch + 1, val_accuracy)

            # Track history
            training_history.append({
                'epoch': epoch + 1,
                'train_loss': avg_train_loss,
                'train_accuracy': train_accuracy,
                'val_loss': avg_val_loss,
                'val_accuracy': val_accuracy
            })

        # Save training history
        history_path = self.output_dir / 'training_history.json'
        with open(history_path, 'w') as f:
            json.dump(training_history, f, indent=2)

        logger.info(f"\n{'='*80}")
        logger.info("TRAINING COMPLETE")
        logger.info(f"{'='*80}")
        logger.info(f"Best validation accuracy: {best_val_accuracy:.2%}")
        logger.info(f"Model saved to: {self.output_dir}")
        logger.info(f"Training history: {history_path}")

        return training_history

    def save_model(self, epoch: int, accuracy: float):
        """Save model checkpoint"""
        checkpoint_dir = self.output_dir / f'checkpoint_epoch{epoch}'
        checkpoint_dir.mkdir(parents=True, exist_ok=True)

        # Save model and tokenizer
        self.model.save_pretrained(checkpoint_dir)
        self.tokenizer.save_pretrained(checkpoint_dir)

        # Save metadata
        metadata = {
            'epoch': epoch,
            'accuracy': accuracy,
            'model_name': self.model_name,
            'num_labels': self.model.config.num_labels,
            'trained_at': datetime.now().isoformat()
        }

        with open(checkpoint_dir / 'metadata.json', 'w') as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"Checkpoint saved: {checkpoint_dir}")


def main():
    """Main training execution"""
    print("=" * 80)
    print("DISTILBERT DOCUMENT CLASSIFIER TRAINING")
    print("=" * 80)
    print(f"\nStarted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Configuration
    training_csv = '.ifmos/training_data.csv'
    output_dir = 'ifmos/models/distilbert'
    batch_size = 16
    num_epochs = 3

    # Check GPU
    if not torch.cuda.is_available():
        logger.warning("CUDA not available - training will be SLOW on CPU")
        logger.warning("Expected training time: 12-24 hours on CPU vs 2-4 hours on GPU")
        response = input("Continue with CPU training? (y/n): ")
        if response.lower() != 'y':
            sys.exit(0)

    # Initialize trainer
    trainer = DistilBERTTrainer(
        output_dir=output_dir,
        batch_size=batch_size,
        num_epochs=num_epochs
    )

    # Load training data
    file_paths, labels, label_to_id = trainer.load_training_data(training_csv)
    trainer.label_to_id = label_to_id
    trainer.id_to_label = {v: k for k, v in label_to_id.items()}

    # Create dataloaders
    train_loader, val_loader = trainer.create_dataloaders(
        file_paths,
        labels,
        label_to_id
    )

    # Train
    history = trainer.train(
        train_loader,
        val_loader,
        num_labels=len(label_to_id)
    )

    print("\n" + "=" * 80)
    print("TRAINING SUMMARY")
    print("=" * 80)
    print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Final validation accuracy: {history[-1]['val_accuracy']:.2%}")
    print(f"Model saved to: {output_dir}")
    print("=" * 80)


if __name__ == '__main__':
    main()
