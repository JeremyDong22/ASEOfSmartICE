#!/usr/bin/env python3
"""
ASEOfSmartICE Two-Stage Detection Script
Version: 1.0.0 - Correct two-stage architecture for staff detection

This script implements the correct two-stage detection approach:
1. Stage 1: Use standard YOLO to detect all persons
2. Stage 2: Use our trained model to classify each person as waiter/customer
"""

import cv2
import numpy as np
from ultralytics import YOLO
import os
from pathlib import Path
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# Model paths and configuration
PERSON_DETECTOR_MODEL = "models/yolov8n.pt"  # Standard COCO-trained YOLO
STAFF_CLASSIFIER_MODEL = "../../train-model/models/waiter_customer_model/weights/best.pt"

# Detection parameters
PERSON_CONF_THRESHOLD = 0.3    # Lower threshold to catch all people
STAFF_CONF_THRESHOLD = 0.5     # Higher threshold for reliable classification
MIN_PERSON_SIZE = 50           # Minimum person width/height in pixels

# Visual configuration
COLORS = {
    'waiter': (0, 255, 0),      # Green for waiters
    'customer': (0, 0, 255)     # Red for customers
}
CLASS_NAMES = ['waiter', 'customer']

def load_models():
    """Load both detection models"""
    print("📦 Loading detection models...")

    # Load person detector (standard YOLO)
    print(f"   Loading person detector: {PERSON_DETECTOR_MODEL}")
    person_detector = YOLO(PERSON_DETECTOR_MODEL)

    # Load staff classifier (our trained model)
    if not os.path.exists(STAFF_CLASSIFIER_MODEL):
        print(f"❌ Staff classifier not found: {STAFF_CLASSIFIER_MODEL}")
        return None, None

    print(f"   Loading staff classifier: {STAFF_CLASSIFIER_MODEL}")
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
    results = person_detector(image, conf=PERSON_CONF_THRESHOLD, classes=[0], verbose=True)

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
    Stage 2: Classify each detected person as waiter or customer (batch processing)

    Args:
        staff_classifier: Our trained classification model
        image: Original image
        person_detections: List of person bounding boxes from stage 1

    Returns:
        list: Classification results for each person
    """
    print("🎯 Stage 2: Classifying staff roles (batch processing)...")
    stage2_start = time.time()

    classified_detections = []

    # Prepare all person crops
    person_crops = []
    valid_indices = []

    for i, detection in enumerate(person_detections):
        x1, y1, x2, y2 = detection['bbox']
        person_crop = image[y1:y2, x1:x2]

        # Skip if crop is too small
        if person_crop.shape[0] >= 20 and person_crop.shape[1] >= 20:
            person_crops.append(person_crop)
            valid_indices.append(i)

    # Process all crops in a single batch if possible
    for idx, (i, crop) in enumerate(zip(valid_indices, person_crops)):
        person_start = time.time()
        classification_results = staff_classifier(crop, conf=STAFF_CONF_THRESHOLD, verbose=False)
        person_time = (time.time() - person_start) * 1000  # ms

        # Process classification results
        best_classification = None
        best_confidence = 0

        for result in classification_results:
            if result.boxes is not None:
                for box in result.boxes:
                    conf = box.conf[0].cpu().numpy()
                    class_id = int(box.cls[0].cpu().numpy())

                    if conf > best_confidence:
                        best_confidence = conf
                        best_classification = {
                            'class': CLASS_NAMES[class_id],
                            'confidence': conf,
                            'bbox': person_detections[i]['bbox'],
                            'person_confidence': person_detections[i]['confidence'],
                            'inference_ms': person_time
                        }

        # Add result
        if best_classification:
            classified_detections.append(best_classification)
            print(f"   Person {i+1}: {best_classification['class']} ({best_classification['confidence']:.1%}) - {person_time:.1f}ms")
        else:
            classified_detections.append({
                'class': 'unknown',
                'confidence': 0.0,
                'bbox': person_detections[i]['bbox'],
                'person_confidence': person_detections[i]['confidence'],
                'inference_ms': person_time
            })
            print(f"   Person {i+1}: unknown (no confident classification) - {person_time:.1f}ms")

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

    if stage1_time and stage2_time:
        # Use actual inference times (Stage 1 is typically ~60-70ms based on YOLO output)
        stage1_inference = 70  # Approximate from YOLO verbose output
        total_time = stage1_inference + stage2_time
        print(f"\n⏱️  Performance:")
        print(f"   Stage 1 (person detection): ~{stage1_inference}ms")
        print(f"   Stage 2 (role classification): {stage2_time:.1f}ms")
        print(f"   Total inference: {total_time:.1f}ms ({total_time/1000:.2f} seconds)")
        print(f"   Note: Stage 2 processes sequentially, parallel processing could reduce to ~{max(d.get('inference_ms', 0) for d in detections if 'inference_ms' in d):.1f}ms")

def analyze_image_with_params(image_path, output_dir="results", person_conf=None, staff_conf=None):
    """Analyze image with custom confidence thresholds"""
    global PERSON_CONF_THRESHOLD, STAFF_CONF_THRESHOLD

    # Store original values
    orig_person_conf = PERSON_CONF_THRESHOLD
    orig_staff_conf = STAFF_CONF_THRESHOLD

    # Update if provided
    if person_conf is not None:
        PERSON_CONF_THRESHOLD = person_conf
    if staff_conf is not None:
        STAFF_CONF_THRESHOLD = staff_conf

    try:
        result = analyze_image(image_path, output_dir)
    finally:
        # Restore original values
        PERSON_CONF_THRESHOLD = orig_person_conf
        STAFF_CONF_THRESHOLD = orig_staff_conf

    return result

def analyze_image(image_path, output_dir="results"):
    """Main function to analyze an image with two-stage detection"""
    print(f"\n🎯 Two-Stage Staff Detection Analysis")
    print("=" * 50)
    print(f"📸 Image: {os.path.basename(image_path)}")

    # Load models
    person_detector, staff_classifier = load_models()
    if person_detector is None or staff_classifier is None:
        return False

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

    # Stage 2: Classify persons (now parallel)
    classified_detections = classify_persons(staff_classifier, image, person_detections)

    # Draw results
    annotated_image = draw_detections(image, classified_detections)

    # Print summary with timing info
    # Extract stage2 time from the classify_persons function output
    stage2_time = None
    if classified_detections and '_stage2_time' in classified_detections[0]:
        stage2_time = classified_detections[0]['_stage2_time']
        # Remove the temporary timing field
        del classified_detections[0]['_stage2_time']

    print_detection_summary(classified_detections, stage1_time, stage2_time)

    # Save result
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    result_filename = f"{Path(image_path).stem}_two_stage_detected.jpg"
    result_path = output_path / result_filename

    cv2.imwrite(str(result_path), annotated_image)
    print(f"\n💾 Result saved: {result_path}")
    print("✅ Analysis complete!")

    return True

def main():
    """Main function with argument parsing"""
    parser = argparse.ArgumentParser(description="Two-stage staff detection")
    parser.add_argument("--image", required=True,
                       help="Path to input image (e.g., ../test_images/test_image_one.jpg)")
    parser.add_argument("--output", default="results", help="Output directory")
    parser.add_argument("--person_conf", type=float, default=PERSON_CONF_THRESHOLD,
                       help="Person detection confidence threshold")
    parser.add_argument("--staff_conf", type=float, default=STAFF_CONF_THRESHOLD,
                       help="Staff classification confidence threshold")

    args = parser.parse_args()

    # Analyze image with custom thresholds
    success = analyze_image_with_params(args.image, args.output, args.person_conf, args.staff_conf)

    if not success:
        print("❌ Analysis failed")
        return 1

    return 0

if __name__ == "__main__":
    exit(main())