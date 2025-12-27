#!/usr/bin/env python3
"""
Manual Camera Capacity Tester - PyAV + GPU Decoding Version
Uses hardware-accelerated video decoding with NVDEC
"""

import cv2
import numpy as np
from ultralytics import YOLO
from flask import Flask, render_template, Response, jsonify, request
import threading
import time
import os
import psutil
import subprocess
from datetime import datetime
import av
import logging

# Configure verbose logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Limit FFMPEG threads globally - MORE AGGRESSIVE
os.environ['FFREPORT'] = 'level=quiet'
os.environ['AV_LOG_FORCE_NOCOLOR'] = '1'
os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'threads;1'
os.environ['OMP_NUM_THREADS'] = '1'

# Suppress PyAV/FFmpeg warnings about SEI metadata
av.logging.set_level(av.logging.ERROR)

# =============================================================================
# Configuration
# =============================================================================

NVR_IP = "192.168.1.3"
NVR_USERNAME = "admin"
NVR_PASSWORD = "ybl123456789"
MODEL_PATH = "models/staff_customer_detector.pt"
CONF_THRESHOLD = 0.5
IOU_THRESHOLD = 0.45

SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8001  # V5 runs on 8001 to avoid conflict with V4

# Frame rate control
TARGET_FPS = 15  # Process 15 frames per second (testing browser lag vs backend capacity)
FRAME_INTERVAL = 1.0 / TARGET_FPS  # 0.067 seconds between frames
MAX_CAMERAS = 30  # Maximum cameras (increased for GPU decode testing)

# Detection visualization settings
STAFF_COLOR = (0, 255, 0)      # Green for staff
CUSTOMER_COLOR = (0, 0, 255)   # Red for customers
BOX_THICKNESS = 2
FONT_SCALE = 0.5

# =============================================================================
# Global State
# =============================================================================

app = Flask(__name__)

# Shared YOLO model (GPU accelerated)
shared_model = None

# Batch inference system
from queue import Queue
from collections import namedtuple

InferenceRequest = namedtuple('InferenceRequest', ['frame', 'result_queue', 'channel'])
inference_queue = Queue(maxsize=100)  # Queue for frames to infer
batch_size = 16  # Process 16 frames at once (increased for GPU utilization)
inference_running = True

# Active cameras
active_cameras = {}
camera_locks = {}

# =============================================================================
# Camera Class with PyAV + GPU Decoding
# =============================================================================

