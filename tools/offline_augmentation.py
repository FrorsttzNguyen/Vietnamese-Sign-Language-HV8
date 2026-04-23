"""
Offline Data Augmentation for Vietnamese Sign Language Videos
Generates augmented samples for minority classes
"""

import os
import cv2
import numpy as np
import pandas as pd
import random
import argparse
from pathlib import Path
from tqdm import tqdm
import shutil


class VideoAugmentor:
    """Video augmentation class with multiple augmentation techniques"""

    def __init__(self, prob=0.5):
        self.prob = prob

    def augment(self, frames, aug_types=None):
        """
        Apply random augmentations to video frames

        Args:
            frames: list of numpy arrays (H, W, C)
            aug_types: list of augmentation types to apply, or None for random

        Returns:
            augmented frames
        """
        if aug_types is None:
            aug_types = random.sample(
                ['brightness', 'contrast', 'blur', 'noise', 'crop', 'time_warp'],
                k=random.randint(1, 3)
            )

        frames = [f.copy() for f in frames]

        for aug_type in aug_types:
            if aug_type == 'brightness' and random.random() < self.prob:
                frames = self.adjust_brightness(frames)
            elif aug_type == 'contrast' and random.random() < self.prob:
                frames = self.adjust_contrast(frames)
            elif aug_type == 'blur' and random.random() < self.prob:
                frames = self.gaussian_blur(frames)
            elif aug_type == 'noise' and random.random() < self.prob:
                frames = self.add_noise(frames)
            elif aug_type == 'crop' and random.random() < self.prob:
                frames = self.random_crop(frames)
            elif aug_type == 'time_warp' and random.random() < self.prob:
                frames = self.time_warp(frames)

        return frames

    def adjust_brightness(self, frames, delta_range=(-30, 30)):
        """Adjust brightness of all frames"""
        delta = random.randint(*delta_range)
        return [np.clip(f.astype(np.int16) + delta, 0, 255).astype(np.uint8) for f in frames]

    def adjust_contrast(self, frames, alpha_range=(0.8, 1.2)):
        """Adjust contrast of all frames"""
        alpha = random.uniform(*alpha_range)
        return [np.clip(alpha * f, 0, 255).astype(np.uint8) for f in frames]

    def gaussian_blur(self, frames, kernel_range=(3, 7)):
        """Apply Gaussian blur"""
        kernel_size = random.choice(range(kernel_range[0], kernel_range[1] + 1, 2))
        return [cv2.GaussianBlur(f, (kernel_size, kernel_size), 0) for f in frames]

    def add_noise(self, frames, noise_level=10):
        """Add Gaussian noise"""
        augmented = []
        for f in frames:
            noise = np.random.normal(0, noise_level, f.shape).astype(np.int16)
            augmented.append(np.clip(f.astype(np.int16) + noise, 0, 255).astype(np.uint8))
        return augmented

    def random_crop(self, frames, scale_range=(0.85, 0.95)):
        """Random crop and resize back"""
        if len(frames) == 0:
            return frames

        h, w = frames[0].shape[:2]
        scale = random.uniform(*scale_range)
        new_h, new_w = int(h * scale), int(w * scale)

        top = random.randint(0, h - new_h)
        left = random.randint(0, w - new_w)

        augmented = []
        for f in frames:
            cropped = f[top:top + new_h, left:left + new_w]
            resized = cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)
            augmented.append(resized)

        return augmented

    def time_warp(self, frames, warp_range=(0.8, 1.2)):
        """Temporal warping - speed up or slow down"""
        if len(frames) < 4:
            return frames

        speed = random.uniform(*warp_range)
        n_frames = len(frames)
        new_n_frames = int(n_frames / speed)

        # Create new indices
        new_indices = np.linspace(0, n_frames - 1, new_n_frames).astype(int)
        return [frames[i] for i in new_indices]


def load_video_frames(video_dir, video_name):
    """
    Load video frames from directory

    Args:
        video_dir: base directory containing video folders
        video_name: name of the video (folder name or video file)

    Returns:
        list of frames as numpy arrays
    """
    video_path = os.path.join(video_dir, video_name)

    if os.path.isdir(video_path):
        # Frames stored as images in folder
        frame_files = sorted([f for f in os.listdir(video_path)
                              if f.endswith(('.jpg', '.png', '.jpeg'))])
        frames = []
        for ff in frame_files:
            img = cv2.imread(os.path.join(video_path, ff))
            if img is not None:
                frames.append(img)
        return frames

    elif os.path.isfile(video_path + '.mp4') or os.path.isfile(video_path + '.avi'):
        # Video file
        ext = '.mp4' if os.path.isfile(video_path + '.mp4') else '.avi'
        cap = cv2.VideoCapture(video_path + ext)
        frames = []
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frames.append(frame)
        cap.release()
        return frames

    else:
        print(f"Warning: Could not find video: {video_name}")
        return []


