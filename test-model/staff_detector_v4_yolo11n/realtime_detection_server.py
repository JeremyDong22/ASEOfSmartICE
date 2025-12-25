#!/usr/bin/env python3
"""
ASEOfSmartICE Staff Detector V4 - Real-Time Detection Server
Version: 1.1.0 - Added multi-channel support via --channel argument

Purpose:
- Serve real-time staff detection via web interface
- Connect to NVR RTSP stream (configurable channel)
- Display comprehensive detection and video quality metrics
- Track FPS, latency, detection confidence, and video health stats

RTSP Source: SmartICE NVR (192.168.1.3) - Channels 1-30
Model: YOLO11n Staff Detection (~5.4MB)

Usage:
  python3 realtime_detection_server.py --channel 18   # Port 5018
  python3 realtime_detection_server.py --channel 14   # Port 5014
  python3 realtime_detection_server.py --channel 2    # Port 5002

Created: 2025-12-25
Updated: 2025-12-25 - Added --channel argument support
"""

import cv2
import numpy as np
from ultralytics import YOLO
from flask import Flask, render_template, Response, jsonify
import threading
import time
import os
import argparse
from collections import deque
from datetime import datetime

# =============================================================================
# Configuration
# =============================================================================

# NVR Configuration
NVR_IP = "192.168.1.3"
NVR_PORT = 554
NVR_USER = "admin"
NVR_PASS = "ybl123456789"

# Default channel (can be overridden via --channel argument)
DEFAULT_CHANNEL = 18

# These will be set based on channel selection
CHANNEL = DEFAULT_CHANNEL
RTSP_URL = ""
RTSP_URL_SUB = ""
SERVER_PORT = 5000 + DEFAULT_CHANNEL

def set_channel(channel):
    """Configure RTSP URLs and port based on channel number"""
    global CHANNEL, RTSP_URL, RTSP_URL_SUB, SERVER_PORT
    CHANNEL = channel
    RTSP_URL = f"rtsp://{NVR_USER}:{NVR_PASS}@{NVR_IP}:{NVR_PORT}/unicast/c{channel}/s0/live"
    RTSP_URL_SUB = f"rtsp://{NVR_USER}:{NVR_PASS}@{NVR_IP}:{NVR_PORT}/unicast/c{channel}/s1/live"
    SERVER_PORT = 5000 + channel

# Model Configuration
MODEL_PATH = "models/staff_detector.pt"
CONF_THRESHOLD = 0.5
IOU_THRESHOLD = 0.45

# Server Configuration
SERVER_HOST = "0.0.0.0"

# Visual Configuration
STAFF_COLOR = (0, 255, 0)  # Green for staff detection
BOX_THICKNESS = 2
FONT_SCALE = 0.6

# Stats window size (rolling average)
STATS_WINDOW = 30

# =============================================================================
# Global State
# =============================================================================

app = Flask(__name__)

# Statistics tracking with thread-safe deques
stats = {
    "fps_history": deque(maxlen=STATS_WINDOW),
    "inference_times": deque(maxlen=STATS_WINDOW),
    "detection_counts": deque(maxlen=STATS_WINDOW),
    "confidence_scores": deque(maxlen=100),
    "frame_drop_count": 0,
    "total_frames": 0,
    "start_time": None,
    "last_frame_time": None,
    "stream_width": 0,
    "stream_height": 0,
    "stream_fps": 0,
    "stream_bitrate_kbps": 0,
    "frame_size_bytes": deque(maxlen=STATS_WINDOW),
    "connection_status": "disconnected",
    "model_loaded": False,
    "current_detections": 0,
    "avg_confidence": 0.0,
    "latency_ms": 0,
}

stats_lock = threading.Lock()

# Model and capture objects
model = None
capture = None
output_frame = None
frame_lock = threading.Lock()

# =============================================================================
# Model Loading
# =============================================================================

def load_model():
    """Load YOLO11n staff detection model"""
    global model, stats

    print("=" * 60)
    print("Loading YOLO11n Staff Detection Model")
    print("=" * 60)

    model_path = os.path.join(os.path.dirname(__file__), MODEL_PATH)

    if not os.path.exists(model_path):
        print(f"ERROR: Model not found at {model_path}")
        return False

    try:
        start_time = time.time()
        model = YOLO(model_path)
        load_time = (time.time() - start_time) * 1000

        print(f"Model Path: {model_path}")
        print(f"Model Size: ~5.4 MB")
        print(f"Load Time: {load_time:.1f}ms")
        print("Model loaded successfully!")

        with stats_lock:
            stats["model_loaded"] = True

        return True
    except Exception as e:
        print(f"ERROR loading model: {e}")
        return False

# =============================================================================
# RTSP Stream Handling
# =============================================================================

