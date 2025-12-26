#!/usr/bin/env python3
"""
ASEOfSmartICE Staff/Customer Detector V5 Performance Testing
Version: 1.0.0 - YOLO11s Two-Class Detection

Purpose:
- Test newly trained YOLO11s staff/customer detection model
- Measure inference speed (FPS) for performance benchmarking
- Generate visual outputs with colored bounding boxes
- Compare performance with V4 single-class approach

Model: YOLO11s Detection (~20MB)
- Direct staff AND customer detection with bounding boxes
- Two classes: staff (green), customer (red)
- Trained with Gemini-optimized augmentation parameters
- 800x800 input size for better accuracy

Created: 2025-12-26
"""

import cv2
import numpy as np
from ultralytics import YOLO
import os
from pathlib import Path
import time
import glob

# Model configuration
MODEL_PATH = "models/staff_customer_detector.pt"

# Detection parameters
CONF_THRESHOLD = 0.5  # Confidence threshold for detection
IOU_THRESHOLD = 0.45  # IOU threshold for NMS

# Visual configuration - Two classes
STAFF_COLOR = (0, 255, 0)      # Green for staff
CUSTOMER_COLOR = (0, 0, 255)   # Red for customer
BOX_THICKNESS = 2
FONT_SCALE = 0.6
FONT_THICKNESS = 2

# Class names
CLASS_NAMES = {0: 'Staff', 1: 'Customer'}

# Performance tracking
class PerformanceTracker:
    """Track inference timing and FPS metrics"""
    def __init__(self):
        self.image_times = []
        self.video_frame_times = []
        self.staff_counts = []
        self.customer_counts = []

    def add_image_time(self, time_ms, staff_count, customer_count):
        """Record image inference time"""
        self.image_times.append(time_ms)
        self.staff_counts.append(staff_count)
        self.customer_counts.append(customer_count)

    def add_video_frame_time(self, time_ms):
        """Record video frame inference time"""
        self.video_frame_times.append(time_ms)

    def get_image_stats(self):
        """Get image processing statistics"""
        if not self.image_times:
            return None
        return {
            'avg_time_ms': np.mean(self.image_times),
            'min_time_ms': np.min(self.image_times),
            'max_time_ms': np.max(self.image_times),
            'total_images': len(self.image_times),
            'total_staff': sum(self.staff_counts),
            'total_customers': sum(self.customer_counts),
            'avg_staff': np.mean(self.staff_counts),
            'avg_customers': np.mean(self.customer_counts)
        }

    def get_video_stats(self):
        """Get video processing statistics"""
        if not self.video_frame_times:
            return None
        avg_time = np.mean(self.video_frame_times)
        fps = 1000.0 / avg_time if avg_time > 0 else 0
        return {
            'avg_time_ms': avg_time,
            'min_time_ms': np.min(self.video_frame_times),
            'max_time_ms': np.max(self.video_frame_times),
            'total_frames': len(self.video_frame_times),
            'fps': fps
        }

# Initialize performance tracker
perf_tracker = PerformanceTracker()

def load_model():
    """Load the YOLO11s staff/customer detection model"""
    print("=" * 80)
    print("Loading YOLO11s Staff/Customer Detection Model (V5)")
    print("=" * 80)

    if not os.path.exists(MODEL_PATH):
        print(f"ERROR: Model not found at {MODEL_PATH}")
        print("Please copy the trained model to models/staff_customer_detector.pt")
        return None

    print(f"Model Path: {MODEL_PATH}")

    # Load model
    start_time = time.time()
    model = YOLO(MODEL_PATH)
    load_time = (time.time() - start_time) * 1000

    print(f"Model Type: YOLO11s Detection (Two-Class)")
    print(f"Classes: Staff (0), Customer (1)")
    print(f"Load Time: {load_time:.1f}ms")
    print(f"Device: MPS (Apple Silicon) / CPU fallback")
    print("Model loaded successfully!\n")

    return model

