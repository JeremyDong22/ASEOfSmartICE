#!/usr/bin/env python3
# Version: 5.0 (Model V4 - One-Step Staff Detection)
# Filter images that contain people using YOLO detection
# Deletes images with NO people to reduce labeling workload
# Keeps images with at least 1 person for staff annotation

import cv2
import os
from ultralytics import YOLO
from pathlib import Path
from datetime import datetime
import shutil

# Paths
IMAGES_DIR = "../raw_images"
FILTERED_DIR = "../filtered_images_with_people"
REJECTED_DIR = "../rejected_no_people"  # Optional: keep rejected images for review
MODEL_PATH = "yolov8m.pt"  # YOLOv8 Medium for reliable detection

# Detection settings
CONFIDENCE_THRESHOLD = 0.3  # Lower threshold to catch all people
MIN_PERSON_SIZE = 80  # Minimum pixel size (relaxed for initial filtering)
SAVE_REJECTED = False  # Set to True if you want to review rejected images

def has_people(image_path, model):
    """Check if image contains any people"""
    # Read image
    image = cv2.imread(image_path)
    if image is None:
        print(f"      ❌ Failed to load: {os.path.basename(image_path)}")
        return False, 0

    # Run detection for person class only (class 0)
    results = model(image, conf=CONFIDENCE_THRESHOLD, classes=[0], verbose=False)

    person_count = 0
    for r in results:
        boxes = r.boxes
        if boxes is not None:
            for box in boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                width = x2 - x1
                height = y2 - y1

                # Check minimum size
                if width >= MIN_PERSON_SIZE and height >= MIN_PERSON_SIZE:
                    person_count += 1

    return person_count > 0, person_count

def filter_images():
    """Filter all images in raw_images directory"""
    print("🚀 Starting image filtering for people detection...")
    print(f"📂 Input directory: {IMAGES_DIR}")
    print(f"📂 Output directory: {FILTERED_DIR}")
    print(f"🎯 Confidence threshold: {CONFIDENCE_THRESHOLD}")
    print(f"📏 Min person size: {MIN_PERSON_SIZE}px")
    print("=" * 70)

    # Create output directories
    os.makedirs(FILTERED_DIR, exist_ok=True)
    if SAVE_REJECTED:
        os.makedirs(REJECTED_DIR, exist_ok=True)

    # Load YOLO model
    print(f"\n📦 Loading YOLO model: {MODEL_PATH}")
    model = YOLO(MODEL_PATH)
    print("   ✅ Model loaded successfully\n")

    # Find all image files recursively
    image_files = []
    for ext in ['*.jpg', '*.jpeg', '*.png', '*.bmp']:
        image_files.extend(Path(IMAGES_DIR).rglob(ext))

    if not image_files:
        print(f"❌ No image files found in {IMAGES_DIR}")
        return

    print(f"📁 Found {len(image_files)} total images to process\n")

    # Statistics
    kept_count = 0
    deleted_count = 0
    failed_count = 0
    total_people_found = 0

    start_time = datetime.now()

    # Process each image
    for i, image_path in enumerate(image_files, 1):
        # Extract channel info from path
        parent_dir = image_path.parent.name
        filename = image_path.name

        # Progress indicator
        if i % 50 == 0 or i == len(image_files):
            elapsed = (datetime.now() - start_time).total_seconds()
            rate = i / elapsed if elapsed > 0 else 0
            print(f"Progress: {i}/{len(image_files)} ({rate:.1f} img/s) | ✅ {kept_count} kept | ❌ {deleted_count} deleted")

        try:
            has_person, person_count = has_people(str(image_path), model)

            if has_person:
                # Keep image - copy to filtered directory
                # Maintain channel folder structure
                if parent_dir.startswith('channel_'):
                    channel_dir = Path(FILTERED_DIR) / parent_dir
                    channel_dir.mkdir(exist_ok=True)
                    dest_path = channel_dir / filename
                else:
                    dest_path = Path(FILTERED_DIR) / filename

                shutil.copy2(image_path, dest_path)
                kept_count += 1
                total_people_found += person_count
            else:
                # No people - delete or move to rejected folder
                if SAVE_REJECTED:
                    if parent_dir.startswith('channel_'):
                        reject_dir = Path(REJECTED_DIR) / parent_dir
                        reject_dir.mkdir(exist_ok=True)
                        dest_path = reject_dir / filename
                    else:
                        dest_path = Path(REJECTED_DIR) / filename
                    shutil.move(str(image_path), dest_path)

                deleted_count += 1

        except Exception as e:
            print(f"      ⚠️  Error processing {filename}: {e}")
            failed_count += 1

    # Summary
    duration = (datetime.now() - start_time).total_seconds()

    print("\n" + "=" * 70)
    print("✅ Image filtering complete!")
    print("=" * 70)
    print(f"📊 Statistics:")
    print(f"   Total images processed: {len(image_files)}")
    print(f"   Images with people:     {kept_count} ({kept_count/len(image_files)*100:.1f}%)")
    print(f"   Images without people:  {deleted_count} ({deleted_count/len(image_files)*100:.1f}%)")
    print(f"   Failed to process:      {failed_count}")
    print(f"   Total people detected:  {total_people_found}")
    print(f"   Avg people per kept img: {total_people_found/kept_count:.2f}" if kept_count > 0 else "")
    print(f"\n⏱️  Duration: {duration:.1f}s ({duration/60:.1f} minutes)")
    print(f"📈 Processing rate: {len(image_files)/duration:.1f} images/second")
    print(f"\n📁 Filtered images saved to: {FILTERED_DIR}")
    if SAVE_REJECTED:
        print(f"📁 Rejected images saved to: {REJECTED_DIR}")
    print("\n🔍 Next steps:")
    print("   1. Review filtered images (should only contain images with people)")
    print("   2. Run 3_label_staff_bboxes.py to draw bounding boxes around staff members")
    print("=" * 70)

if __name__ == "__main__":
    try:
        filter_images()
        os.system('say "Image filtering completed successfully"')
    except KeyboardInterrupt:
        print("\n\n⚠️  Filtering interrupted by user")
        os.system('say "Image filtering interrupted"')
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        os.system('say "Image filtering failed with error"')
        raise
