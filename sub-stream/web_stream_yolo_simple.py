#!/usr/bin/env python3
# Version: 4.0
# Simplified YOLO detection - processes frames directly without complex threading
# Ensures YOLO detection frames are visible

import cv2
import threading
import time
from flask import Flask, Response, render_template_string
import numpy as np
from ultralytics import YOLO
import os

app = Flask(__name__)

# Camera configuration
CAMERA_IP = "202.168.40.35"
USERNAME = "admin"
PASSWORD = "123456"
RTSP_URL = f"rtsp://{USERNAME}:{PASSWORD}@{CAMERA_IP}:554/Streaming/Channels/102"

# Global variables
output_frame = None
lock = threading.Lock()
detection_info = {"persons": 0, "tables": 0, "fps": 0}
model = None

# Frame processing control
frame_skip_counter = 0
SKIP_FRAMES = 3  # Process every 3rd frame

# Classes to detect
TARGET_CLASSES = {
    0: "person",
    60: "dining table",
    56: "chair"
}

def load_yolo_model():
    """Load YOLO model"""
    global model
    try:
        if os.path.exists("model/yolov8s.pt"):
            model_path = "model/yolov8s.pt"
        else:
            model_path = "yolov8s.pt"
            
        print(f"📦 Loading YOLO model from {model_path}")
        model = YOLO(model_path)
        print("✅ YOLO model loaded successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to load YOLO model: {e}")
        return False

