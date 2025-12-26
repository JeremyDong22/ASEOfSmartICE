#!/usr/bin/env python3
"""
Train YOLO11s Staff/Customer Detector - V5
Version: 1.0.0

Improved parameters based on Gemini suggestions:
- Higher imgsz (800)
- Lower hsv_h (0.003)
- Higher hsv_v (0.6)
- Grayscale augmentation (0.15)
- Random erasing (0.2)
- 2 classes: staff, customer

Created: 2025-12-26
"""

import os
from pathlib import Path
from ultralytics import YOLO
import torch

# =============================================================================
# Configuration
# =============================================================================

SCRIPT_DIR = Path(__file__).parent.absolute()
PROJECT_DIR = SCRIPT_DIR.parent

# Dataset
DATASET_YAML = PROJECT_DIR / "dataset_detection" / "data.yaml"

# Output
OUTPUT_DIR = PROJECT_DIR / "models_detection"
MODEL_NAME = "staff_customer_detector_v5"

# Base model - YOLO11s (small) for better accuracy
BASE_MODEL = "yolo11s.pt"

# Training config with Gemini's suggested improvements
TRAIN_CONFIG = {
    # Basic
    'epochs': 150,
    'imgsz': 800,           # Higher resolution (was 640)
    'batch': 12,            # Slightly smaller batch for larger images
    'patience': 20,         # Early stopping
    'workers': 8,

    # Optimizer
    'optimizer': 'SGD',
    'lr0': 0.01,
    'lrf': 0.01,
    'momentum': 0.937,
    'weight_decay': 0.0005,
    'warmup_epochs': 3,
    'warmup_momentum': 0.8,

    # Augmentation - Gemini's suggestions
    'hsv_h': 0.003,         # Lower (was 0.015) - restaurant lighting is consistent
    'hsv_s': 0.5,           # Moderate saturation
    'hsv_v': 0.6,           # Higher (was 0.4) - handle lighting variations
    'degrees': 0.0,         # No rotation - people are upright
    'translate': 0.1,       # 10% translation
    'scale': 0.4,           # Scale variation
    'shear': 0.0,           # No shear
    'perspective': 0.0,     # No perspective
    'flipud': 0.0,          # No vertical flip - people don't flip
    'fliplr': 0.5,          # Horizontal flip OK
    'bgr': 0.0,             # No BGR swap
    'mosaic': 1.0,          # Mosaic augmentation
    'mixup': 0.0,           # No mixup (Gemini suggestion)
    'copy_paste': 0.0,      # No copy-paste
    'erasing': 0.2,         # Random erasing (NEW - Gemini suggestion)
    'crop_fraction': 1.0,   # Full crop

    # Close mosaic in last epochs
    'close_mosaic': 15,     # Disable mosaic in last 15 epochs

    # Other
    'amp': True,            # Mixed precision
    'cache': True,          # Cache images
    'exist_ok': True,
    'plots': True,
    'save': True,
    'save_period': 25,      # Save checkpoint every 25 epochs
}

# =============================================================================
# Main
# =============================================================================

def main():
    print("\n" + "=" * 60)
    print("🚀 Training YOLO11s Staff/Customer Detector (V5)")
    print("=" * 60)

    # Check dataset
    if not DATASET_YAML.exists():
        print(f"❌ Dataset not found: {DATASET_YAML}")
        print("   Run 2_prepare_dataset.py first!")
        return

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Check device
    if torch.backends.mps.is_available():
        device = 'mps'
        print(f"\n✅ Using Apple Silicon GPU (MPS)")
    elif torch.cuda.is_available():
        device = 0
        print(f"\n✅ Using CUDA GPU")
    else:
        device = 'cpu'
        print(f"\n⚠️ Using CPU (slow!)")

    # Load base model
    print(f"\n📥 Loading base model: {BASE_MODEL}")
    model = YOLO(BASE_MODEL)

    # Print training config
    print(f"\n📋 Training Configuration:")
    print(f"   - Model: YOLO11s (small)")
    print(f"   - Image size: {TRAIN_CONFIG['imgsz']}x{TRAIN_CONFIG['imgsz']}")
    print(f"   - Epochs: {TRAIN_CONFIG['epochs']}")
    print(f"   - Batch size: {TRAIN_CONFIG['batch']}")
    print(f"   - Classes: 2 (staff, customer)")
    print(f"\n   Augmentation (Gemini optimized):")
    print(f"   - hsv_h: {TRAIN_CONFIG['hsv_h']} (lower for consistent lighting)")
    print(f"   - hsv_v: {TRAIN_CONFIG['hsv_v']} (higher for lighting variations)")
    print(f"   - erasing: {TRAIN_CONFIG['erasing']} (random erasing)")
    print(f"   - close_mosaic: {TRAIN_CONFIG['close_mosaic']}")

    # Start training
    print(f"\n🏋️ Starting training...")
    print("=" * 60)

    results = model.train(
        data=str(DATASET_YAML),
        project=str(OUTPUT_DIR),
        name=MODEL_NAME,
        device=device,
        **TRAIN_CONFIG
    )

    # Copy best model
    best_model_src = OUTPUT_DIR / MODEL_NAME / "weights" / "best.pt"
    best_model_dst = OUTPUT_DIR / "staff_customer_detector.pt"

    if best_model_src.exists():
        import shutil
        shutil.copy2(best_model_src, best_model_dst)
        print(f"\n✅ Best model saved to: {best_model_dst}")

        # Print model size
        size_mb = best_model_dst.stat().st_size / (1024 * 1024)
        print(f"   Model size: {size_mb:.1f} MB")

    print("\n" + "=" * 60)
    print("🎉 Training complete!")
    print("=" * 60)
    print(f"\n📁 Results: {OUTPUT_DIR / MODEL_NAME}")
    print(f"📊 Metrics: {OUTPUT_DIR / MODEL_NAME / 'results.csv'}")
    print(f"🏆 Best model: {best_model_dst}")

if __name__ == '__main__':
    main()
