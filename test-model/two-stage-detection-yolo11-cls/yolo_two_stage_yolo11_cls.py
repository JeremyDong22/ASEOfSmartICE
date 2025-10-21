#!/usr/bin/env python3
"""
ASEOfSmartICE Two-Stage Detection Script - YOLO11 Classification Model
Version: 3.0.0 - Uses YOLO11n-cls trained on 1,505 high-quality 1080p images

Model Information:
- Stage 1: YOLOv8s (COCO person detection)
- Stage 2: YOLO11n-cls (Classification model trained on 1080p crops)
- Training data: 1,505 manually labeled images (402 waiters, 1,103 customers)
- Camera sources: camera_35 and camera_22 (1920×1080 resolution)
- Person crop quality: Average 300px (superior to previous versions)
- Training accuracy: 92.38% top-1 accuracy on validation set

Key Differences from V2:
- Uses YOLO classification (probs API) instead of detection (boxes API)
- Higher quality training data (300px crops vs 50-90px)
- Trained only on 1080p footage for consistent quality

This script implements the two-stage detection approach:
1. Stage 1: Use YOLOv8s to detect all persons (better than nano)
2. Stage 2: Use YOLO11n-cls to classify each person as waiter/customer
"""

import cv2
import numpy as np
from ultralytics import YOLO
import os
from pathlib import Path
import argparse
import time
import glob

# Model paths and configuration
PERSON_DETECTOR_MODEL = "models/yolov8s.pt"  # COCO-trained YOLO (small model)
STAFF_CLASSIFIER_MODEL = "models/waiter_customer_classifier.pt"  # YOLO11n-cls model

# Detection parameters
PERSON_CONF_THRESHOLD = 0.3    # Lower threshold to catch all people
STAFF_CONF_THRESHOLD = 0.5     # Higher threshold for reliable classification
MIN_PERSON_SIZE = 40           # Minimum person width/height in pixels

# Visual configuration
COLORS = {
    'waiter': (0, 255, 0),      # Green for waiters
    'customer': (0, 0, 255)     # Red for customers
}
# Note: YOLO11 cls uses alphabetical folder order: 0=customer, 1=waiter
CLASS_NAMES = {0: 'customer', 1: 'waiter'}

def load_models():
    """Load both detection models"""
    print("📦 Loading detection models...")

    # Load person detector (standard YOLO)
    print(f"   Loading person detector: {PERSON_DETECTOR_MODEL}")
    person_detector = YOLO(PERSON_DETECTOR_MODEL)

    # Load staff classifier (YOLO11n-cls model)
    if not os.path.exists(STAFF_CLASSIFIER_MODEL):
        print(f"❌ Staff classifier not found: {STAFF_CLASSIFIER_MODEL}")
        return None, None

    print(f"   Loading YOLO11n-cls staff classifier: {STAFF_CLASSIFIER_MODEL}")
    print(f"   Model specs: 92.38% accuracy, trained on 1,505 images (1080p crops)")
    staff_classifier = YOLO(STAFF_CLASSIFIER_MODEL)

    print("✅ Both models loaded successfully!")
    return person_detector, staff_classifier

def detect_persons(person_detector, image):
    """
    Stage 1: Detect all persons in the image using standard YOLO

    Args:
        person_detector: YOLO model for person detection
        image: Input image

    Returns:
        list: Person detection results with bounding boxes
    """
    print("🔍 Stage 1: Detecting persons...")

    # Run person detection (class 0 = person in COCO dataset)
    results = person_detector(image, conf=PERSON_CONF_THRESHOLD, classes=[0], verbose=False)

    person_detections = []
    for result in results:
        boxes = result.boxes
        if boxes is not None:
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                confidence = box.conf[0].cpu().numpy()

                # Filter by minimum size
                width = x2 - x1
                height = y2 - y1
                if width >= MIN_PERSON_SIZE and height >= MIN_PERSON_SIZE:
                    person_detections.append({
                        'bbox': (int(x1), int(y1), int(x2), int(y2)),
                        'confidence': confidence
                    })

    print(f"   Found {len(person_detections)} persons")
    return person_detections

