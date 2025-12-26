#!/usr/bin/env python3
"""
Real-time Staff/Customer Detection Server - V5
Version: 1.0.0

Flask-based web server for real-time YOLO11s staff/customer detection
from RTSP camera streams with comprehensive metrics dashboard.

Features:
- Two-class detection: Staff (green), Customer (red)
- RTSP stream support from SmartICE NVR
- Web dashboard with live video and metrics
- Auto-reconnect on stream failures
- Comprehensive stats: FPS, counts, confidence scores

Created: 2025-12-26
"""

from flask import Flask, Response, render_template, jsonify
import cv2
import numpy as np
from ultralytics import YOLO
import time
import threading
import argparse
from collections import deque
from datetime import datetime

# =============================================================================
# Configuration
# =============================================================================

# Default camera settings (SmartICE NVR)
DEFAULT_CHANNEL = 18
NVR_IP = "192.168.1.3"
NVR_USER = "admin"
NVR_PASS = "ybl123456789"

# Model configuration
MODEL_PATH = "models/staff_customer_detector.pt"
CONF_THRESHOLD = 0.5
IOU_THRESHOLD = 0.45

# Visual settings
STAFF_COLOR = (0, 255, 0)      # Green for staff
CUSTOMER_COLOR = (0, 0, 255)   # Red for customer
BOX_THICKNESS = 2
FONT_SCALE = 0.6

# Class names
CLASS_NAMES = {0: 'Staff', 1: 'Customer'}

# =============================================================================
# Global State
# =============================================================================

app = Flask(__name__)

# Thread-safe stats
stats_lock = threading.Lock()
stats = {
    'fps': 0,
    'inference_time_ms': 0,
    'staff_count': 0,
    'customer_count': 0,
    'total_detections': 0,
    'avg_staff_conf': 0,
    'avg_customer_conf': 0,
    'resolution': 'N/A',
    'stream_fps': 0,
    'frame_drops': 0,
    'uptime_seconds': 0,
    'start_time': datetime.now()
}

# Frame buffer
frame_buffer = None
frame_lock = threading.Lock()

# Model instance
model = None

# =============================================================================
# Detection Thread
# =============================================================================