def detect_staff_customer(model, image, verbose=True):
    """
    Detect staff and customers in image

    Args:
        model: YOLO model
        image: Input image (BGR format)
        verbose: Print detection details

    Returns:
        tuple: (detections list, inference_time_ms)
    """
    # Run inference with timing
    start_time = time.time()
    results = model(image, conf=CONF_THRESHOLD, iou=IOU_THRESHOLD, verbose=False)
    inference_time = (time.time() - start_time) * 1000  # Convert to ms

    detections = []
    staff_count = 0
    customer_count = 0

    for result in results:
        boxes = result.boxes
        if boxes is not None:
            for box in boxes:
                # Get box coordinates, confidence, and class
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                confidence = float(box.conf[0].cpu().numpy())
                class_id = int(box.cls[0].cpu().numpy())
                class_name = CLASS_NAMES.get(class_id, f"Unknown_{class_id}")

                detections.append({
                    'bbox': (int(x1), int(y1), int(x2), int(y2)),
                    'confidence': confidence,
                    'class_id': class_id,
                    'class_name': class_name
                })

                if class_id == 0:
                    staff_count += 1
                else:
                    customer_count += 1

                if verbose:
                    print(f"   {class_name} detected: confidence={confidence:.1%}")

    if verbose:
        print(f"   Total: {len(detections)} (Staff: {staff_count}, Customers: {customer_count})")
        print(f"   Inference time: {inference_time:.2f}ms")

    return detections, inference_time, staff_count, customer_count

