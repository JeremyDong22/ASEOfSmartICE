#!/usr/bin/env python3
"""
ASEOfSmartICE Two-Stage Detection + Area Division
Version: 1.0.0 - ROI-based staff detection for specific service areas

Features:
- Interactive polygon ROI drawing for monitoring areas
- Two-stage detection (YOLOv8s + custom classifier)
- Filters detections to only people inside ROI
- Batch processing of images from same camera

This script allows you to define specific service division areas
and only detect/classify people within those boundaries.
"""

import cv2
import numpy as np
from ultralytics import YOLO
import os
from pathlib import Path
import argparse
import time
import glob
import json

# Model paths and configuration
PERSON_DETECTOR_MODEL = "models/yolov8s.pt"
STAFF_CLASSIFIER_MODEL = "models/waiter_customer_advanced.pt"

# Detection parameters
PERSON_CONF_THRESHOLD = 0.3
STAFF_CONF_THRESHOLD = 0.5
MIN_PERSON_SIZE = 40

# ROI configuration
ROI_CONFIG_FILE = "roi_config.json"

# Visual configuration
COLORS = {
    'waiter': (0, 255, 0),      # Green
    'customer': (0, 0, 255),    # Red
    'roi': (255, 255, 0)        # Cyan for ROI
}
CLASS_NAMES = ['waiter', 'customer']

# Global variables for ROI drawing
roi_points = []
drawing_complete = False

def mouse_callback(event, x, y, flags, param):
    """Mouse callback for ROI polygon drawing"""
    global roi_points, drawing_complete
    
    if drawing_complete:
        return
    
    if event == cv2.EVENT_LBUTTONDOWN:
        roi_points.append((x, y))
        print(f"   Point {len(roi_points)}: ({x}, {y})")

def draw_roi_on_image(image, points, color=(255, 255, 0), thickness=2):
    """Draw ROI polygon on image"""
    if len(points) < 2:
        return image
    
    img_copy = image.copy()
    
    # Draw lines between points
    for i in range(len(points)):
        pt1 = points[i]
        pt2 = points[(i + 1) % len(points)]
        cv2.line(img_copy, pt1, pt2, color, thickness)
    
    # Draw points
    for pt in points:
        cv2.circle(img_copy, pt, 5, color, -1)
    
    # Fill polygon with semi-transparent overlay
    if len(points) >= 3:
        overlay = img_copy.copy()
        pts = np.array(points, np.int32)
        cv2.fillPoly(overlay, [pts], color)
        cv2.addWeighted(overlay, 0.2, img_copy, 0.8, 0, img_copy)
    
    return img_copy

