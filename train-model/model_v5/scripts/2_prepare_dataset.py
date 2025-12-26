#!/usr/bin/env python3
"""
Prepare YOLO Detection Dataset from V5 Labels
Version: 1.0.0

Converts SQLite labels to YOLO detection format:
- Class 0: staff
- Class 1: customer
- Images with 0 boxes = background images (empty label files)

Created: 2025-12-26
"""

import sqlite3
import os
import shutil
from pathlib import Path
import random
import cv2

# =============================================================================
# Configuration
# =============================================================================

SCRIPT_DIR = Path(__file__).parent.absolute()
PROJECT_DIR = SCRIPT_DIR.parent

# V4 source images
V4_DIR = PROJECT_DIR.parent / "model_v4"
SOURCE_IMAGES_DIR = V4_DIR / "filtered_images_with_people"

# V5 labels database
DB_PATH = PROJECT_DIR / "labeled_staff_customer" / "labels.db"

# Output dataset
OUTPUT_DIR = PROJECT_DIR / "dataset_detection"

# Train/Val split
TRAIN_RATIO = 0.85
RANDOM_SEED = 42

# Class mapping
CLASS_MAP = {
    'staff': 0,
    'customer': 1
}

# =============================================================================
# Main
# =============================================================================

def main():
    print("\n" + "=" * 60)
    print("📦 Preparing YOLO Detection Dataset (V5)")
    print("=" * 60)

    # Check inputs
    if not DB_PATH.exists():
        print(f"❌ Database not found: {DB_PATH}")
        return

    if not SOURCE_IMAGES_DIR.exists():
        print(f"❌ Source images not found: {SOURCE_IMAGES_DIR}")
        return

    # Create output directories
    for split in ['train', 'val']:
        (OUTPUT_DIR / 'images' / split).mkdir(parents=True, exist_ok=True)
        (OUTPUT_DIR / 'labels' / split).mkdir(parents=True, exist_ok=True)

    # Load labeled data from database
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # Get all labeled images (not skipped)
    cursor.execute("""
        SELECT id, filename FROM images
        WHERE labeled_at IS NOT NULL AND (skipped = FALSE OR skipped IS NULL)
    """)
    images = cursor.fetchall()

    print(f"\n📊 Found {len(images)} labeled images")

    # Shuffle and split
    random.seed(RANDOM_SEED)
    random.shuffle(images)

    split_idx = int(len(images) * TRAIN_RATIO)
    train_images = images[:split_idx]
    val_images = images[split_idx:]

    print(f"   Train: {len(train_images)} images")
    print(f"   Val: {len(val_images)} images")

    # Process images
    stats = {
        'train': {'images': 0, 'staff': 0, 'customer': 0, 'background': 0},
        'val': {'images': 0, 'staff': 0, 'customer': 0, 'background': 0}
    }

    def process_split(image_list, split_name):
        for image_id, filename in image_list:
            # Get source image path
            src_path = SOURCE_IMAGES_DIR / filename
            if not src_path.exists():
                print(f"   ⚠️ Image not found: {filename}")
                continue

            # Read image to get dimensions
            img = cv2.imread(str(src_path))
            if img is None:
                print(f"   ⚠️ Failed to read: {filename}")
                continue

            h, w = img.shape[:2]

            # Get boxes for this image
            cursor.execute("""
                SELECT x1, y1, x2, y2, class_name FROM boxes WHERE image_id = ?
            """, (image_id,))
            boxes = cursor.fetchall()

            # Generate unique filename
            safe_name = filename.replace('/', '_').replace('\\', '_')
            base_name = Path(safe_name).stem
            img_ext = Path(filename).suffix

            # Copy image
            dst_img = OUTPUT_DIR / 'images' / split_name / f"{base_name}{img_ext}"
            shutil.copy2(src_path, dst_img)

            # Create label file
            dst_label = OUTPUT_DIR / 'labels' / split_name / f"{base_name}.txt"

            if len(boxes) == 0:
                # Background image - empty label file
                dst_label.write_text("")
                stats[split_name]['background'] += 1
            else:
                # Convert boxes to YOLO format
                lines = []
                for x1, y1, x2, y2, class_name in boxes:
                    if class_name not in CLASS_MAP:
                        continue

                    class_id = CLASS_MAP[class_name]

                    # Convert to YOLO format (normalized center x, center y, width, height)
                    cx = ((x1 + x2) / 2) / w
                    cy = ((y1 + y2) / 2) / h
                    bw = (x2 - x1) / w
                    bh = (y2 - y1) / h

                    # Clamp to [0, 1]
                    cx = max(0, min(1, cx))
                    cy = max(0, min(1, cy))
                    bw = max(0, min(1, bw))
                    bh = max(0, min(1, bh))

                    lines.append(f"{class_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")

                    if class_name == 'staff':
                        stats[split_name]['staff'] += 1
                    else:
                        stats[split_name]['customer'] += 1

                dst_label.write_text("\n".join(lines))

            stats[split_name]['images'] += 1

    print("\n🔄 Processing train split...")
    process_split(train_images, 'train')

    print("🔄 Processing val split...")
    process_split(val_images, 'val')

    conn.close()

    # Create data.yaml
    yaml_content = f"""# V5 Staff/Customer Detection Dataset
# Generated: 2025-12-26
# Classes: staff (0), customer (1)

path: {OUTPUT_DIR}
train: images/train
val: images/val

nc: 2
names:
  0: staff
  1: customer
"""

    yaml_path = OUTPUT_DIR / "data.yaml"
    yaml_path.write_text(yaml_content)

    # Print summary
    print("\n" + "=" * 60)
    print("✅ Dataset prepared successfully!")
    print("=" * 60)
    print(f"\n📁 Output: {OUTPUT_DIR}")
    print(f"\n📊 Statistics:")
    print(f"   Train: {stats['train']['images']} images")
    print(f"      - Staff boxes: {stats['train']['staff']}")
    print(f"      - Customer boxes: {stats['train']['customer']}")
    print(f"      - Background images: {stats['train']['background']}")
    print(f"   Val: {stats['val']['images']} images")
    print(f"      - Staff boxes: {stats['val']['staff']}")
    print(f"      - Customer boxes: {stats['val']['customer']}")
    print(f"      - Background images: {stats['val']['background']}")
    print(f"\n📄 Config: {yaml_path}")
    print("\n🚀 Next: Run 3_train_model.py to train YOLO11s")

if __name__ == '__main__':
    main()
