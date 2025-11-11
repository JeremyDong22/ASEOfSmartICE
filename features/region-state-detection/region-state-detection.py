#!/usr/bin/env python3
"""
ASEOfSmartICE Two-Stage Video Analysis with ROI + Alert System (YOLOv8m Edition)
Version: 4.0.0 - YOLOv8m-based detection for improved accuracy
Last Updated: 2025-10-30

Features:
- Interactive polygon ROI drawing for monitoring areas
- Two-stage detection (YOLOv8m + YOLO11n-cls)
- Filters detections to only people inside ROI
- Debounced waiter detection: Waiter must be present for 1s to count (prevents false positives)
- Alert system: Flash screen if no waiter in ROI for > 5s (production threshold)
- Performance tracking for real-time 2K video analysis

Changes from v3.3.0:
- v4.0.0 (2025-10-30): Upgraded from YOLOv8s to YOLOv8m for better person detection accuracy
  YOLOv8m has more parameters and better accuracy than YOLOv8s, at the cost of slightly slower speed

Version History:
- v4.0.0 (2025-10-30): YOLOv8m person detector for improved accuracy
- v3.3.0 (2025-10-26): Added 1s waiter debounce buffer, increased alert to 5s for production
- v3.2.0 (2025-10-26): Initial version with ROI and alert system
- v3.1.0 (2025-10-26): Base video analysis with performance tracking
- v3.0.0 (2025-10-26): YOLO11n-cls classification model integration

Author: ASEOfSmartICE Team
"""

# Reference: Copied from ../../test-model/two-stage-detection-yolo11-cls/yolov8m_yolo11ncls_roi_video_analysis.py
# Original version: 4.0.0 (2025-10-30)

import cv2
import numpy as np
from ultralytics import YOLO
import os
from pathlib import Path
import argparse
import time
import glob
import json
from collections import deque
from datetime import datetime

# Model paths and configuration
PERSON_DETECTOR_MODEL = "models/yolov8m.pt"
STAFF_CLASSIFIER_MODEL = "models/waiter_customer_classifier.pt"

# Detection parameters
PERSON_CONF_THRESHOLD = 0.3
STAFF_CONF_THRESHOLD = 0.5
MIN_PERSON_SIZE = 40

# ROI configuration
ROI_CONFIG_FILE = "roi_config.json"

# Alert configuration
WAITER_DEBOUNCE_SECONDS = 1.0   # Waiter must be present for 1s to count (prevents false positives)
ALERT_THRESHOLD_SECONDS = 5.0   # Flash if no waiter for > 5.0 seconds (production threshold)
FLASH_COLOR = (0, 0, 255)       # Red flash
FLASH_ALPHA = 0.3               # Flash transparency

# Visual configuration
COLORS = {
    'person': (255, 255, 0),        # Cyan for person detection (Stage 1)
    'waiter': (0, 255, 0),          # Green for waiters (Stage 2)
    'customer': (0, 0, 255),        # Red for customers (Stage 2)
    'unknown': (128, 128, 128),     # Gray for unknown (Stage 2, low confidence)
    'roi': (255, 255, 0)            # Cyan for ROI boundary
}

CLASS_NAMES = {0: 'customer', 1: 'waiter'}

# Global variables for ROI drawing
roi_points = []
drawing_complete = False