def draw_detections(image, detections):
    """Draw bounding boxes and labels on image"""
    annotated = image.copy()

    for detection in detections:
        x1, y1, x2, y2 = detection['bbox']
        confidence = detection['confidence']
        class_name = detection['class_name']
        class_id = detection['class_id']

        # Select color based on class
        color = STAFF_COLOR if class_id == 0 else CUSTOMER_COLOR

        # Draw bounding box
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, BOX_THICKNESS)

        # Prepare label
        label = f"{class_name}: {confidence:.1%}"

        # Draw label background
        label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, FONT_SCALE, FONT_THICKNESS)[0]
        cv2.rectangle(annotated,
                     (x1, y1 - label_size[1] - 10),
                     (x1 + label_size[0], y1),
                     color, -1)

        # Draw label text
        text_color = (0, 0, 0) if class_id == 0 else (255, 255, 255)
        cv2.putText(annotated, label,
                   (x1, y1 - 5),
                   cv2.FONT_HERSHEY_SIMPLEX, FONT_SCALE, text_color, FONT_THICKNESS)

    # Draw legend
    cv2.rectangle(annotated, (10, 10), (150, 70), (0, 0, 0), -1)
    cv2.putText(annotated, "Staff", (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.6, STAFF_COLOR, 2)
    cv2.putText(annotated, "Customer", (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, CUSTOMER_COLOR, 2)

    return annotated

def test_images(model, input_dir="test_images", output_dir="results/images"):
    """Test model on all images in test_images folder"""
    print("=" * 80)
    print("Testing on Images")
    print("=" * 80)

    # Try centralized test_images first, then local folder
    if not os.path.exists(input_dir):
        input_dir = "../test_images"

    # Find all images
    image_files = sorted(glob.glob(os.path.join(input_dir, "*.jpg")))

    if not image_files:
        print(f"No images found in {input_dir}")
        print("Please add test images to test_images/ folder")
        return False

    print(f"Found {len(image_files)} test images\n")

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    # Process each image
    for idx, image_path in enumerate(image_files, 1):
        print(f"[{idx}/{len(image_files)}] Processing: {os.path.basename(image_path)}")

        # Load image
        image = cv2.imread(image_path)
        if image is None:
            print(f"   ERROR: Could not load image")
            continue

        print(f"   Image size: {image.shape[1]}x{image.shape[0]}")

        # Detect staff and customers
        detections, inference_time, staff_count, customer_count = detect_staff_customer(model, image, verbose=True)

        # Track performance
        perf_tracker.add_image_time(inference_time, staff_count, customer_count)

        # Draw detections
        annotated = draw_detections(image, detections)

        # Save result
        output_filename = f"{Path(image_path).stem}_detected.jpg"
        output_path = os.path.join(output_dir, output_filename)
        cv2.imwrite(output_path, annotated)
        print(f"   Saved: {output_path}\n")

    print("Image testing completed!\n")
    return True

def test_video(model, video_path="test_videos/test_video.mp4", output_dir="results/videos"):
    """Test model on video and measure FPS"""
    print("=" * 80)
    print("Testing on Video")
    print("=" * 80)

    # Try local folder first, then parent
    if not os.path.exists(video_path):
        video_path = "../test_videos/test_video.mp4"

    if not os.path.exists(video_path):
        print(f"Video not found: {video_path}")
        print("Skipping video test...\n")
        return False

    print(f"Video Path: {video_path}")

    # Open video
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print("ERROR: Could not open video")
        return False

    # Get video properties
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    print(f"Video Properties:")
    print(f"   Resolution: {width}x{height}")
    print(f"   FPS: {fps}")
    print(f"   Total Frames: {total_frames}")
    print(f"\nProcessing video...")

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    # Setup video writer
    output_filename = f"{Path(video_path).stem}_detected.mp4"
    output_path = os.path.join(output_dir, output_filename)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    # Process frames
    frame_count = 0
    max_frames = min(300, total_frames)  # Process max 300 frames for testing

    print(f"Processing {max_frames} frames...\n")

    while frame_count < max_frames:
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1

        # Detect staff and customers
        detections, inference_time, _, _ = detect_staff_customer(model, frame, verbose=False)

        # Track performance
        perf_tracker.add_video_frame_time(inference_time)

        # Draw detections
        annotated = draw_detections(frame, detections)

        # Add FPS overlay
        current_fps = 1000.0 / inference_time if inference_time > 0 else 0
        cv2.putText(annotated, f"FPS: {current_fps:.1f}",
                   (width - 150, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

        # Write frame
        out.write(annotated)

        # Progress update every 30 frames
        if frame_count % 30 == 0:
            print(f"   Frame {frame_count}/{max_frames} - Inference: {inference_time:.2f}ms - FPS: {current_fps:.1f}")

    # Cleanup
    cap.release()
    out.release()

    print(f"\nVideo saved: {output_path}")
    print("Video testing completed!\n")

    return True

def generate_performance_report(output_dir="results"):
    """Generate detailed performance report"""
    print("=" * 80)
    print("Performance Report")
    print("=" * 80)

    report_lines = []
    report_lines.append("=" * 80)
    report_lines.append("YOLO11s Staff/Customer Detector V5 - Performance Test Report")
    report_lines.append("=" * 80)
    report_lines.append(f"Test Date: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"Model: YOLO11s Detection (Two-Class)")
    report_lines.append(f"Classes: Staff (0), Customer (1)")
    report_lines.append(f"Training: Gemini-optimized augmentation")
    report_lines.append("")

    # Image statistics
    image_stats = perf_tracker.get_image_stats()
    if image_stats:
        report_lines.append("IMAGE PROCESSING PERFORMANCE")
        report_lines.append("-" * 80)
        report_lines.append(f"Total Images Processed: {image_stats['total_images']}")
        report_lines.append(f"Average Inference Time: {image_stats['avg_time_ms']:.2f}ms")
        report_lines.append(f"Min Inference Time: {image_stats['min_time_ms']:.2f}ms")
        report_lines.append(f"Max Inference Time: {image_stats['max_time_ms']:.2f}ms")
        report_lines.append("")
        report_lines.append("DETECTION COUNTS")
        report_lines.append(f"Total Staff Detected: {image_stats['total_staff']}")
        report_lines.append(f"Total Customers Detected: {image_stats['total_customers']}")
        report_lines.append(f"Average Staff per Image: {image_stats['avg_staff']:.1f}")
        report_lines.append(f"Average Customers per Image: {image_stats['avg_customers']:.1f}")
        report_lines.append("")

    # Video statistics
    video_stats = perf_tracker.get_video_stats()
    if video_stats:
        report_lines.append("VIDEO PROCESSING PERFORMANCE")
        report_lines.append("-" * 80)
        report_lines.append(f"Total Frames Processed: {video_stats['total_frames']}")
        report_lines.append(f"Average Inference Time: {video_stats['avg_time_ms']:.2f}ms")
        report_lines.append(f"Min Inference Time: {video_stats['min_time_ms']:.2f}ms")
        report_lines.append(f"Max Inference Time: {video_stats['max_time_ms']:.2f}ms")
        report_lines.append(f"Average FPS: {video_stats['fps']:.1f}")
        report_lines.append("")

    # V5 vs V4 comparison
    report_lines.append("COMPARISON WITH V4 (Single-Class Staff Only)")
    report_lines.append("-" * 80)
    report_lines.append("| Feature             | V4 (YOLO11n)    | V5 (YOLO11s)    |")
    report_lines.append("|---------------------|-----------------|-----------------|")
    report_lines.append("| Classes             | 1 (staff only)  | 2 (staff+cust)  |")
    report_lines.append("| Model Size          | ~5.4MB          | ~20MB           |")
    report_lines.append("| Input Size          | 640x640         | 800x800         |")
    report_lines.append("| Architecture        | YOLO11n (nano)  | YOLO11s (small) |")
    report_lines.append("")

    # Summary
    report_lines.append("SUMMARY")
    report_lines.append("-" * 80)

    if video_stats:
        if video_stats['fps'] >= 30:
            report_lines.append("✓ Real-time capable: FPS >= 30")
        else:
            report_lines.append("✗ Not real-time: FPS < 30 (consider smaller model)")

    if image_stats:
        if image_stats['avg_time_ms'] <= 20:
            report_lines.append("✓ Inference speed: Excellent (<= 20ms)")
        elif image_stats['avg_time_ms'] <= 50:
            report_lines.append("✓ Inference speed: Good (<= 50ms)")
        else:
            report_lines.append("⚠ Inference speed: Acceptable (> 50ms)")

    report_lines.append("")
    report_lines.append("TEST CONFIGURATION")
    report_lines.append("-" * 80)
    report_lines.append(f"Confidence Threshold: {CONF_THRESHOLD}")
    report_lines.append(f"IOU Threshold: {IOU_THRESHOLD}")
    report_lines.append("")
    report_lines.append("=" * 80)

    # Print to console
    for line in report_lines:
        print(line)

    # Save to file
    os.makedirs(output_dir, exist_ok=True)
    report_path = os.path.join(output_dir, "performance_report.txt")
    with open(report_path, 'w') as f:
        f.write('\n'.join(report_lines))

    print(f"\nReport saved: {report_path}\n")

def main():
    """Main test execution"""
    print("\n")
    print("*" * 80)
    print("*" + " " * 78 + "*")
    print("*" + "  YOLO11s Staff/Customer Detector V5 - Performance Testing Suite".center(78) + "*")
    print("*" + " " * 78 + "*")
    print("*" * 80)
    print("\n")

    # Load model
    model = load_model()
    if model is None:
        print("Failed to load model. Exiting...")
        return 1

    # Test on images
    test_images(model)

    # Test on video
    test_video(model)

    # Generate performance report
    generate_performance_report()

    print("*" * 80)
    print("*" + " " * 78 + "*")
    print("*" + "  All Tests Completed Successfully!".center(78) + "*")
    print("*" + " " * 78 + "*")
    print("*" + "  Check results/ folder for annotated outputs and performance report".center(78) + "*")
    print("*" + " " * 78 + "*")
    print("*" * 80)
    print("\n")

    return 0

if __name__ == "__main__":
    exit(main())
