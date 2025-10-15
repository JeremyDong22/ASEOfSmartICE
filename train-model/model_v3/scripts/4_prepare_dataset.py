#!/usr/bin/env python3
# Version: 2.0
# Prepare YOLO training dataset from manually labeled images
# Creates train/val split and YOLO format labels

import os
import shutil
from pathlib import Path
import random
import cv2

# Paths
LABELED_DIR = "../labeled-persons"
DATASET_DIR = "../dataset"
TRAIN_RATIO = 0.8  # 80% for training, 20% for validation

# Class mapping
CLASS_NAMES = {
    'waiter': 0,
    'customer': 1
}

def create_yolo_label(image_path, class_id):
    """Create YOLO format label file"""
    # For person detection, use full image as bounding box
    # Format: class_id x_center y_center width height (all normalized 0-1)
    return f"{class_id} 0.5 0.5 1.0 1.0\n"

def prepare_dataset():
    """Prepare dataset from manually labeled images"""
    print("🚀 Preparing YOLO training dataset from labeled images...")

    # Create dataset structure
    train_img_dir = os.path.join(DATASET_DIR, "images", "train")
    val_img_dir = os.path.join(DATASET_DIR, "images", "val")
    train_lbl_dir = os.path.join(DATASET_DIR, "labels", "train")
    val_lbl_dir = os.path.join(DATASET_DIR, "labels", "val")

    for dir_path in [train_img_dir, val_img_dir, train_lbl_dir, val_lbl_dir]:
        os.makedirs(dir_path, exist_ok=True)

    # Collect all labeled images
    all_data = []

    # Check for labeled directories
    waiter_dir = Path(LABELED_DIR) / "waiters"
    customer_dir = Path(LABELED_DIR) / "customers"

    if not waiter_dir.exists() or not customer_dir.exists():
        print("❌ No labeled data found!")
        print(f"   Expected directories:")
        print(f"   - {waiter_dir}")
        print(f"   - {customer_dir}")
        print("\n📝 Please run 3_label_images.py first to label your images")
        return

    # Collect waiter images (recursively search subdirectories)
    waiter_images = list(waiter_dir.glob("**/*.jpg")) + list(waiter_dir.glob("**/*.png"))
    for img_path in waiter_images:
        all_data.append((img_path, CLASS_NAMES['waiter'], 'waiter'))
    print(f"✅ Found {len(waiter_images)} waiter images")

    # Collect customer images (recursively search subdirectories)
    customer_images = list(customer_dir.glob("**/*.jpg")) + list(customer_dir.glob("**/*.png"))
    for img_path in customer_images:
        all_data.append((img_path, CLASS_NAMES['customer'], 'customer'))
    print(f"✅ Found {len(customer_images)} customer images")

    if not all_data:
        print("❌ No labeled images found in directories")
        return
    
    # Shuffle and split data
    random.shuffle(all_data)
    split_idx = int(len(all_data) * TRAIN_RATIO)
    train_data = all_data[:split_idx]
    val_data = all_data[split_idx:]
    
    print(f"\n📊 Dataset split:")
    print(f"   Training: {len(train_data)} images")
    print(f"   Validation: {len(val_data)} images")
    
    # Copy images and create labels
    def process_split(data, img_dir, lbl_dir, split_name):
        waiter_count = 0
        customer_count = 0
        
        for i, (img_path, class_id, class_name) in enumerate(data):
            # New filename
            new_name = f"{split_name}_{i:05d}.jpg"
            
            # Copy image
            dest_img = os.path.join(img_dir, new_name)
            shutil.copy2(img_path, dest_img)
            
            # Create label
            label_content = create_yolo_label(dest_img, class_id)
            label_path = os.path.join(lbl_dir, new_name.replace('.jpg', '.txt'))
            with open(label_path, 'w') as f:
                f.write(label_content)
            
            # Count classes
            if class_name == 'waiter':
                waiter_count += 1
            else:
                customer_count += 1
        
        return waiter_count, customer_count
    
    # Process training set
    print("\n📝 Creating training set...")
    train_w, train_c = process_split(train_data, train_img_dir, train_lbl_dir, "train")
    
    # Process validation set
    print("📝 Creating validation set...")
    val_w, val_c = process_split(val_data, val_img_dir, val_lbl_dir, "val")
    
    # Create data.yaml for YOLO training
    yaml_content = f"""# Restaurant Staff Detection Dataset
path: {os.path.abspath(DATASET_DIR)}
train: images/train
val: images/val

# Classes
nc: 2
names: ['waiter', 'customer']

# Dataset info
train_samples: {len(train_data)}
val_samples: {len(val_data)}
train_waiters: {train_w}
train_customers: {train_c}
val_waiters: {val_w}
val_customers: {val_c}
"""
    
    yaml_path = os.path.join(DATASET_DIR, "data.yaml")
    with open(yaml_path, 'w') as f:
        f.write(yaml_content)
    
    print(f"\n✅ Dataset prepared successfully!")
    print(f"📊 Class distribution:")
    print(f"   Training: {train_w} waiters, {train_c} customers")
    print(f"   Validation: {val_w} waiters, {val_c} customers")
    print(f"📁 Dataset location: {DATASET_DIR}")
    print(f"📄 Config file: {yaml_path}")
    print("\n🎯 Ready for training! Run: 5_train_model.py")

if __name__ == "__main__":
    try:
        prepare_dataset()
        os.system('say "Dataset preparation completed successfully"')
    except Exception as e:
        print(f"\n❌ Error: {e}")
        os.system('say "Dataset preparation failed with error"')
        raise