class PerformanceTracker:
    """Track processing performance metrics"""

    def __init__(self, window_size=30):
        self.window_size = window_size
        self.frame_times = deque(maxlen=window_size)
        self.stage1_times = deque(maxlen=window_size)
        self.stage2_times = deque(maxlen=window_size)
        self.person_counts = deque(maxlen=window_size)
        self.waiter_counts = deque(maxlen=window_size)
        self.customer_counts = deque(maxlen=window_size)

        self.total_frames = 0
        self.total_persons = 0
        self.total_waiters = 0
        self.total_customers = 0
        self.total_unknown = 0

        # Track total processing time separately
        self.total_processing_time = 0.0
        self.total_stage1_time = 0.0
        self.total_stage2_time = 0.0

        # Alert tracking
        self.total_alert_frames = 0
        self.max_alert_duration = 0.0
        self.current_alert_duration = 0.0

    def add_frame(self, frame_time, stage1_time, stage2_time, persons, waiters, customers, alert_active=False, alert_duration=0.0):
        """Add frame processing stats"""
        self.frame_times.append(frame_time)
        self.stage1_times.append(stage1_time)
        self.stage2_times.append(stage2_time)
        self.person_counts.append(persons)
        self.waiter_counts.append(waiters)
        self.customer_counts.append(customers)

        self.total_frames += 1
        self.total_persons += persons
        self.total_waiters += waiters
        self.total_customers += customers
        self.total_unknown += (persons - waiters - customers)

        # Track total processing time
        self.total_processing_time += frame_time
        self.total_stage1_time += stage1_time
        self.total_stage2_time += stage2_time

        # Track alerts
        if alert_active:
            self.total_alert_frames += 1
            self.current_alert_duration = alert_duration
            self.max_alert_duration = max(self.max_alert_duration, alert_duration)

    def get_current_fps(self):
        """Get current processing FPS (rolling average)"""
        if len(self.frame_times) == 0:
            return 0.0
        avg_time = sum(self.frame_times) / len(self.frame_times)
        return 1.0 / avg_time if avg_time > 0 else 0.0

    def get_avg_stage_times(self):
        """Get average stage processing times in ms"""
        avg_stage1 = (sum(self.stage1_times) / len(self.stage1_times) * 1000) if self.stage1_times else 0
        avg_stage2 = (sum(self.stage2_times) / len(self.stage2_times) * 1000) if self.stage2_times else 0
        return avg_stage1, avg_stage2

    def print_summary(self, video_duration, original_fps):
        """Print final processing summary"""
        total_time = self.total_processing_time
        avg_fps = self.total_frames / total_time if total_time > 0 else 0

        # Calculate average stage times from totals
        avg_stage1_ms = (self.total_stage1_time / self.total_frames * 1000) if self.total_frames > 0 else 0
        avg_stage2_ms = (self.total_stage2_time / self.total_frames * 1000) if self.total_frames > 0 else 0

        print(f"\n{'='*70}")
        print(f"📊 PROCESSING SUMMARY")
        print(f"{'='*70}")
        print(f"🎬 Video Information:")
        print(f"   Total frames processed: {self.total_frames}")
        print(f"   Original video FPS: {original_fps:.2f}")
        print(f"   Video duration: {video_duration:.2f}s")
        print(f"")
        print(f"⚡ Performance Metrics:")
        print(f"   Processing FPS: {avg_fps:.2f} fps")
        print(f"   Real-time ratio: {avg_fps/original_fps:.2%} (processing speed / original speed)")
        print(f"   Total processing time: {total_time:.2f}s")
        print(f"   Average frame time: {(total_time/self.total_frames)*1000:.1f}ms")
        print(f"")
        print(f"🔍 Stage Processing Times (average):")
        print(f"   Stage 1 (person detection): {avg_stage1_ms:.1f}ms")
        print(f"   Stage 2 (classification): {avg_stage2_ms:.1f}ms")
        print(f"   Total pipeline: {avg_stage1_ms + avg_stage2_ms:.1f}ms")
        print(f"")
        print(f"👥 Detection Results:")
        print(f"   Total persons detected: {self.total_persons}")
        print(f"   Total waiters: {self.total_waiters} ({self.total_waiters/self.total_persons*100:.1f}%)")
        print(f"   Total customers: {self.total_customers} ({self.total_customers/self.total_persons*100:.1f}%)")
        print(f"   Total unknown: {self.total_unknown} ({self.total_unknown/self.total_persons*100:.1f}%)")
        print(f"")
        print(f"🚨 Alert Statistics:")
        alert_percentage = (self.total_alert_frames / self.total_frames * 100) if self.total_frames > 0 else 0
        print(f"   Frames with alert: {self.total_alert_frames}/{self.total_frames} ({alert_percentage:.1f}%)")
        print(f"   Max consecutive alert: {self.max_alert_duration:.2f}s")
        print(f"")
        print(f"🎯 Real-Time Analysis for 2K Video:")

        current_frame_time = avg_stage1_ms + avg_stage2_ms
        print(f"   Current test video frame time: {current_frame_time:.1f}ms")
        print(f"")

        # Calculate 2K inference
        print(f"   📐 Resolution Analysis:")
        current_pixels = 1920 * 1080
        k2_pixels = 2560 * 1440
        pixel_ratio = k2_pixels / current_pixels

        print(f"      Test video: 1920×1080 ({current_pixels:,} pixels)")
        print(f"      2K video (QHD): 2560×1440 ({k2_pixels:,} pixels)")
        print(f"      Pixel ratio: {pixel_ratio:.2f}x more pixels in 2K")
        print(f"")

        estimated_2k_frame_time = current_frame_time * pixel_ratio
        estimated_2k_fps = 1000 / estimated_2k_frame_time

        print(f"   🔮 Estimated 2K Performance:")
        print(f"      Estimated frame time: {estimated_2k_frame_time:.1f}ms")
        print(f"      Estimated processing FPS: {estimated_2k_fps:.1f} fps")
        print(f"{'='*70}\n")


