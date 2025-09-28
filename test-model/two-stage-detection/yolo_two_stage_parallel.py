#!/usr/bin/env python3
"""
ASEOfSmartICE Two-Stage Detection Script - Parallel/GPU Optimized Version
Version: 2.0.0 - Optimized for parallel processing and GPU acceleration

This script implements parallel/batch processing for better performance:
1. Stage 1: Use standard YOLO to detect all persons
2. Stage 2: Batch process all detected persons for role classification

Performance Notes:
- On CPU: Sequential processing is actually faster (~1.6 FPS)
- On GPU: This parallel/batch version should achieve 5-10x speedup
- Target: 10-20 FPS with GPU acceleration
"""

import cv2
import numpy as np
from ultralytics import YOLO
import os
from pathlib import Path
import argparse
import time
import torch

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

def check_gpu():
    """Check if GPU is available and return device"""
    if torch.cuda.is_available():
        device = 'cuda'
        gpu_name = torch.cuda.get_device_name(0)
        print(f"🎮 GPU detected: {gpu_name}")
        print(f"   CUDA version: {torch.version.cuda}")
    else:
        device = 'cpu'
        print("💻 Running on CPU (GPU not available)")
        print("   Note: For optimal performance, GPU is recommended")

    return device

def load_models(device='cpu'):
    """Load both detection models with device specification"""
    print("📦 Loading detection models...")

    # Load person detector (standard YOLO)
    print(f"   Loading person detector: {PERSON_DETECTOR_MODEL}")
    person_detector = YOLO(PERSON_DETECTOR_MODEL)
    if device == 'cuda':
        person_detector.to('cuda')

    # Load staff classifier (our trained model)
    if not os.path.exists(STAFF_CLASSIFIER_MODEL):
        print(f"❌ Staff classifier not found: {STAFF_CLASSIFIER_MODEL}")
        return None, None

    print(f"   Loading staff classifier: {STAFF_CLASSIFIER_MODEL}")
    staff_classifier = YOLO(STAFF_CLASSIFIER_MODEL)
    if device == 'cuda':
        staff_classifier.to('cuda')

    print("✅ Both models loaded successfully!")
    return person_detector, staff_classifier

def detect_persons_batch(person_detector, image, device='cpu'):
    """
    Stage 1: Detect all persons in the image using standard YOLO

    Args:
        person_detector: YOLO model for person detection
        image: Input image
        device: Device to run on ('cpu' or 'cuda')

    Returns:
        list: Person detection results with bounding boxes
    """
    print("🔍 Stage 1: Detecting persons...")

    # Run person detection (class 0 = person in COCO dataset)
    stage1_start = time.time()
    results = person_detector(image, conf=PERSON_CONF_THRESHOLD, classes=[0], device=device, verbose=True)
    stage1_time = (time.time() - stage1_start) * 1000

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
    print(f"   Stage 1 time: {stage1_time:.1f}ms")

    return person_detections, stage1_time

def classify_persons_batch(staff_classifier, image, person_detections, device='cpu'):
    """
    Stage 2: Classify all detected persons as waiter or customer using batch processing

    Args:
        staff_classifier: Our trained classification model
        image: Original image
        person_detections: List of person bounding boxes from stage 1
        device: Device to run on ('cpu' or 'cuda')

    Returns:
        list: Classification results for each person
    """
    print("🎯 Stage 2: Classifying staff roles (batch mode)...")

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

    if not person_crops:
        print("   No valid person crops to classify")
        return [], 0

    # Batch process all crops
    print(f"   Processing {len(person_crops)} person crops in batch...")
    stage2_start = time.time()

    # YOLO can accept a list of images for batch processing
    batch_results = staff_classifier(person_crops, conf=STAFF_CONF_THRESHOLD, device=device, verbose=False)

    stage2_time = (time.time() - stage2_start) * 1000

    # Process batch results
    classified_detections = []

    for idx, (i, result) in enumerate(zip(valid_indices, batch_results)):
        detection = person_detections[i]

        # Default to unknown
        best_classification = {
            'class': 'unknown',
            'confidence': 0.0,
            'bbox': detection['bbox'],
            'person_confidence': detection['confidence']
        }

        # Check for classification results
        if result.boxes is not None and len(result.boxes) > 0:
            box = result.boxes[0]
            conf = float(box.conf[0].cpu().numpy())
            class_id = int(box.cls[0].cpu().numpy())

            best_classification = {
                'class': CLASS_NAMES[class_id],
                'confidence': conf,
                'bbox': detection['bbox'],
                'person_confidence': detection['confidence']
            }

        classified_detections.append(best_classification)
        print(f"   Person {i+1}: {best_classification['class']} ({best_classification['confidence']:.1%})")

    print(f"   Stage 2 time: {stage2_time:.1f}ms")

    # Calculate average inference per person
    avg_per_person = stage2_time / len(person_crops) if person_crops else 0
    print(f"   Average per person: {avg_per_person:.1f}ms")

    return classified_detections, stage2_time

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