def classify_persons(staff_classifier, image, person_detections):
    """
    Stage 2: Classify each detected person as waiter or customer using YOLO11n-cls

    Args:
        staff_classifier: YOLO11n-cls classification model
        image: Original image
        person_detections: List of person bounding boxes from stage 1

    Returns:
        list: Classification results for each person
    """
    print("🎯 Stage 2: Classifying staff roles with YOLO11n-cls...")
    stage2_start = time.time()

    classified_detections = []

    for i, detection in enumerate(person_detections):
        x1, y1, x2, y2 = detection['bbox']
        person_crop = image[y1:y2, x1:x2]

        # Skip if crop is too small
        if person_crop.shape[0] < 20 or person_crop.shape[1] < 20:
            classified_detections.append({
                'class': 'unknown',
                'confidence': 0.0,
                'bbox': detection['bbox'],
                'person_confidence': detection['confidence']
            })
            continue

        person_start = time.time()
        # YOLO11 classification uses probs API (not boxes)
        classification_results = staff_classifier(person_crop, verbose=False)
        person_time = (time.time() - person_start) * 1000  # ms

        # Process classification results using probs API
        result = classification_results[0]

        # Get top prediction
        if result.probs is not None:
            class_id = result.probs.top1        # 0=customer, 1=waiter
            confidence = float(result.probs.top1conf)
            class_name = CLASS_NAMES[class_id]

            # Only accept predictions above threshold
            if confidence >= STAFF_CONF_THRESHOLD:
                classified_detections.append({
                    'class': class_name,
                    'confidence': confidence,
                    'bbox': detection['bbox'],
                    'person_confidence': detection['confidence'],
                    'inference_ms': person_time
                })
                print(f"   Person {i+1}: {class_name} ({confidence:.1%}) - {person_time:.1f}ms")
            else:
                classified_detections.append({
                    'class': 'unknown',
                    'confidence': confidence,
                    'bbox': detection['bbox'],
                    'person_confidence': detection['confidence'],
                    'inference_ms': person_time
                })
                print(f"   Person {i+1}: unknown (confidence {confidence:.1%} below threshold) - {person_time:.1f}ms")
        else:
            classified_detections.append({
                'class': 'unknown',
                'confidence': 0.0,
                'bbox': detection['bbox'],
                'person_confidence': detection['confidence'],
                'inference_ms': person_time
            })
            print(f"   Person {i+1}: unknown (no classification) - {person_time:.1f}ms")

    stage2_time = (time.time() - stage2_start) * 1000
    print(f"   Stage 2 total time: {stage2_time:.1f}ms")

    # Store the stage2 time for summary
    if classified_detections:
        classified_detections[0]['_stage2_time'] = stage2_time

    return classified_detections

