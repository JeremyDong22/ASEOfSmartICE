#!/usr/bin/env python3
# Version: 5.0 (Model V4 - One-Step Staff Detection)
# Prepare YOLO detection dataset from bounding box labels
# Converts SQLite database labels to YOLO detection format
# Format: class_id center_x center_y width height (normalized 0-1)

import os
import sqlite3
import shutil
import cv2
import random
from pathlib import Path

# Paths
LABELED_DIR = "../labeled_staff_bboxes"
INPUT_DIR = "../filtered_images_with_people"
DATASET_DIR = "../dataset_detection"
DB_PATH = f"{LABELED_DIR}/labels.db"
TRAIN_RATIO = 0.8  # 80% train, 20% validation

def convert_to_yolo_format(bbox, img_width, img_height):
    """
    Convert absolute bbox coordinates to YOLO format (normalized)
    YOLO format: class_id center_x center_y width height (all normalized 0-1)
    """
    x, y, width, height = bbox

    # Calculate center
    center_x = x + width / 2
    center_y = y + height / 2

    # Normalize to 0-1
    center_x_norm = center_x / img_width
    center_y_norm = center_y / img_height
    width_norm = width / img_width
    height_norm = height / img_height

    # Class ID: 0 = staff (single class)
    return f"0 {center_x_norm:.6f} {center_y_norm:.6f} {width_norm:.6f} {height_norm:.6f}"