def save_video_frames(frames, output_dir, video_name):
    """Save frames to directory"""
    video_path = os.path.join(output_dir, video_name)
    os.makedirs(video_path, exist_ok=True)

    for i, frame in enumerate(frames):
        cv2.imwrite(os.path.join(video_path, f'{i:04d}.jpg'), frame)


def augment_minority_classes(
        data_dir,
        data_type='200',
        target_samples=30,
        output_dir=None,
        video_dir=None
):
    """
    Generate augmented samples for minority classes

    Args:
        data_dir: directory containing CSV files
        data_type: data type (50, 100, 200)
        target_samples: target number of samples per class
        output_dir: output directory for augmented data
        video_dir: directory containing video data
    """
    if output_dir is None:
        output_dir = os.path.join(data_dir, f'my_data_{data_type}_augmented')

    if video_dir is None:
        video_dir = os.path.join(data_dir, 'my_data')

    os.makedirs(output_dir, exist_ok=True)

    # Load training data
    train_csv = os.path.join(data_dir, f'my_data_{data_type}', f'train_{data_type}.csv')
    train_df = pd.read_csv(train_csv)

    print(f"=== Offline Augmentation for my_data_{data_type} ===")
    print(f"Original samples: {len(train_df)}")
    print(f"Target samples per class: {target_samples}")
    print(f"Video directory: {video_dir}")
    print(f"Output directory: {output_dir}")

    # Find minority classes
    label_counts = train_df['label'].value_counts()
    minority_classes = label_counts[label_counts < target_samples]

    print(f"\nMinority classes (< {target_samples} samples): {len(minority_classes)}")

    # Initialize augmentor
    augmentor = VideoAugmentor(prob=0.7)

    # Track new samples
    new_samples = []

    for label in tqdm(minority_classes.index, desc="Augmenting classes"):
        current_count = label_counts[label]
        samples_to_generate = target_samples - current_count

        # Get samples from this class
        class_samples = train_df[train_df['label'] == label]

        for i in range(samples_to_generate):
            # Randomly select a sample to augment
            sample = class_samples.sample(1).iloc[0]
            original_name = sample['name']

            # Load video frames
            frames = load_video_frames(video_dir, original_name)

            if len(frames) == 0:
                continue

            # Apply augmentation
            aug_frames = augmentor.augment(frames)

            # Generate new name
            new_name = f"{original_name}_aug{i}"

            # Save augmented frames
            save_video_frames(aug_frames, output_dir, new_name)

            # Create new sample entry
            new_sample = sample.copy()
            new_sample['name'] = new_name
            new_sample['NOTE'] = f'augmented_from_{original_name}'
            new_samples.append(new_sample)

    # Create augmented CSV
    if len(new_samples) > 0:
        new_samples_df = pd.DataFrame(new_samples)
        augmented_train_df = pd.concat([train_df, new_samples_df], ignore_index=True)

        # Save augmented CSV
        output_csv = os.path.join(output_dir, f'train_{data_type}_augmented.csv')
        augmented_train_df.to_csv(output_csv, index=False)

        print(f"\n=== Augmentation Complete ===")
        print(f"Original samples: {len(train_df)}")
        print(f"New augmented samples: {len(new_samples)}")
        print(f"Total samples: {len(augmented_train_df)}")
        print(f"Augmented CSV saved to: {output_csv}")

        # Verify new distribution
        new_counts = augmented_train_df['label'].value_counts()
        print(f"\nNew distribution:")
        print(f"  Min samples/class: {new_counts.min()}")
        print(f"  Max samples/class: {new_counts.max()}")
        print(f"  Mean samples/class: {new_counts.mean():.2f}")

    else:
        print("\nNo augmentation performed (no video frames found)")


def copy_augmented_frames_to_my_data(augmented_dir, target_dir):
    """
    Copy augmented frames back to my_data directory for training
    """
    if not os.path.exists(augmented_dir):
        print(f"Error: {augmented_dir} does not exist")
        return

    print(f"Copying augmented data from {augmented_dir} to {target_dir}")

    for folder in tqdm(os.listdir(augmented_dir)):
        if folder.endswith('.csv'):
            continue

        src = os.path.join(augmented_dir, folder)
        dst = os.path.join(target_dir, folder)

        if os.path.isdir(src) and not os.path.exists(dst):
            shutil.copytree(src, dst)

    print("Done!")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data_dir', default='data', help='Data directory')
    parser.add_argument('--data_type', default='200', help='Data type')
    parser.add_argument('--target_samples', type=int, default=30,
                        help='Target samples per minority class')
    parser.add_argument('--video_dir', default=None, help='Video directory')
    parser.add_argument('--output_dir', default=None, help='Output directory')
    args = parser.parse_args()

    augment_minority_classes(
        data_dir=args.data_dir,
        data_type=args.data_type,
        target_samples=args.target_samples,
        video_dir=args.video_dir,
        output_dir=args.output_dir
    )
