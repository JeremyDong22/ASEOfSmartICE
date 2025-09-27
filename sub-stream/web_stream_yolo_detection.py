#!/usr/bin/env python3
# Version: 2.0
# Web interface for camera sub-stream preview with YOLOv10 object detection
# Detects humans (person) and tables in real-time from RTSP stream

import cv2
import threading
import time
from flask import Flask, Response, render_template_string
import numpy as np
from ultralytics import YOLO
import torch
import os
import sys

app = Flask(__name__)

# Camera configuration
CAMERA_IP = "202.168.40.35"
USERNAME = "admin"
PASSWORD = "123456"
# Sub-stream URL (channel 102)
RTSP_URL = f"rtsp://{USERNAME}:{PASSWORD}@{CAMERA_IP}:554/Streaming/Channels/102"

# Global variables
output_frame = None
lock = threading.Lock()
capture_thread = None
is_capturing = False
detection_info = {"persons": 0, "tables": 0, "fps": 0}
model = None

# Classes we want to detect (COCO dataset)
TARGET_CLASSES = {
    0: "person",      # Human detection
    60: "dining table",  # Table detection
    56: "chair",      # Also detect chairs as they often indicate table areas
}

def load_yolo_model():
    """Load YOLOv10 model"""
    global model
    try:
        model_path = "model/yolov10s.pt"
        
        # Check if model file exists
        if not os.path.exists(model_path):
            # Try YOLOv8 as fallback
            model_path = "model/yolov8s.pt"
            if not os.path.exists(model_path):
                print("❌ No YOLO model found, downloading YOLOv8s...")
                model = YOLO('yolov8s.pt')
                # Save to model directory
                os.makedirs("model", exist_ok=True)
                model.save("model/yolov8s.pt")
            else:
                print(f"📦 Loading YOLO model from {model_path}")
                model = YOLO(model_path)
        else:
            print(f"📦 Loading YOLOv10 model from {model_path}")
            model = YOLO(model_path)
        
        # Set device
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"🔧 Using device: {device}")
        model.to(device)
        
        print("✅ YOLO model loaded successfully")
        return True
        
    except Exception as e:
        print(f"❌ Failed to load YOLO model: {e}")
        print("📥 Attempting to download YOLOv8s as fallback...")
        try:
            model = YOLO('yolov8s.pt')
            os.makedirs("model", exist_ok=True)
            print("✅ YOLOv8s model downloaded and loaded")
            return True
        except Exception as e2:
            print(f"❌ Failed to download model: {e2}")
            return False

