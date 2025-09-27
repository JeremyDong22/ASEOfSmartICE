#!/usr/bin/env python3
# Version: 1.0
# Web interface for camera sub-stream preview
# Creates a Flask web server to display RTSP stream from camera 102 channel

import cv2
import threading
import time
from flask import Flask, Response, render_template_string
import numpy as np

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

def capture_frames():
    """Capture frames from RTSP stream continuously"""
    global output_frame, is_capturing

    while True:  # Add reconnection loop
        print(f"🎥 Connecting to sub-stream: {RTSP_URL}")

        # Use FFmpeg backend explicitly for better compatibility
        cap = cv2.VideoCapture(RTSP_URL, cv2.CAP_FFMPEG)

        # Set buffer size and timeouts
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000)

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

        while is_capturing:
            ret, frame = cap.read()
            if not ret:
                consecutive_failures += 1
                print(f"⚠️ Failed to read frame (attempt {consecutive_failures})")
                if consecutive_failures > 10:
                    print("❌ Too many failures, reconnecting...")
                    break
                time.sleep(0.1)
                continue

            consecutive_failures = 0

            # Add timestamp to frame
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            cv2.putText(frame, timestamp, (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            # Update global frame
            with lock:
                output_frame = frame.copy()

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
    """Home page with video player"""
    html_template = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Camera Stream Preview - Channel 102</title>
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
                max-width: 1200px;
                width: 100%;
            }
            h1 {
                text-align: center;
                color: #ecf0f1;
                margin-bottom: 10px;
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
        </style>
        <script>
            function refreshStream() {
                var img = document.getElementById('stream');
                img.src = '/video_feed?' + new Date().getTime();
            }

            function toggleFullscreen() {
                var img = document.getElementById('stream');
                if (img.requestFullscreen) {
                    img.requestFullscreen();
                } else if (img.webkitRequestFullscreen) {
                    img.webkitRequestFullscreen();
                } else if (img.msRequestFullscreen) {
                    img.msRequestFullscreen();
                }
            }
        </script>
    </head>
    <body>
        <div class="container">
            <h1>🎥 Camera Stream Preview</h1>
            <div class="info">
                Camera IP: {{ camera_ip }} | Channel: 102 (Sub-stream) | Protocol: RTSP
            </div>
            <div class="video-container">
                <img id="stream" class="stream" src="/video_feed" alt="Camera Stream">
                <div class="status">
                    ✅ Stream Active
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

def main():
    global capture_thread

    print("🚀 Starting Camera Stream Web Interface")
    print(f"📹 Camera: {CAMERA_IP}")
    print(f"📺 Channel: 102 (Sub-stream)")
    print("-" * 50)

    # Start capture thread
    capture_thread = threading.Thread(target=capture_frames)
    capture_thread.daemon = True
    capture_thread.start()

    # Wait for initial connection
    print("⏳ Waiting for camera connection...")
    time.sleep(2)

    # Start Flask server
    print("\n🌐 Starting web server...")
    print("✨ Open your browser and navigate to:")
    print("   http://localhost:5001")
    print("-" * 50)

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