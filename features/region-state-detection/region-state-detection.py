#!/usr/bin/env python3
"""
ASEOfSmartICE Division + Service Area Detection System (YOLOv8m Edition)
Version: 5.0.0 - Multi-area state detection with service zones
Last Updated: 2025-11-13

Features:
- Interactive division and service area labeling (multiple service areas per division)
- Configuration file support (region_config.json) for reusable setups
- Three-state detection: Green (served), Yellow (busy), Red (ignored/needs attention)
- Two-stage detection (YOLOv8m + YOLO11n-cls)
- 1-second debounce buffer for waiter transitions
- Performance tracking for real-time 2K video analysis

State Logic:
- GREEN (Free/Served): Waiter in division BUT NOT in service area - customers being attended
- YELLOW (Busy): Waiter in service area AND within division - waiter occupied
- RED (Ignored): No waiter in division - area needs attention

Changes from v4.0.0:
- v5.0.0 (2025-11-13): Added division + service area support with 3-state detection logic
  - Interactive labeling: division first, then multiple service areas
  - Configuration file support (region_config.json)
  - New color-coded states based on waiter position relative to service areas
  - Maintains 1s debounce buffer for stable detection

Version History:
- v5.0.0 (2025-11-13): Division + service area detection with 3-state logic
- v4.0.0 (2025-10-30): YOLOv8m person detector for improved accuracy
- v3.3.0 (2025-10-26): Added 1s waiter debounce buffer, increased alert to 5s for production

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

# Region configuration
REGION_CONFIG_FILE = "region_config.json"

# State detection configuration
WAITER_DEBOUNCE_SECONDS = 1.0   # Waiter must be present for 1s to count (prevents false positives)

# Visual configuration - State colors
STATE_COLORS = {
    'green': (0, 255, 0),           # Green: Waiter in division but NOT in service area (being served)
    'yellow': (0, 255, 255),        # Yellow: Waiter in service area (busy)
    'red': (0, 0, 255)              # Red: No waiter in division (ignored/needs attention)
}

COLORS = {
    'person': (255, 255, 0),        # Cyan for person detection (Stage 1)
    'waiter': (0, 255, 0),          # Green for waiters (Stage 2)
    'customer': (0, 0, 255),        # Red for customers (Stage 2)
    'unknown': (128, 128, 128),     # Gray for unknown (Stage 2, low confidence)
    'division': (255, 255, 0),      # Cyan for division boundary
    'service_area': (255, 0, 255)   # Magenta for service area boundary
}

CLASS_NAMES = {0: 'customer', 1: 'waiter'}

# Global variables for interactive drawing
drawing_points = []
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

        # State tracking
        self.state_counts = {'green': 0, 'yellow': 0, 'red': 0}

    def add_frame(self, frame_time, stage1_time, stage2_time, persons, waiters, customers, state='red'):
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

        # Track states
        if state in self.state_counts:
            self.state_counts[state] += 1

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
        print(f"🎨 State Statistics:")
        green_pct = (self.state_counts['green'] / self.total_frames * 100) if self.total_frames > 0 else 0
        yellow_pct = (self.state_counts['yellow'] / self.total_frames * 100) if self.total_frames > 0 else 0
        red_pct = (self.state_counts['red'] / self.total_frames * 100) if self.total_frames > 0 else 0
        print(f"   GREEN (Served): {self.state_counts['green']}/{self.total_frames} ({green_pct:.1f}%)")
        print(f"   YELLOW (Busy): {self.state_counts['yellow']}/{self.total_frames} ({yellow_pct:.1f}%)")
        print(f"   RED (Ignored): {self.state_counts['red']}/{self.total_frames} ({red_pct:.1f}%)")
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
    """Mouse callback for polygon drawing"""
    global drawing_points, drawing_complete

    if drawing_complete:
        return

    if event == cv2.EVENT_LBUTTONDOWN:
        drawing_points.append((x, y))
        print(f"   Point {len(drawing_points)}: ({x}, {y})")


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


def draw_instruction_panel(frame, stage, points_count, service_areas_count):
    """Draw instruction panel on frame"""
    overlay = frame.copy()
    panel_height = 210
    panel_width = 580

    # Semi-transparent background
    cv2.rectangle(overlay, (10, 10), (panel_width, panel_height), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

    font = cv2.FONT_HERSHEY_SIMPLEX
    y_offset = 35

    # Stage indicator
    if stage == 'division':
        stage_text = "STEP 1/2: DIVISION AREA"
        stage_color = COLORS['division']
        workflow = "Draw the division area to monitor"
    else:  # service_area
        stage_text = f"STEP 2/2: SERVICE AREA #{service_areas_count + 1}"
        stage_color = COLORS['service_area']
        workflow = f"Draw service area #{service_areas_count + 1} (can draw multiple)"

    cv2.putText(frame, stage_text, (20, y_offset), font, 0.8, stage_color, 2)

    # Workflow info
    y_offset += 30
    cv2.putText(frame, workflow, (20, y_offset), font, 0.5, (150, 255, 150), 1)

    # Points counter
    y_offset += 25
    cv2.putText(frame, f"Points drawn: {points_count} (minimum 3)",
               (20, y_offset), font, 0.5, (255, 255, 255), 1)

    # Service areas counter
    if stage == 'service_area':
        y_offset += 25
        cv2.putText(frame, f"Service areas completed: {service_areas_count}",
                   (20, y_offset), font, 0.5, (255, 255, 255), 1)

    # Instructions
    y_offset += 35
    cv2.putText(frame, "CONTROLS:", (20, y_offset), font, 0.6, (100, 255, 255), 2)

    y_offset += 25
    instructions = [
        "'N' - Complete current polygon (min 3 points)",
        "'D' - Done (only for service areas)",
        "'Z' - Undo last point",
        "'R' - Reset and start over",
        "'Q' - Quit without saving"
    ]

    for instruction in instructions:
        cv2.putText(frame, instruction, (30, y_offset), font, 0.45, (200, 200, 200), 1)
        y_offset += 20

    return frame


def setup_division_and_service_areas(video_path):
    """Interactive setup for division and service areas"""
    global drawing_points

    print("\n" + "="*70)
    print("🎯 Division + Service Areas Setup Mode")
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
    print("\n" + "="*70)
    print("WORKFLOW:")
    print("="*70)
    print("   1. Draw DIVISION area, press 'N' to complete")
    print("   2. Draw SERVICE AREA(s), press 'N' for each")
    print("      (Can draw multiple service areas)")
    print("   3. Press 'D' when done with all service areas")
    print("\n   'N' - Complete current polygon")
    print("   'D' - Done with service areas, save and finish")
    print("   'Z' - Undo last point")
    print("   'R' - Reset current polygon")
    print("   'Q' - Quit without saving")
    print("="*70 + "\n")

    division_polygon = None
    service_areas = []
    drawing_points = []
    current_stage = 'division'  # 'division' or 'service_area'

    cv2.namedWindow('Region Setup', cv2.WINDOW_NORMAL)
    cv2.resizeWindow('Region Setup', 1280, 720)
    cv2.setMouseCallback('Region Setup', mouse_callback)

    while True:
        display_frame = frame.copy()

        # Draw completed division
        if division_polygon is not None:
            display_frame = draw_roi_on_frame(display_frame, division_polygon, COLORS['division'], 3, 0.1)

        # Draw completed service areas
        for sa in service_areas:
            display_frame = draw_roi_on_frame(display_frame, sa, COLORS['service_area'], 2, 0.15)

        # Get current drawing color
        draw_color = COLORS['division'] if current_stage == 'division' else COLORS['service_area']

        # Draw current points being drawn
        if len(drawing_points) > 0:
            # Draw points
            for idx, pt in enumerate(drawing_points):
                cv2.circle(display_frame, pt, 7, draw_color, -1)
                cv2.circle(display_frame, pt, 9, (255, 255, 255), 2)
                cv2.putText(display_frame, f"{idx+1}", (pt[0] + 12, pt[1] - 5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, draw_color, 2)

            # Draw lines between points
            if len(drawing_points) >= 2:
                for i in range(len(drawing_points)):
                    pt1 = drawing_points[i]
                    pt2 = drawing_points[(i + 1) % len(drawing_points)]
                    cv2.line(display_frame, pt1, pt2, draw_color, 3)

            # Show preview polygon if we have 3+ points
            if len(drawing_points) >= 3:
                pts = np.array(drawing_points, np.int32)
                pts = pts.reshape((-1, 1, 2))
                cv2.polylines(display_frame, [pts], isClosed=True, color=draw_color, thickness=2)

        # Draw instruction panel
        display_frame = draw_instruction_panel(display_frame, current_stage,
                                               len(drawing_points), len(service_areas))

        cv2.imshow('Region Setup', display_frame)
        key = cv2.waitKey(10) & 0xFF

        # 'n' or 'N' to complete current polygon
        if key == ord('n') or key == ord('N'):
            if len(drawing_points) >= 3:
                if current_stage == 'division':
                    division_polygon = drawing_points.copy()
                    print(f"\n✓ Division area completed with {len(division_polygon)} points")
                    print(f"   >> Switching to SERVICE AREAS")
                    print(f"   (Draw service areas, press 'D' when done)")
                    current_stage = 'service_area'
                    drawing_points = []

                elif current_stage == 'service_area':
                    service_areas.append(drawing_points.copy())
                    print(f"\n✓ Service Area #{len(service_areas)} completed with {len(drawing_points)} points")
                    print(f"   >> You can draw more service areas or press 'D' to finish")
                    drawing_points = []
            else:
                print(f"\n✗ Need at least 3 points (currently {len(drawing_points)})")

        # 'd' or 'D' to finish service areas and save
        elif key == ord('d') or key == ord('D'):
            if current_stage == 'service_area' and division_polygon is not None and len(service_areas) > 0:
                # Save configuration
                region_data = {
                    'division': division_polygon,
                    'service_areas': service_areas,
                    'frame_size': [frame.shape[1], frame.shape[0]],
                    'video': video_path
                }

                with open(REGION_CONFIG_FILE, 'w') as f:
                    json.dump(region_data, f, indent=2)

                print(f"\n{'='*70}")
                print(f"✓ Configuration Saved: {REGION_CONFIG_FILE}")
                print(f"{'='*70}")
                print(f"   Division: {len(division_polygon)} points")
                print(f"   Service areas: {len(service_areas)}")
                print(f"{'='*70}\n")

                cv2.destroyAllWindows()
                return region_data
            elif current_stage == 'division':
                print(f"\n⚠ You must complete the division first (press 'N' after drawing)")
            elif len(service_areas) == 0:
                print(f"\n⚠ You must draw at least one service area")

        # 'z' or 'Z' to undo
        elif key == ord('z') or key == ord('Z'):
            if drawing_points:
                removed_point = drawing_points.pop()
                print(f"   ↶ Undo: Removed point {removed_point} ({len(drawing_points)} points remaining)")

        # 'r' or 'R' to reset
        elif key == ord('r') or key == ord('R'):
            if drawing_points:
                drawing_points = []
                print("\n🔄 Reset - cleared current polygon")

        # 'q' or 'Q' to quit
        elif key == ord('q') or key == ord('Q'):
            print("\n❌ Setup cancelled")
            cv2.destroyAllWindows()
            return None

    cv2.destroyAllWindows()
    return None


def load_region_config():
    """Load region configuration from file"""
    if not os.path.exists(REGION_CONFIG_FILE):
        return None

    try:
        with open(REGION_CONFIG_FILE, 'r') as f:
            config = json.load(f)
        print(f"✅ Loaded configuration from: {REGION_CONFIG_FILE}")
        print(f"   Division: {len(config['division'])} points")
        print(f"   Service areas: {len(config['service_areas'])}")
        return config
    except Exception as e:
        print(f"❌ Error loading configuration: {e}")
        return None


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


def filter_by_division(detections, division_polygon):
    """Filter detections - keep only those inside division"""
    if division_polygon is None or len(division_polygon) < 3:
        return detections

    filtered = []
    for detection in detections:
        center = detection['center']
        if point_in_polygon(center, division_polygon):
            filtered.append(detection)

    return filtered


def check_waiter_in_service_areas(waiter_detections, service_areas):
    """Check if any waiter is in any service area"""
    if not waiter_detections or not service_areas:
        return False

    for waiter in waiter_detections:
        center = waiter['center']
        for service_area in service_areas:
            if point_in_polygon(center, service_area):
                return True

    return False


def determine_division_state(waiter_detections, service_areas):
    """Determine the state of the division based on waiter positions

    Returns:
        'green': Waiter in division but NOT in service area (being served/free)
        'yellow': Waiter in service area (busy)
        'red': No waiter in division (ignored/needs attention)
    """
    if not waiter_detections or len(waiter_detections) == 0:
        return 'red'  # No waiter in division

    # Check if any waiter is in service area
    waiter_in_service_area = check_waiter_in_service_areas(waiter_detections, service_areas)

    if waiter_in_service_area:
        return 'yellow'  # Waiter is in service area (busy)
    else:
        return 'green'  # Waiter in division but not in service area (being served)


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


def draw_detections_with_state(frame, detections, division_polygon, service_areas, tracker, state='red', waiter_confirmed=False):
    """Draw detections, division, service areas, stats overlay, and state-based coloring"""
    annotated_frame = frame.copy()

    # Apply state-based overlay
    state_color = STATE_COLORS.get(state, STATE_COLORS['red'])
    overlay = annotated_frame.copy()
    overlay[:] = state_color
    cv2.addWeighted(overlay, 0.2, annotated_frame, 0.8, 0, annotated_frame)

    # Draw division boundary
    if division_polygon is not None and len(division_polygon) >= 3:
        annotated_frame = draw_roi_on_frame(annotated_frame, division_polygon, COLORS['division'], 3, 0.1)

    # Draw service area boundaries
    if service_areas:
        for service_area in service_areas:
            if service_area is not None and len(service_area) >= 3:
                annotated_frame = draw_roi_on_frame(annotated_frame, service_area, COLORS['service_area'], 2, 0.05)

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

    # State status
    stats_y += line_height
    state_text = {
        'green': 'GREEN (Served/Free)',
        'yellow': 'YELLOW (Busy)',
        'red': 'RED (Ignored)'
    }
    state_display_color = STATE_COLORS.get(state, STATE_COLORS['red'])

    if waiter_count > 0 and not waiter_confirmed:
        cv2.putText(annotated_frame, f"Status: Debouncing... ({WAITER_DEBOUNCE_SECONDS:.0f}s check)",
                   (stats_x, stats_y), font, font_scale, (0, 165, 255), font_thickness)  # Orange
    else:
        cv2.putText(annotated_frame, f"State: {state_text.get(state, 'UNKNOWN')}",
                   (stats_x, stats_y), font, font_scale, state_display_color, font_thickness)

    # Region info
    stats_y += line_height
    cv2.putText(annotated_frame, f"Division: {len(division_polygon) if division_polygon else 0} points",
               (stats_x, stats_y), font, font_scale, (255, 255, 0), font_thickness)

    stats_y += line_height
    num_service_areas = len(service_areas) if service_areas else 0
    cv2.putText(annotated_frame, f"Service Areas: {num_service_areas}",
               (stats_x, stats_y), font, font_scale, (255, 0, 255), font_thickness)

    return annotated_frame


def process_video(video_path, person_detector, staff_classifier, region_config, output_dir=None, duration_limit=None):
    """Process video with division/service area filtering and state detection"""
    # Default output to script's own results directory
    if output_dir is None:
        output_dir = str(Path(__file__).parent / "results")

    division_polygon = region_config['division']
    service_areas = region_config['service_areas']

    print(f"\n{'='*70}")
    print(f"🎬 Processing Video with Division + Service Area Detection")
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

    # State tracking with debouncing
    first_waiter_seen_time = None      # When we first see a waiter (for debouncing)
    waiter_confirmed = False           # Whether waiter has passed debounce check
    current_state = 'red'              # Current division state

    # Process video frames
    frame_idx = 0
    processed_frames = 0

    print("🔄 Processing frames...")
    print(f"🔄 Waiter debounce: Must be present for {WAITER_DEBOUNCE_SECONDS:.1f}s to count")
    print(f"🎨 State colors: GREEN (served) | YELLOW (busy) | RED (ignored)\n")

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

            # Filter by division
            division_filtered = filter_by_division(person_detections, division_polygon)

            # Stage 2: Classify persons in division
            stage2_start = time.time()
            classified_detections = classify_persons(staff_classifier, frame, division_filtered)
            stage2_time = time.time() - stage2_start

            # Count waiters and customers in division
            waiter_detections = [d for d in classified_detections if d['class'] == 'waiter']
            waiter_count = len(waiter_detections)
            customer_count = sum(1 for d in classified_detections if d['class'] == 'customer')

            # Debounced state logic: Waiter must be present for 1s before confirming
            current_time = time.time()

            if waiter_count > 0:
                # Waiter detected in division
                if first_waiter_seen_time is None:
                    # First time seeing waiter, start debounce timer
                    first_waiter_seen_time = current_time
                    waiter_confirmed = False
                else:
                    # Check if waiter has been present long enough
                    waiter_duration = current_time - first_waiter_seen_time
                    if waiter_duration >= WAITER_DEBOUNCE_SECONDS:
                        # Waiter confirmed after debounce period
                        waiter_confirmed = True
            else:
                # No waiter detected in division
                first_waiter_seen_time = None
                waiter_confirmed = False

            # Determine state based on confirmed waiters
            if waiter_confirmed:
                current_state = determine_division_state(waiter_detections, service_areas)
            else:
                # Not confirmed yet, use red state
                current_state = 'red'

            # Total frame time
            frame_time = time.time() - frame_start

            # Update tracker
            tracker.add_frame(frame_time, stage1_time, stage2_time,
                            len(division_filtered), waiter_count, customer_count,
                            current_state)

            # Draw detections with state overlay
            annotated_frame = draw_detections_with_state(frame, classified_detections, division_polygon,
                                                         service_areas, tracker, current_state, waiter_confirmed)

            # Write frame
            out.write(annotated_frame)

            processed_frames += 1
            frame_idx += 1

            # Print progress every 30 frames
            if processed_frames % 30 == 0:
                progress = (frame_idx / max_frames) * 100
                current_fps = tracker.get_current_fps()

                state_emoji = {'green': '🟢', 'yellow': '🟡', 'red': '🔴'}
                if waiter_count > 0 and not waiter_confirmed:
                    status = "⏳ Debouncing"
                else:
                    status = f"{state_emoji.get(current_state, '⚪')} {current_state.upper()}"

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
        description="Division + Service Area Detection System (YOLOv8m edition)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode - setup division and service areas
  python3 region-state-detection.py --video videos/test.mp4 --interactive

  # Default mode - use existing configuration
  python3 region-state-detection.py --video videos/test.mp4

  # Process with duration limit
  python3 region-state-detection.py --video videos/test.mp4 --duration 20
        """
    )
    parser.add_argument("--video", required=True, help="Path to input video")
    parser.add_argument("--output", default=str(Path(__file__).parent / "results"), help="Output directory")
    parser.add_argument("--interactive", action="store_true",
                       help="Interactive mode: setup division and service areas")
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

    # Step 1: Get region configuration (interactive or load from file)
    print("\n" + "="*70)
    print("🎯 Step 1: Region Configuration")
    print("="*70)

    region_config = None

    if args.interactive:
        # Interactive mode: setup division and service areas
        region_config = setup_division_and_service_areas(args.video)
        if region_config is None:
            print("\n❌ Region setup cancelled. Exiting.")
            return 1
    else:
        # Default mode: try to load existing configuration
        region_config = load_region_config()
        if region_config is None:
            print(f"\n⚠️  No configuration file found: {REGION_CONFIG_FILE}")
            print("   Use --interactive flag to create configuration")
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
    success = process_video(args.video, person_detector, staff_classifier, region_config,
                           args.output, args.duration)

    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