def connect_stream():
    """Connect to RTSP stream with fallback"""
    global capture, stats

    print("\n" + "=" * 60)
    print("Connecting to RTSP Stream")
    print("=" * 60)

    # Try main stream first
    urls_to_try = [
        ("Main Stream (s0)", RTSP_URL),
        ("Sub Stream (s1)", RTSP_URL_SUB),
    ]

    for stream_name, url in urls_to_try:
        print(f"\nTrying {stream_name}...")
        print(f"URL: {url}")

        cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)

        # Set buffer size to minimize latency
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        # Wait for connection
        time.sleep(2)

        if cap.isOpened():
            # Read a test frame
            ret, frame = cap.read()
            if ret and frame is not None:
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = cap.get(cv2.CAP_PROP_FPS)

                print(f"Connected successfully!")
                print(f"Resolution: {width}x{height}")
                print(f"Stream FPS: {fps}")

                with stats_lock:
                    stats["stream_width"] = width
                    stats["stream_height"] = height
                    stats["stream_fps"] = fps
                    stats["connection_status"] = "connected"
                    stats["start_time"] = time.time()

                return cap

        cap.release()
        print(f"Failed to connect to {stream_name}")

    print("\nERROR: Could not connect to any stream")
    with stats_lock:
        stats["connection_status"] = "failed"

    return None

# =============================================================================
# Detection and Frame Processing
# =============================================================================

def detect_and_annotate(frame):
    """Run detection and annotate frame"""
    global stats

    if model is None:
        return frame, [], 0

    # Run inference with timing
    start_time = time.time()
    results = model(frame, conf=CONF_THRESHOLD, iou=IOU_THRESHOLD, verbose=False)
    inference_time = (time.time() - start_time) * 1000

    detections = []
    annotated = frame.copy()

    for result in results:
        boxes = result.boxes
        if boxes is not None:
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                confidence = float(box.conf[0].cpu().numpy())

                detections.append({
                    "bbox": (x1, y1, x2, y2),
                    "confidence": confidence
                })

                # Draw bounding box
                cv2.rectangle(annotated, (x1, y1), (x2, y2), STAFF_COLOR, BOX_THICKNESS)

                # Draw label
                label = f"Staff: {confidence:.1%}"
                label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, FONT_SCALE, 2)[0]
                cv2.rectangle(annotated,
                             (x1, y1 - label_size[1] - 10),
                             (x1 + label_size[0], y1),
                             STAFF_COLOR, -1)
                cv2.putText(annotated, label, (x1, y1 - 5),
                           cv2.FONT_HERSHEY_SIMPLEX, FONT_SCALE, (255, 255, 255), 2)

    return annotated, detections, inference_time