def prepare_detection_dataset():
    """Prepare YOLO detection dataset from labeled bounding boxes"""
    print("🚀 Preparing YOLO Detection dataset from bounding box labels...")
    print("📝 Format: YOLO detection (class_id center_x center_y width height)")
    print("=" * 70)

    # Check if database exists
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found: {DB_PATH}")
        print("   Please run 3_label_staff_bboxes.py first")
        return

    # Connect to database
    db_conn = sqlite3.connect(DB_PATH)
    cursor = db_conn.cursor()

    # Get all labeled images
    cursor.execute('''
        SELECT id, image_path FROM images WHERE labeled = 1
    ''')
    labeled_images = cursor.fetchall()

    if not labeled_images:
        print("❌ No labeled images found in database")
        print("   Please run 3_label_staff_bboxes.py to label images")
        db_conn.close()
        return

    print(f"✅ Found {len(labeled_images)} labeled images")

    # Create dataset structure
    train_img_dir = Path(DATASET_DIR) / "images" / "train"
    train_lbl_dir = Path(DATASET_DIR) / "labels" / "train"
    val_img_dir = Path(DATASET_DIR) / "images" / "val"
    val_lbl_dir = Path(DATASET_DIR) / "labels" / "val"

    for dir_path in [train_img_dir, train_lbl_dir, val_img_dir, val_lbl_dir]:
        dir_path.mkdir(parents=True, exist_ok=True)

    # Shuffle and split
    random.shuffle(labeled_images)
    split_idx = int(len(labeled_images) * TRAIN_RATIO)
    train_images = labeled_images[:split_idx]
    val_images = labeled_images[split_idx:]

    print(f"\n📊 Dataset split:")
    print(f"   Training:   {len(train_images)} images")
    print(f"   Validation: {len(val_images)} images")

    # Statistics
    stats = {
        'train': {'images': 0, 'images_with_staff': 0, 'total_bboxes': 0},
        'val': {'images': 0, 'images_with_staff': 0, 'total_bboxes': 0}
    }

    def process_split(images, split_name, img_dir, lbl_dir):
        """Process a dataset split (train or val)"""
        print(f"\n🔄 Processing {split_name} split...")

        for idx, (image_id, image_path) in enumerate(images):
            # Get bounding boxes for this image
            cursor.execute('''
                SELECT x, y, width, height FROM bboxes WHERE image_id = ?
            ''', (image_id,))
            bboxes = cursor.fetchall()

            # Read image to get dimensions
            img_full_path = os.path.join(INPUT_DIR, image_path)
            img = cv2.imread(img_full_path)
            if img is None:
                print(f"   ⚠️  Warning: Could not read {image_path}, skipping")
                continue

            img_height, img_width = img.shape[:2]

            # Generate unique filename
            filename = f"{split_name}_{idx:05d}{Path(image_path).suffix}"
            label_filename = f"{split_name}_{idx:05d}.txt"

            # Copy image
            dest_img_path = img_dir / filename
            shutil.copy2(img_full_path, dest_img_path)

            # Create label file
            label_path = lbl_dir / label_filename
            with open(label_path, 'w') as f:
                if bboxes:
                    for bbox in bboxes:
                        yolo_line = convert_to_yolo_format(bbox, img_width, img_height)
                        f.write(yolo_line + '\n')

            # Update statistics
            stats[split_name]['images'] += 1
            if bboxes:
                stats[split_name]['images_with_staff'] += 1
                stats[split_name]['total_bboxes'] += len(bboxes)

            # Progress
            if (idx + 1) % 50 == 0 or (idx + 1) == len(images):
                print(f"   Progress: {idx + 1}/{len(images)} images processed")

        print(f"   ✅ {split_name.capitalize()} split complete!")

    # Process train and validation splits
    process_split(train_images, 'train', train_img_dir, train_lbl_dir)
    process_split(val_images, 'val', val_img_dir, val_lbl_dir)

    db_conn.close()

    # Create data.yaml
    yaml_content = f"""# Staff Detection Dataset (YOLO Detection Format)
# One-step staff detection: directly detect staff members with bounding boxes
# Class: staff (people wearing hats/uniforms)

path: {os.path.abspath(DATASET_DIR)}
train: images/train
val: images/val

# Classes
nc: 1
names:
  0: staff

# Dataset Statistics
train_images: {stats['train']['images']}
train_images_with_staff: {stats['train']['images_with_staff']}
train_images_no_staff: {stats['train']['images'] - stats['train']['images_with_staff']}
train_total_bboxes: {stats['train']['total_bboxes']}

val_images: {stats['val']['images']}
val_images_with_staff: {stats['val']['images_with_staff']}
val_images_no_staff: {stats['val']['images'] - stats['val']['images_with_staff']}
val_total_bboxes: {stats['val']['total_bboxes']}

# Model Performance Notes
# Previous two-stage approach: YOLOv8m detect + classifier (61.7ms, 55MB)
# New one-step approach: YOLO11n detect staff directly (~2ms, 6MB)
# Label ONLY staff members wearing hats/uniforms - DO NOT label customers
"""

    yaml_path = Path(DATASET_DIR) / "data.yaml"
    with open(yaml_path, 'w') as f:
        f.write(yaml_content)

    # Print summary
    print("\n" + "=" * 70)
    print("✅ Detection dataset prepared successfully!")
    print("=" * 70)
    print(f"\n📊 Final Statistics:")
    print(f"\n🏋️  Training Set:")
    print(f"   Total images:        {stats['train']['images']}")
    print(f"   Images with staff:   {stats['train']['images_with_staff']}")
    print(f"   Images without staff: {stats['train']['images'] - stats['train']['images_with_staff']}")
    print(f"   Total bounding boxes: {stats['train']['total_bboxes']}")
    if stats['train']['images_with_staff'] > 0:
        print(f"   Avg boxes per img (with staff): {stats['train']['total_bboxes'] / stats['train']['images_with_staff']:.2f}")

    print(f"\n✅ Validation Set:")
    print(f"   Total images:        {stats['val']['images']}")
    print(f"   Images with staff:   {stats['val']['images_with_staff']}")
    print(f"   Images without staff: {stats['val']['images'] - stats['val']['images_with_staff']}")
    print(f"   Total bounding boxes: {stats['val']['total_bboxes']}")
    if stats['val']['images_with_staff'] > 0:
        print(f"   Avg boxes per img (with staff): {stats['val']['total_bboxes'] / stats['val']['images_with_staff']:.2f}")

    print(f"\n📁 Dataset structure:")
    print(f"   {DATASET_DIR}/")
    print(f"   ├── images/")
    print(f"   │   ├── train/  ({stats['train']['images']} images)")
    print(f"   │   └── val/    ({stats['val']['images']} images)")
    print(f"   ├── labels/")
    print(f"   │   ├── train/  ({stats['train']['images']} label files)")
    print(f"   │   └── val/    ({stats['val']['images']} label files)")
    print(f"   └── data.yaml")

    print(f"\n📄 Config file: {yaml_path}")
    print("\n🎯 Ready for YOLO detection training!")
    print("   Next: Run 5_train_staff_detector.py")
    print("=" * 70)

if __name__ == "__main__":
    try:
        # Set random seed for reproducibility
        random.seed(42)

        prepare_detection_dataset()
        os.system('say "Detection dataset preparation completed successfully"')
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        os.system('say "Dataset preparation failed with error"')
        raise