def detection_thread(rtsp_url, channel):
    """Main detection loop running in background thread"""
    global frame_buffer, stats, model

    print(f"\n[Detection Thread] Starting for channel {channel}")
    print(f"[Detection Thread] RTSP URL: {rtsp_url}")

    # Load model
    print(f"[Detection Thread] Loading model: {MODEL_PATH}")
    try:
        model = YOLO(MODEL_PATH)
        print("[Detection Thread] Model loaded successfully!")
    except Exception as e:
        print(f"[Detection Thread] ERROR loading model: {e}")
        return

    # Metrics tracking
    fps_history = deque(maxlen=30)
    inference_history = deque(maxlen=30)
    reconnect_attempts = 0
    max_reconnects = 10

    while reconnect_attempts < max_reconnects:
        print(f"\n[Detection Thread] Connecting to stream (attempt {reconnect_attempts + 1})...")

        # Open RTSP stream
        cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        if not cap.isOpened():
            print("[Detection Thread] Failed to open stream, retrying in 5s...")
            reconnect_attempts += 1
            time.sleep(5)
            continue

        # Get stream info
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        stream_fps = cap.get(cv2.CAP_PROP_FPS)

        print(f"[Detection Thread] Connected! Resolution: {width}x{height}, Stream FPS: {stream_fps}")

        with stats_lock:
            stats['resolution'] = f"{width}x{height}"
            stats['stream_fps'] = stream_fps

        reconnect_attempts = 0  # Reset on successful connection
        frame_count = 0
        last_time = time.time()

        while True:
            ret, frame = cap.read()

            if not ret:
                print("[Detection Thread] Frame read failed, reconnecting...")
                with stats_lock:
                    stats['frame_drops'] += 1
                break

            frame_count += 1

            # Run detection
            start_time = time.time()
            results = model(frame, conf=CONF_THRESHOLD, iou=IOU_THRESHOLD, verbose=False)
            inference_time = (time.time() - start_time) * 1000

            # Process detections
            staff_count = 0
            customer_count = 0
            staff_confs = []
            customer_confs = []
            detections = []

            for result in results:
                boxes = result.boxes
                if boxes is not None:
                    for box in boxes:
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        conf = float(box.conf[0].cpu().numpy())
                        cls = int(box.cls[0].cpu().numpy())

                        detections.append({
                            'bbox': (int(x1), int(y1), int(x2), int(y2)),
                            'conf': conf,
                            'class': cls
                        })

                        if cls == 0:
                            staff_count += 1
                            staff_confs.append(conf)
                        else:
                            customer_count += 1
                            customer_confs.append(conf)

            # Draw on frame
            annotated = frame.copy()

            for det in detections:
                x1, y1, x2, y2 = det['bbox']
                conf = det['conf']
                cls = det['class']
                color = STAFF_COLOR if cls == 0 else CUSTOMER_COLOR
                label = f"{CLASS_NAMES[cls]}: {conf:.0%}"

                cv2.rectangle(annotated, (x1, y1), (x2, y2), color, BOX_THICKNESS)

                # Label background
                label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, FONT_SCALE, 2)[0]
                cv2.rectangle(annotated, (x1, y1 - label_size[1] - 10),
                            (x1 + label_size[0], y1), color, -1)

                # Label text
                text_color = (0, 0, 0) if cls == 0 else (255, 255, 255)
                cv2.putText(annotated, label, (x1, y1 - 5),
                          cv2.FONT_HERSHEY_SIMPLEX, FONT_SCALE, text_color, 2)

            # Draw stats overlay
            current_fps = 1000.0 / inference_time if inference_time > 0 else 0
            fps_history.append(current_fps)
            inference_history.append(inference_time)

            avg_fps = np.mean(fps_history) if fps_history else 0

            # Top-left overlay
            cv2.rectangle(annotated, (10, 10), (280, 120), (0, 0, 0), -1)
            cv2.putText(annotated, f"FPS: {avg_fps:.1f}", (20, 35),
                      cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(annotated, f"Staff: {staff_count}", (20, 60),
                      cv2.FONT_HERSHEY_SIMPLEX, 0.7, STAFF_COLOR, 2)
            cv2.putText(annotated, f"Customers: {customer_count}", (20, 85),
                      cv2.FONT_HERSHEY_SIMPLEX, 0.7, CUSTOMER_COLOR, 2)
            cv2.putText(annotated, f"Inference: {inference_time:.1f}ms", (20, 110),
                      cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

            # Update frame buffer
            with frame_lock:
                frame_buffer = annotated.copy()

            # Update stats
            with stats_lock:
                stats['fps'] = avg_fps
                stats['inference_time_ms'] = np.mean(inference_history) if inference_history else 0
                stats['staff_count'] = staff_count
                stats['customer_count'] = customer_count
                stats['total_detections'] = staff_count + customer_count
                stats['avg_staff_conf'] = np.mean(staff_confs) * 100 if staff_confs else 0
                stats['avg_customer_conf'] = np.mean(customer_confs) * 100 if customer_confs else 0
                stats['uptime_seconds'] = (datetime.now() - stats['start_time']).total_seconds()

        cap.release()
        reconnect_attempts += 1
        time.sleep(2)

    print("[Detection Thread] Max reconnection attempts reached. Exiting.")

# =============================================================================
# Flask Routes
# =============================================================================

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('detection_dashboard.html')

@app.route('/video_feed')
def video_feed():
    """MJPEG video stream endpoint"""
    def generate():
        while True:
            with frame_lock:
                if frame_buffer is None:
                    time.sleep(0.1)
                    continue
                frame = frame_buffer.copy()

            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

            time.sleep(0.033)  # ~30 FPS max

    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/stats')
def api_stats():
    """Return current stats as JSON"""
    with stats_lock:
        return jsonify({
            'fps': round(stats['fps'], 1),
            'inference_time_ms': round(stats['inference_time_ms'], 1),
            'staff_count': stats['staff_count'],
            'customer_count': stats['customer_count'],
            'total_detections': stats['total_detections'],
            'avg_staff_conf': round(stats['avg_staff_conf'], 1),
            'avg_customer_conf': round(stats['avg_customer_conf'], 1),
            'resolution': stats['resolution'],
            'stream_fps': stats['stream_fps'],
            'frame_drops': stats['frame_drops'],
            'uptime_seconds': int(stats['uptime_seconds'])
        })

# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='Staff/Customer Detection Server V5')
    parser.add_argument('--channel', type=int, default=DEFAULT_CHANNEL,
                       help=f'NVR channel number (default: {DEFAULT_CHANNEL})')
    parser.add_argument('--rtsp', type=str, default=None,
                       help='Custom RTSP URL (overrides channel)')
    args = parser.parse_args()

    # Build RTSP URL
    if args.rtsp:
        rtsp_url = args.rtsp
    else:
        rtsp_url = f"rtsp://{NVR_USER}:{NVR_PASS}@{NVR_IP}:554/unicast/c{args.channel}/s0/live"

    port = 5000 + args.channel

    print("\n" + "=" * 60)
    print("Staff/Customer Detection Server V5 - YOLO11s")
    print("=" * 60)
    print(f"Channel: {args.channel}")
    print(f"RTSP URL: {rtsp_url}")
    print(f"Server Port: {port}")
    print(f"Dashboard: http://localhost:{port}")
    print("=" * 60 + "\n")

    # Start detection thread
    thread = threading.Thread(target=detection_thread, args=(rtsp_url, args.channel), daemon=True)
    thread.start()

    # Start Flask server
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)

if __name__ == '__main__':
    main()