def detect_objects(frame):
    """Perform object detection on frame"""
    global model, detection_info
    
    if model is None:
        return frame
    
    try:
        # Run inference
        results = model(frame, conf=0.5, verbose=False)
        
        # Reset counters
        persons = 0
        tables = 0
        
        # Process detections
        for r in results:
            boxes = r.boxes
            if boxes is not None:
                for box in boxes:
                    # Get box coordinates
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
                    
                    # Get class and confidence
                    cls = int(box.cls[0])
                    conf = float(box.conf[0])
                    
                    # Check if it's a target class
                    if cls in TARGET_CLASSES:
                        label = TARGET_CLASSES[cls]
                        color = (0, 255, 0) if cls == 0 else (255, 0, 0)  # Green for person, Blue for table
                        
                        # Draw bounding box
                        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                        
                        # Draw label
                        label_text = f"{label}: {conf:.2f}"
                        label_size, _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                        cv2.rectangle(frame, (x1, y1 - label_size[1] - 5), 
                                    (x1 + label_size[0], y1), color, -1)
                        cv2.putText(frame, label_text, (x1, y1 - 5),
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                        
                        # Count detections
                        if cls == 0:
                            persons += 1
                        elif cls == 60:
                            tables += 1
        
        # Update detection info
        with lock:
            detection_info["persons"] = persons
            detection_info["tables"] = tables
        
    except Exception as e:
        print(f"⚠️ Detection error: {e}")
    
    return frame

def capture_frames():
    """Capture frames from RTSP stream with YOLO detection"""
    global output_frame, is_capturing, detection_info
    
    while True:  # Reconnection loop
        print(f"🎥 Connecting to sub-stream: {RTSP_URL}")
        
        # Use FFmpeg backend for better compatibility
        cap = cv2.VideoCapture(RTSP_URL, cv2.CAP_FFMPEG)
        
        # Set buffer and timeouts
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 10000)
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 10000)
        
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
        start_time = time.time()
        
        while is_capturing:
            ret, frame = cap.read()
            if not ret:
                consecutive_failures += 1
                if consecutive_failures > 10:
                    print("❌ Too many failures, reconnecting...")
                    break
                time.sleep(0.1)
                continue
            
            consecutive_failures = 0
            frame_count += 1
            
            # Calculate FPS
            if frame_count % 30 == 0:
                elapsed = time.time() - start_time
                fps = frame_count / elapsed
                with lock:
                    detection_info["fps"] = round(fps, 1)
            
            # Run YOLO detection
            frame = detect_objects(frame)
            
            # Add timestamp and detection info overlay
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            cv2.putText(frame, timestamp, (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # Add detection counts
            info_text = f"Persons: {detection_info['persons']} | Tables: {detection_info['tables']} | FPS: {detection_info['fps']}"
            cv2.putText(frame, info_text, (10, 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
            
            # Update global frame
            with lock:
                output_frame = frame.copy()
            
            # Print detection stats every 100 frames
            if frame_count % 100 == 0:
                print(f"📈 Frame {frame_count}: Detected {detection_info['persons']} persons, {detection_info['tables']} tables")
        
        cap.release()
        print("🔄 Reconnecting to stream...")
        time.sleep(2)

def generate_frames():
    """Generate frames for web streaming"""
    global output_frame, lock
    
    while True:
        with lock:
            if output_frame is None:
                continue
            
            # Encode frame as JPEG
            ret, buffer = cv2.imencode('.jpg', output_frame,
                                      [cv2.IMWRITE_JPEG_QUALITY, 85])
            if not ret:
                continue
            
            frame_bytes = buffer.tobytes()
        
        # Yield frame in byte format
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        
        # Small delay to control frame rate
        time.sleep(0.03)  # ~30 FPS

@app.route('/')
def index():
    """Home page with video player and detection info"""
    html_template = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Camera Stream with YOLO Detection</title>
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
            .legend {
                position: absolute;
                top: 20px;
                right: 30px;
                background-color: rgba(52, 73, 94, 0.9);
                padding: 10px;
                border-radius: 5px;
                font-size: 12px;
            }
            .legend-item {
                margin: 5px 0;
            }
            .legend-color {
                display: inline-block;
                width: 20px;
                height: 10px;
                margin-right: 5px;
            }
        </style>
        <script>
            let statsInterval;
            
            function updateStats() {
                // Auto-refresh stats every 2 seconds
                fetch('/stats')
                    .then(response => response.json())
                    .then(data => {
                        document.getElementById('person-count').textContent = data.persons;
                        document.getElementById('table-count').textContent = data.tables;
                        document.getElementById('fps-count').textContent = data.fps;
                    });
            }
            
            window.onload = function() {
                statsInterval = setInterval(updateStats, 2000);
                updateStats();
            };
            
            function refreshStream() {
                var img = document.getElementById('stream');
                img.src = '/video_feed?' + new Date().getTime();
            }
            
            function toggleFullscreen() {
                var img = document.getElementById('stream');
                if (img.requestFullscreen) {
                    img.requestFullscreen();
                }
            }
        </script>
    </head>
    <body>
        <div class="container">
            <h1>🎥 Camera Stream with YOLO Object Detection</h1>
            
            <div class="detection-stats">
                <div class="stat-card">
                    <div class="stat-number" id="person-count">0</div>
                    <div class="stat-label">👤 Persons Detected</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="table-count">0</div>
                    <div class="stat-label">🪑 Tables Detected</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="fps-count">0</div>
                    <div class="stat-label">📊 FPS</div>
                </div>
            </div>
            
            <div class="info">
                Camera IP: {{ camera_ip }} | Channel: 102 (Sub-stream) | Model: YOLOv8/v10
            </div>
            
            <div class="video-container">
                <div class="legend">
                    <div class="legend-item">
                        <span class="legend-color" style="background-color: #00ff00;"></span>
                        Person
                    </div>
                    <div class="legend-item">
                        <span class="legend-color" style="background-color: #0000ff;"></span>
                        Table
                    </div>
                </div>
                <img id="stream" class="stream" src="/video_feed" alt="Camera Stream">
                <div class="status">
                    ✅ Stream Active with Object Detection
                </div>
            </div>
            
            <div class="controls">
                <button onclick="refreshStream()">🔄 Refresh Stream</button>
                <button onclick="toggleFullscreen()">⛶ Fullscreen</button>
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
    return detection_info

def main():
    global capture_thread
    
    print("=" * 60)
    print("🚀 Starting Camera Stream with YOLO Object Detection")
    print("=" * 60)
    print(f"📹 Camera: {CAMERA_IP}")
    print(f"📺 Channel: 102 (Sub-stream)")
    print(f"🤖 Loading YOLO model for person and table detection...")
    print("-" * 60)
    
    # Load YOLO model
    if not load_yolo_model():
        print("❌ Failed to load YOLO model, exiting...")
        sys.exit(1)
    
    # Start capture thread
    capture_thread = threading.Thread(target=capture_frames)
    capture_thread.daemon = True
    capture_thread.start()
    
    # Wait for initial connection
    print("⏳ Waiting for camera connection...")
    time.sleep(3)
    
    # Start Flask server
    print("\n🌐 Starting web server with object detection...")
    print("✨ Open your browser and navigate to:")
    print("   http://localhost:5001")
    print("=" * 60)
    print("🎯 Detecting: Persons (humans) and Tables")
    print("=" * 60)
    
    try:
        app.run(host='0.0.0.0', port=5001, debug=False, threaded=True)
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
        global is_capturing
        is_capturing = False
        if capture_thread:
            capture_thread.join(timeout=2)

if __name__ == "__main__":
    main()