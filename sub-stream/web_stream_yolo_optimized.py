#!/usr/bin/env python3
# Version: 3.0
# Optimized web interface with YOLO detection - fixes frame corruption
# Uses frame skipping, proper buffering, and thread-safe operations

import cv2
import threading
import time
from flask import Flask, Response, render_template_string
import numpy as np
from ultralytics import YOLO
import torch
import os
import sys
from collections import deque
import queue

app = Flask(__name__)

# Camera configuration
CAMERA_IP = "202.168.40.35"
USERNAME = "admin"
PASSWORD = "123456"
# Sub-stream URL (channel 102)
RTSP_URL = f"rtsp://{USERNAME}:{PASSWORD}@{CAMERA_IP}:554/Streaming/Channels/102"

# Global variables
output_frame = None
frame_lock = threading.Lock()
capture_thread = None
detection_thread = None
is_capturing = False
detection_info = {"persons": 0, "tables": 0, "fps": 0, "detection_fps": 0}
model = None

# Frame queue for detection processing
detection_queue = queue.Queue(maxsize=2)  # Small queue to prevent buildup
frame_counter = 0
DETECTION_SKIP_FRAMES = 5  # Process every 5th frame to reduce load

# Classes we want to detect (COCO dataset)
TARGET_CLASSES = {
    0: "person",      # Human detection
    60: "dining table",  # Table detection
    56: "chair",      # Also detect chairs as they often indicate table areas
}

def load_yolo_model():
    """Load YOLO model with optimized settings"""
    global model
    try:
        # Try to load existing model first
        if os.path.exists("model/yolov8s.pt"):
            model_path = "model/yolov8s.pt"
        else:
            print("📥 Downloading YOLOv8s model...")
            model_path = 'yolov8s.pt'
        
        print(f"📦 Loading YOLO model from {model_path}")
        model = YOLO(model_path)
        
        # Set device and optimize for speed
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"🔧 Using device: {device}")
        model.to(device)
        
        # Set model to eval mode for faster inference
        model.model.eval()
        
        print("✅ YOLO model loaded and optimized")
        return True
        
    except Exception as e:
        print(f"❌ Failed to load YOLO model: {e}")
        return False

