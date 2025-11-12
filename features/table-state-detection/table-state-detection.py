#!/usr/bin/env python3
"""
Table State Detection System
Version: 2.0.0
Last Updated: 2025-11-12

Purpose: Monitor individual restaurant tables and detect state transitions
States: IDLE, BUSY, CLEANING

Reference: Based on ../../test-model/two-stage-detection-yolo11-cls/yolov8m_yolo11ncls_roi_video_analysis.py
Modified to support multi-table monitoring instead of single ROI zone monitoring

Key Changes from Reference:
- Multi-table ROI support (instead of single ROI)
- 3-state tracking per table (IDLE, BUSY, CLEANING)
- Table-specific statistics and state transitions
- Enhanced ROI drawing system for multiple tables
- Sitting area labeling for customer seating zones
- Enhanced visual feedback during ROI setup
- TRUE POLYGON support (not forced to axis-aligned rectangles)
- Sequential labeling workflow (Table → Sitting per table)
- Center point visualization for ROI assignment debugging

State Definitions:
- IDLE: No one around the table (GREEN - empty/available)
- BUSY: Only customers present (YELLOW - customers dining)
- CLEANING: Only employees present (BLUE - staff cleaning/turnover)

Visual Design (Result Video):
- Tables change color based on state (GREEN/YELLOW/BLUE)
- Sitting areas show as gray lines (not changing)
- White circles mark person center points used for ROI assignment
- State labels display in English (OpenCV compatible)

Version History:
- v2.0.0: Simplified to 3 states, removed service area tracking
         State renamed: OCCUPIED → BUSY, removed SERVING state
- v1.4.1: Fixed Chinese character display issue - now uses English state labels
- v1.4.0: Added center point visualization for debugging ROI assignments
- v1.3.0: Added sitting area labeling, sequential workflow
- v1.2.0: Fixed polygon support - tables can now be any quadrilateral shape
- v1.1.0: Added service area labeling, improved visual feedback
- v1.0.0: Initial release

Author: ASEOfSmartICE Team
"""

import cv2
import numpy as np
from ultralytics import YOLO
import os
from pathlib import Path
import argparse
import time
import json
from collections import deque
from datetime import datetime
from enum import Enum

# Model paths and configuration (relative to script location)
SCRIPT_DIR = Path(__file__).parent.resolve()
PERSON_DETECTOR_MODEL = str(SCRIPT_DIR / "models" / "yolov8m.pt")
STAFF_CLASSIFIER_MODEL = str(SCRIPT_DIR / "models" / "waiter_customer_classifier.pt")

# Detection parameters
PERSON_CONF_THRESHOLD = 0.3
STAFF_CONF_THRESHOLD = 0.5
MIN_PERSON_SIZE = 40

# ROI configuration
TABLE_CONFIG_FILE = str(SCRIPT_DIR / "table_config.json")

# State transition parameters
STATE_DEBOUNCE_SECONDS = 1.0  # State must be stable for 1s before confirming change

# Visual configuration
COLORS = {
    'person': (255, 255, 0),        # Cyan for person detection
    'waiter': (0, 255, 0),          # Green for waiters
    'customer': (0, 0, 255),        # Red for customers
    'unknown': (128, 128, 128),     # Gray for unknown

    # Table state colors (in result video)
    'table_idle': (0, 255, 0),      # GREEN for IDLE (empty/available)
    'table_busy': (0, 255, 255),    # YELLOW for BUSY (customers dining)
    'table_cleaning': (255, 0, 0),  # BLUE for CLEANING (staff cleaning/turnover)

    # ROI colors in result video (gray - not changing)
    'sitting_area_result': (128, 128, 128),  # Gray for sitting areas in result

    # Drawing colors (during labeling)
    'drawing_table': (0, 255, 255),      # Yellow for table being drawn
    'drawing_sitting': (0, 200, 255),    # Light yellow for sitting area being drawn
}

CLASS_NAMES = {0: 'customer', 1: 'waiter'}


class TableState(Enum):
    """Table state enumeration"""
    IDLE = "IDLE"           # No one at table
    BUSY = "BUSY"           # Customers only
    CLEANING = "CLEANING"   # Staff only


class SittingArea:
    """Represents a sitting area (chairs around a table)"""

    def __init__(self, area_id, polygon, table_id):
        self.id = area_id
        self.polygon = polygon  # List of (x, y) tuples for polygon vertices
        self.table_id = table_id  # Which table this sitting area belongs to
        self.customers_present = 0

    def get_polygon_from_bbox(self):
        """Get polygon points for ROI checking"""
        return self.polygon

    def get_bbox(self):
        """Get bounding box for display purposes"""
        xs = [p[0] for p in self.polygon]
        ys = [p[1] for p in self.polygon]
        return [min(xs), min(ys), max(xs), max(ys)]


