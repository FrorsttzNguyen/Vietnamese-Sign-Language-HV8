"""
Data Analysis Tool for Vietnamese Sign Language Dataset
Analyzes class distribution and identifies minority classes for augmentation
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import argparse

def analyze_distribution(data_dir, data_type='200', output_dir='analysis_output'):
    """Analyze data distribution and generate report"""

    os.makedirs(output_dir, exist_ok=True)

    # Load data
    train = pd.read_csv(f'{data_dir}/my_data_{data_type}/train_{data_type}.csv')
    val = pd.read_csv(f'{data_dir}/my_data_{data_type}/val_{data_type}.csv')
    test = pd.read_csv(f'{data_dir}/my_data_{data_type}/test_{data_type}.csv')

    print(f"=== DATA DISTRIBUTION ANALYSIS (my_data_{data_type}) ===\n")
    print(f"Train: {len(train)}, Val: {len(val)}, Test: {len(test)}")
    print(f"Total: {len(train) + len(val) + len(test)}\n")

    # Training distribution
    label_counts = train['label'].value_counts().sort_index()
    gloss_map = train.groupby('label')['GLOSS'].first().to_dict()

    # Statistics
    stats = {
        'num_classes': len(label_counts),
        'total_samples': len(train),
        'max_samples': label_counts.max(),
        'min_samples': label_counts.min(),
        'mean_samples': label_counts.mean(),
        'median_samples': label_counts.median(),
        'std_samples': label_counts.std(),
        'imbalance_ratio': label_counts.max() / label_counts.min()
    }

    print("Statistics:")
    for k, v in stats.items():
        print(f"  {k}: {v:.2f}" if isinstance(v, float) else f"  {k}: {v}")

    # Categorize classes
    minority_threshold = 30
    minority = label_counts[label_counts < minority_threshold]
    balanced = label_counts[(label_counts >= minority_threshold) & (label_counts < 100)]
    majority = label_counts[label_counts >= 100]

    print(f"\nClass Categories:")
    print(f"  Minority (< {minority_threshold} samples): {len(minority)} classes")
    print(f"  Balanced (30-100 samples): {len(balanced)} classes")
    print(f"  Majority (>= 100 samples): {len(majority)} classes")

    # Generate augmentation plan
    target_samples = 30
    augment_plan = []

    for label, count in minority.items():
        need = target_samples - count
        augment_plan.append({
            'label': label,
            'gloss': gloss_map.get(label, 'N/A'),
            'current_samples': count,
            'target_samples': target_samples,
            'samples_to_generate': need
        })

    augment_df = pd.DataFrame(augment_plan)
    augment_df = augment_df.sort_values('current_samples')

    # Save augmentation plan
    augment_df.to_csv(f'{output_dir}/augmentation_plan_{data_type}.csv', index=False)
    print(f"\nAugmentation plan saved to: {output_dir}/augmentation_plan_{data_type}.csv")
    print(f"Total samples to generate: {augment_df['samples_to_generate'].sum()}")

    # Plot distribution
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Histogram
    axes[0].hist(label_counts.values, bins=30, edgecolor='black', alpha=0.7)
    axes[0].axvline(x=minority_threshold, color='r', linestyle='--', label=f'Threshold={minority_threshold}')
    axes[0].set_xlabel('Samples per Class')
    axes[0].set_ylabel('Number of Classes')
    axes[0].set_title('Distribution of Samples per Class')
    axes[0].legend()

    # Bar chart (sorted)
    sorted_counts = label_counts.sort_values()
    colors = ['red' if c < minority_threshold else 'orange' if c < 100 else 'green' for c in sorted_counts.values]
    axes[1].bar(range(len(sorted_counts)), sorted_counts.values, color=colors, alpha=0.7)
    axes[1].axhline(y=minority_threshold, color='r', linestyle='--', label=f'Threshold={minority_threshold}')
    axes[1].set_xlabel('Class Index (sorted)')
    axes[1].set_ylabel('Number of Samples')
    axes[1].set_title('Samples per Class (Sorted)')
    axes[1].legend()

    plt.tight_layout()
    plt.savefig(f'{output_dir}/distribution_{data_type}.png', dpi=150)
    print(f"Distribution plot saved to: {output_dir}/distribution_{data_type}.png")

    # Save full report
    report_df = pd.DataFrame({
        'label': label_counts.index,
        'count': label_counts.values,
        'gloss': [gloss_map.get(l, 'N/A') for l in label_counts.index],
        'category': ['minority' if c < minority_threshold else 'balanced' if c < 100 else 'majority'
                     for c in label_counts.values]
    })
    report_df.to_csv(f'{output_dir}/full_report_{data_type}.csv', index=False)
    print(f"Full report saved to: {output_dir}/full_report_{data_type}.csv")

    return augment_df, stats


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data_dir', default='data', help='Data directory')
    parser.add_argument('--data_type', default='200', help='Data type (50, 100, 200)')
    parser.add_argument('--output_dir', default='analysis_output', help='Output directory')
    args = parser.parse_args()

    analyze_distribution(args.data_dir, args.data_type, args.output_dir)
