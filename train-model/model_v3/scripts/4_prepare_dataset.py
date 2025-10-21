#!/usr/bin/env python3
# Version: 3.0 - YOLO Classification Format
# Prepare YOLO classification dataset from manually labeled images
# Creates train/val split with class-based folder structure (no label files needed)

import os
import shutil
from pathlib import Path
import random

# Paths
LABELED_DIR = "../labeled-persons"
DATASET_DIR = "../dataset"
TRAIN_RATIO = 0.8  # 80% for training, 20% for validation

# Classes
CLASSES = ['waiter', 'customer']

def prepare_classification_dataset():
    """Prepare YOLO classification dataset from manually labeled images"""
    print("🚀 Preparing YOLO Classification dataset from labeled images...")
    print("📝 Format: ImageFolder structure (no label files needed)")

    # Create dataset structure for YOLO classification
    # Structure: dataset/train/waiter/, dataset/train/customer/, etc.
    train_dir = os.path.join(DATASET_DIR, "train")
    val_dir = os.path.join(DATASET_DIR, "val")

    for split_dir in [train_dir, val_dir]:
        for class_name in CLASSES:
            class_dir = os.path.join(split_dir, class_name)
            os.makedirs(class_dir, exist_ok=True)

    # Collect all labeled images by class
    all_data = {}

    for class_name in CLASSES:
        class_dir = Path(LABELED_DIR) / f"{class_name}s"  # waiters, customers

        if not class_dir.exists():
            print(f"❌ {class_name.capitalize()} directory not found: {class_dir}")
            print("📝 Please run 3_label_images.py first to label your images")
            return

        # Collect all images (recursively search subdirectories like camera_22, camera_35)
        images = list(class_dir.glob("**/*.jpg")) + list(class_dir.glob("**/*.png"))
        all_data[class_name] = images
        print(f"✅ Found {len(images)} {class_name} images")

    if not any(all_data.values()):
        print("❌ No labeled images found in any class directory")
        return

    # Shuffle and split each class independently to maintain class balance
    print(f"\n📊 Creating train/val split ({int(TRAIN_RATIO*100)}/{int((1-TRAIN_RATIO)*100)})...")

    stats = {
        'train': {},
        'val': {}
    }

    for class_name, images in all_data.items():
        # Shuffle images
        random.shuffle(images)

        # Split
        split_idx = int(len(images) * TRAIN_RATIO)
        train_images = images[:split_idx]
        val_images = images[split_idx:]

        # Copy training images
        train_class_dir = os.path.join(train_dir, class_name)
        for i, img_path in enumerate(train_images):
            dest_name = f"train_{class_name}_{i:05d}{img_path.suffix}"
            dest_path = os.path.join(train_class_dir, dest_name)
            shutil.copy2(img_path, dest_path)

        # Copy validation images
        val_class_dir = os.path.join(val_dir, class_name)
        for i, img_path in enumerate(val_images):
            dest_name = f"val_{class_name}_{i:05d}{img_path.suffix}"
            dest_path = os.path.join(val_class_dir, dest_name)
            shutil.copy2(img_path, dest_path)

        # Save stats
        stats['train'][class_name] = len(train_images)
        stats['val'][class_name] = len(val_images)

        print(f"   {class_name.capitalize()}: {len(train_images)} train, {len(val_images)} val")

    # Calculate totals
    total_train = sum(stats['train'].values())
    total_val = sum(stats['val'].values())

    # Create data.yaml for YOLO classification training
    yaml_content = f"""# Restaurant Staff Classification Dataset (YOLO Classification Format)
# This is a classification task - folder structure defines classes, no label files needed
path: {os.path.abspath(DATASET_DIR)}
train: train
val: val

# Classes (MUST match alphabetical folder order: customer, waiter)
names:
  0: customer
  1: waiter

# Dataset statistics
train_samples: {total_train}
val_samples: {total_val}
train_waiters: {stats['train']['waiter']}
train_customers: {stats['train']['customer']}
val_waiters: {stats['val']['waiter']}
val_customers: {stats['val']['customer']}
"""

    yaml_path = os.path.join(DATASET_DIR, "data.yaml")
    with open(yaml_path, 'w') as f:
        f.write(yaml_content)

    print(f"\n✅ Classification dataset prepared successfully!")
    print(f"\n📊 Final Statistics:")
    print(f"   Total images: {total_train + total_val}")
    print(f"   Training: {total_train} ({stats['train']['waiter']} waiters, {stats['train']['customer']} customers)")
    print(f"   Validation: {total_val} ({stats['val']['waiter']} waiters, {stats['val']['customer']} customers)")
    print(f"\n📁 Dataset structure:")
    print(f"   {DATASET_DIR}/")
    print(f"   ├── train/")
    print(f"   │   ├── waiter/     ({stats['train']['waiter']} images)")
    print(f"   │   └── customer/   ({stats['train']['customer']} images)")
    print(f"   └── val/")
    print(f"       ├── waiter/     ({stats['val']['waiter']} images)")
    print(f"       └── customer/   ({stats['val']['customer']} images)")
    print(f"\n📄 Config file: {yaml_path}")
    print("\n🎯 Ready for YOLO classification training!")
    print("   Next: Run 5_train_model.py")

if __name__ == "__main__":
    try:
        # Set random seed for reproducibility
        random.seed(42)

        prepare_classification_dataset()
        os.system('say "Classification dataset preparation completed successfully"')
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        os.system('say "Dataset preparation failed with error"')
        raise