def mouse_callback(event, x, y, flags, param):
    """Mouse callback for ROI polygon drawing"""
    global roi_points, drawing_complete

    if drawing_complete:
        return

    if event == cv2.EVENT_LBUTTONDOWN:
        roi_points.append((x, y))
        print(f"   Point {len(roi_points)}: ({x}, {y})")


def draw_roi_on_frame(frame, points, color=(255, 255, 0), thickness=2, fill_alpha=0.2):
    """Draw ROI polygon on frame"""
    if len(points) < 2:
        return frame

    frame_copy = frame.copy()

    # Draw lines between points
    for i in range(len(points)):
        pt1 = points[i]
        pt2 = points[(i + 1) % len(points)]
        cv2.line(frame_copy, pt1, pt2, color, thickness)

    # Draw points
    for pt in points:
        cv2.circle(frame_copy, pt, 5, color, -1)

    # Fill polygon with semi-transparent overlay
    if len(points) >= 3:
        overlay = frame_copy.copy()
        pts = np.array(points, np.int32)
        cv2.fillPoly(overlay, [pts], color)
        cv2.addWeighted(overlay, fill_alpha, frame_copy, 1 - fill_alpha, 0, frame_copy)

    return frame_copy


def setup_roi_from_video(video_path):
    """Setup ROI using first frame of video"""
    global roi_points, drawing_complete

    print("\n" + "="*70)
    print("🎯 ROI Setup Mode")
    print("="*70)

    # Open video and get first frame
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"❌ Could not open video: {video_path}")
        return None

    ret, frame = cap.read()
    cap.release()

    if not ret:
        print(f"❌ Could not read first frame from video")
        return None

    print(f"📸 Using first frame from: {os.path.basename(video_path)}")
    print(f"📏 Frame size: {frame.shape[1]}x{frame.shape[0]}")
    print("\n📝 Instructions:")
    print("   1. Left-click to add polygon points")
    print("   2. 'z' key to undo last point")
    print("   3. 's' key to complete and save (minimum 3 points)")
    print("   4. 'r' to reset and start over")
    print("   5. 'q' to quit without saving")
    print("\nℹ️  Draw the area where you want to monitor staff...")

    roi_points = []
    drawing_complete = False

    cv2.namedWindow('ROI Setup', cv2.WINDOW_NORMAL)
    cv2.resizeWindow('ROI Setup', 1280, 720)
    cv2.setMouseCallback('ROI Setup', mouse_callback)

    while True:
        display_frame = draw_roi_on_frame(frame, roi_points)

        # Add instruction text
        cv2.putText(display_frame, f"Points: {len(roi_points)} | 's' to save | 'z' to undo | 'r' to reset | 'q' to quit",
                   (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        cv2.imshow('ROI Setup', display_frame)
        key = cv2.waitKey(1) & 0xFF

        # 's' to save
        if key == ord('s'):
            if len(roi_points) >= 3:
                roi_data = {
                    'points': roi_points,
                    'frame_size': [frame.shape[1], frame.shape[0]],
                    'video': video_path
                }
                with open(ROI_CONFIG_FILE, 'w') as f:
                    json.dump(roi_data, f, indent=2)
                print(f"\n✅ ROI polygon completed with {len(roi_points)} points")
                print(f"💾 ROI saved to: {ROI_CONFIG_FILE}")
                cv2.destroyAllWindows()
                return roi_points
            else:
                print(f"\n⚠️  Need at least 3 points (currently {len(roi_points)})")

        # 'z' to undo
        elif key == ord('z'):
            if roi_points:
                removed_point = roi_points.pop()
                print(f"   ↶ Undo: Removed point {removed_point} ({len(roi_points)} points remaining)")
            else:
                print("   ⚠️  No points to undo")

        # 'r' to reset
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
    print(f"   Using YOLOv8m - Medium model with better accuracy than YOLOv8s")
    person_detector = YOLO(PERSON_DETECTOR_MODEL)

    if not os.path.exists(STAFF_CLASSIFIER_MODEL):
        print(f"❌ Staff classifier not found: {STAFF_CLASSIFIER_MODEL}")
        return None, None

    print(f"   Loading YOLO11n-cls staff classifier: {STAFF_CLASSIFIER_MODEL}")
    print(f"   Model specs: 92.38% accuracy, trained on 1,505 images (1080p crops)")
    staff_classifier = YOLO(STAFF_CLASSIFIER_MODEL)

    print("✅ Both models loaded successfully!\n")
    return person_detector, staff_classifier


def detect_persons(person_detector, frame):
    """Stage 1: Detect all persons in the frame"""
    results = person_detector(frame, conf=PERSON_CONF_THRESHOLD, classes=[0], verbose=False)

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
                    center_x = int((x1 + x2) / 2)
                    center_y = int((y1 + y2) / 2)
                    person_detections.append({
                        'bbox': (int(x1), int(y1), int(x2), int(y2)),
                        'confidence': float(confidence),
                        'center': (center_x, center_y)
                    })

    return person_detections


def filter_by_roi(detections, roi_polygon):
    """Filter detections - keep only those inside ROI"""
    if roi_polygon is None or len(roi_polygon) < 3:
        return detections

    filtered = []
    for detection in detections:
        center = detection['center']
        if point_in_polygon(center, roi_polygon):
            filtered.append(detection)

    return filtered


def classify_persons(staff_classifier, frame, person_detections):
    """Stage 2: Classify each detected person as waiter or customer"""
    classified_detections = []

    for detection in person_detections:
        x1, y1, x2, y2 = detection['bbox']
        person_crop = frame[y1:y2, x1:x2]

        if person_crop.shape[0] < 20 or person_crop.shape[1] < 20:
            classified_detections.append({
                'class': 'unknown',
                'confidence': 0.0,
                'bbox': detection['bbox'],
                'center': detection['center'],
                'person_confidence': detection['confidence']
            })
            continue

        classification_results = staff_classifier(person_crop, verbose=False)
        result = classification_results[0]

        if result.probs is not None:
            class_id = result.probs.top1
            confidence = float(result.probs.top1conf)
            class_name = CLASS_NAMES[class_id]

            if confidence >= STAFF_CONF_THRESHOLD:
                classified_detections.append({
                    'class': class_name,
                    'confidence': confidence,
                    'bbox': detection['bbox'],
                    'center': detection['center'],
                    'person_confidence': detection['confidence']
                })
            else:
                classified_detections.append({
                    'class': 'unknown',
                    'confidence': confidence,
                    'bbox': detection['bbox'],
                    'center': detection['center'],
                    'person_confidence': detection['confidence']
                })
        else:
            classified_detections.append({
                'class': 'unknown',
                'confidence': 0.0,
                'bbox': detection['bbox'],
                'center': detection['center'],
                'person_confidence': detection['confidence']
            })

    return classified_detections


def draw_detections_with_alert(frame, detections, roi_polygon, tracker, alert_active=False, alert_duration=0.0, waiter_confirmed=False):
    """Draw detections, ROI, stats overlay, and alert flash"""
    annotated_frame = frame.copy()

    # Apply red flash if alert is active
    if alert_active:
        overlay = annotated_frame.copy()
        overlay[:] = FLASH_COLOR
        cv2.addWeighted(overlay, FLASH_ALPHA, annotated_frame, 1 - FLASH_ALPHA, 0, annotated_frame)

    # Draw ROI boundary
    if roi_polygon is not None and len(roi_polygon) >= 3:
        annotated_frame = draw_roi_on_frame(annotated_frame, roi_polygon, COLORS['roi'], 3, 0.1)

    # Draw detections
    for detection in detections:
        x1, y1, x2, y2 = detection['bbox']
        class_name = detection['class']
        confidence = detection['confidence']

        color = COLORS.get(class_name, COLORS['unknown'])
        cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 3)

        if confidence > 0:
            label = f"{class_name}: {confidence:.1%}"
        else:
            label = f"{class_name}"

        label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
        cv2.rectangle(annotated_frame,
                     (x1, y1 - label_size[1] - 10),
                     (x1 + label_size[0] + 10, y1),
                     color, -1)

        cv2.putText(annotated_frame, label,
                   (x1 + 5, y1 - 5),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    # Draw stats overlay
    stats_y = 30
    stats_x = 10
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.7
    font_thickness = 2
    line_height = 30

    # Background for stats
    overlay = annotated_frame.copy()
    cv2.rectangle(overlay, (5, 5), (520, 280), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, annotated_frame, 0.4, 0, annotated_frame)

    # Current FPS
    current_fps = tracker.get_current_fps()
    cv2.putText(annotated_frame, f"Processing FPS: {current_fps:.2f}",
               (stats_x, stats_y), font, font_scale, (0, 255, 255), font_thickness)

    # Frame count
    stats_y += line_height
    cv2.putText(annotated_frame, f"Frame: {tracker.total_frames}",
               (stats_x, stats_y), font, font_scale, (255, 255, 255), font_thickness)

    # Stage times
    avg_stage1, avg_stage2 = tracker.get_avg_stage_times()
    stats_y += line_height
    cv2.putText(annotated_frame, f"Stage 1: {avg_stage1:.1f}ms | Stage 2: {avg_stage2:.1f}ms",
               (stats_x, stats_y), font, font_scale, (255, 255, 0), font_thickness)

    # Detection counts
    stats_y += line_height
    waiter_count = sum(1 for d in detections if d['class'] == 'waiter')
    customer_count = sum(1 for d in detections if d['class'] == 'customer')

    cv2.putText(annotated_frame, f"Waiters: {waiter_count} | Customers: {customer_count}",
               (stats_x, stats_y), font, font_scale, (0, 255, 0), font_thickness)

    # Alert status
    stats_y += line_height
    waiter_count = sum(1 for d in detections if d['class'] == 'waiter')
    if alert_active:
        cv2.putText(annotated_frame, f"ALERT: No waiter for {alert_duration:.1f}s",
                   (stats_x, stats_y), font, font_scale, (0, 0, 255), font_thickness)
    elif waiter_count > 0 and not waiter_confirmed:
        cv2.putText(annotated_frame, f"Status: Debouncing... ({WAITER_DEBOUNCE_SECONDS:.0f}s check)",
                   (stats_x, stats_y), font, font_scale, (0, 165, 255), font_thickness)  # Orange
    elif waiter_confirmed:
        cv2.putText(annotated_frame, f"Status: Waiter confirmed OK",
                   (stats_x, stats_y), font, font_scale, (0, 255, 0), font_thickness)
    else:
        cv2.putText(annotated_frame, f"Status: Monitoring...",
                   (stats_x, stats_y), font, font_scale, (128, 128, 128), font_thickness)

    # ROI info
    stats_y += line_height
    cv2.putText(annotated_frame, f"ROI: {len(roi_polygon) if roi_polygon else 0} points",
               (stats_x, stats_y), font, font_scale, (255, 255, 0), font_thickness)

    return annotated_frame


def process_video(video_path, person_detector, staff_classifier, roi_polygon, output_dir="results", duration_limit=None):
    """Process video with ROI filtering and alert system"""
    print(f"\n{'='*70}")
    print(f"🎬 Processing Video with ROI + Alert System")
    print(f"{'='*70}")
    print(f"📹 Video: {os.path.basename(video_path)}\n")

    # Open video
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"❌ Could not open video: {video_path}")
        return False

    # Get video properties
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration = frame_count / fps if fps > 0 else 0

    # Calculate max frames if duration limit is set
    max_frames = frame_count
    if duration_limit is not None:
        max_frames = int(duration_limit * fps)
        print(f"📹 Video Properties (processing first {duration_limit}s only):")
    else:
        print(f"📹 Video Properties:")

    print(f"   Resolution: {width}x{height}")
    print(f"   FPS: {fps:.2f}")
    print(f"   Total frames in video: {frame_count}")
    print(f"   Total duration: {duration:.2f}s")
    if duration_limit is not None:
        print(f"   Frames to process: {max_frames} (first {duration_limit}s)")
    else:
        print(f"   Frames to process: {frame_count} (entire video)")
    print()

    # Setup output video
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    # New naming convention: {script_name}_{original_video_name}.mp4
    script_name = Path(__file__).stem
    output_filename = f"{script_name}_{Path(video_path).stem}.mp4"
    output_file = str(output_path / output_filename)

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_file, fourcc, fps, (width, height))

    if not out.isOpened():
        print(f"❌ Could not create output video: {output_file}")
        cap.release()
        return False

    # Initialize performance tracker
    tracker = PerformanceTracker(window_size=30)

    # Alert tracking with debouncing
    first_waiter_seen_time = None      # When we first see a waiter (for debouncing)
    last_confirmed_waiter_time = None  # When we last confirmed a waiter (after debounce)
    waiter_confirmed = False           # Whether waiter has passed debounce check
    alert_active = False

    # Process video frames
    frame_idx = 0
    processed_frames = 0

    print("🔄 Processing frames...")
    print(f"🔄 Waiter debounce: Must be present for {WAITER_DEBOUNCE_SECONDS:.1f}s to count")
    print(f"🚨 Alert: Will flash screen if no confirmed waiter for > {ALERT_THRESHOLD_SECONDS:.1f}s\n")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Stop if we've reached the duration limit
            if frame_idx >= max_frames:
                break

            frame_start = time.time()

            # Stage 1: Detect all persons
            stage1_start = time.time()
            person_detections = detect_persons(person_detector, frame)
            stage1_time = time.time() - stage1_start

            # Filter by ROI
            if roi_polygon:
                roi_filtered = filter_by_roi(person_detections, roi_polygon)
            else:
                roi_filtered = person_detections

            # Stage 2: Classify persons in ROI
            stage2_start = time.time()
            classified_detections = classify_persons(staff_classifier, frame, roi_filtered)
            stage2_time = time.time() - stage2_start

            # Count waiters in ROI
            waiter_count = sum(1 for d in classified_detections if d['class'] == 'waiter')
            customer_count = sum(1 for d in classified_detections if d['class'] == 'customer')

            # Debounced alert logic: Waiter must be present for 1s before counting
            current_time = time.time()

            if waiter_count > 0:
                # Waiter detected in ROI
                if first_waiter_seen_time is None:
                    # First time seeing waiter, start debounce timer
                    first_waiter_seen_time = current_time
                    waiter_confirmed = False
                else:
                    # Check if waiter has been present long enough
                    waiter_duration = current_time - first_waiter_seen_time
                    if waiter_duration >= WAITER_DEBOUNCE_SECONDS:
                        # Waiter confirmed after debounce period
                        if not waiter_confirmed:
                            waiter_confirmed = True
                            last_confirmed_waiter_time = current_time
                        else:
                            # Update last confirmed time
                            last_confirmed_waiter_time = current_time
            else:
                # No waiter detected in ROI
                first_waiter_seen_time = None
                waiter_confirmed = False

            # Calculate alert status based on last confirmed waiter
            if last_confirmed_waiter_time is None:
                # Never had a confirmed waiter yet - no alert
                alert_duration = 0.0
                alert_active = False
            else:
                alert_duration = current_time - last_confirmed_waiter_time
                if alert_duration > ALERT_THRESHOLD_SECONDS:
                    alert_active = True
                else:
                    alert_active = False

            # Total frame time
            frame_time = time.time() - frame_start

            # Update tracker
            tracker.add_frame(frame_time, stage1_time, stage2_time,
                            len(roi_filtered), waiter_count, customer_count,
                            alert_active, alert_duration)

            # Draw detections with alert overlay
            annotated_frame = draw_detections_with_alert(frame, classified_detections, roi_polygon,
                                                         tracker, alert_active, alert_duration, waiter_confirmed)

            # Write frame
            out.write(annotated_frame)

            processed_frames += 1
            frame_idx += 1

            # Print progress every 30 frames
            if processed_frames % 30 == 0:
                progress = (frame_idx / max_frames) * 100
                current_fps = tracker.get_current_fps()

                if alert_active:
                    status = f"🚨 ALERT ({alert_duration:.1f}s)"
                elif waiter_count > 0 and not waiter_confirmed:
                    status = "⏳ Debouncing"
                elif waiter_confirmed:
                    status = "✅ Confirmed"
                else:
                    status = "👀 Monitoring"

                print(f"   Progress: {progress:.1f}% | Frame {frame_idx}/{max_frames} | "
                      f"FPS: {current_fps:.2f} | Waiters: {waiter_count} | {status}")

    except KeyboardInterrupt:
        print("\n⚠️  Processing interrupted by user")

    finally:
        cap.release()
        out.release()

        # Print summary
        tracker.print_summary(duration if duration_limit is None else duration_limit, fps)

        print(f"💾 Output saved: {output_file}")
        print(f"✅ Video processing complete!\n")

    return True


