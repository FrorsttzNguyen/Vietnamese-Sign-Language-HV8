from dataset.videoLoader import load_batch_video,get_selected_indexs,pad_array,pad_index
from dataset.dataset import build_dataset
import torch
from torch.utils.data import WeightedRandomSampler
from functools import partial
import random
import numpy as np
import os
import torchvision
import json
from utils.video_augmentation import DeleteFlowKeypoints,ToFloatTensor,Compose
import math
from transformers import AutoTokenizer
from PIL import Image
import random
import cv2
from collections import Counter



def vtn_pf_collate_fn_(batch):
    labels = torch.stack([s[2] for s in batch],dim = 0)
    clip = torch.stack([s[0] for s in batch],dim = 0) 
    poseflow = torch.stack([s[1] for s in batch],dim = 0) 
    return {'clip':clip,'poseflow':poseflow},labels


def gcn_bert_collate_fn_(batch):
    labels = torch.stack([s[1] for s in batch],dim = 0)
    keypoints = torch.stack([s[0] for s in batch],dim = 0) # bs t n c
   
    return {'keypoints':keypoints},labels


def three_viewpoints_collate_fn_(batch):
    center_video = torch.stack([s[0] for s in batch],dim = 0)
    left_video = torch.stack([s[1] for s in batch],dim = 0)
    right_video = torch.stack([s[2] for s in batch],dim = 0)
    labels = torch.stack([s[3] for s in batch],dim = 0)
    
    return {'left':left_video,'center':center_video,'right':right_video},labels

def i3d_collate_fn_(batch):
    clip = torch.stack([s[0] for s in batch],dim = 0)
    labels = torch.stack([s[1] for s in batch],dim = 0)
    
    return {'clip':clip},labels

def videomae_collate_fn_(batch):
    clip = torch.stack([s[0] for s in batch],dim = 0)
    mask = torch.stack([s[1] for s in batch],dim = 0)
    labels = torch.stack([s[2] for s in batch],dim = 0)
    return {'clip':clip,'mask':mask},labels

def swin_transformer_collate_fn_(batch):
    clip = torch.stack([s[0] for s in batch],dim = 0).permute(0,2,1,3,4) # b,t,c,h,w -> b,c,t,h,w
    labels = torch.stack([s[1] for s in batch],dim = 0)
    return {'clip':clip},labels

def mvit_transformer_collate_fn_(batch):
    clip = torch.stack([s[0] for s in batch],dim = 0).permute(0,2,1,3,4) # b,t,c,h,w -> b,c,t,h,w
    labels = torch.stack([s[1] for s in batch],dim = 0)
    return {'clip':clip},labels

def vtn_hc_pf_three_view_collate_fn_(batch):
    center_video = torch.stack([s[0] for s in batch],dim = 0)
    left_video = torch.stack([s[2] for s in batch],dim = 0)
    right_video = torch.stack([s[4] for s in batch],dim = 0)
    labels = torch.stack([s[6] for s in batch],dim = 0)

    center_pf = torch.stack([s[1] for s in batch],dim = 0)
    left_pf = torch.stack([s[3] for s in batch],dim = 0)
    right_pf = torch.stack([s[5] for s in batch],dim = 0)
    
    return {'left':left_video,'center':center_video,'right':right_video,'center_pf':center_pf,'left_pf':left_pf,'right_pf':right_pf},labels

def distilation_collate_fn_(batch):
    center_video = torch.stack([s[0] for s in batch],dim = 0)
    left_video = torch.stack([s[2] for s in batch],dim = 0)
    right_video = torch.stack([s[4] for s in batch],dim = 0)

    center_pf = torch.stack([s[1] for s in batch],dim = 0)
    left_pf = torch.stack([s[3] for s in batch],dim = 0)
    right_pf = torch.stack([s[5] for s in batch],dim = 0)

    center_clip_no_crop_hand = torch.stack([s[6] for s in batch],dim = 0)
    labels = torch.stack([s[7] for s in batch],dim = 0)
    
    return {'left':left_video,'center':center_video,'right':right_video,
            'center_pf':center_pf,'left_pf':left_pf,'right_pf':right_pf,
            'center_clip_no_crop_hand':center_clip_no_crop_hand
            },labels