class CameraStream:
    def __init__(self, channel):
        self.channel = channel
        self.container = None
        self.stream = None
        self.frame = None
        self.running = False
        self.thread = None

        # Async inference fields
        self.latest_result = None  # Cache latest inference result
        self.pending_inference = False
        self.result_lock = threading.Lock()

        self.stats = {
            "total_frames": 0,
            "processed_frames": 0,
            "skipped_frames": 0,
            "frame_drops": 0,
            "connection_status": "connecting",
            "stream_width": 0,
            "stream_height": 0,
            "current_detections": 0,
            "avg_confidence": 0.0,
            "current_fps": 0.0,
            "current_inference_ms": 0.0,
            "current_decode_ms": 0.0,  # NEW: Track decode time
            "avg_decode_ms": 0.0,       # NEW: Average decode time
            "avg_inference_ms": 0.0,    # NEW: Average inference time
            "decode_method": "unknown",
            "hw_accel_verified": False  # NEW: Verify hardware acceleration is actually working
        }

    def get_rtsp_url(self, substream=False):
        stream_type = "s1" if substream else "s0"
        return f"rtsp://{NVR_USERNAME}:{NVR_PASSWORD}@{NVR_IP}:554/unicast/c{self.channel}/{stream_type}/live"

    def connect(self):
        """Connect to RTSP stream with GPU decoding (non-blocking)"""
        logger.info(f"[CH{self.channel}] Starting connection attempt...")
        urls = [
            ("Sub", self.get_rtsp_url(True)),   # Try SUB first for bandwidth test
            ("Main", self.get_rtsp_url(False))
        ]

        for name, url in urls:
            if not self.running:  # Allow early exit
                break

            try:
                logger.info(f"[CH{self.channel}] Trying {name} stream with GPU decode...")

                # CRITICAL: Use h264_cuvid codec for GPU decoding
                container = av.open(url, options={
                    'rtsp_transport': 'tcp',
                    'fflags': 'nobuffer',
                    'flags': 'low_delay',
                    'max_delay': '0',
                    'timeout': '5000000',
                    'hwaccel': 'cuda',           # Enable CUDA hardware acceleration
                    'hwaccel_output_format': 'cuda',  # Keep frames on GPU
                    'c:v': 'h264_cuvid',         # Use CUVID decoder (GPU)
                    'threads': '1',
                    'buffer_size': '65536'
                }, timeout=5.0)

                # Get video stream
                video_stream = container.streams.video[0]

                # Verify hardware acceleration
                codec_name = video_stream.codec_context.name
                is_hw_accel = 'cuvid' in codec_name.lower() or video_stream.codec_context.codec.is_decoder

                if is_hw_accel or 'h264_cuvid' in str(video_stream.codec_context):
                    self.stats["decode_method"] = "NVDEC (GPU)"
                    self.stats["hw_accel_verified"] = True
                    logger.info(f"[CH{self.channel}] ✓ GPU hardware decode enabled: {codec_name}")
                else:
                    self.stats["decode_method"] = "CPU"
                    self.stats["hw_accel_verified"] = False
                    logger.warning(f"[CH{self.channel}] ⚠️  GPU decode not verified, may be using CPU: {codec_name}")

                # Quick test read with timeout
                frame_count = 0
                for frame in container.decode(video=0):
                    img = frame.to_ndarray(format='bgr24')
                    self.stats["stream_width"] = img.shape[1]
                    self.stats["stream_height"] = img.shape[0]
                    self.stats["connection_status"] = "connected"

                    frame_count += 1
                    if frame_count >= 1:  # Just get 1 frame for testing
                        break

                logger.info(f"[CH{self.channel}] ✓ Connected via {name} stream ({img.shape[1]}x{img.shape[0]}) - Decode: {self.stats['decode_method']}")
                return container, video_stream

            except Exception as e:
                logger.warning(f"[CH{self.channel}] ✗ {name} failed: {str(e)[:100]}")
                time.sleep(0.5)  # Brief pause before trying next URL
                continue

        self.stats["connection_status"] = "failed"
        logger.error(f"[CH{self.channel}] ✗✗✗ All connection attempts failed")
        return None, None

    def detect_and_annotate(self, frame):
        """Non-blocking inference submission with cached results"""
        if shared_model is None:
            return frame, [], 0

        # Try to submit frame to inference queue (non-blocking)
        if not self.pending_inference:
            try:
                result_queue = Queue(maxsize=1)
                request = InferenceRequest(frame=frame, result_queue=result_queue, channel=self.channel)
                inference_queue.put_nowait(request)  # Non-blocking put
                self.pending_inference = True

                # Start background thread to wait for result
                threading.Thread(target=self._wait_for_result, args=(result_queue,), daemon=True).start()
            except:
                # Queue full, skip this frame submission
                pass

        # Return cached result immediately (don't wait)
        with self.result_lock:
            if self.latest_result is not None:
                return self.annotate_frame(frame, self.latest_result)
            else:
                # No result yet, return original frame
                return frame, [], 0

    def _wait_for_result(self, result_queue):
        """Background thread to wait for inference result"""
        try:
            results = result_queue.get(timeout=5.0)
            with self.result_lock:
                self.latest_result = results
                self.pending_inference = False
        except:
            self.pending_inference = False

    def annotate_frame(self, frame, results):
        """Annotate frame with cached results"""
        start_time = time.time()
        detections = []
        annotated = frame.copy()

        for result in results:
            boxes = result.boxes
            if boxes is not None:
                for box in boxes:
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                    confidence = float(box.conf[0].cpu().numpy())
                    class_id = int(box.cls[0].cpu().numpy())  # Get class ID (0=staff, 1=customer)

                    # Determine color and label based on class
                    if class_id == 0:  # Staff
                        color = STAFF_COLOR
                        label = f"Staff: {confidence:.1%}"
                    else:  # Customer (class_id == 1)
                        color = CUSTOMER_COLOR
                        label = f"Customer: {confidence:.1%}"

                    detections.append({
                        "bbox": (x1, y1, x2, y2),
                        "confidence": confidence,
                        "class": class_id
                    })

                    # Draw bounding box
                    cv2.rectangle(annotated, (x1, y1), (x2, y2), color, BOX_THICKNESS)

                    # Draw label background
                    label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, FONT_SCALE, 2)[0]
                    cv2.rectangle(annotated, (x1, y1 - label_size[1] - 10), (x1 + label_size[0], y1), color, -1)

                    # Draw label text
                    cv2.putText(annotated, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, FONT_SCALE, (255, 255, 255), 2)

        inference_time = (time.time() - start_time) * 1000
        return annotated, detections, inference_time

    def add_overlay(self, frame, fps, inference_time, detection_count):
        """Add stats overlay with server timestamp"""
        h, w = frame.shape[:2]
        overlay = frame.copy()
        cv2.rectangle(overlay, (10, 10), (300, 150), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

        # Get current server time with milliseconds
        from datetime import datetime
        current_time = datetime.now()
        timestamp_str = current_time.strftime("%H:%M:%S.%f")[:-3]  # HH:MM:SS.mmm

        texts = [
            f"Channel {self.channel}",
            f"Time: {timestamp_str}",  # Server timestamp for lag testing
            f"FPS: {fps:.1f}",
            f"Inference: {inference_time:.1f}ms",
            f"Detections: {detection_count}",
            f"Res: {w}x{h}",
            f"Decode: {self.stats['decode_method']}"
        ]

        y = 25
        for text in texts:
            cv2.putText(frame, text, (15, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            y += 18

        return frame

    def process_stream(self):
        """Main processing loop with frame skipping"""
        logger.info(f"[CH{self.channel}] Starting process_stream thread...")

        self.container, self.stream = self.connect()
        if self.container is None:
            logger.error(f"[CH{self.channel}] Connection failed, thread exiting")
            return

        logger.info(f"[CH{self.channel}] Connection successful, starting frame processing...")

        fps_start = time.time()
        fps_count = 0
        current_fps = 0.0
        last_process_time = 0

        # Performance tracking
        decode_times = []
        inference_times = []

        try:
            for packet in self.container.demux(self.stream):
                if not self.running:
                    break

                # ✅ FIX: Wrap packet.decode() in try/except to skip corrupted H.264 packets
                # NVR occasionally sends corrupted packets that crash PyAV
                # This makes the decoder fault-tolerant like OpenCV was in V4
                try:
                    frames = packet.decode()
                except Exception as decode_error:
                    # Log but don't crash - just skip this corrupted packet
                    if self.stats["total_frames"] % 100 == 0:  # Log occasionally to avoid spam
                        logger.warning(f"[CH{self.channel}] Skipping corrupted packet: {str(decode_error)[:80]}")
                    self.stats["frame_drops"] += 1
                    continue  # Skip this packet and continue with next one

                for frame in frames:
                    if not self.running:
                        break

                    self.stats["total_frames"] += 1
                    current_time = time.time()

                    # Frame skipping: Only process if enough time has passed
                    if current_time - last_process_time < FRAME_INTERVAL:
                        self.stats["skipped_frames"] += 1
                        continue

                    last_process_time = current_time
                    self.stats["processed_frames"] += 1

                    # === DECODE TIME MEASUREMENT ===
                    decode_start = time.time()
                    try:
                        img = frame.to_ndarray(format='bgr24')
                    except:
                        self.stats["frame_drops"] += 1
                        continue
                    decode_time = (time.time() - decode_start) * 1000  # ms

                    # === INFERENCE TIME MEASUREMENT ===
                    inference_start = time.time()
                    annotated, detections, _ = self.detect_and_annotate(img)
                    inference_time = (time.time() - inference_start) * 1000  # ms

                    # Track performance
                    decode_times.append(decode_time)
                    inference_times.append(inference_time)
                    if len(decode_times) > 100:  # Keep last 100 samples
                        decode_times.pop(0)
                    if len(inference_times) > 100:
                        inference_times.pop(0)

                    # Calculate FPS
                    fps_count += 1
                    elapsed = current_time - fps_start
                    if elapsed >= 1.0:
                        current_fps = fps_count / elapsed
                        fps_count = 0
                        fps_start = current_time

                    # Update stats with detailed timing
                    self.stats["current_detections"] = len(detections)
                    self.stats["current_fps"] = current_fps
                    self.stats["current_decode_ms"] = decode_time
                    self.stats["current_inference_ms"] = inference_time
                    self.stats["avg_decode_ms"] = np.mean(decode_times) if decode_times else 0
                    self.stats["avg_inference_ms"] = np.mean(inference_times) if inference_times else 0

                    if detections:
                        confidences = [d["confidence"] for d in detections]
                        self.stats["avg_confidence"] = np.mean(confidences)

                    # Add overlay
                    annotated = self.add_overlay(annotated, current_fps, inference_time, len(detections))
                    self.frame = annotated.copy()

                    # Periodic performance logging (every 30 frames)
                    if self.stats["processed_frames"] % 30 == 0:
                        logger.info(f"[CH{self.channel}] Perf: Decode={self.stats['avg_decode_ms']:.1f}ms | Inference={self.stats['avg_inference_ms']:.1f}ms | FPS={current_fps:.1f} | HW={self.stats['hw_accel_verified']}")

        except Exception as e:
            logger.error(f"[CH{self.channel}] Error in processing: {e}")
        finally:
            if self.container:
                try:
                    self.container.close()
                except:
                    pass
                self.container = None
            logger.info(f"[CH{self.channel}] Thread exiting | Avg Decode: {self.stats['avg_decode_ms']:.1f}ms | Avg Inference: {self.stats['avg_inference_ms']:.1f}ms")

    def start(self):
        """Start camera stream"""
        self.running = True
        self.thread = threading.Thread(target=self.process_stream, daemon=True)
        self.thread.start()
        logger.info(f"[CH{self.channel}] Thread started")

    def stop(self):
        """Stop camera stream"""
        logger.info(f"[CH{self.channel}] Stopping camera...")
        self.running = False
        self.frame = None

        # ✅ FIX: Wait for thread to exit BEFORE closing container
        # This avoids deadlock when closing container while thread is reading from it
        if self.thread and self.thread.is_alive():
            logger.info(f"[CH{self.channel}] Waiting for thread to exit...")
            self.thread.join(timeout=5)  # Give it 5 seconds to exit gracefully

            if self.thread.is_alive():
                logger.warning(f"[CH{self.channel}] Thread did not exit gracefully after timeout")

        # Now close container after thread has stopped
        if self.container:
            try:
                logger.info(f"[CH{self.channel}] Closing container...")
                self.container.close()
                logger.info(f"[CH{self.channel}] Container closed")
            except Exception as e:
                logger.warning(f"[CH{self.channel}] Error closing container: {e}")
            finally:
                self.container = None

        logger.info(f"[CH{self.channel}] Stopped")

# =============================================================================
# System Monitoring
# =============================================================================

def get_gpu_stats():
    """Get GPU stats using nvidia-smi"""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw",
             "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(',')
            return {
                "utilization": float(parts[0]),
                "memory_used_mb": float(parts[1]),
                "memory_total_mb": float(parts[2]),
                "temperature_c": float(parts[3]),
                "power_draw_w": float(parts[4])
            }
    except:
        pass
    return None

def get_system_stats():
    """Get comprehensive system stats"""
    cpu_percent = psutil.cpu_percent(interval=0.5, percpu=False)
    cpu_per_core = psutil.cpu_percent(interval=0.5, percpu=True)
    memory = psutil.virtual_memory()

    cpu_temp = None
    try:
        temps = psutil.sensors_temperatures()
        if 'coretemp' in temps:
            cpu_temp = max(t.current for t in temps['coretemp'])
        elif 'k10temp' in temps:
            cpu_temp = temps['k10temp'][0].current
    except:
        pass

    gpu_stats = get_gpu_stats()

    return {
        "cpu": {
            "overall": cpu_percent,
            "per_core": cpu_per_core,
            "temperature_c": cpu_temp
        },
        "memory": {
            "percent": memory.percent,
            "used_gb": round(memory.used / (1024**3), 2),
            "total_gb": round(memory.total / (1024**3), 2)
        },
        "gpu": gpu_stats,
        "timestamp": datetime.now().isoformat()
    }

# =============================================================================
# Batch Inference Worker
# =============================================================================

def batch_inference_worker():
    """
    Batch inference worker thread
    Collects multiple frames and processes them together on GPU
    """
    global inference_running
    worker_id = threading.current_thread().name
    logger.info(f"🚀 Batch inference worker started: {worker_id}")

    batch_count = 0

    while inference_running:
        batch_requests = []
        batch_frames = []

        # Collect batch (wait for first frame, then quickly collect more)
        try:
            # Wait for first request (blocking)
            wait_start = time.time()
            first_request = inference_queue.get(timeout=1.0)
            wait_time = (time.time() - wait_start) * 1000

            batch_requests.append(first_request)
            batch_frames.append(first_request.frame)

            # CRITICAL: Collect more frames with short timeout instead of sleep
            # This is smarter - we wait for frames but don't delay if none are available
            # With 15 cameras @ 3 FPS: frames arrive every ~22ms
            # With 30 cameras @ 3 FPS: frames arrive every ~11ms
            # Use 20ms timeout to collect 1-2 more frames
            collect_start = time.time()
            while len(batch_frames) < batch_size and (time.time() - collect_start) < 0.02:  # 20ms timeout
                try:
                    request = inference_queue.get(timeout=0.005)  # 5ms wait
                    batch_requests.append(request)
                    batch_frames.append(request.frame)
                except:
                    break  # Timeout, no more frames available

            collect_time = (time.time() - collect_start) * 1000
            logger.info(f"[{worker_id}] Collected {len(batch_frames)} frames in {collect_time:.1f}ms")

        except:
            continue  # Timeout, try again

        if not batch_frames:
            continue

        # Batch inference
        try:
            infer_start = time.time()
            results = shared_model(batch_frames, conf=CONF_THRESHOLD, iou=IOU_THRESHOLD, verbose=False)
            infer_time = (time.time() - infer_start) * 1000

            batch_count += 1
            per_frame_time = infer_time / len(batch_frames)
            logger.info(f"[{worker_id}] ⚡ Batch #{batch_count}: {len(batch_frames)} frames in {infer_time:.1f}ms ({per_frame_time:.1f}ms/frame)")

            # Return results to each request
            for i, request in enumerate(batch_requests):
                try:
                    request.result_queue.put([results[i]], timeout=0.1)
                except:
                    logger.warning(f"[{worker_id}] Failed to return result {i}")

        except Exception as e:
            logger.error(f"[{worker_id}] Batch inference error: {e}")
            import traceback
            logger.error(f"[{worker_id}] Traceback: {traceback.format_exc()}")
            # Return empty results on error
            for request in batch_requests:
                try:
                    request.result_queue.put([], timeout=0.1)
                except:
                    pass

    logger.info(f"🛑 Batch inference worker stopped: {worker_id}, processed {batch_count} batches")

# =============================================================================
# Model Loading
# =============================================================================

def load_shared_model():
    """Load YOLO model once for GPU sharing"""
    global shared_model

    logger.info("Loading YOLO11s V5 model (staff/customer detector)...")
    model_path = os.path.join(os.path.dirname(__file__), MODEL_PATH)

    if not os.path.exists(model_path):
        logger.error(f"Model not found at {model_path}")
        return False

    try:
        shared_model = YOLO(model_path)
        shared_model.to('cuda')
        logger.info(f"✓ Model loaded on device: {shared_model.device}")
        return True
    except Exception as e:
        logger.error(f"Model loading failed: {e}")
        return False

# =============================================================================
# Flask Routes
# =============================================================================

@app.route('/')
def index():
    return render_template('manual_tester.html')

@app.route('/api/start_camera', methods=['POST'])
def start_camera():
    """Start a camera stream (non-blocking)"""
    data = request.json
    channel = data.get('channel')

    logger.info(f"🚀 [API] START_CAMERA request for channel {channel}")

    if not channel:
        logger.error(f"🚀 [API] START_CAMERA: No channel provided")
        return jsonify({"error": "Channel required"}), 400

    if channel in active_cameras:
        logger.warning(f"🚀 [API] START_CAMERA: Channel {channel} already active")
        return jsonify({"error": f"Channel {channel} already active"}), 400

    # Check maximum camera limit
    if len(active_cameras) >= MAX_CAMERAS:
        logger.warning(f"🚀 [API] START_CAMERA: Maximum {MAX_CAMERAS} cameras reached")
        return jsonify({"error": f"Maximum {MAX_CAMERAS} cameras reached. Stop some cameras first."}), 400

    # Get current thread count
    try:
        current_process = psutil.Process()
        thread_count_before = current_process.num_threads()
    except:
        thread_count_before = -1

    logger.info(f"🚀 [API] START_CAMERA CH{channel}: Creating CameraStream object...")
    # Create and start camera in background
    cam = CameraStream(channel)
    active_cameras[channel] = cam
    camera_locks[channel] = threading.Lock()

    logger.info(f"🚀 [API] START_CAMERA CH{channel}: Starting camera thread...")
    # Start thread (connection happens in background)
    cam.start()

    # Get thread count after starting
    try:
        thread_count_after = current_process.num_threads()
        logger.info(f"🚀 [API] START_CAMERA CH{channel}: ✓ Started | Active: {len(active_cameras)}/{MAX_CAMERAS} | Threads: {thread_count_before} → {thread_count_after} (+{thread_count_after - thread_count_before})")
    except:
        logger.info(f"🚀 [API] START_CAMERA CH{channel}: ✓ Started | Active: {len(active_cameras)}/{MAX_CAMERAS}")

    # Return immediately - connection status updates asynchronously
    return jsonify({
        "success": True,
        "channel": channel,
        "status": "connecting",
        "active_cameras": len(active_cameras),
        "thread_count": thread_count_after if 'thread_count_after' in locals() else None
    })

@app.route('/api/stop_camera', methods=['POST'])
def stop_camera():
    """Stop a camera stream"""
    data = request.json
    channel = data.get('channel')

    if channel not in active_cameras:
        return jsonify({"error": f"Channel {channel} not active"}), 400

    cam = active_cameras[channel]
    cam.stop()

    time.sleep(0.5)

    del active_cameras[channel]
    del camera_locks[channel]

    return jsonify({"success": True, "channel": channel})

@app.route('/api/active_cameras')
def get_active_cameras():
    """Get list of active cameras"""
    return jsonify({"cameras": list(active_cameras.keys())})

@app.route('/video_feed/<int:channel>')
def video_feed(channel):
    """Stream video for a channel"""
    logger.info(f"🌐 [CH{channel}] HTTP: video_feed endpoint requested")

    if channel not in active_cameras:
        logger.error(f"🌐 [CH{channel}] HTTP: Camera not in active_cameras dict, returning 404")
        return "Camera not active", 404

    def generate():
        cam = active_cameras[channel]
        frame_count = 0
        logger.info(f"🌐 [CH{channel}] HTTP: Starting generator, cam.running={cam.running}, cam.frame={'present' if cam.frame is not None else 'None'}")

        # Wait for first frame (up to 10 seconds)
        wait_time = 0
        logger.info(f"🌐 [CH{channel}] HTTP: Waiting for first frame...")
        while cam.frame is None and cam.running and wait_time < 10:
            time.sleep(0.1)
            wait_time += 0.1
            if int(wait_time * 10) % 10 == 0:  # Log every second
                logger.info(f"🌐 [CH{channel}] HTTP: Still waiting... ({wait_time:.1f}s)")

        # If camera failed to connect or stopped, send error frame
        if cam.frame is None or not cam.running:
            logger.error(f"🌐 [CH{channel}] HTTP: No frame available after {wait_time:.1f}s, cam.running={cam.running}")
            # Create a black frame with error message
            error_frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(error_frame, f"Camera {channel} Failed", (50, 240),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            ret, buffer = cv2.imencode('.jpg', error_frame)
            if ret:
                logger.info(f"🌐 [CH{channel}] HTTP: Yielding error frame")
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            return

        logger.info(f"🌐 [CH{channel}] HTTP: First frame available, starting stream loop")

        # Stream frames
        last_log_time = time.time()
        while cam.running:
            if cam.frame is not None:
                try:
                    encode_start = time.time()
                    ret, buffer = cv2.imencode('.jpg', cam.frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
                    encode_time = (time.time() - encode_start) * 1000

                    if ret:
                        frame_count += 1

                        # Log every 30 frames or every 5 seconds
                        current_time = time.time()
                        if frame_count % 30 == 0 or (current_time - last_log_time) >= 5.0:
                            logger.info(f"🌐 [CH{channel}] HTTP: Streamed {frame_count} frames, JPEG encode={encode_time:.1f}ms, size={len(buffer)}B")
                            last_log_time = current_time

                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
                    else:
                        logger.warning(f"🌐 [CH{channel}] HTTP: JPEG encode failed at frame {frame_count}")
                except Exception as e:
                    logger.error(f"🌐 [CH{channel}] HTTP: Exception during encode/yield: {e}")
                    pass
            time.sleep(0.05)  # Slightly slower to reduce browser load

        logger.info(f"🌐 [CH{channel}] HTTP: Generator exiting, cam.running={cam.running}, total_frames_streamed={frame_count}")

    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/stats')
def get_stats():
    """Get comprehensive system and camera stats"""
    system_stats = get_system_stats()

    camera_stats_list = []
    total_fps = 0
    total_decode_time = 0
    total_inference_time = 0
    hw_accel_count = 0

    for channel, cam in active_cameras.items():
        stats = {
            "channel": channel,
            "total_frames": cam.stats["total_frames"],
            "processed_frames": cam.stats["processed_frames"],
            "skipped_frames": cam.stats["skipped_frames"],
            "frame_drops": cam.stats["frame_drops"],
            "connection_status": cam.stats["connection_status"],
            "stream_width": cam.stats["stream_width"],
            "stream_height": cam.stats["stream_height"],
            "current_detections": cam.stats["current_detections"],
            "avg_confidence": cam.stats["avg_confidence"],
            "current_fps": cam.stats["current_fps"],
            "current_inference_ms": cam.stats["current_inference_ms"],
            "current_decode_ms": cam.stats["current_decode_ms"],
            "avg_inference_ms": cam.stats["avg_inference_ms"],
            "avg_decode_ms": cam.stats["avg_decode_ms"],
            "decode_method": cam.stats["decode_method"],
            "hw_accel_verified": cam.stats["hw_accel_verified"]
        }
        camera_stats_list.append(stats)
        total_fps += stats.get("current_fps", 0)
        total_decode_time += stats.get("avg_decode_ms", 0)
        total_inference_time += stats.get("avg_inference_ms", 0)
        if stats.get("hw_accel_verified", False):
            hw_accel_count += 1

    avg_decode = total_decode_time / len(active_cameras) if active_cameras else 0
    avg_inference = total_inference_time / len(active_cameras) if active_cameras else 0

    return jsonify({
        "system": system_stats,
        "cameras": camera_stats_list,
        "summary": {
            "active_cameras": len(active_cameras),
            "total_fps": round(total_fps, 1),
            "target_fps": TARGET_FPS,
            "avg_decode_ms": round(avg_decode, 2),
            "avg_inference_ms": round(avg_inference, 2),
            "hw_accel_cameras": hw_accel_count,
            "hw_accel_percentage": round(hw_accel_count / len(active_cameras) * 100, 1) if active_cameras else 0,
            "inference_queue_size": inference_queue.qsize(),
            "batch_size": batch_size
        }
    })

# =============================================================================
# Main
# =============================================================================

def main():
    global inference_running

    logger.info("="*70)
    logger.info("🎥 MANUAL CAMERA TESTER - PyAV + GPU Decoding + BATCH INFERENCE")
    logger.info("="*70)
    logger.info(f"Target FPS: {TARGET_FPS} frames/sec per camera")
    logger.info(f"Frame interval: {FRAME_INTERVAL:.3f}s (skip {int(30/TARGET_FPS - 1)} frames per processed frame)")
    logger.info(f"Decode: PyAV with NVDEC (GPU hardware decoding)")
    logger.info(f"Inference: Batch processing (batch size: {batch_size})")
    logger.info(f"Threads: One per camera (limited to 1 FFMPEG thread each)")
    logger.info(f"Max cameras: {MAX_CAMERAS}")
    logger.info(f"Server: http://{SERVER_HOST}:{SERVER_PORT}")

    # System info
    try:
        import platform
        logger.info(f"System: {platform.system()} {platform.release()}")
        logger.info(f"Python: {platform.python_version()}")
        logger.info(f"PyAV: {av.__version__}")
    except:
        pass

    logger.info("="*70)

    if not load_shared_model():
        return

    # Start batch inference workers
    num_workers = 3  # Multiple workers for better GPU utilization
    logger.info(f"🚀 Starting {num_workers} batch inference worker(s)...")
    inference_threads = []
    for i in range(num_workers):
        thread = threading.Thread(target=batch_inference_worker, daemon=True, name=f"InferenceWorker-{i}")
        thread.start()
        inference_threads.append(thread)
        logger.info(f"  ✓ Worker {i+1} started")

    logger.info(f"Starting Flask server on {SERVER_HOST}:{SERVER_PORT}...")
    try:
        app.run(host=SERVER_HOST, port=SERVER_PORT, threaded=True, debug=False)
    finally:
        # Cleanup on shutdown
        inference_running = False
        for thread in inference_threads:
            thread.join(timeout=2)

if __name__ == "__main__":
    main()
