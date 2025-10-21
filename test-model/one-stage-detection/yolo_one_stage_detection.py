#!/usr/bin/env python3
"""
ASEOfSmartICE One-Stage Person Detection Script
Version: 2.0.0 - Base YOLO person detection testing

Purpose:
- Test base YOLO model (YOLOv8s) for person detection accuracy
- Evaluate how well YOLO detects people in restaurant camera footage
- No classification (waiter/customer) - just raw person detection

Model: yolov8s.pt (COCO-trained, class 0 = person)
- Better performance than yolov8n (nano)
- Standard detection without custom training
"""

import cv2
import numpy as np
from ultralytics import YOLO
import os
from pathlib import Path
import argparse
import time
import glob

# Model path and configuration
DETECTION_MODEL = "models/yolov8s.pt"  # Base YOLO small model (better than nano)

# Detection parameters
CONF_THRESHOLD = 0.3           # Confidence threshold for person detection
MIN_PERSON_SIZE = 50           # Minimum person width/height in pixels

# Visual configuration
PERSON_COLOR = (0, 255, 0)     # Green for all detected persons

def load_model():
    """Load the YOLO detection model"""
    print("📦 Loading YOLO model...")

    print(f"   Loading model: {DETECTION_MODEL}")
    print(f"   Model type: YOLOv8s (COCO-trained, person detection)")
    model = YOLO(DETECTION_MODEL)

    print("✅ Model loaded successfully!")
    return model

def detect_persons(model, image):
    """
    Detect all persons in the image using base YOLO model

    Args:
        model: YOLO model for person detection
        image: Input image

    Returns:
        list: Detection results with bounding boxes and confidence scores
    """
    print("🔍 Running person detection...")

    start_time = time.time()
    results = model(image, conf=CONF_THRESHOLD, verbose=False)
    inference_time = (time.time() - start_time) * 1000  # ms

    detections = []
    for result in results:
        boxes = result.boxes
        if boxes is not None:
            for box in boxes:
                class_id = int(box.cls[0].cpu().numpy())

                # Only process person class (class 0 in COCO)
                if class_id == 0:
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    confidence = box.conf[0].cpu().numpy()

                    # Filter by minimum size
                    width = x2 - x1
                    height = y2 - y1
                    if width >= MIN_PERSON_SIZE and height >= MIN_PERSON_SIZE:
                        detections.append({
                            'bbox': (int(x1), int(y1), int(x2), int(y2)),
                            'confidence': confidence
                        })
                        print(f"   Detected person: {confidence:.1%}")

    print(f"   Found {len(detections)} person(s)")
    print(f"   Inference time: {inference_time:.1f}ms")

    # Store inference time
    if detections:
        detections[0]['_inference_time'] = inference_time

    return detections

def draw_detections(image, detections):
    """Draw bounding boxes and labels on the image"""
    annotated_image = image.copy()

    for detection in detections:
        x1, y1, x2, y2 = detection['bbox']
        confidence = detection['confidence']

        # Draw bounding box
        cv2.rectangle(annotated_image, (x1, y1), (x2, y2), PERSON_COLOR, 2)

        # Prepare label
        label = f"Person: {confidence:.1%}"

        # Draw label background
        label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
        cv2.rectangle(annotated_image,
                     (x1, y1 - label_size[1] - 10),
                     (x1 + label_size[0], y1),
                     PERSON_COLOR, -1)

        # Draw label text
        cv2.putText(annotated_image, label,
                   (x1, y1 - 5),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    return annotated_image

def print_detection_summary(detections):
    """Print summary of detection results"""
    if not detections:
        print("❌ No persons detected")
        return

    print(f"\n📊 Detection Summary:")
    print(f"   👥 Total persons detected: {len(detections)}")

    # Show confidence distribution
    confidences = [d['confidence'] for d in detections if '_inference_time' not in d]
    if confidences:
        avg_conf = sum(confidences) / len(confidences)
        min_conf = min(confidences)
        max_conf = max(confidences)
        print(f"   📈 Confidence: avg={avg_conf:.1%}, min={min_conf:.1%}, max={max_conf:.1%}")

    # Get inference time if available
    if detections and '_inference_time' in detections[0]:
        inference_time = detections[0]['_inference_time']
        print(f"\n⏱️  Performance:")
        print(f"   Total inference time: {inference_time:.1f}ms")

def analyze_image(image_path, output_dir="results"):
    """Main function to analyze an image with person detection"""
    print(f"\n{'='*60}")
    print(f"🎯 Base YOLO Person Detection Test")
    print(f"{'='*60}")
    print(f"📸 Image: {os.path.basename(image_path)}")

    # Load model (only once for all images)
    if not hasattr(analyze_image, 'model'):
        analyze_image.model = load_model()
        if analyze_image.model is None:
            return False

    model = analyze_image.model

    # Load image
    if not os.path.exists(image_path):
        print(f"❌ Image not found: {image_path}")
        return False

    image = cv2.imread(image_path)
    if image is None:
        print(f"❌ Could not load image: {image_path}")
        return False

    print(f"📏 Image size: {image.shape[1]}x{image.shape[0]}")

    # Detect persons
    detections = detect_persons(model, image)

    if not detections:
        print("❌ No persons detected in image")
        return False

    # Draw results
    annotated_image = draw_detections(image, detections)

    # Extract inference time before printing summary
    if detections and '_inference_time' in detections[0]:
        del detections[0]['_inference_time']

    print_detection_summary(detections)

    # Save result
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    result_filename = f"{Path(image_path).stem}_person_detected.jpg"
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
        description="Base YOLO person detection testing (YOLOv8s)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process single image
  python3 yolo_one_stage_detection.py --image ../test_images/test_image_two.jpg

  # Process all JPG images in test_images directory
  python3 yolo_one_stage_detection.py --batch

  # Custom confidence threshold
  python3 yolo_one_stage_detection.py --image ../test_images/test.jpg --conf 0.4
        """
    )
    parser.add_argument("--image", help="Path to input image")
    parser.add_argument("--batch", action="store_true",
                       help="Process all JPG images in test_images directory (../test_images)")
    parser.add_argument("--input_dir", default="../test_images",
                       help="Input directory for batch processing (default: ../test_images)")
    parser.add_argument("--output", default="results", help="Output directory")
    parser.add_argument("--conf", type=float, default=0.3,
                       help="Detection confidence threshold (default: 0.3)")

    args = parser.parse_args()

    # Update global threshold if specified
    global CONF_THRESHOLD
    CONF_THRESHOLD = args.conf

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