def capture_and_detect():
    """Single thread for capture and detection"""
    global output_frame, detection_info, frame_skip_counter
    
    while True:
        print(f"🎥 Connecting to: {RTSP_URL}")
        
        # Open video capture
        cap = cv2.VideoCapture(RTSP_URL, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 10000)
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 10000)
        
        if not cap.isOpened():
            print("❌ Failed to open camera stream, retrying...")
            time.sleep(5)
            continue
            
        print("✅ Connected to camera stream")
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        print(f"📊 Stream: {width}x{height} @ {fps} FPS")
        
        frame_count = 0
        start_time = time.time()
        
        while True:
            ret, frame = cap.read()
            if not ret:
                print("⚠️ Failed to read frame")
                break
                
            frame_count += 1
            frame_skip_counter += 1
            
            # Calculate FPS
            if frame_count % 30 == 0:
                elapsed = time.time() - start_time
                current_fps = frame_count / elapsed
                detection_info["fps"] = round(current_fps, 1)
            
            # Run YOLO detection on selected frames
            if frame_skip_counter >= SKIP_FRAMES and model is not None:
                frame_skip_counter = 0
                
                try:
                    # Run detection
                    results = model(frame, conf=0.4, verbose=False)
                    
                    persons = 0
                    tables = 0
                    
                    # Draw detections
                    for r in results:
                        boxes = r.boxes
                        if boxes is not None:
                            for box in boxes:
                                cls = int(box.cls[0])
                                if cls in TARGET_CLASSES:
                                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                                    conf = float(box.conf[0])
                                    
                                    # Count detections
                                    if cls == 0:
                                        persons += 1
                                        color = (0, 255, 0)  # Green for person
                                    elif cls == 60:
                                        tables += 1
                                        color = (255, 0, 0)  # Blue for table
                                    else:
                                        color = (255, 255, 0)  # Yellow for chair
                                    
                                    # Draw bounding box
                                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                                    
                                    # Draw label
                                    label = f"{TARGET_CLASSES[cls]}: {conf:.2f}"
                                    label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
                                    cv2.rectangle(frame, (x1, y1 - label_size[1] - 5),
                                                (x1 + label_size[0], y1), color, -1)
                                    cv2.putText(frame, label, (x1, y1 - 5),
                                              cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
                    
                    detection_info["persons"] = persons
                    detection_info["tables"] = tables
                    
                except Exception as e:
                    print(f"⚠️ Detection error: {e}")
            
            # Add timestamp
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            cv2.putText(frame, timestamp, (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # Add detection info
            info_text = f"Persons: {detection_info['persons']} | Tables: {detection_info['tables']} | FPS: {detection_info['fps']}"
            cv2.putText(frame, info_text, (10, 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
            
            # Update global frame
            with lock:
                output_frame = frame.copy()
            
            # Print stats periodically
            if frame_count % 100 == 0:
                print(f"📈 Processed {frame_count} frames | Detected: {detection_info['persons']} persons, {detection_info['tables']} tables")
        
        cap.release()
        print("🔄 Reconnecting...")
        time.sleep(2)

def generate_frames():
    """Generate frames for web streaming"""
    global output_frame, lock
    
    while True:
        with lock:
            if output_frame is None:
                time.sleep(0.1)
                continue
            frame = output_frame.copy()
        
        # Encode frame as JPEG
        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ret:
            continue
            
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/')
def index():
    """Home page"""
    html_template = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>YOLO Object Detection Stream</title>
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
            }
            .container {
                padding: 20px;
                max-width: 1200px;
                width: 100%;
            }
            h1 {
                text-align: center;
                color: #ecf0f1;
            }
            .stats {
                display: flex;
                justify-content: center;
                gap: 30px;
                margin: 20px 0;
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
            .video-container {
                background-color: #34495e;
                border-radius: 10px;
                padding: 20px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            }
            .stream {
                width: 100%;
                border-radius: 5px;
                border: 2px solid #16a085;
            }
            .info {
                text-align: center;
                color: #95a5a6;
                margin: 10px 0;
            }
            .legend {
                display: flex;
                justify-content: center;
                gap: 20px;
                margin: 15px 0;
            }
            .legend-item {
                display: flex;
                align-items: center;
                gap: 5px;
            }
            .color-box {
                width: 20px;
                height: 15px;
                border: 1px solid white;
            }
        </style>
        <script>
            function updateStats() {
                fetch('/stats')
                    .then(response => response.json())
                    .then(data => {
                        document.getElementById('persons').textContent = data.persons;
                        document.getElementById('tables').textContent = data.tables;
                        document.getElementById('fps').textContent = data.fps;
                    });
            }
            setInterval(updateStats, 1000);
        </script>
    </head>
    <body>
        <div class="container">
            <h1>🎥 YOLO Object Detection - Simplified</h1>
            
            <div class="stats">
                <div class="stat-card">
                    <div class="stat-number" id="persons">0</div>
                    <div>👤 Persons</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="tables">0</div>
                    <div>🪑 Tables</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="fps">0</div>
                    <div>📊 FPS</div>
                </div>
            </div>
            
            <div class="legend">
                <div class="legend-item">
                    <div class="color-box" style="background-color: #00ff00;"></div>
                    <span>Person</span>
                </div>
                <div class="legend-item">
                    <div class="color-box" style="background-color: #0000ff;"></div>
                    <span>Table</span>
                </div>
                <div class="legend-item">
                    <div class="color-box" style="background-color: #ffff00;"></div>
                    <span>Chair</span>
                </div>
            </div>
            
            <div class="info">Camera: {{ camera_ip }} | Processing: 1 frame every 3 frames</div>
            
            <div class="video-container">
                <img class="stream" src="/video_feed" alt="Camera Stream">
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
    """Return detection statistics"""
    return detection_info

def main():
    print("=" * 60)
    print("🚀 Starting Simplified YOLO Detection Stream")
    print("=" * 60)
    print(f"📹 Camera: {CAMERA_IP}")
    print("🔧 Processing: Every 3rd frame")
    print("-" * 60)
    
    # Load YOLO model
    if not load_yolo_model():
        print("❌ Failed to load YOLO model")
        return
    
    # Start capture thread
    capture_thread = threading.Thread(target=capture_and_detect)
    capture_thread.daemon = True
    capture_thread.start()
    
    # Wait for connection
    print("⏳ Waiting for camera connection...")
    time.sleep(3)
    
    # Start Flask server
    print("\n🌐 Starting web server...")
    print("✨ Open browser at: http://localhost:5001")
    print("=" * 60)
    
    try:
        app.run(host='0.0.0.0', port=5001, debug=False, threaded=True)
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")

if __name__ == "__main__":
    main()