class Table:
    """Represents a single restaurant table with state tracking"""

    def __init__(self, table_id, polygon, capacity=4):
        self.id = table_id
        self.polygon = polygon  # List of (x, y) tuples for polygon vertices (4 points)
        self.capacity = capacity
        self.state = TableState.IDLE
        self.customers_present = 0
        self.waiters_present = 0
        self.state_change_time = None
        self.pending_state = None
        self.pending_state_start = None

        # Associated ROIs (can have multiple sitting areas)
        self.sitting_area_ids = []  # List of associated sitting area IDs

        # Statistics
        self.state_durations = {state: 0.0 for state in TableState}
        self.state_transitions = []

    def get_polygon_from_bbox(self):
        """Get polygon points for ROI checking"""
        return self.polygon

    def get_bbox(self):
        """Get bounding box for display purposes"""
        xs = [p[0] for p in self.polygon]
        ys = [p[1] for p in self.polygon]
        return [min(xs), min(ys), max(xs), max(ys)]

    def update_counts(self, customers, waiters):
        """Update customer and waiter counts"""
        self.customers_present = customers
        self.waiters_present = waiters

    def determine_state(self):
        """Determine table state based on current counts"""
        if self.customers_present == 0 and self.waiters_present == 0:
            return TableState.IDLE
        elif self.customers_present > 0 and self.waiters_present == 0:
            return TableState.BUSY
        elif self.waiters_present > 0:
            # If there are any waiters, it's cleaning (regardless of customers)
            # This prioritizes cleaning state when staff is present
            return TableState.CLEANING
        return TableState.IDLE

    def update_state(self, current_time):
        """Update state with debouncing"""
        new_state = self.determine_state()

        # Check if state is different from current
        if new_state != self.state:
            # Check if this is a new pending state
            if self.pending_state != new_state:
                self.pending_state = new_state
                self.pending_state_start = current_time
            else:
                # Same pending state - check if debounce period has passed
                if current_time - self.pending_state_start >= STATE_DEBOUNCE_SECONDS:
                    # Confirm state transition
                    old_state = self.state
                    self.state = new_state
                    self.state_change_time = current_time
                    self.pending_state = None
                    self.pending_state_start = None

                    # Record transition
                    self.state_transitions.append({
                        'time': current_time,
                        'from': old_state.value,
                        'to': new_state.value
                    })
                    return True  # State changed
        else:
            # Current observation matches current state - reset pending
            self.pending_state = None
            self.pending_state_start = None

        return False  # No state change

    def get_state_color(self):
        """Get color for current table state"""
        color_map = {
            TableState.IDLE: COLORS['table_idle'],
            TableState.BUSY: COLORS['table_busy'],
            TableState.CLEANING: COLORS['table_cleaning']
        }
        return color_map.get(self.state, COLORS['table_idle'])


# Global variables for ROI drawing
tables = []
sitting_areas = []  # Track sitting areas (chairs around tables)
current_table_points = []
drawing_mode = True
drawing_type = 'table'  # 'table' or 'sitting'
mouse_position = (0, 0)  # Track mouse for visual feedback
current_table_index = 0  # Track which table we're working on


class PerformanceTracker:
    """Track processing performance metrics"""

    def __init__(self, window_size=30):
        self.window_size = window_size
        self.frame_times = deque(maxlen=window_size)
        self.stage1_times = deque(maxlen=window_size)
        self.stage2_times = deque(maxlen=window_size)

        self.total_frames = 0
        self.total_processing_time = 0.0
        self.total_stage1_time = 0.0
        self.total_stage2_time = 0.0

    def add_frame(self, frame_time, stage1_time, stage2_time):
        """Add frame processing stats"""
        self.frame_times.append(frame_time)
        self.stage1_times.append(stage1_time)
        self.stage2_times.append(stage2_time)

        self.total_frames += 1
        self.total_processing_time += frame_time
        self.total_stage1_time += stage1_time
        self.total_stage2_time += stage2_time

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

        avg_stage1_ms = (self.total_stage1_time / self.total_frames * 1000) if self.total_frames > 0 else 0
        avg_stage2_ms = (self.total_stage2_time / self.total_frames * 1000) if self.total_frames > 0 else 0

        print(f"\n{'='*70}")
        print(f"Processing Summary")
        print(f"{'='*70}")
        print(f"Video Information:")
        print(f"   Total frames processed: {self.total_frames}")
        print(f"   Original video FPS: {original_fps:.2f}")
        print(f"   Video duration: {video_duration:.2f}s")
        print(f"")
        print(f"Performance Metrics:")
        print(f"   Processing FPS: {avg_fps:.2f} fps")
        print(f"   Real-time ratio: {avg_fps/original_fps:.2%}")
        print(f"   Total processing time: {total_time:.2f}s")
        print(f"")
        print(f"Stage Processing Times (average):")
        print(f"   Stage 1 (person detection): {avg_stage1_ms:.1f}ms")
        print(f"   Stage 2 (classification): {avg_stage2_ms:.1f}ms")
        print(f"   Total pipeline: {avg_stage1_ms + avg_stage2_ms:.1f}ms")
        print(f"{'='*70}\n")


