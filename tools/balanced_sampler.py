"""
Balanced Sampler for handling imbalanced datasets
Provides WeightedRandomSampler and class-balanced batch sampler
"""

import torch
from torch.utils.data import WeightedRandomSampler, Sampler
import numpy as np
from collections import Counter
import pandas as pd


def get_sample_weights(labels, method='inverse'):
    """
    Calculate sample weights for WeightedRandomSampler

    Args:
        labels: list or array of class labels
        method: 'inverse' (1/count), 'sqrt_inverse' (1/sqrt(count)), 'effective' (effective number)

    Returns:
        sample_weights: tensor of weights for each sample
        class_weights: dict of weights for each class
    """
    labels = np.array(labels)
    class_counts = Counter(labels)
    n_classes = len(class_counts)
    n_samples = len(labels)

    if method == 'inverse':
        # Simple inverse frequency
        class_weights = {cls: n_samples / (n_classes * count)
                         for cls, count in class_counts.items()}

    elif method == 'sqrt_inverse':
        # Square root inverse (less aggressive)
        class_weights = {cls: np.sqrt(n_samples / (n_classes * count))
                         for cls, count in class_counts.items()}

    elif method == 'effective':
        # Effective number of samples (from "Class-Balanced Loss" paper)
        beta = 0.9999
        class_weights = {}
        for cls, count in class_counts.items():
            effective_num = (1 - beta**count) / (1 - beta)
            class_weights[cls] = 1.0 / effective_num

        # Normalize
        total = sum(class_weights.values())
        class_weights = {k: v * n_classes / total for k, v in class_weights.items()}

    else:
        raise ValueError(f"Unknown method: {method}")

    # Create sample weights
    sample_weights = torch.tensor([class_weights[label] for label in labels], dtype=torch.float64)

    return sample_weights, class_weights


def create_balanced_sampler(labels, num_samples=None, replacement=True, method='inverse'):
    """
    Create a WeightedRandomSampler for balanced sampling

    Args:
        labels: list or array of class labels
        num_samples: number of samples to draw (default: len(labels))
        replacement: sample with replacement (default: True)
        method: weighting method

    Returns:
        WeightedRandomSampler
    """
    sample_weights, class_weights = get_sample_weights(labels, method)

    if num_samples is None:
        num_samples = len(labels)

    sampler = WeightedRandomSampler(
        weights=sample_weights,
        num_samples=num_samples,
        replacement=replacement
    )

    return sampler, class_weights


class BalancedBatchSampler(Sampler):
    """
    Batch sampler that ensures each batch has balanced class distribution
    Each batch contains samples from all classes (or as many as possible)
    """

    def __init__(self, labels, batch_size, drop_last=False):
        self.labels = np.array(labels)
        self.batch_size = batch_size
        self.drop_last = drop_last

        # Group indices by class
        self.class_indices = {}
        for idx, label in enumerate(self.labels):
            if label not in self.class_indices:
                self.class_indices[label] = []
            self.class_indices[label].append(idx)

        self.n_classes = len(self.class_indices)
        self.samples_per_class = max(1, batch_size // self.n_classes)

    def __iter__(self):
        # Shuffle indices within each class
        class_indices_shuffled = {
            cls: np.random.permutation(indices).tolist()
            for cls, indices in self.class_indices.items()
        }

        # Track position in each class
        class_positions = {cls: 0 for cls in self.class_indices}

        # Generate batches
        batches = []
        while True:
            batch = []
            classes = list(self.class_indices.keys())
            np.random.shuffle(classes)

            for cls in classes:
                pos = class_positions[cls]
                indices = class_indices_shuffled[cls]

                # Get samples from this class
                for _ in range(self.samples_per_class):
                    if pos >= len(indices):
                        # Reshuffle and reset
                        class_indices_shuffled[cls] = np.random.permutation(
                            self.class_indices[cls]).tolist()
                        pos = 0
                    batch.append(indices[pos])
                    pos += 1

                class_positions[cls] = pos

                if len(batch) >= self.batch_size:
                    break

            if len(batch) >= self.batch_size:
                batches.append(batch[:self.batch_size])
            elif not self.drop_last and len(batch) > 0:
                batches.append(batch)

            # Stop condition: processed enough samples
            total_sampled = sum(len(b) for b in batches)
            if total_sampled >= len(self.labels):
                break

        for batch in batches:
            yield batch

    def __len__(self):
        if self.drop_last:
            return len(self.labels) // self.batch_size
        return (len(self.labels) + self.batch_size - 1) // self.batch_size


def get_class_weights_for_loss(labels, method='inverse', device='cuda'):
    """
    Get class weights for weighted loss function (e.g., CrossEntropyLoss)

    Args:
        labels: list or array of class labels
        method: weighting method
        device: torch device

    Returns:
        weights tensor for loss function
    """
    _, class_weights = get_sample_weights(labels, method)

    # Convert to tensor (sorted by class index)
    max_class = max(class_weights.keys()) + 1
    weights = torch.ones(max_class, dtype=torch.float32)

    for cls, weight in class_weights.items():
        weights[cls] = weight

    return weights.to(device)


# Example usage and testing
if __name__ == '__main__':
    # Test with sample data
    labels = [0] * 100 + [1] * 20 + [2] * 5  # Imbalanced: 100, 20, 5

    print("=== Testing Balanced Sampler ===\n")
    print(f"Original distribution: {Counter(labels)}")

    # Create sampler
    sampler, class_weights = create_balanced_sampler(labels, method='inverse')
    print(f"\nClass weights (inverse): {class_weights}")

    # Sample and check distribution
    sampled_indices = list(sampler)
    sampled_labels = [labels[i] for i in sampled_indices]
    print(f"Sampled distribution: {Counter(sampled_labels)}")

    # Test class weights for loss
    loss_weights = get_class_weights_for_loss(labels, device='cpu')
    print(f"\nLoss weights: {loss_weights}")
