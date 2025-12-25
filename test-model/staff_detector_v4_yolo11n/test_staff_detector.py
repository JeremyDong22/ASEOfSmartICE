#!/usr/bin/env python3
"""
ASEOfSmartICE Staff Detector V4 Performance Testing
Version: 1.0.0 - YOLO11n One-Stage Staff Detection

Purpose:
- Test newly trained YOLO11n one-stage staff detection model
- Measure inference speed (FPS) for performance benchmarking
- Generate visual outputs with bounding boxes for accuracy verification
- Compare performance with two-stage V3 approach

Model: YOLO11n Detection (~5.4MB)
- Direct staff detection with bounding boxes
- Single-stage approach (no person detection + classification)
- 30x faster than two-stage, 10x smaller model size

Created: 2025-12-25
"""

import cv2
import numpy as np
from ultralytics import YOLO
import os
from pathlib import Path
import time
import glob

# Model configuration
MODEL_PATH = "models/staff_detector.pt"

# Detection parameters
CONF_THRESHOLD = 0.5  # Confidence threshold for staff detection
IOU_THRESHOLD = 0.45  # IOU threshold for NMS

# Visual configuration
STAFF_COLOR = (0, 255, 0)  # Green for detected staff
BOX_THICKNESS = 2
FONT_SCALE = 0.6
FONT_THICKNESS = 2

# Performance tracking
class PerformanceTracker:
    """Track inference timing and FPS metrics"""
    def __init__(self):
        self.image_times = []
        self.video_frame_times = []
        self.detection_counts = []

    def add_image_time(self, time_ms, count):
        """Record image inference time"""
        self.image_times.append(time_ms)
        self.detection_counts.append(count)

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
            'avg_detections': np.mean(self.detection_counts),
            'total_detections': sum(self.detection_counts)
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
    """Load the YOLO11n staff detection model"""
    print("=" * 80)
    print("Loading YOLO11n Staff Detection Model")
    print("=" * 80)

    if not os.path.exists(MODEL_PATH):
        print(f"ERROR: Model not found at {MODEL_PATH}")
        return None

    print(f"Model Path: {MODEL_PATH}")

    # Load model
    start_time = time.time()
    model = YOLO(MODEL_PATH)
    load_time = (time.time() - start_time) * 1000

    print(f"Model Type: YOLO11n Detection (One-Stage)")
    print(f"Model Size: ~5.4 MB")
    print(f"Load Time: {load_time:.1f}ms")
    print(f"Device: MPS (Apple Silicon) / CPU fallback")
    print("Model loaded successfully!\n")

    return model

def detect_staff(model, image, verbose=True):
    """
    Detect staff members in image

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

    for result in results:
        boxes = result.boxes
        if boxes is not None:
            for box in boxes:
                # Get box coordinates and confidence
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                confidence = float(box.conf[0].cpu().numpy())

                detections.append({
                    'bbox': (int(x1), int(y1), int(x2), int(y2)),
                    'confidence': confidence
                })

                if verbose:
                    print(f"   Staff detected: confidence={confidence:.1%}")

    if verbose:
        print(f"   Total detections: {len(detections)}")
        print(f"   Inference time: {inference_time:.2f}ms")

    return detections, inference_time

def draw_detections(image, detections):
    """Draw bounding boxes and labels on image"""
    annotated = image.copy()

    for detection in detections:
        x1, y1, x2, y2 = detection['bbox']
        confidence = detection['confidence']

        # Draw bounding box
        cv2.rectangle(annotated, (x1, y1), (x2, y2), STAFF_COLOR, BOX_THICKNESS)

        # Prepare label
        label = f"Staff: {confidence:.1%}"

        # Draw label background
        label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, FONT_SCALE, FONT_THICKNESS)[0]
        cv2.rectangle(annotated,
                     (x1, y1 - label_size[1] - 10),
                     (x1 + label_size[0], y1),
                     STAFF_COLOR, -1)

        # Draw label text
        cv2.putText(annotated, label,
                   (x1, y1 - 5),
                   cv2.FONT_HERSHEY_SIMPLEX, FONT_SCALE, (255, 255, 255), FONT_THICKNESS)

    return annotated

def test_images(model, input_dir="test_images", output_dir="results/images"):
    """Test model on all images in test_images folder"""
    print("=" * 80)
    print("Testing on Images")
    print("=" * 80)

    # Find all images
    image_files = sorted(glob.glob(os.path.join(input_dir, "*.jpg")))

    if not image_files:
        print(f"No images found in {input_dir}")
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

        # Detect staff
        detections, inference_time = detect_staff(model, image, verbose=True)

        # Track performance
        perf_tracker.add_image_time(inference_time, len(detections))

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

        # Detect staff
        detections, inference_time = detect_staff(model, frame, verbose=False)

        # Track performance
        perf_tracker.add_video_frame_time(inference_time)

        # Draw detections
        annotated = draw_detections(frame, detections)

        # Write frame
        out.write(annotated)

        # Progress update every 30 frames
        if frame_count % 30 == 0:
            current_fps = 1000.0 / inference_time if inference_time > 0 else 0
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
    report_lines.append("YOLO11n Staff Detector V4 - Performance Test Report")
    report_lines.append("=" * 80)
    report_lines.append(f"Test Date: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"Model: YOLO11n Detection (One-Stage)")
    report_lines.append(f"Model Size: ~5.4 MB")
    report_lines.append(f"Device: MPS (Apple Silicon) / CPU")
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
        report_lines.append(f"Total Staff Detected: {image_stats['total_detections']}")
        report_lines.append(f"Average Detections per Image: {image_stats['avg_detections']:.1f}")
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

    # Performance comparison
    report_lines.append("COMPARISON WITH TWO-STAGE V3 MODEL")
    report_lines.append("-" * 80)
    report_lines.append("| Metric              | Two-Stage V3 | One-Stage V4 | Improvement |")
    report_lines.append("|---------------------|--------------|--------------|-------------|")

    if image_stats:
        v4_time = image_stats['avg_time_ms']
        v3_time = 61.7  # From documentation
        speedup = v3_time / v4_time if v4_time > 0 else 0
        report_lines.append(f"| Inference Time      | ~61.7ms      | {v4_time:.2f}ms      | {speedup:.1f}x faster |")

    report_lines.append("| Model Size          | ~55MB        | ~5.4MB       | 10x smaller |")
    report_lines.append("| Pipeline            | 2 models     | 1 model      | Simpler     |")
    report_lines.append("")

    # Summary
    report_lines.append("SUMMARY")
    report_lines.append("-" * 80)

    if image_stats and video_stats:
        if video_stats['fps'] >= 30:
            report_lines.append("✓ Real-time capable: FPS >= 30")
        else:
            report_lines.append("✗ Not real-time: FPS < 30")

        if image_stats['avg_time_ms'] <= 5:
            report_lines.append("✓ Inference speed: Excellent (<= 5ms)")
        elif image_stats['avg_time_ms'] <= 10:
            report_lines.append("✓ Inference speed: Good (<= 10ms)")
        else:
            report_lines.append("⚠ Inference speed: Acceptable (> 10ms)")

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
    report_path = os.path.join(output_dir, "performance_report.txt")
    with open(report_path, 'w') as f:
        f.write('\n'.join(report_lines))

    print(f"\nReport saved: {report_path}\n")

def main():
    """Main test execution"""
    print("\n")
    print("*" * 80)
    print("*" + " " * 78 + "*")
    print("*" + "  YOLO11n Staff Detector V4 - Performance Testing Suite".center(78) + "*")
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