def create_balanced_sampler(dataset, method='inverse'):
    """
    Create a balanced sampler for imbalanced datasets

    Args:
        dataset: dataset object with labels attribute or get_labels() method
        method: 'inverse' (1/count), 'sqrt_inverse' (1/sqrt(count)), 'effective'

    Returns:
        WeightedRandomSampler
    """
    # Get labels from dataset
    if hasattr(dataset, 'labels'):
        labels = dataset.labels
    elif hasattr(dataset, 'get_labels'):
        labels = dataset.get_labels()
    else:
        # Try to get from underlying data
        labels = [dataset[i][1] if isinstance(dataset[i][1], int) else dataset[i][1].item()
                  for i in range(len(dataset))]

    labels = np.array(labels)
    class_counts = Counter(labels)
    n_classes = len(class_counts)
    n_samples = len(labels)

    if method == 'inverse':
        class_weights = {cls: n_samples / (n_classes * count)
                         for cls, count in class_counts.items()}
    elif method == 'sqrt_inverse':
        class_weights = {cls: np.sqrt(n_samples / (n_classes * count))
                         for cls, count in class_counts.items()}
    elif method == 'effective':
        beta = 0.9999
        class_weights = {}
        for cls, count in class_counts.items():
            effective_num = (1 - beta**count) / (1 - beta)
            class_weights[cls] = 1.0 / effective_num
        total = sum(class_weights.values())
        class_weights = {k: v * n_classes / total for k, v in class_weights.items()}
    else:
        raise ValueError(f"Unknown method: {method}")

    sample_weights = torch.tensor([class_weights[label] for label in labels], dtype=torch.float64)

    sampler = WeightedRandomSampler(
        weights=sample_weights,
        num_samples=len(labels),
        replacement=True
    )

    print(f"[BalancedSampler] Created with method='{method}'")
    print(f"[BalancedSampler] Classes: {n_classes}, Samples: {n_samples}")
    print(f"[BalancedSampler] Min class weight: {min(class_weights.values()):.4f}, Max: {max(class_weights.values()):.4f}")

    return sampler


def build_dataloader(cfg, split, is_train=True, model = None,labels = None):
    dataset = build_dataset(cfg['data'], split,model,train_labels = labels)

    if cfg['data']['model_name'] == 'vtn_att_poseflow' or 'HandCrop' in cfg['data']['model_name'] or cfg['data']['model_name'] == 'VTNHCPF_OneView_Sim_Knowledge_Distilation_Inference':
        collate_func = vtn_pf_collate_fn_
    if cfg['data']['model_name'] == 'gcn_bert':
        collate_func = gcn_bert_collate_fn_

    distillation_models = ['MvitV2_OneView_Sim_Knowledge_Distillation','I3D_OneView_Sim_Knowledge_Distillation','VideoSwinTransformer_OneView_Sim_Knowledge_Distillation','MvitV2_OneView_KD_Knowledge_Distillation_Visual_Prompt_Tuning']

    if 'ThreeView' in cfg['data']['model_name'] or cfg['data']['model_name'] in distillation_models:
        collate_func = three_viewpoints_collate_fn_
    if cfg['data']['model_name'] == 'InceptionI3d' or cfg['data']['model_name'] == 'I3D_OneView_Sim_Knowledge_Distillation_Inference':
        collate_func = i3d_collate_fn_
    if cfg['data']['model_name'] == 'videomae':
        collate_func = videomae_collate_fn_
    if cfg['data']['model_name'] == 'swin_transformer' or cfg['data']['model_name'] == 'VideoSwinTransformer_OneView_Sim_Knowledge_Distillation_Inference':
        collate_func = swin_transformer_collate_fn_
    if 'mvit' in cfg['data']['model_name'] or cfg['data']['model_name'] == 'MvitV2_OneView_Sim_Knowledge_Distillation_Inference':
        collate_func = mvit_transformer_collate_fn_
    if cfg['data']['model_name']  == 'VTNHCPF_Three_view' or cfg['data']['model_name'] == 'VTNHCPF_OneView_Sim_Knowledge_Distilation' or cfg['data']['model_name'] == "VTNHCPF_Three_View_Visual_Prompt_Tuning":
        collate_func = vtn_hc_pf_three_view_collate_fn_

    # Check if balanced sampling is enabled
    use_balanced_sampling = cfg['training'].get('balanced_sampling', False)
    balanced_method = cfg['training'].get('balanced_method', 'inverse')

    sampler = None
    shuffle = is_train

    if is_train and use_balanced_sampling:
        sampler = create_balanced_sampler(dataset, method=balanced_method)
        shuffle = False  # Cannot use shuffle with sampler

    dataloader = torch.utils.data.DataLoader(dataset,
                                            collate_fn = collate_func,
                                            batch_size = cfg['training']['batch_size'],
                                            num_workers = cfg['training'].get('num_workers',2),
                                            shuffle = shuffle,
                                            prefetch_factor = cfg['training'].get('prefetch_factor',2),
                                            persistent_workers = True,
                                            sampler = sampler
                                            )
    return dataloader