def draw_detections(image, detections):
    """Draw bounding boxes and labels on the image"""
    annotated_image = image.copy()

    for detection in detections:
        x1, y1, x2, y2 = detection['bbox']
        class_name = detection['class']
        confidence = detection['confidence']

        # Get color for this class
        if class_name in COLORS:
            color = COLORS[class_name]
        else:
            color = (128, 128, 128)  # Gray for unknown

        # Draw bounding box
        cv2.rectangle(annotated_image, (x1, y1), (x2, y2), color, 2)

        # Prepare label
        if confidence > 0:
            label = f"{class_name}: {confidence:.1%}"
        else:
            label = f"{class_name}"

        # Draw label background
        label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
        cv2.rectangle(annotated_image,
                     (x1, y1 - label_size[1] - 10),
                     (x1 + label_size[0], y1),
                     color, -1)

        # Draw label text
        cv2.putText(annotated_image, label,
                   (x1, y1 - 5),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    return annotated_image

def print_detection_summary(detections, stage1_time=None, stage2_time=None):
    """Print summary of detection results"""
    if not detections:
        print("❌ No detections found")
        return

    waiter_count = sum(1 for d in detections if d['class'] == 'waiter')
    customer_count = sum(1 for d in detections if d['class'] == 'customer')
    unknown_count = sum(1 for d in detections if d['class'] == 'unknown')

    print(f"\n📊 Detection Summary:")
    print(f"   👨‍🍳 Waiters: {waiter_count}")
    print(f"   👥 Customers: {customer_count}")
    print(f"   ❓ Unknown: {unknown_count}")
    print(f"   📋 Total: {len(detections)}")

    if stage2_time:
        print(f"\n⏱️  Performance:")
        print(f"   Stage 2 (role classification): {stage2_time:.1f}ms")

def analyze_image(image_path, output_dir="results"):
    """Main function to analyze an image with two-stage detection"""
    print(f"\n{'='*60}")
    print(f"🎯 Two-Stage Detection - YOLO11 Classification")
    print(f"{'='*60}")
    print(f"📸 Image: {os.path.basename(image_path)}")

    # Load models (only once for all images)
    if not hasattr(analyze_image, 'person_detector'):
        analyze_image.person_detector, analyze_image.staff_classifier = load_models()
        if analyze_image.person_detector is None or analyze_image.staff_classifier is None:
            return False

    person_detector = analyze_image.person_detector
    staff_classifier = analyze_image.staff_classifier

    # Load image
    if not os.path.exists(image_path):
        print(f"❌ Image not found: {image_path}")
        return False

    image = cv2.imread(image_path)
    if image is None:
        print(f"❌ Could not load image: {image_path}")
        return False

    print(f"📏 Image size: {image.shape[1]}x{image.shape[0]}")

    # Stage 1: Detect persons
    stage1_start = time.time()
    person_detections = detect_persons(person_detector, image)
    stage1_time = (time.time() - stage1_start) * 1000  # ms

    if not person_detections:
        print("❌ No persons detected in image")
        return False

    # Stage 2: Classify persons
    classified_detections = classify_persons(staff_classifier, image, person_detections)

    # Draw results
    annotated_image = draw_detections(image, classified_detections)

    # Print summary with timing info
    stage2_time = None
    if classified_detections and '_stage2_time' in classified_detections[0]:
        stage2_time = classified_detections[0]['_stage2_time']
        del classified_detections[0]['_stage2_time']

    print_detection_summary(classified_detections, stage1_time, stage2_time)

    # Save result
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    result_filename = f"{Path(image_path).stem}_yolo11_cls_detected.jpg"
    result_path = output_path / result_filename

    cv2.imwrite(str(result_path), annotated_image)
    print(f"\n💾 Result saved: {result_path}")
    print("✅ Analysis complete!")

    return True

def process_all_images(input_dir="../test_images", output_dir="results"):
    """Process all JPG images in the specified directory"""
    print(f"\n🔍 Searching for JPG images in: {input_dir}")

    # Find all JPG files
    jpg_files = glob.glob(os.path.join(input_dir, "*.jpg"))
    jpg_files.extend(glob.glob(os.path.join(input_dir, "*.JPG")))

    if not jpg_files:
        print(f"❌ No JPG images found in {input_dir}")
        return False

    print(f"✅ Found {len(jpg_files)} JPG image(s)")

    success_count = 0
    for img_path in jpg_files:
        if analyze_image(img_path, output_dir):
            success_count += 1

    print(f"\n{'='*60}")
    print(f"🎉 Batch Processing Complete!")
    print(f"   Successfully processed: {success_count}/{len(jpg_files)} images")
    print(f"{'='*60}")

    return success_count > 0

def main():
    """Main function with argument parsing"""
    parser = argparse.ArgumentParser(
        description="Two-stage detection with YOLO11n-cls (trained on 1,505 high-quality 1080p images)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process single image
  python3 yolo_two_stage_yolo11_cls.py --image ../test_images/test_image_two.jpg

  # Process all JPG images in test_images directory
  python3 yolo_two_stage_yolo11_cls.py --batch

  # Custom confidence thresholds
  python3 yolo_two_stage_yolo11_cls.py --image ../test_images/test.jpg --person_conf 0.4 --staff_conf 0.6
        """
    )
    parser.add_argument("--image", help="Path to input image")
    parser.add_argument("--batch", action="store_true",
                       help="Process all JPG images in test_images directory (../test_images)")
    parser.add_argument("--input_dir", default="../test_images",
                       help="Input directory for batch processing (default: ../test_images)")
    parser.add_argument("--output", default="results", help="Output directory")
    parser.add_argument("--person_conf", type=float, default=0.3,
                       help="Person detection confidence threshold (default: 0.3)")
    parser.add_argument("--staff_conf", type=float, default=0.5,
                       help="Staff classification confidence threshold (default: 0.5)")

    args = parser.parse_args()

    # Update global thresholds if specified
    global PERSON_CONF_THRESHOLD, STAFF_CONF_THRESHOLD
    PERSON_CONF_THRESHOLD = args.person_conf
    STAFF_CONF_THRESHOLD = args.staff_conf

    # Batch processing mode
    if args.batch:
        success = process_all_images(args.input_dir, args.output)
        return 0 if success else 1

    # Single image mode
    if not args.image:
        parser.print_help()
        print("\n❌ Error: Please specify --image or use --batch mode")
        return 1

    success = analyze_image(args.image, args.output)
    return 0 if success else 1

if __name__ == "__main__":
    exit(main())