def mouse_callback(event, x, y, flags, param):
    """Mouse callback for ROI drawing with visual feedback"""
    global current_table_points, drawing_mode, drawing_type, mouse_position

    if not drawing_mode:
        return

    # Update mouse position for visual feedback
    if event == cv2.EVENT_MOUSEMOVE:
        mouse_position = (x, y)

    if event == cv2.EVENT_LBUTTONDOWN:
        current_table_points.append((x, y))
        roi_type_map = {
            'table': 'TABLE',
            'sitting': 'SITTING AREA'
        }
        roi_type = roi_type_map.get(drawing_type, 'ROI')
        print(f"   {roi_type} Point {len(current_table_points)}: ({x}, {y})")


def draw_sitting_area_roi(frame, sitting_area, thickness=1, fill_alpha=0.05, is_labeling=False):
    """Draw sitting area ROI on frame (supports polygons)"""
    frame_copy = frame.copy()

    # Use bright color during labeling, gray in result video
    if is_labeling:
        color = COLORS['drawing_sitting']
        thickness = 2
        fill_alpha = 0.15
    else:
        color = COLORS['sitting_area_result']  # Gray in result

    # Get polygon points
    polygon_points = sitting_area.polygon
    pts = np.array(polygon_points, np.int32)
    pts = pts.reshape((-1, 1, 2))

    # Draw polygon outline
    cv2.polylines(frame_copy, [pts], isClosed=True, color=color, thickness=thickness)

    # Fill with very light semi-transparent overlay (subtle)
    if fill_alpha > 0:
        overlay = frame_copy.copy()
        cv2.fillPoly(overlay, [pts], color)
        cv2.addWeighted(overlay, fill_alpha, frame_copy, 1 - fill_alpha, 0, frame_copy)

    # Draw sitting area ID at center (only during labeling)
    if is_labeling:
        bbox = sitting_area.get_bbox()
        label_x = int((bbox[0] + bbox[2]) / 2 - 20)
        label_y = int((bbox[1] + bbox[3]) / 2)
        label = f"S{sitting_area.id[1:]}"  # Show "S1" instead of "SA1"
        cv2.putText(frame_copy, label, (label_x, label_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    return frame_copy


def draw_table_roi(frame, table, thickness=3, fill_alpha=0.25):
    """Draw single table ROI on frame (supports polygons)"""
    frame_copy = frame.copy()

    # Get polygon points
    polygon_points = table.polygon
    pts = np.array(polygon_points, np.int32)
    pts = pts.reshape((-1, 1, 2))

    # Get color based on state
    color = table.get_state_color()

    # Draw polygon outline (thicker for visibility)
    cv2.polylines(frame_copy, [pts], isClosed=True, color=color, thickness=thickness)

    # Fill with semi-transparent overlay
    overlay = frame_copy.copy()
    cv2.fillPoly(overlay, [pts], color)
    cv2.addWeighted(overlay, fill_alpha, frame_copy, 1 - fill_alpha, 0, frame_copy)

    # Draw table ID and state at center
    bbox = table.get_bbox()
    center_x = int((bbox[0] + bbox[2]) / 2)
    center_y = int((bbox[1] + bbox[3]) / 2)

    # Table ID on top line
    label_id = f"{table.id}"
    id_size = cv2.getTextSize(label_id, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)[0]
    cv2.putText(frame_copy, label_id,
               (center_x - id_size[0]//2, center_y - 10),
               cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

    # State name on bottom line (English)
    label_state = table.state.value  # Use English state names directly
    state_size = cv2.getTextSize(label_state, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
    cv2.putText(frame_copy, label_state,
               (center_x - state_size[0]//2, center_y + 20),
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    return frame_copy


def draw_all_rois(frame, tables, sitting_areas, is_labeling=False):
    """Draw all ROIs (sitting areas and tables) on frame"""
    result = frame.copy()

    # Draw in layers: sitting areas (bottom) -> tables (top)
    for sitting_area in sitting_areas:
        result = draw_sitting_area_roi(result, sitting_area, is_labeling=is_labeling)

    for table in tables:
        result = draw_table_roi(result, table)

    return result


def draw_enhanced_instruction_panel(frame, drawing_type, current_table_idx, tables_count, sitting_count, points_count, mouse_pos, current_sitting_count):
    """Draw enhanced instruction panel with visual feedback"""
    overlay = frame.copy()
    panel_height = 210
    panel_width = 580

    # Semi-transparent background
    cv2.rectangle(overlay, (10, 10), (panel_width, panel_height), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

    font = cv2.FONT_HERSHEY_SIMPLEX
    y_offset = 35

    # Current table and mode indicator
    mode_map = {
        'table': 'TABLE',
        'sitting': 'SITTING AREAS'
    }
    color_map = {
        'table': COLORS['drawing_table'],
        'sitting': COLORS['drawing_sitting']
    }

    mode_text = f"TABLE {current_table_idx + 1} - {mode_map[drawing_type]}"
    mode_color = color_map[drawing_type]
    cv2.putText(frame, mode_text, (20, y_offset), font, 0.8, mode_color, 2)

    # Workflow progress
    y_offset += 30
    workflow_step = ""
    if drawing_type == 'table':
        workflow_step = f"Step 1/2: Label table area"
    elif drawing_type == 'sitting':
        workflow_step = f"Step 2/2: Sitting areas for T{current_table_idx + 1} (drawn: {current_sitting_count})"
    cv2.putText(frame, workflow_step, (20, y_offset), font, 0.5, (150, 255, 150), 1)

    # Counters
    y_offset += 25
    cv2.putText(frame, f"Total: T:{tables_count} S:{sitting_count} | Points: {points_count}",
               (20, y_offset), font, 0.5, (255, 255, 255), 1)

    # Mouse coordinates
    y_offset += 23
    cv2.putText(frame, f"Mouse: ({mouse_pos[0]}, {mouse_pos[1]})",
               (20, y_offset), font, 0.5, (255, 255, 0), 1)

    # Instructions
    y_offset += 28
    instructions = [
        "WORKFLOW (can draw multiple Sitting areas per table):",
        "  1. Click 4 corners for Table, press 'N'",
        "  2. Click 4 corners for Sitting Area, press 'N' (repeat for more)",
        "  3. Press 'D' when done with Sitting -> next table",
        "",
        "CONTROLS: 'N' Add ROI | 'D' Done (next table) | 'Z' Undo | 'S' Save | 'Q' Quit"
    ]

    for instruction in instructions:
        cv2.putText(frame, instruction, (20, y_offset), font, 0.35, (200, 200, 200), 1)
        y_offset += 16

    return frame


def setup_tables_from_video(video_path):
    """Setup multiple tables with associated sitting areas"""
    global tables, sitting_areas, current_table_points, drawing_mode, drawing_type, mouse_position, current_table_index

    print("\n" + "="*70)
    print("ROI Setup Mode - Sequential Table Labeling")
    print("="*70)

    # Open video and get first frame
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Could not open video: {video_path}")
        return None, None

    ret, frame = cap.read()
    cap.release()

    if not ret:
        print(f"Could not read first frame from video")
        return None, None

    print(f"Using first frame from: {os.path.basename(video_path)}")
    print(f"Frame size: {frame.shape[1]}x{frame.shape[0]}")
    print("\n" + "="*70)
    print("WORKFLOW (Multiple Sitting Areas per Table):")
    print("="*70)
    print("   1. Label TABLE area (yellow), press 'N'")
    print("   2. Label SITTING AREAS (light yellow), press 'N' for each")
    print("      (Can draw multiple sitting areas for one table)")
    print("   3. Press 'D' to complete this table and start next")
    print("\n   'N' - Complete current ROI and add it")
    print("   'D' - Done with current table, start next")
    print("   'S' - Save all and finish")
    print("   'Z' - Undo last point")
    print("   'Q' - Quit without saving")
    print("="*70 + "\n")

    tables = []
    sitting_areas = []
    current_table_points = []
    drawing_mode = True
    drawing_type = 'table'  # Start with table
    mouse_position = (0, 0)
    current_table_index = 0

    # Track how many sitting areas for current table
    current_table_sitting_count = 0

    cv2.namedWindow('ROI Setup', cv2.WINDOW_NORMAL)
    cv2.resizeWindow('ROI Setup', 1280, 720)
    cv2.setMouseCallback('ROI Setup', mouse_callback)

    while True:
        display_frame = frame.copy()

        # Draw existing ROIs (with bright colors for labeling)
        display_frame = draw_all_rois(display_frame, tables, sitting_areas, is_labeling=True)

        # Get current drawing color
        color_map = {
            'table': COLORS['drawing_table'],
            'sitting': COLORS['drawing_sitting']
        }
        draw_color = color_map[drawing_type]

        # Draw current ROI being defined
        if len(current_table_points) > 0:
            # Draw points with coordinates
            for idx, pt in enumerate(current_table_points):
                cv2.circle(display_frame, pt, 7, draw_color, -1)
                cv2.circle(display_frame, pt, 9, (255, 255, 255), 2)
                # Label each point
                cv2.putText(display_frame, f"{idx+1}", (pt[0] + 12, pt[1] - 5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, draw_color, 2)

            # Draw lines between points
            if len(current_table_points) >= 2:
                for i in range(len(current_table_points)):
                    pt1 = current_table_points[i]
                    pt2 = current_table_points[(i + 1) % len(current_table_points)]
                    cv2.line(display_frame, pt1, pt2, draw_color, 3)

            # Show preview polygon if we have 3+ points
            if len(current_table_points) >= 3:
                pts = np.array(current_table_points, np.int32)
                pts = pts.reshape((-1, 1, 2))
                cv2.polylines(display_frame, [pts], isClosed=True, color=draw_color, thickness=2)

        # Draw crosshair at mouse position
        if mouse_position != (0, 0):
            mx, my = mouse_position
            cv2.drawMarker(display_frame, (mx, my), draw_color, cv2.MARKER_CROSS, 20, 2)

        # Draw enhanced instruction panel
        display_frame = draw_enhanced_instruction_panel(
            display_frame, drawing_type, current_table_index, len(tables),
            len(sitting_areas), len(current_table_points), mouse_position,
            current_table_sitting_count
        )

        cv2.imshow('ROI Setup', display_frame)
        key = cv2.waitKey(10) & 0xFF

        # 'n' or 'N' to add current ROI
        if key == ord('n') or key == ord('N'):
            if len(current_table_points) == 4:
                # Create ROI from 4 points as a polygon
                polygon = current_table_points.copy()

                if drawing_type == 'table':
                    # Create table
                    table_id = f"T{current_table_index + 1}"
                    table = Table(table_id, polygon)
                    tables.append(table)
                    print(f"\n✓ Table {table_id} created")
                    print(f"   >> Auto-switching to SITTING AREAS for {table_id}")
                    print(f"   (You can draw multiple sitting areas, press 'D' when done)")

                    # Auto-switch to sitting area
                    drawing_type = 'sitting'
                    current_table_sitting_count = 0
                    current_table_points = []

                elif drawing_type == 'sitting':
                    # Create sitting area
                    current_table_sitting_count += 1
                    sitting_id = f"SA{len(sitting_areas) + 1}"
                    table_id = f"T{current_table_index + 1}"
                    sitting_area = SittingArea(sitting_id, polygon, table_id)
                    sitting_areas.append(sitting_area)

                    # Link to table
                    tables[current_table_index].sitting_area_ids.append(sitting_id)

                    print(f"\n✓ Sitting Area {sitting_id} created (linked to {table_id})")
                    print(f"   >> You can draw more sitting areas or press 'D' to continue")

                    # Stay in sitting mode, clear points for next one
                    current_table_points = []

            else:
                print(f"\n✗ Need exactly 4 points (currently {len(current_table_points)})")

        # 'd' or 'D' to finish current table and switch to next
        elif key == ord('d') or key == ord('D'):
            if drawing_type == 'sitting':
                print(f"\n{'='*70}")
                print(f"✓ Finished {current_table_sitting_count} sitting area(s) for T{current_table_index + 1}")
                print(f"✓ TABLE {current_table_index + 1} COMPLETE!")
                print(f"{'='*70}")

                # Move to next table
                current_table_index += 1
                drawing_type = 'table'
                current_table_sitting_count = 0
                current_table_points = []

                print(f"\n>> Starting TABLE {current_table_index + 1}...")

            elif drawing_type == 'table':
                print(f"\n⚠ You must complete the table first (press 'N' after drawing 4 points)")

        # 's' or 'S' to save all ROIs
        elif key == ord('s') or key == ord('S'):
            if len(tables) > 0:
                # Check if there are incomplete tables
                if drawing_type != 'table' or current_table_points:
                    print(f"\n⚠ Warning: Current table not complete!")
                    print(f"   Current mode: {drawing_type}")
                    print(f"   Points drawn: {len(current_table_points)}")
                    print(f"   Press 'S' again to save anyway, or 'N' to complete current ROI")
                    continue

                # Save to config file
                config_data = {
                    'tables': [
                        {
                            'id': t.id,
                            'polygon': t.polygon,
                            'capacity': t.capacity,
                            'sitting_area_ids': t.sitting_area_ids
                        } for t in tables
                    ],
                    'sitting_areas': [
                        {
                            'id': sa.id,
                            'polygon': sa.polygon,
                            'table_id': sa.table_id
                        } for sa in sitting_areas
                    ],
                    'frame_size': [frame.shape[1], frame.shape[0]],
                    'video': video_path
                }

                with open(TABLE_CONFIG_FILE, 'w') as f:
                    json.dump(config_data, f, indent=2)

                print(f"\n{'='*70}")
                print(f"✓ Configuration Saved: {TABLE_CONFIG_FILE}")
                print(f"{'='*70}")
                print(f"  Complete Tables: {len(tables)}")
                print(f"  Sitting Areas: {len(sitting_areas)}")
                print(f"{'='*70}\n")

                cv2.destroyAllWindows()
                return tables, sitting_areas
            else:
                print("\n✗ No tables defined yet")

        # 'z' or 'Z' to undo
        elif key == ord('z') or key == ord('Z'):
            if current_table_points:
                removed_point = current_table_points.pop()
                print(f"   ↶ Undo: Removed point {removed_point}")
            else:
                print("   ✗ No points to undo")

        # 'q' or 'Q' to quit
        elif key == ord('q') or key == ord('Q'):
            print("\nROI setup cancelled")
            cv2.destroyAllWindows()
            return None, None

    cv2.destroyAllWindows()
    return tables, sitting_areas


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


def load_config_from_file(config_file):
    """Load table configuration from existing JSON file"""
    if not os.path.exists(config_file):
        return None, None

    print(f"\n{'='*70}")
    print(f"Loading existing configuration from: {os.path.basename(config_file)}")
    print(f"{'='*70}")

    try:
        with open(config_file, 'r') as f:
            config_data = json.load(f)

        # Reconstruct tables
        tables = []
        for table_data in config_data.get('tables', []):
            table = Table(
                table_data['id'],
                table_data['polygon'],
                table_data.get('capacity', 4)
            )
            table.sitting_area_ids = table_data.get('sitting_area_ids', [])
            tables.append(table)

        # Reconstruct sitting areas
        sitting_areas = []
        for sa_data in config_data.get('sitting_areas', []):
            sitting_area = SittingArea(
                sa_data['id'],
                sa_data['polygon'],
                sa_data['table_id']
            )
            sitting_areas.append(sitting_area)

        print(f"✓ Loaded {len(tables)} table(s) and {len(sitting_areas)} sitting area(s)")
        print(f"{'='*70}\n")

        return tables, sitting_areas

    except Exception as e:
        print(f"✗ Error loading config file: {e}")
        return None, None


def load_models():
    """Load both detection models"""
    print("Loading detection models...")

    print(f"   Loading person detector: {PERSON_DETECTOR_MODEL}")
    person_detector = YOLO(PERSON_DETECTOR_MODEL)

    if not os.path.exists(STAFF_CLASSIFIER_MODEL):
        print(f"Staff classifier not found: {STAFF_CLASSIFIER_MODEL}")
        return None, None

    print(f"   Loading staff classifier: {STAFF_CLASSIFIER_MODEL}")
    staff_classifier = YOLO(STAFF_CLASSIFIER_MODEL)

    print("Both models loaded successfully!\n")
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


def assign_detections_to_rois(tables, sitting_areas, detections):
    """Assign each detection to appropriate table or sitting area"""
    # Reset counts
    for table in tables:
        table.update_counts(0, 0)
    for sitting_area in sitting_areas:
        sitting_area.customers_present = 0

    for detection in detections:
        center = detection['center']
        assigned = False

        # Priority 1: Check tables (main eating surface)
        for table in tables:
            polygon = table.get_polygon_from_bbox()
            if point_in_polygon(center, polygon):
                # Count both customers and waiters on table
                if detection['class'] == 'customer':
                    table.customers_present += 1
                elif detection['class'] == 'waiter':
                    table.waiters_present += 1
                assigned = True
                break

        # Priority 2: Check sitting areas (chairs around tables)
        if not assigned:
            for sitting_area in sitting_areas:
                polygon = sitting_area.get_polygon_from_bbox()
                if point_in_polygon(center, polygon):
                    # Count both customers and waiters in sitting areas
                    if detection['class'] == 'customer':
                        sitting_area.customers_present += 1
                        # Also count for associated table
                        for table in tables:
                            if table.id == sitting_area.table_id:
                                table.customers_present += 1
                                break
                    elif detection['class'] == 'waiter':
                        # Count waiters in sitting areas for associated table
                        for table in tables:
                            if table.id == sitting_area.table_id:
                                table.waiters_present += 1
                                break
                    assigned = True
                    break


def draw_detections_and_tables(frame, detections, tables, sitting_areas, tracker):
    """Draw detections, tables, and sitting areas"""
    annotated_frame = frame.copy()

    # Draw all ROIs (sitting areas + tables)
    # is_labeling=False means gray ROIs for sitting areas in result video
    annotated_frame = draw_all_rois(annotated_frame, tables, sitting_areas, is_labeling=False)

    # Draw detections
    for detection in detections:
        x1, y1, x2, y2 = detection['bbox']
        class_name = detection['class']
        confidence = detection['confidence']
        center = detection['center']

        color = COLORS.get(class_name, COLORS['unknown'])
        cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)

        if confidence > 0:
            label = f"{class_name}: {confidence:.1%}"
        else:
            label = f"{class_name}"

        label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
        cv2.rectangle(annotated_frame,
                     (x1, y1 - label_size[1] - 8),
                     (x1 + label_size[0] + 6, y1),
                     color, -1)

        cv2.putText(annotated_frame, label,
                   (x1 + 3, y1 - 4),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        # Draw center point used for ROI assignment (bright white circle with black outline)
        cv2.circle(annotated_frame, center, 8, (0, 0, 0), -1)  # Black fill
        cv2.circle(annotated_frame, center, 6, (255, 255, 255), -1)  # White center
        cv2.circle(annotated_frame, center, 6, color, 2)  # Colored outline matching person class

    # Draw stats overlay
    stats_y = 30
    stats_x = 10
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.6
    font_thickness = 2
    line_height = 25

    # Background for stats
    overlay = annotated_frame.copy()
    stats_height = 100 + (len(tables) * 25)
    cv2.rectangle(overlay, (5, 5), (400, stats_height), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, annotated_frame, 0.4, 0, annotated_frame)

    # Current FPS
    current_fps = tracker.get_current_fps()
    cv2.putText(annotated_frame, f"FPS: {current_fps:.2f}",
               (stats_x, stats_y), font, font_scale, (0, 255, 255), font_thickness)

    # Frame count
    stats_y += line_height
    cv2.putText(annotated_frame, f"Frame: {tracker.total_frames}",
               (stats_x, stats_y), font, font_scale, (255, 255, 255), font_thickness)

    # Stage times
    avg_stage1, avg_stage2 = tracker.get_avg_stage_times()
    stats_y += line_height
    cv2.putText(annotated_frame, f"Stage1: {avg_stage1:.0f}ms | Stage2: {avg_stage2:.0f}ms",
               (stats_x, stats_y), font, font_scale, (255, 255, 0), font_thickness)

    # ROI counts
    stats_y += line_height
    cv2.putText(annotated_frame, f"T:{len(tables)} S:{len(sitting_areas)}",
               (stats_x, stats_y), font, font_scale, (255, 255, 255), font_thickness)

    # Individual table info
    for table in tables:
        stats_y += line_height
        state_color = table.get_state_color()
        table_info = f"{table.id}: {table.state.value} (C:{table.customers_present} W:{table.waiters_present})"
        cv2.putText(annotated_frame, table_info,
                   (stats_x + 10, stats_y), font, 0.5, state_color, 1)

    return annotated_frame


def process_video(video_path, person_detector, staff_classifier, tables, sitting_areas, output_dir=None, duration_limit=None):
    """Process video with multi-table state detection and sitting area tracking"""
    # Default output to script's own results directory
    if output_dir is None:
        output_dir = str(Path(__file__).parent / "results")

    print(f"\n{'='*70}")
    print(f"Processing Video with Table State Detection")
    print(f"{'='*70}")
    print(f"Video: {os.path.basename(video_path)}")
    print(f"Tables: {len(tables)} | Sitting Areas: {len(sitting_areas)}\n")

    # Open video
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Could not open video: {video_path}")
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

    print(f"Video Properties:")
    print(f"   Resolution: {width}x{height}")
    print(f"   FPS: {fps:.2f}")
    print(f"   Total frames: {frame_count}")
    print(f"   Duration: {duration:.2f}s")
    if duration_limit is not None:
        print(f"   Processing: {max_frames} frames ({duration_limit}s)")
    print()

    # Setup output video
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    script_name = Path(__file__).stem
    output_filename = f"{script_name}_{Path(video_path).stem}.mp4"
    output_file = str(output_path / output_filename)

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_file, fourcc, fps, (width, height))

    if not out.isOpened():
        print(f"Could not create output video: {output_file}")
        cap.release()
        return False

    # Initialize performance tracker
    tracker = PerformanceTracker(window_size=30)

    # Process video frames
    frame_idx = 0

    print("Processing frames...")
    print(f"Monitoring {len(tables)} tables, {len(sitting_areas)} sitting areas")
    print(f"State debounce: {STATE_DEBOUNCE_SECONDS}s")
    print("\nTable State Colors (in output video):")
    print("  GREEN   - IDLE: Empty table, no one around")
    print("  YELLOW  - BUSY: Only customers present (dining)")
    print("  BLUE    - CLEANING: Only staff present (cleaning/turnover)")
    print()

    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame_idx >= max_frames:
                break

            frame_start = time.time()
            current_time = time.time()

            # Stage 1: Detect all persons
            stage1_start = time.time()
            person_detections = detect_persons(person_detector, frame)
            stage1_time = time.time() - stage1_start

            # Stage 2: Classify persons
            stage2_start = time.time()
            classified_detections = classify_persons(staff_classifier, frame, person_detections)
            stage2_time = time.time() - stage2_start

            # Assign detections to tables and sitting areas
            assign_detections_to_rois(tables, sitting_areas, classified_detections)

            # Update table states
            for table in tables:
                if table.update_state(current_time):
                    print(f"   {table.id} state changed: {table.state.value} "
                          f"(C:{table.customers_present} W:{table.waiters_present})")

            # Total frame time
            frame_time = time.time() - frame_start

            # Update tracker
            tracker.add_frame(frame_time, stage1_time, stage2_time)

            # Draw detections, tables, and sitting areas
            annotated_frame = draw_detections_and_tables(frame, classified_detections, tables, sitting_areas, tracker)

            # Write frame
            out.write(annotated_frame)

            frame_idx += 1

            # Print progress every 30 frames
            if frame_idx % 30 == 0:
                progress = (frame_idx / max_frames) * 100
                current_fps = tracker.get_current_fps()

                table_states = " | ".join([f"{t.id}:{t.state.value[:3]}" for t in tables])
                print(f"   Progress: {progress:.1f}% | Frame {frame_idx}/{max_frames} | "
                      f"FPS: {current_fps:.2f} | {table_states}")

    except KeyboardInterrupt:
        print("\nProcessing interrupted by user")

    finally:
        cap.release()
        out.release()

        # Print summary
        tracker.print_summary(duration if duration_limit is None else duration_limit, fps)

        # Print table statistics
        print(f"\n{'='*70}")
        print(f"Table State Summary")
        print(f"{'='*70}")
        for table in tables:
            print(f"\n{table.id}:")
            print(f"   Final State: {table.state.value}")
            print(f"   Customers: {table.customers_present}")
            print(f"   Waiters: {table.waiters_present}")
            print(f"   Transitions: {len(table.state_transitions)}")
            if table.state_transitions:
                print(f"   Recent transitions:")
                for trans in table.state_transitions[-3:]:
                    print(f"      {trans['from']} -> {trans['to']}")
        print(f"{'='*70}\n")

        print(f"Output saved: {output_file}")
        print(f"Video processing complete!\n")

    return True


def main():
    """Main function with argument parsing"""
    parser = argparse.ArgumentParser(
        description="Table State Detection System - Multi-table monitoring with state tracking",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process video with ROI setup (tables + sitting areas)
  python3 table-state-detection.py --video test_video.mp4 --duration 60

  # Process full video
  python3 table-state-detection.py --video restaurant_cam.mp4

Note: System tracks 3 states - IDLE (no one), BUSY (customers only), CLEANING (staff only)
        """
    )
    parser.add_argument("--video", required=True, help="Path to input video")
    parser.add_argument("--output", default=str(Path(__file__).parent / "results"), help="Output directory")
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

    # Step 1: Setup tables and sitting areas
    print("\n" + "="*70)
    print("Step 1: ROI Setup (Tables + Sitting Areas)")
    print("="*70)

    # Try to load existing config first
    tables, sitting_areas = load_config_from_file(TABLE_CONFIG_FILE)

    # If no existing config, create new one using GUI
    if tables is None or len(tables) == 0:
        print("No existing configuration found. Starting interactive ROI setup...")
        tables, sitting_areas = setup_tables_from_video(args.video)

        if tables is None:
            print("\nROI setup cancelled. Exiting.")
            return 1

        if len(tables) == 0:
            print("\nNo tables defined. At least one table is required. Exiting.")
            return 1

    # Sitting areas are optional but recommended
    if sitting_areas is None:
        sitting_areas = []

    # Step 2: Load models
    print("\n" + "="*70)
    print("Step 2: Loading Models")
    print("="*70)
    person_detector, staff_classifier = load_models()
    if person_detector is None or staff_classifier is None:
        return 1

    # Step 3: Process video
    print("\n" + "="*70)
    print("Step 3: Processing Video")
    print("="*70)
    success = process_video(args.video, person_detector, staff_classifier, tables, sitting_areas,
                           args.output, args.duration)

    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