def add_stats_overlay(frame, fps, inference_time, detection_count):
    """Add stats overlay to frame"""
    h, w = frame.shape[:2]

    # Create semi-transparent overlay for stats
    overlay = frame.copy()
    cv2.rectangle(overlay, (10, 10), (300, 140), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

    # Stats text
    stats_text = [
        f"FPS: {fps:.1f}",
        f"Inference: {inference_time:.1f}ms",
        f"Detections: {detection_count}",
        f"Resolution: {w}x{h}",
        f"Channel: {CHANNEL}"
    ]

    y_offset = 30
    for text in stats_text:
        cv2.putText(frame, text, (20, y_offset),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        y_offset += 22

    return frame

def capture_frames():
    """Background thread for capturing and processing frames"""
    global output_frame, capture, stats

    # Load model first
    if not load_model():
        print("Failed to load model")
        return

    # Connect to stream
    capture = connect_stream()
    if capture is None:
        print("Failed to connect to stream")
        return

    print("\n" + "=" * 60)
    print("Starting Real-Time Detection")
    print("=" * 60)

    fps_start_time = time.time()
    fps_frame_count = 0
    current_fps = 0.0

    while True:
        ret, frame = capture.read()

        if not ret or frame is None:
            with stats_lock:
                stats["frame_drop_count"] += 1

            # Try to reconnect
            print("Frame read failed, attempting reconnect...")
            capture.release()
            time.sleep(1)
            capture = connect_stream()
            if capture is None:
                break
            continue

        # Track frame timing
        current_time = time.time()
        with stats_lock:
            stats["total_frames"] += 1
            stats["last_frame_time"] = current_time
            stats["frame_size_bytes"].append(frame.nbytes)

        # Run detection
        annotated_frame, detections, inference_time = detect_and_annotate(frame)

        # Calculate FPS
        fps_frame_count += 1
        elapsed = current_time - fps_start_time
        if elapsed >= 1.0:
            current_fps = fps_frame_count / elapsed
            fps_frame_count = 0
            fps_start_time = current_time

        # Update statistics
        with stats_lock:
            stats["fps_history"].append(current_fps)
            stats["inference_times"].append(inference_time)
            stats["detection_counts"].append(len(detections))
            stats["current_detections"] = len(detections)
            stats["latency_ms"] = inference_time

            for det in detections:
                stats["confidence_scores"].append(det["confidence"])

            if stats["confidence_scores"]:
                stats["avg_confidence"] = np.mean(list(stats["confidence_scores"]))

        # Add overlay and update output frame
        annotated_frame = add_stats_overlay(annotated_frame, current_fps, inference_time, len(detections))

        with frame_lock:
            output_frame = annotated_frame.copy()

def generate_frames():
    """Generator for video streaming"""
    global output_frame

    while True:
        with frame_lock:
            if output_frame is None:
                continue

            # Encode frame as JPEG
            ret, buffer = cv2.imencode('.jpg', output_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if not ret:
                continue

            frame_bytes = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

        time.sleep(0.033)  # ~30 FPS target

# =============================================================================
# Flask Routes
# =============================================================================

@app.route('/')
def index():
    """Main page"""
    return render_template('detection_dashboard.html')

@app.route('/video_feed')
def video_feed():
    """Video streaming route"""
    return Response(generate_frames(),
                   mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/stats')
def get_stats():
    """Return current statistics as JSON"""
    with stats_lock:
        # Calculate rolling averages
        avg_fps = np.mean(list(stats["fps_history"])) if stats["fps_history"] else 0
        avg_inference = np.mean(list(stats["inference_times"])) if stats["inference_times"] else 0
        avg_detections = np.mean(list(stats["detection_counts"])) if stats["detection_counts"] else 0
        avg_frame_size = np.mean(list(stats["frame_size_bytes"])) if stats["frame_size_bytes"] else 0

        # Calculate uptime
        uptime_seconds = time.time() - stats["start_time"] if stats["start_time"] else 0

        # Estimate bitrate
        bitrate_kbps = (avg_frame_size * 8 * avg_fps) / 1000 if avg_fps > 0 else 0

        return jsonify({
            # Core metrics
            "fps": round(avg_fps, 1),
            "inference_time_ms": round(avg_inference, 1),
            "current_detections": stats["current_detections"],
            "avg_detections": round(avg_detections, 1),

            # Confidence stats
            "avg_confidence": round(stats["avg_confidence"] * 100, 1),
            "min_confidence": round(min(stats["confidence_scores"]) * 100, 1) if stats["confidence_scores"] else 0,
            "max_confidence": round(max(stats["confidence_scores"]) * 100, 1) if stats["confidence_scores"] else 0,

            # Video quality metrics
            "resolution": f"{stats['stream_width']}x{stats['stream_height']}",
            "stream_fps": stats["stream_fps"],
            "estimated_bitrate_kbps": round(bitrate_kbps, 0),
            "avg_frame_size_kb": round(avg_frame_size / 1024, 1),

            # Health metrics
            "connection_status": stats["connection_status"],
            "model_loaded": stats["model_loaded"],
            "total_frames": stats["total_frames"],
            "frame_drops": stats["frame_drop_count"],
            "drop_rate_percent": round((stats["frame_drop_count"] / stats["total_frames"] * 100) if stats["total_frames"] > 0 else 0, 2),
            "uptime_seconds": round(uptime_seconds, 0),

            # Model config
            "conf_threshold": CONF_THRESHOLD,
            "iou_threshold": IOU_THRESHOLD,
            "channel": CHANNEL,

            # Timestamp
            "timestamp": datetime.now().isoformat()
        })

@app.route('/health')
def health():
    """Health check endpoint"""
    with stats_lock:
        return jsonify({
            "status": "healthy" if stats["connection_status"] == "connected" else "unhealthy",
            "model_loaded": stats["model_loaded"],
            "stream_connected": stats["connection_status"] == "connected"
        })

# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    """Main entry point with argument parsing"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Staff Detector V4 Real-Time Detection Server')
    parser.add_argument('--channel', type=int, default=DEFAULT_CHANNEL,
                        help=f'NVR channel number (1-30, default: {DEFAULT_CHANNEL})')
    parser.add_argument('--port', type=int, default=None,
                        help='Server port (default: 5000 + channel)')
    args = parser.parse_args()

    # Validate channel
    if args.channel < 1 or args.channel > 30:
        print(f"ERROR: Channel must be between 1 and 30, got {args.channel}")
        return 1

    # Configure channel
    set_channel(args.channel)

    # Override port if specified
    global SERVER_PORT
    if args.port:
        SERVER_PORT = args.port

    print("\n")
    print("*" * 60)
    print("*" + " " * 58 + "*")
    print("*" + "  Staff Detector V4 - Real-Time Detection Server".center(58) + "*")
    print("*" + " " * 58 + "*")
    print("*" * 60)
    print(f"\nChannel: {CHANNEL}")
    print(f"RTSP: {RTSP_URL}")
    print(f"Server URL: http://{SERVER_HOST}:{SERVER_PORT}")
    print("\n")

    # Create templates directory if needed
    templates_dir = os.path.join(os.path.dirname(__file__), 'templates')
    os.makedirs(templates_dir, exist_ok=True)

    # Start capture thread
    capture_thread = threading.Thread(target=capture_frames, daemon=True)
    capture_thread.start()

    # Give the capture thread time to initialize
    time.sleep(3)

    # Start Flask server
    print(f"\nStarting web server on http://{SERVER_HOST}:{SERVER_PORT}")
    print("Open in browser to view real-time detection\n")

    app.run(host=SERVER_HOST, port=SERVER_PORT, threaded=True, debug=False)

if __name__ == "__main__":
    main()