def print_detection_summary(detections, stage1_time, stage2_time, device):
    """Print summary of detection results with performance metrics"""
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

    # Performance metrics
    total_time = stage1_time + stage2_time
    fps = 1000 / total_time

    print(f"\n⏱️  Performance Metrics:")
    print(f"   Device: {device.upper()}")
    print(f"   Stage 1 (person detection): {stage1_time:.1f}ms")
    print(f"   Stage 2 (batch classification): {stage2_time:.1f}ms")
    print(f"   Total inference: {total_time:.1f}ms")
    print(f"   Throughput: {fps:.2f} FPS")

    if device == 'cpu':
        print(f"\n💡 Performance Notes:")
        print(f"   - CPU performance is limited to ~1-2 FPS")
        print(f"   - GPU acceleration recommended for real-time processing")
        print(f"   - Expected GPU performance: 10-20 FPS")

def analyze_image(image_path, output_dir="results", device='cpu'):
    """Main function to analyze an image with two-stage detection"""
    print(f"\n🎯 Two-Stage Staff Detection Analysis (Parallel/Batch Mode)")
    print("=" * 60)
    print(f"📸 Image: {os.path.basename(image_path)}")

    # Check device
    device = check_gpu()

    # Load models
    person_detector, staff_classifier = load_models(device)
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
    person_detections, stage1_time = detect_persons_batch(person_detector, image, device)
    if not person_detections:
        print("❌ No persons detected in image")
        return False

    # Stage 2: Classify persons (batch processing)
    classified_detections, stage2_time = classify_persons_batch(
        staff_classifier, image, person_detections, device
    )

    # Draw results
    annotated_image = draw_detections(image, classified_detections)

    # Print summary
    print_detection_summary(classified_detections, stage1_time, stage2_time, device)

    # Save result
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    result_filename = f"{Path(image_path).stem}_parallel_detected.jpg"
    result_path = output_path / result_filename

    cv2.imwrite(str(result_path), annotated_image)
    print(f"\n💾 Result saved: {result_path}")
    print("✅ Analysis complete!")

    return True

def main():
    """Main function with argument parsing"""
    parser = argparse.ArgumentParser(
        description="Two-stage staff detection with parallel/batch processing"
    )
    parser.add_argument("--image", default="test_screenshot.jpg",
                       help="Path to input image")
    parser.add_argument("--output", default="results",
                       help="Output directory")
    parser.add_argument("--person_conf", type=float, default=PERSON_CONF_THRESHOLD,
                       help="Person detection confidence threshold")
    parser.add_argument("--staff_conf", type=float, default=STAFF_CONF_THRESHOLD,
                       help="Staff classification confidence threshold")
    parser.add_argument("--device", choices=['cpu', 'cuda', 'auto'], default='auto',
                       help="Device to use (cpu/cuda/auto)")

    args = parser.parse_args()

    # Determine device
    if args.device == 'auto':
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
    else:
        device = args.device

    # Update global thresholds if provided
    if args.person_conf:
        global PERSON_CONF_THRESHOLD
        PERSON_CONF_THRESHOLD = args.person_conf
    if args.staff_conf:
        global STAFF_CONF_THRESHOLD
        STAFF_CONF_THRESHOLD = args.staff_conf

    # Analyze image
    success = analyze_image(args.image, args.output, device)

    if not success:
        print("❌ Analysis failed")
        return 1

    return 0

if __name__ == "__main__":
    exit(main())