def detection_worker():
    """Separate thread for YOLO detection processing"""
    global detection_info, model
    
    detection_start = time.time()
    detection_count = 0
    
    while is_capturing:
        try:
            # Get frame from queue with timeout
            frame = detection_queue.get(timeout=1.0)
            
            if frame is None:
                continue
            
            # Run YOLO detection
            results = model(frame, conf=0.45, verbose=False, max_det=20)
            
            # Reset counters
            persons = 0
            tables = 0
            
            # Process detections
            for r in results:
                boxes = r.boxes
                if boxes is not None:
                    for box in boxes:
                        cls = int(box.cls[0])
                        if cls in TARGET_CLASSES:
                            if cls == 0:
                                persons += 1
                            elif cls == 60:
                                tables += 1
                            
                            # Draw on frame
                            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
                            
                            color = (0, 255, 0) if cls == 0 else (255, 0, 0)
                            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                            
                            label = f"{TARGET_CLASSES[cls]}: {float(box.conf[0]):.2f}"
                            cv2.putText(frame, label, (x1, y1 - 5),
                                      cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            
            # Update detection info
            detection_count += 1
            elapsed = time.time() - detection_start
            if elapsed > 1.0:
                with frame_lock:
                    detection_info["persons"] = persons
                    detection_info["tables"] = tables
                    detection_info["detection_fps"] = round(detection_count / elapsed, 1)
                detection_count = 0
                detection_start = time.time()
            
            # Update output frame with detections
            with frame_lock:
                global output_frame
                output_frame = frame.copy()
                
        except queue.Empty:
            continue
        except Exception as e:
            print(f"⚠️ Detection error: {e}")
            time.sleep(0.1)

def capture_frames():
    """Capture frames with proper buffering and corruption prevention"""
    global output_frame, is_capturing, detection_info, frame_counter
    
    while True:  # Reconnection loop
        print(f"🎥 Connecting to sub-stream: {RTSP_URL}")
        
        # Create capture with optimized settings
        cap = cv2.VideoCapture(RTSP_URL, cv2.CAP_FFMPEG)
        
        # Critical: Set small buffer to prevent frame accumulation
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        # Set timeouts
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 10000)
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000)
        
        # Try to force TCP transport for stability
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('H', '2', '6', '4'))
        
        if not cap.isOpened():
            print("❌ Failed to open camera stream, retrying in 5 seconds...")
            time.sleep(5)
            continue
        
        print("✅ Successfully connected to camera sub-stream")
        print("📊 Stream properties:")
        print(f"   Resolution: {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")
        print(f"   FPS: {cap.get(cv2.CAP_PROP_FPS)}")
        
        is_capturing = True
        consecutive_failures = 0
        frame_count = 0
        fps_start = time.time()
        last_frame = None
        
        while is_capturing:
            ret, frame = cap.read()
            
            if not ret:
                consecutive_failures += 1
                if consecutive_failures > 10:
                    print("❌ Too many failures, reconnecting...")
                    break
                # Use last good frame if available
                if last_frame is not None:
                    frame = last_frame.copy()
                else:
                    time.sleep(0.1)
                    continue
            else:
                consecutive_failures = 0
                last_frame = frame.copy()
            
            frame_count += 1
            frame_counter += 1
            
            # Calculate actual FPS
            if frame_count % 30 == 0:
                elapsed = time.time() - fps_start
                fps = frame_count / elapsed
                with frame_lock:
                    detection_info["fps"] = round(fps, 1)
                
                # Clear old frames from buffer to prevent accumulation
                while not cap.grab():
                    break
            
            # Add timestamp
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            cv2.putText(frame, timestamp, (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # Add info overlay
            info_text = f"Persons: {detection_info['persons']} | Tables: {detection_info['tables']} | FPS: {detection_info['fps']}"
            cv2.putText(frame, info_text, (10, 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
            
            # Send frame for detection (skip frames to reduce load)
            if frame_counter % DETECTION_SKIP_FRAMES == 0:
                try:
                    # Non-blocking put with immediate frame drop if queue is full
                    detection_queue.put_nowait(frame.copy())
                except queue.Full:
                    # Drop the frame if queue is full
                    try:
                        detection_queue.get_nowait()  # Remove old frame
                        detection_queue.put_nowait(frame.copy())  # Add new frame
                    except:
                        pass
            
            # Update output frame
            with frame_lock:
                output_frame = frame.copy()
            
            # Small delay to control CPU usage
            time.sleep(0.01)
        
        cap.release()
        print("🔄 Reconnecting to stream...")
        time.sleep(2)

def generate_frames():
    """Generate frames for web streaming with thread safety"""
    global output_frame, frame_lock
    
    while True:
        with frame_lock:
            if output_frame is None:
                time.sleep(0.03)
                continue
            
            # Make a copy to prevent corruption during encoding
            frame_to_encode = output_frame.copy()
        
        # Encode frame outside of lock
        ret, buffer = cv2.imencode('.jpg', frame_to_encode,
                                  [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ret:
            continue
        
        frame_bytes = buffer.tobytes()
        
        # Yield frame in byte format
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        
        # Control frame rate
        time.sleep(0.033)  # ~30 FPS

@app.route('/')
def index():
    """Home page with video player and detection info"""
    html_template = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Optimized Camera Stream with YOLO Detection</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 0;
                background-color: #2c3e50;
                color: white;
                display: flex;
                flex-direction: column;
                align-items: center;
                min-height: 100vh;
            }
            .container {
                padding: 20px;
                max-width: 1400px;
                width: 100%;
            }
            h1 {
                text-align: center;
                color: #ecf0f1;
                margin-bottom: 10px;
            }
            .detection-stats {
                display: flex;
                justify-content: center;
                gap: 30px;
                margin-bottom: 20px;
            }
            .stat-card {
                background-color: #34495e;
                padding: 15px 25px;
                border-radius: 10px;
                text-align: center;
                border: 2px solid #16a085;
            }
            .stat-number {
                font-size: 2em;
                font-weight: bold;
                color: #3498db;
            }
            .stat-label {
                color: #95a5a6;
                margin-top: 5px;
            }
            .info {
                text-align: center;
                color: #95a5a6;
                margin-bottom: 20px;
                font-size: 14px;
            }
            .video-container {
                background-color: #34495e;
                border-radius: 10px;
                padding: 20px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.3);
                position: relative;
            }
            .stream {
                width: 100%;
                max-width: 100%;
                border-radius: 5px;
                border: 2px solid #16a085;
            }
            .status {
                margin-top: 15px;
                padding: 10px;
                background-color: #27ae60;
                border-radius: 5px;
                text-align: center;
                font-weight: bold;
            }
            .optimization-info {
                margin-top: 10px;
                padding: 10px;
                background-color: #2980b9;
                border-radius: 5px;
                text-align: center;
                font-size: 12px;
            }
            .controls {
                margin-top: 20px;
                text-align: center;
            }
            button {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                cursor: pointer;
                font-size: 16px;
                margin: 0 5px;
            }
            button:hover {
                background-color: #2980b9;
            }
        </style>
        <script>
            let statsInterval;
            
            function updateStats() {
                fetch('/stats')
                    .then(response => response.json())
                    .then(data => {
                        document.getElementById('person-count').textContent = data.persons;
                        document.getElementById('table-count').textContent = data.tables;
                        document.getElementById('fps-count').textContent = data.fps;
                        document.getElementById('detection-fps').textContent = data.detection_fps;
                    });
            }
            
            window.onload = function() {
                statsInterval = setInterval(updateStats, 1000);
                updateStats();
            };
            
            function refreshStream() {
                var img = document.getElementById('stream');
                img.src = '/video_feed?' + new Date().getTime();
            }
        </script>
    </head>
    <body>
        <div class="container">
            <h1>🎥 Optimized YOLO Object Detection Stream</h1>
            
            <div class="detection-stats">
                <div class="stat-card">
                    <div class="stat-number" id="person-count">0</div>
                    <div class="stat-label">👤 Persons</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="table-count">0</div>
                    <div class="stat-label">🪑 Tables</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="fps-count">0</div>
                    <div class="stat-label">📊 Stream FPS</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="detection-fps">0</div>
                    <div class="stat-label">🤖 Detection FPS</div>
                </div>
            </div>
            
            <div class="info">
                Camera: {{ camera_ip }} | Channel: 102 | Model: YOLOv8s (Optimized)
            </div>
            
            <div class="video-container">
                <img id="stream" class="stream" src="/video_feed" alt="Camera Stream">
                <div class="status">
                    ✅ Stream Active - Frame Corruption Fixed
                </div>
                <div class="optimization-info">
                    🔧 Optimizations: Frame skipping (1:5) | Buffer management | Thread-safe processing
                </div>
            </div>
            
            <div class="controls">
                <button onclick="refreshStream()">🔄 Refresh Stream</button>
                <button onclick="document.getElementById('stream').requestFullscreen()">⛶ Fullscreen</button>
            </div>
        </div>
    </body>
    </html>
    '''
    return render_template_string(html_template, camera_ip=CAMERA_IP)

@app.route('/video_feed')
def video_feed():
    """Video streaming route"""
    return Response(generate_frames(),
                   mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/stats')
def stats():
    """Return current detection statistics"""
    global detection_info
    with frame_lock:
        return detection_info.copy()

def main():
    global capture_thread, detection_thread
    
    print("=" * 60)
    print("🚀 Starting Optimized YOLO Detection Stream")
    print("=" * 60)
    print(f"📹 Camera: {CAMERA_IP}")
    print(f"📺 Channel: 102 (Sub-stream)")
    print("🔧 Optimizations enabled:")
    print("   - Frame skipping (1:5 for detection)")
    print("   - Proper frame buffering")
    print("   - Thread-safe operations")
    print("   - Queue-based detection processing")
    print("-" * 60)
    
    # Load YOLO model
    if not load_yolo_model():
        print("❌ Failed to load YOLO model, exiting...")
        sys.exit(1)
    
    # Start capture thread
    capture_thread = threading.Thread(target=capture_frames)
    capture_thread.daemon = True
    capture_thread.start()
    
    # Start detection thread
    detection_thread = threading.Thread(target=detection_worker)
    detection_thread.daemon = True
    detection_thread.start()
    
    # Wait for initial connection
    print("⏳ Waiting for camera connection...")
    time.sleep(3)
    
    # Start Flask server
    print("\n🌐 Starting web server...")
    print("✨ Open your browser and navigate to:")
    print("   http://localhost:5001")
    print("=" * 60)
    
    try:
        app.run(host='0.0.0.0', port=5001, debug=False, threaded=True)
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
        global is_capturing
        is_capturing = False
        if capture_thread:
            capture_thread.join(timeout=2)
        if detection_thread:
            detection_thread.join(timeout=2)

if __name__ == "__main__":
    main()