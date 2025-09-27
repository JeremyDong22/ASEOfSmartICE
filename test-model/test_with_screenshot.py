#!/usr/bin/env python3
"""
ASEOfSmartICE Model Testing Script with Screenshot
Version: 1.1.0 - Test YOLO detection with user-provided screenshot
Author: Claude Code
Date: 2025-09-28

This script tests the two-stage detection model with the provided camera screenshot.
It uses YOLOv8 for general person detection and a custom model for staff classification.
"""

import cv2
import numpy as np
from ultralytics import YOLO
import os
from pathlib import Path
import sys

# Configuration for model paths
YOLO_MODEL_PATH = "../model/yolov8s.pt"  # General YOLO model for person detection
CUSTOM_MODEL_PATH = "../train-model/models/waiter_customer_model/weights/best.pt"  # Custom trained model
TEST_IMAGE_PATH = "test_camera_image.jpg"  # Screenshot from camera

# Detection thresholds
PERSON_CONF_THRESHOLD = 0.3  # Lower threshold for person detection
STAFF_CONF_THRESHOLD = 0.5   # Higher threshold for staff classification

# Visual settings
COLORS = {
    'person': (255, 0, 0),       # Blue for general person detection
    'waiter': (0, 255, 0),       # Green for waiters
    'customer': (0, 0, 255),     # Red for customers
    'unknown': (128, 128, 128)   # Gray for unknown
}