def setup_roi(reference_image_path):
    """Interactive ROI setup - draw polygon on reference image"""
    global roi_points, drawing_complete

    print("\n" + "="*60)
    print("🎯 ROI Setup Mode")
    print("="*60)
    print(f"📸 Reference image: {reference_image_path}")

    # Load reference image
    if not os.path.exists(reference_image_path):
        print(f"❌ Reference image not found: {reference_image_path}")
        return None

    image = cv2.imread(reference_image_path)
    if image is None:
        print(f"❌ Could not load image: {reference_image_path}")
        return None

    print(f"📏 Image size: {image.shape[1]}x{image.shape[0]}")
    print("\n📝 Instructions:")
    print("   1. Left-click to add polygon points")
    print("   2. Cmd+Z / Ctrl+Z to undo last point")
    print("   3. Cmd+S / Ctrl+S to complete and save (minimum 3 points)")
    print("   4. Press 'r' to reset and start over")
    print("   5. Press 'q' to quit without saving")
    print("\nℹ️  Define the area where you want to monitor staff...")

    roi_points = []
    drawing_complete = False

    cv2.namedWindow('ROI Setup', cv2.WINDOW_NORMAL)
    cv2.setMouseCallback('ROI Setup', mouse_callback)

    while True:
        display_img = draw_roi_on_image(image, roi_points)

        # Add instruction text on image
        cv2.putText(display_img, f"Points: {len(roi_points)} | Cmd+S to save | Cmd+Z to undo | 'r' to reset",
                   (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        cv2.imshow('ROI Setup', display_img)
        key = cv2.waitKey(1) & 0xFF

        # Cmd+S / Ctrl+S to save (key 19 is Ctrl+S, key 115 is 's')
        if key == 19 or key == ord('s'):
            if len(roi_points) >= 3:
                # Save ROI to file
                roi_data = {
                    'points': roi_points,
                    'image_size': [image.shape[1], image.shape[0]],
                    'reference_image': reference_image_path
                }
                with open(ROI_CONFIG_FILE, 'w') as f:
                    json.dump(roi_data, f, indent=2)
                print(f"\n✅ ROI polygon completed with {len(roi_points)} points")
                print(f"💾 ROI saved to: {ROI_CONFIG_FILE}")
                cv2.destroyAllWindows()
                return roi_points
            else:
                print(f"\n⚠️  Need at least 3 points (currently {len(roi_points)})")

        # Cmd+Z / Ctrl+Z to undo (key 26 is Ctrl+Z)
        elif key == 26 or key == ord('z'):
            if roi_points:
                removed_point = roi_points.pop()
                print(f"   ↶ Undo: Removed point {removed_point} ({len(roi_points)} points remaining)")
            else:
                print("   ⚠️  No points to undo")

        # 'r' to reset all
        elif key == ord('r'):
            roi_points = []
            drawing_complete = False
            print("\n🔄 Reset ROI - start drawing again")

        # 'q' to quit
        elif key == ord('q'):
            print("\n❌ ROI setup cancelled")
            cv2.destroyAllWindows()
            return None

    cv2.destroyAllWindows()
    return roi_points

def load_roi():
    """Load ROI from config file"""
    if not os.path.exists(ROI_CONFIG_FILE):
        print(f"❌ ROI config not found: {ROI_CONFIG_FILE}")
        print("   Run with --setup-roi first to define monitoring area")
        return None
    
    with open(ROI_CONFIG_FILE, 'r') as f:
        roi_data = json.load(f)
    
    points = [tuple(pt) for pt in roi_data['points']]
    print(f"✅ Loaded ROI with {len(points)} points from {ROI_CONFIG_FILE}")
    return points

def point_in_polygon(point, polygon):
    """Check if point is inside polygon using ray casting algorithm"""
    x, y = point
    n = len(polygon)
    inside = False
    
    p1x, p1y = polygon[0]
    for i in range(1, n + 1):
        p2x, p2y = polygon[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    
    return inside

def load_models():
    """Load both detection models"""
    print("📦 Loading detection models...")
    
    print(f"   Loading person detector: {PERSON_DETECTOR_MODEL}")
    person_detector = YOLO(PERSON_DETECTOR_MODEL)
    
    if not os.path.exists(STAFF_CLASSIFIER_MODEL):
        print(f"❌ Staff classifier not found: {STAFF_CLASSIFIER_MODEL}")
        return None, None
    
    print(f"   Loading staff classifier: {STAFF_CLASSIFIER_MODEL}")
    staff_classifier = YOLO(STAFF_CLASSIFIER_MODEL)
    
    print("✅ Both models loaded successfully!")
    return person_detector, staff_classifier

def detect_persons(person_detector, image):
    """Stage 1: Detect all persons"""
    results = person_detector(image, conf=PERSON_CONF_THRESHOLD, classes=[0], verbose=False)
    
    person_detections = []
    for result in results:
        boxes = result.boxes
        if boxes is not None:
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                confidence = box.conf[0].cpu().numpy()
                
                width = x2 - x1
                height = y2 - y1
                if width >= MIN_PERSON_SIZE and height >= MIN_PERSON_SIZE:
                    person_detections.append({
                        'bbox': (int(x1), int(y1), int(x2), int(y2)),
                        'confidence': confidence,
                        'center': (int((x1 + x2) / 2), int((y1 + y2) / 2))
                    })
    
    return person_detections

def filter_by_roi(detections, roi_polygon):
    """Filter detections - keep only those inside ROI"""
    if roi_polygon is None:
        return detections
    
    filtered = []
    for detection in detections:
        center = detection['center']
        if point_in_polygon(center, roi_polygon):
            filtered.append(detection)
    
    return filtered

def classify_persons(staff_classifier, image, person_detections):
    """Stage 2: Classify each detected person"""
    classified_detections = []
    
    for detection in person_detections:
        x1, y1, x2, y2 = detection['bbox']
        person_crop = image[y1:y2, x1:x2]
        
        if person_crop.shape[0] < 20 or person_crop.shape[1] < 20:
            classified_detections.append({
                'class': 'unknown',
                'confidence': 0.0,
                'bbox': detection['bbox'],
                'center': detection['center'],
                'person_confidence': detection['confidence']
            })
            continue
        
        classification_results = staff_classifier(person_crop, conf=STAFF_CONF_THRESHOLD, verbose=False)
        
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
                            'bbox': detection['bbox'],
                            'center': detection['center'],
                            'person_confidence': detection['confidence']
                        }
        
        if best_classification:
            classified_detections.append(best_classification)
        else:
            classified_detections.append({
                'class': 'unknown',
                'confidence': 0.0,
                'bbox': detection['bbox'],
                'center': detection['center'],
                'person_confidence': detection['confidence']
            })
    
    return classified_detections

def draw_detections(image, detections, roi_polygon=None):
    """Draw bounding boxes, labels, and ROI on image"""
    annotated_image = image.copy()
    
    # Draw ROI first (background layer)
    if roi_polygon is not None:
        annotated_image = draw_roi_on_image(annotated_image, roi_polygon, COLORS['roi'], 3)
    
    # Draw detections
    for detection in detections:
        x1, y1, x2, y2 = detection['bbox']
        class_name = detection['class']
        confidence = detection['confidence']
        
        color = COLORS.get(class_name, (128, 128, 128))
        
        cv2.rectangle(annotated_image, (x1, y1), (x2, y2), color, 2)
        
        if confidence > 0:
            label = f"{class_name}: {confidence:.1%}"
        else:
            label = f"{class_name}"
        
        label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
        cv2.rectangle(annotated_image,
                     (x1, y1 - label_size[1] - 10),
                     (x1 + label_size[0], y1),
                     color, -1)
        
        cv2.putText(annotated_image, label,
                   (x1, y1 - 5),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    
    return annotated_image

def analyze_image(image_path, person_detector, staff_classifier, roi_polygon, output_dir="results"):
    """Main detection pipeline with ROI filtering"""
    print(f"\n{'='*60}")
    print(f"🎯 Two-Stage Detection + ROI Filtering")
    print(f"{'='*60}")
    print(f"📸 Image: {os.path.basename(image_path)}")
    
    # Load image
    if not os.path.exists(image_path):
        print(f"❌ Image not found: {image_path}")
        return False
    
    image = cv2.imread(image_path)
    if image is None:
        print(f"❌ Could not load image: {image_path}")
        return False
    
    print(f"📏 Image size: {image.shape[1]}x{image.shape[0]}")
    
    # Stage 1: Detect all persons
    print("🔍 Stage 1: Detecting persons...")
    person_detections = detect_persons(person_detector, image)
    print(f"   Found {len(person_detections)} person(s) total")
    
    # Filter by ROI
    if roi_polygon:
        print("📐 Filtering by ROI...")
        roi_filtered = filter_by_roi(person_detections, roi_polygon)
        print(f"   {len(roi_filtered)} person(s) inside ROI")
        print(f"   {len(person_detections) - len(roi_filtered)} person(s) outside ROI (ignored)")
        person_detections = roi_filtered
    
    if not person_detections:
        print("❌ No persons detected inside ROI")
        return False
    
    # Stage 2: Classify persons
    print("🎯 Stage 2: Classifying staff roles...")
    classified_detections = classify_persons(staff_classifier, image, person_detections)
    
    for i, det in enumerate(classified_detections):
        print(f"   Person {i+1}: {det['class']} ({det['confidence']:.1%})")
    
    # Summary
    waiter_count = sum(1 for d in classified_detections if d['class'] == 'waiter')
    customer_count = sum(1 for d in classified_detections if d['class'] == 'customer')
    unknown_count = sum(1 for d in classified_detections if d['class'] == 'unknown')
    
    print(f"\n📊 Detection Summary:")
    print(f"   👨‍🍳 Waiters: {waiter_count}")
    print(f"   👥 Customers: {customer_count}")
    print(f"   ❓ Unknown: {unknown_count}")
    print(f"   📋 Total: {len(classified_detections)}")
    
    # Draw results
    annotated_image = draw_detections(image, classified_detections, roi_polygon)
    
    # Save result
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    result_filename = f"{Path(image_path).stem}_roi_detected.jpg"
    result_path = output_path / result_filename
    
    cv2.imwrite(str(result_path), annotated_image)
    print(f"\n💾 Result saved: {result_path}")
    print("✅ Analysis complete!")
    
    return True

def process_all_images(test_images_dir, output_dir, person_detector, staff_classifier, roi_polygon):
    """Batch process all images in test_images folder"""
    print(f"\n🔍 Searching for JPG images in: {test_images_dir}")
    
    jpg_files = glob.glob(os.path.join(test_images_dir, "*.jpg"))
    jpg_files.extend(glob.glob(os.path.join(test_images_dir, "*.JPG")))
    
    if not jpg_files:
        print(f"❌ No JPG images found in {test_images_dir}")
        return False
    
    print(f"✅ Found {len(jpg_files)} JPG image(s)")
    
    success_count = 0
    for img_path in jpg_files:
        if analyze_image(img_path, person_detector, staff_classifier, roi_polygon, output_dir):
            success_count += 1
    
    print(f"\n{'='*60}")
    print(f"🎉 Batch Processing Complete!")
    print(f"   Successfully processed: {success_count}/{len(jpg_files)} images")
    print(f"{'='*60}")
    
    return success_count > 0

def main():
    """Main function - Interactive ROI setup then auto batch processing"""
    test_images_dir = "../test_images"
    output_dir = "results"

    # Find first image in test_images to use as reference for ROI
    test_images = glob.glob(os.path.join(test_images_dir, "*.jpg"))
    test_images.extend(glob.glob(os.path.join(test_images_dir, "*.JPG")))

    if not test_images:
        print(f"\n❌ No images found in {test_images_dir}/")
        print(f"   Please add images to {test_images_dir}/ first")
        return 1

    # Always start with ROI setup using first image
    reference_image = test_images[0]

    print("\n" + "="*60)
    print("🎯 Two-Stage Detection + Area Division")
    print("="*60)
    print(f"\n📂 Found {len(test_images)} image(s) in {test_images_dir}/")
    print(f"📸 Using {os.path.basename(reference_image)} for ROI setup\n")

    # Step 1: Setup ROI (always, every time)
    roi_polygon = setup_roi(reference_image)

    if roi_polygon is None:
        print("\n❌ ROI setup cancelled. Exiting.")
        return 1

    # Step 2: Load models
    print("\n" + "="*60)
    person_detector, staff_classifier = load_models()
    if person_detector is None or staff_classifier is None:
        return 1

    # Step 3: Auto batch process all images
    print("\n" + "="*60)
    print("🚀 Starting Batch Processing")
    print("="*60)
    success = process_all_images(test_images_dir, output_dir, person_detector, staff_classifier, roi_polygon)

    return 0 if success else 1

if __name__ == "__main__":
    exit(main())