def main():
    """Main function with argument parsing"""
    parser = argparse.ArgumentParser(
        description="Two-stage video analysis with ROI and alert system (YOLOv8m edition)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process video with ROI setup
  python3 yolov8m_yolo11ncls_roi_video_analysis.py --video ../linux_rtx_video_streaming/camera_35_20251022_195212_compressed.mp4 --duration 20

  # Process full video
  python3 yolov8m_yolo11ncls_roi_video_analysis.py --video ../linux_rtx_video_streaming/camera_35.mp4
        """
    )
    parser.add_argument("--video", required=True, help="Path to input video")
    parser.add_argument("--output", default="results", help="Output directory")
    parser.add_argument("--duration", type=int, default=None,
                       help="Process only first N seconds of video (default: process entire video)")
    parser.add_argument("--person_conf", type=float, default=0.3,
                       help="Person detection confidence threshold (default: 0.3)")
    parser.add_argument("--staff_conf", type=float, default=0.5,
                       help="Staff classification confidence threshold (default: 0.5)")

    args = parser.parse_args()

    # Update global thresholds
    global PERSON_CONF_THRESHOLD, STAFF_CONF_THRESHOLD
    PERSON_CONF_THRESHOLD = args.person_conf
    STAFF_CONF_THRESHOLD = args.staff_conf

    # Step 1: Setup ROI using first frame of video
    print("\n" + "="*70)
    print("🎯 Step 1: ROI Setup")
    print("="*70)
    roi_polygon = setup_roi_from_video(args.video)

    if roi_polygon is None:
        print("\n❌ ROI setup cancelled. Exiting.")
        return 1

    # Step 2: Load models
    print("\n" + "="*70)
    print("🎯 Step 2: Loading Models")
    print("="*70)
    person_detector, staff_classifier = load_models()
    if person_detector is None or staff_classifier is None:
        return 1

    # Step 3: Process video
    print("\n" + "="*70)
    print("🎯 Step 3: Processing Video")
    print("="*70)
    success = process_video(args.video, person_detector, staff_classifier, roi_polygon,
                           args.output, args.duration)

    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