def test_general_yolo_detection():
    """Test general YOLO model for object detection"""
    print("\n" + "="*60)
    print("🔍 TESTING GENERAL YOLO OBJECT DETECTION")
    print("="*60)

    # Load the general YOLO model
    if not os.path.exists(YOLO_MODEL_PATH):
        print(f"❌ YOLO model not found at: {YOLO_MODEL_PATH}")
        return None

    print(f"📦 Loading YOLO model: {YOLO_MODEL_PATH}")
    model = YOLO(YOLO_MODEL_PATH)

    # Load test image
    if not os.path.exists(TEST_IMAGE_PATH):
        print(f"❌ Test image not found: {TEST_IMAGE_PATH}")
        return None

    print(f"📸 Loading test image: {TEST_IMAGE_PATH}")
    image = cv2.imread(TEST_IMAGE_PATH)

    if image is None:
        print(f"❌ Failed to load image")
        return None

    print(f"📏 Image dimensions: {image.shape[1]}x{image.shape[0]}")

    # Run detection
    print("🎯 Running object detection...")
    results = model(image, conf=0.25)  # Lower confidence for broader detection

    # Process results
    detections = []
    class_names = model.names  # Get class names from model

    for result in results:
        if result.boxes is not None:
            boxes = result.boxes
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                confidence = box.conf[0].cpu().numpy()
                class_id = int(box.cls[0].cpu().numpy())
                class_name = class_names[class_id]

                detections.append({
                    'bbox': (int(x1), int(y1), int(x2), int(y2)),
                    'confidence': float(confidence),
                    'class': class_name,
                    'class_id': class_id
                })

                print(f"   ✅ Detected: {class_name} ({confidence:.1%}) at [{x1:.0f},{y1:.0f},{x2:.0f},{y2:.0f}]")

    # Draw detections on image
    annotated = image.copy()
    for det in detections:
        x1, y1, x2, y2 = det['bbox']
        label = f"{det['class']}: {det['confidence']:.1%}"

        # Use blue for all general detections
        color = (255, 0, 0)

        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

        # Add label
        label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
        cv2.rectangle(annotated, (x1, y1-20), (x1+label_size[0], y1), color, -1)
        cv2.putText(annotated, label, (x1, y1-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 2)

    # Save result
    output_path = "results/general_yolo_detection.jpg"
    os.makedirs("results", exist_ok=True)
    cv2.imwrite(output_path, annotated)
    print(f"\n💾 Saved annotated image: {output_path}")

    # Summary
    print(f"\n📊 Detection Summary:")
    print(f"   Total objects detected: {len(detections)}")

    # Count by class
    class_counts = {}
    for det in detections:
        class_name = det['class']
        class_counts[class_name] = class_counts.get(class_name, 0) + 1

    for class_name, count in sorted(class_counts.items()):
        print(f"   {class_name}: {count}")

    return detections

def test_person_detection():
    """Test YOLO for person detection specifically"""
    print("\n" + "="*60)
    print("👥 TESTING PERSON DETECTION")
    print("="*60)

    # Load model
    if not os.path.exists(YOLO_MODEL_PATH):
        print(f"❌ YOLO model not found at: {YOLO_MODEL_PATH}")
        return None

    print(f"📦 Loading YOLO model for person detection")
    model = YOLO(YOLO_MODEL_PATH)

    # Load image
    image = cv2.imread(TEST_IMAGE_PATH)
    if image is None:
        print(f"❌ Failed to load image")
        return None

    # Run detection for persons only (class 0 in COCO)
    print("🎯 Detecting persons...")
    results = model(image, conf=PERSON_CONF_THRESHOLD, classes=[0])

    person_detections = []
    for result in results:
        if result.boxes is not None:
            for box in result.boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                confidence = box.conf[0].cpu().numpy()

                # Check minimum size
                width = x2 - x1
                height = y2 - y1
                if width >= 50 and height >= 50:
                    person_detections.append({
                        'bbox': (int(x1), int(y1), int(x2), int(y2)),
                        'confidence': float(confidence)
                    })
                    print(f"   ✅ Person detected ({confidence:.1%}) at [{x1:.0f},{y1:.0f},{x2:.0f},{y2:.0f}]")

    print(f"\n📊 Found {len(person_detections)} persons in the image")

    # Draw person detections
    annotated = image.copy()
    for i, det in enumerate(person_detections):
        x1, y1, x2, y2 = det['bbox']
        color = COLORS['person']

        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

        label = f"Person {i+1}: {det['confidence']:.1%}"
        cv2.putText(annotated, label, (x1, y1-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

    # Save result
    output_path = "results/person_detection.jpg"
    cv2.imwrite(output_path, annotated)
    print(f"💾 Saved person detection result: {output_path}")

    return person_detections

def test_staff_classification():
    """Test the custom trained model for staff classification"""
    print("\n" + "="*60)
    print("👨‍🍳 TESTING STAFF CLASSIFICATION MODEL")
    print("="*60)

    # Check if custom model exists
    if not os.path.exists(CUSTOM_MODEL_PATH):
        print(f"⚠️  Custom trained model not found at: {CUSTOM_MODEL_PATH}")
        print("   The model needs to be trained first using the training pipeline")
        print("   Run: cd train-model/scripts && python3 5_train_model.py")
        return None

    print(f"📦 Loading custom staff classification model")

    # First detect persons
    print("🔍 Stage 1: Detecting persons...")
    person_model = YOLO(YOLO_MODEL_PATH)
    image = cv2.imread(TEST_IMAGE_PATH)

    person_results = person_model(image, conf=PERSON_CONF_THRESHOLD, classes=[0])

    person_detections = []
    for result in person_results:
        if result.boxes is not None:
            for box in result.boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                person_detections.append((int(x1), int(y1), int(x2), int(y2)))

    print(f"   Found {len(person_detections)} persons")

    if not person_detections:
        print("❌ No persons detected for classification")
        return None

    # Load staff classifier
    print("🎯 Stage 2: Classifying staff roles...")
    staff_model = YOLO(CUSTOM_MODEL_PATH)

    classified_persons = []
    for i, (x1, y1, x2, y2) in enumerate(person_detections):
        # Extract person crop
        person_crop = image[y1:y2, x1:x2]

        # Run classification
        classification = staff_model(person_crop, conf=STAFF_CONF_THRESHOLD)

        # Process results
        staff_class = 'unknown'
        confidence = 0.0

        for result in classification:
            if result.boxes is not None:
                for box in result.boxes:
                    conf = box.conf[0].cpu().numpy()
                    class_id = int(box.cls[0].cpu().numpy())
                    # Assuming class 0=waiter, 1=customer
                    staff_class = ['waiter', 'customer'][class_id] if class_id < 2 else 'unknown'
                    confidence = float(conf)
                    break

        classified_persons.append({
            'bbox': (x1, y1, x2, y2),
            'class': staff_class,
            'confidence': confidence
        })

        print(f"   Person {i+1}: {staff_class} ({confidence:.1%})")

    # Draw classified results
    annotated = image.copy()
    for det in classified_persons:
        x1, y1, x2, y2 = det['bbox']
        color = COLORS.get(det['class'], COLORS['unknown'])

        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

        label = f"{det['class']}: {det['confidence']:.1%}" if det['confidence'] > 0 else det['class']
        cv2.putText(annotated, label, (x1, y1-5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    # Save result
    output_path = "results/staff_classification.jpg"
    cv2.imwrite(output_path, annotated)
    print(f"\n💾 Saved staff classification result: {output_path}")

    # Summary
    print(f"\n📊 Classification Summary:")
    waiters = sum(1 for p in classified_persons if p['class'] == 'waiter')
    customers = sum(1 for p in classified_persons if p['class'] == 'customer')
    unknown = sum(1 for p in classified_persons if p['class'] == 'unknown')

    print(f"   👨‍🍳 Waiters: {waiters}")
    print(f"   👥 Customers: {customers}")
    print(f"   ❓ Unknown: {unknown}")

    return classified_persons

def main():
    """Main testing function"""
    print("\n" + "🎯"*30)
    print(" ASEOfSmartICE MODEL TESTING SUITE")
    print(" Testing with camera screenshot")
    print("🎯"*30)

    # Check if test image exists
    if not os.path.exists(TEST_IMAGE_PATH):
        print(f"\n❌ Test image not found: {TEST_IMAGE_PATH}")
        print("   Please ensure the screenshot has been saved to test-model/test_camera_image.jpg")
        return 1

    # Display image info
    image = cv2.imread(TEST_IMAGE_PATH)
    if image is not None:
        print(f"\n📸 Test Image: {TEST_IMAGE_PATH}")
        print(f"📏 Resolution: {image.shape[1]}x{image.shape[0]} pixels")
        print(f"📊 Channels: {image.shape[2]}")

    # Test 1: General YOLO detection
    print("\n" + "─"*60)
    general_detections = test_general_yolo_detection()

    # Test 2: Person-specific detection
    print("\n" + "─"*60)
    person_detections = test_person_detection()

    # Test 3: Staff classification (if model exists)
    print("\n" + "─"*60)
    staff_classifications = test_staff_classification()

    # Final summary
    print("\n" + "="*60)
    print("✅ TESTING COMPLETE")
    print("="*60)

    if general_detections:
        print(f"✓ General YOLO: {len(general_detections)} objects detected")

    if person_detections:
        print(f"✓ Person Detection: {len(person_detections)} persons found")

    if staff_classifications:
        print(f"✓ Staff Classification: Processed {len(staff_classifications)} persons")
    else:
        print("⚠ Staff Classification: Model not available (needs training)")

    print(f"\n📂 Results saved in: test-model/results/")
    print("   - general_yolo_detection.jpg")
    print("   - person_detection.jpg")
    print("   - staff_classification.jpg (if model available)")

    return 0

if __name__ == "__main__":
    exit(main())