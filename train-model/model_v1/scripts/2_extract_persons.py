#!/usr/bin/env python3
# Version: 3.0
# Extract all persons from screenshot images using YOLO
# Updated: Process images from raw_images folder instead of video files

import cv2
import os
from ultralytics import YOLO
import numpy as np
from pathlib import Path
from datetime import datetime
import glob

# Paths
IMAGES_DIR = "../raw_images"
OUTPUT_DIR = "../extracted-persons"
MODEL_PATH = "../../model/yolov8s.pt"  # Use existing model

# Extraction settings
MIN_PERSON_SIZE = 30  # Minimum pixel size for person detection
CONFIDENCE_THRESHOLD = 0.5
MAX_PERSONS_PER_IMAGE = 10  # Limit persons extracted per image

def extract_persons_from_image(image_path):
    """Extract all persons from a single image file"""
    print(f"📸 Processing: {os.path.basename(image_path)}")
    
    # Load YOLO model
    model = YOLO(MODEL_PATH if os.path.exists(MODEL_PATH) else "yolov8s.pt")
    
    # Read image
    image = cv2.imread(image_path)
    if image is None:
        print(f"❌ Failed to load image: {image_path}")
        return 0
    
    # Create output directory based on image source camera
    image_name = Path(image_path).stem
    # Extract camera info from filename (e.g., camera_27_2592_1944_20250927_230846.jpg)
    parts = image_name.split('_')
    if len(parts) >= 2 and parts[0] == 'camera':
        camera_id = f"camera_{parts[1]}"
    else:
        camera_id = "unknown_camera"
    
    output_path = os.path.join(OUTPUT_DIR, camera_id)
    os.makedirs(output_path, exist_ok=True)
    
    person_count = 0
    
    # Run detection
    results = model(image, conf=CONFIDENCE_THRESHOLD, classes=[0])  # Class 0 = person
    
    # Extract persons
    for r in results:
        boxes = r.boxes
        if boxes is not None:
            print(f"   🔍 Found {len(boxes)} detection(s)")
            for i, box in enumerate(boxes):
                if person_count >= MAX_PERSONS_PER_IMAGE:
                    break

                x1, y1, x2, y2 = map(int, box.xyxy[0])

                # Check minimum size
                width = x2 - x1
                height = y2 - y1
                print(f"   📏 Detection {i+1}: {width}x{height}px at ({x1},{y1})")
                if width < MIN_PERSON_SIZE or height < MIN_PERSON_SIZE:
                    print(f"   ❌ Too small (min size: {MIN_PERSON_SIZE}px)")
                    continue
                
                # Crop person with padding
                padding = 10
                y1_pad = max(0, y1 - padding)
                y2_pad = min(image.shape[0], y2 + padding)
                x1_pad = max(0, x1 - padding)
                x2_pad = min(image.shape[1], x2 + padding)
                
                person_img = image[y1_pad:y2_pad, x1_pad:x2_pad]
                
                # Save person image
                conf = float(box.conf[0])
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"person_{image_name}_{i}_{conf:.2f}_{timestamp}.jpg"
                filepath = os.path.join(output_path, filename)
                cv2.imwrite(filepath, person_img)
                
                person_count += 1
                print(f"   👤 Extracted person {person_count}: {width}x{height}px, conf={conf:.2f}")
    
    if person_count == 0:
        print(f"   ⚠️ No persons detected in {os.path.basename(image_path)}")
    else:
        print(f"   ✅ Found {person_count} person(s) in {os.path.basename(image_path)}")
    
    return person_count

def process_all_images():
    """Process all images in the raw_images directory"""
    print("🚀 Starting person extraction from screenshots...")
    
    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Find all image files
    image_files = []
    for ext in ['*.jpg', '*.jpeg', '*.png', '*.bmp']:
        image_files.extend(Path(IMAGES_DIR).glob(ext))
    
    if not image_files:
        print("❌ No image files found in", IMAGES_DIR)
        return
    
    print(f"📁 Found {len(image_files)} image(s)")
    print(f"📂 Input directory: {IMAGES_DIR}")
    print(f"📂 Output directory: {OUTPUT_DIR}")
    print("=" * 60)
    
    total_persons = 0
    successful_images = 0
    
    for i, image_path in enumerate(image_files, 1):
        print(f"\n[{i}/{len(image_files)}]", end=" ")
        persons = extract_persons_from_image(str(image_path))
        total_persons += persons
        
        if persons > 0:
            successful_images += 1
    
    print("\n" + "=" * 60)
    print(f"🎉 Extraction Complete!")
    print(f"📊 Statistics:")
    print(f"   - Total images processed: {len(image_files)}")
    print(f"   - Images with persons: {successful_images}")
    print(f"   - Images without persons: {len(image_files) - successful_images}")
    print(f"   - Total persons extracted: {total_persons}")
    print(f"   - Average persons per image: {total_persons/len(image_files):.2f}")
    print(f"📁 Output directory: {OUTPUT_DIR}")
    print("\n🔍 Next steps:")
    print("1. Review extracted persons in", OUTPUT_DIR)
    print("2. Run 3_label_images.py to label as 'waiter' or 'customer'")
    print("3. Run 4_prepare_dataset.py to prepare training dataset")

if __name__ == "__main__":
    process_all_images()