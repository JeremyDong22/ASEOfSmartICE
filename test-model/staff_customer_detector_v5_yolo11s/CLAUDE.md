# Staff/Customer Detector V5 - YOLO11s Two-Class Detection Test

## Overview
This folder contains performance testing for the YOLO11s staff/customer detection model (V5). This model detects both staff AND customers in a single pass with different colored bounding boxes.

## Model Information

### Model Details
- **Model Type**: YOLO11s Detection (Small variant)
- **Architecture**: One-stage direct two-class detection
- **Model Size**: ~20MB
- **Training Data**: 595 labeled images from Smartice 001 location
- **Classes**: 2 (staff, customer)
- **Input Size**: 800×800 (larger than V4 for better accuracy)
- **Device**: MPS (Apple Silicon optimized)

### Training Configuration (Gemini-Optimized)
```python
# Augmentation parameters optimized for restaurant environment
hsv_h: 0.003    # Lower - consistent lighting in restaurants
hsv_v: 0.6      # Higher - handle lighting variations
erasing: 0.2    # Random erasing for robustness
close_mosaic: 15  # Disable mosaic in last 15 epochs
mixup: 0.0      # No mixup for cleaner boundaries
```

### Comparison with V4
| Feature | V4 (YOLO11n) | V5 (YOLO11s) |
|---------|--------------|--------------|
| Classes | 1 (staff only) | 2 (staff + customer) |
| Model Size | ~5.4MB | ~20MB |
| Input Size | 640×640 | 800×800 |
| Architecture | YOLO11n (nano) | YOLO11s (small) |
| Color Coding | Green only | Green=Staff, Red=Customer |

## Test Files

### Models
- `models/staff_customer_detector.pt` - Trained YOLO11s detection model

### Scripts
- `test_staff_customer_detector.py` - Image and video performance testing
- `realtime_detection_server.py` - Flask-based real-time detection server

### Templates
- `templates/detection_dashboard.html` - Web dashboard for real-time detection

### Results (after running tests)
- `results/images/` - Annotated test images with colored bounding boxes
- `results/videos/` - Processed videos with detections
- `results/performance_report.txt` - Detailed timing and FPS metrics

## Visual Output

### Bounding Box Colors
- **Green**: Detected staff member (with confidence score)
- **Red**: Detected customer (with confidence score)

### Label Format
```
Staff: 95.3%     [green box]
Customer: 87.2%  [red box]
```

## Usage

### Run Performance Tests
```bash
cd /Users/jeremydong/Desktop/Smartice/APPs/ASEOfSmartICE/test-model/staff_customer_detector_v5_yolo11s

# Run complete test suite (images + video)
python3 test_staff_customer_detector.py
```

This will:
1. Load the YOLO11s model
2. Test on validation images
3. Process test video and measure FPS
4. Save annotated outputs to results/
5. Generate performance report

### Run Real-Time Detection Server
```bash
# Run on specific NVR channel (port = 5000 + channel)
python3 realtime_detection_server.py --channel 18   # http://localhost:5018
python3 realtime_detection_server.py --channel 14   # http://localhost:5014

# Custom RTSP URL
python3 realtime_detection_server.py --rtsp "rtsp://user:pass@ip:554/stream"

# Open dashboard in browser
open http://localhost:5018
```

### Dashboard Features
- Live video stream with detection overlay
- Real-time staff/customer counts
- Average confidence scores per class
- FPS and inference time metrics
- Stream health monitoring

## Camera Configuration (SmartICE NVR)

### NVR Connection
- **NVR IP**: 192.168.1.3
- **Port**: 554 (RTSP)
- **Username**: admin
- **Password**: ybl123456789
- **Total Channels**: 30

### RTSP URL Pattern
```
rtsp://admin:ybl123456789@192.168.1.3:554/unicast/c{CHANNEL}/s{STREAM}/live
```

### Test Command
```bash
# Test channel connectivity
ffprobe -v error -rtsp_transport tcp "rtsp://admin:ybl123456789@192.168.1.3:554/unicast/c18/s0/live"
```

## Expected Performance

### M4 MacBook Pro (MPS)
- **Image Inference**: ~15-25ms per image
- **Video FPS**: 40-60 FPS
- **Real-time capable**: Yes (>30 FPS)

### Linux RTX 3060
- **Image Inference**: ~8-15ms per image
- **Video FPS**: 60-100 FPS
- **Real-time capable**: Yes

## Model Path
Trained model location:
`/Users/jeremydong/Desktop/Smartice/APPs/ASEOfSmartICE/train-model/model_v5/models_detection/staff_customer_detector_v5/weights/best.pt`

Copy to test folder as: `models/staff_customer_detector.pt`

## Notes

- This is a **two-class detection model** - detects both staff AND customers
- Larger input size (800×800) for improved accuracy on distant subjects
- YOLO11s architecture provides good balance of speed and accuracy
- Trained with Gemini-optimized augmentation for restaurant environments
- Green boxes = Staff, Red boxes = Customers

## Manual Camera Tester (PyAV + GPU + Async)

### Overview
Production-grade multi-camera testing server with hardware-accelerated decoding and asynchronous inference architecture.

### Key Features
- **GPU Decoding**: NVDEC hardware acceleration (h264_cuvid)
- **Async Inference**: Non-blocking frame submission with result caching
- **Batch Processing**: 16-frame batches with 3 dedicated inference workers
- **Multi-Camera**: Supports up to 30 concurrent camera streams
- **Real-time Stats**: Per-camera metrics (FPS, inference time, decode time, lag)
- **Flask API**: RESTful endpoints for camera control and monitoring

### File Location
`manual_camera_tester_pyav.py` - Main multi-camera testing server

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Camera Threads (1-30)                     │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ RTSP → PyAV (NVDEC GPU Decode) → Frame Buffer       │   │
│  └──────────────────────┬───────────────────────────────┘   │
│                         │ Non-blocking frame submission      │
│                         ▼                                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Inference Queue (max 100 frames)                     │   │
│  │  • Async put_nowait() - no blocking                  │   │
│  │  • Result caching with thread-safe locks             │   │
│  └──────────────────────┬───────────────────────────────┘   │
└─────────────────────────┼───────────────────────────────────┘
                          │
          ┌───────────────┼────────────────┐
          │               │                │
┌─────────▼────────┐  ┌───▼──────┐  ┌─────▼────────┐
│ Inference Worker │  │ Worker 2 │  │  Worker 3    │
│  (Batch = 16)    │  │(Batch=16)│  │ (Batch = 16) │
│  YOLO11s GPU     │  │YOLO11s   │  │  YOLO11s     │
└─────────┬────────┘  └───┬──────┘  └─────┬────────┘
          │               │                │
          └───────────────┼────────────────┘
                          │
                          ▼
          ┌────────────────────────────────┐
          │  Result Queues (per-camera)    │
          │  • Background threads wait     │
          │  • Update latest_result cache  │
          └────────────────────────────────┘
```

### Configuration

```python
# Network Configuration
NVR_IP = "192.168.1.3"
NVR_USERNAME = "admin"
NVR_PASSWORD = "ybl123456789"

# Performance Configuration
TARGET_FPS = 15              # Target frames per second per camera
MAX_CAMERAS = 30             # Maximum concurrent cameras
batch_size = 16              # Batch inference size
inference_workers = 3        # Number of inference threads

# Server Configuration
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8001           # V5 port (V4 uses 8000)
```

### Usage

```bash
# Start Python server
cd /home/smartice001/smartice/ASEOfSmartICE/test-model/staff_customer_detector_v5_yolo11s
python3 manual_camera_tester_pyav.py

# Server starts on http://localhost:8001
# Navigate to http://localhost:8001 in browser for basic interface
```

### Flask API Endpoints

#### Camera Control
- `POST /api/start_camera` - Start camera stream
  - Request: `{"channel": 1-30}`
  - Response: `{"success": true, "message": "Camera started"}`

- `POST /api/stop_camera` - Stop camera stream
  - Request: `{"channel": 1-30}`
  - Response: `{"success": true, "message": "Camera stopped"}`

- `GET /api/active_cameras` - Get list of active cameras
  - Response: `{"active_cameras": [1, 2, 3, ...]}`

#### Statistics
- `GET /api/stats` - Get all camera statistics
  - Response: JSON object with per-camera stats

- `GET /api/system_stats` - Get system resource usage
  - Response: GPU/CPU/memory metrics

#### Video Streaming
- `GET /video_feed/<channel>` - MJPEG video stream for specific camera
  - Returns: multipart/x-mixed-replace MJPEG stream

### Performance (Async Architecture)

#### Before Async (Blocking)
- **20 Cameras**: 106 FPS total (5.3 FPS per camera)
- **Bottleneck**: Camera threads blocked waiting for inference
- **Target Achievement**: 35% of 15 FPS target

#### After Async (Non-blocking)
- **20 Cameras**: 219 FPS total (10.9 FPS per camera)
- **Improvement**: 2.1x FPS increase
- **Target Achievement**: 73% of 15 FPS target
- **Queue Depth**: 0-4 frames (no buildup)
- **Inference Time**: 1-8ms average

### Optimization History

**Version 1 (Blocking)**
- Sequential inference
- Camera threads waited for results
- Result: 5.3 FPS per camera

**Version 2 (Async) - Current**
- Non-blocking frame submission
- Result caching with background threads
- Thread-safe access with locks
- Result: 10.9 FPS per camera (2.1x improvement)

### Key Optimizations

1. **GPU Decoding (NVDEC)**
   - Uses `h264_cuvid` codec for hardware acceleration
   - Fallback to CPU if GPU decode fails
   - Tracks decode method in stats

2. **Batch Inference**
   - Collects frames into batches of 16
   - 3 dedicated inference workers
   - Timeout-based batch dispatch (20ms)

3. **Async Architecture**
   - Non-blocking `put_nowait()` for frame submission
   - Background threads wait for inference results
   - Result caching prevents blocking camera threads

4. **Frame Rate Control**
   - Skips frames to maintain target FPS
   - Prevents processing more frames than needed
   - Reduces unnecessary GPU load

### Testing

See `/home/smartice001/smartice/ASEOfSmartICE/test-model/staff_customer_detector_v5_yolo11s/testing-dashboard/` for:
- TypeScript-based testing dashboard
- Automated performance test scripts
- Real-time monitoring interface
- Multi-camera capacity testing tools

### Related Documentation
- `testing-dashboard/CLAUDE.md` - Dashboard architecture and usage
- `testing-dashboard/ASYNC_TEST_RESULTS.md` - Async optimization results
- `test_v5_direct.sh` - Basic testing script

## Version
- **Model Version**: V5.0
- **Test Date**: December 26, 2025
- **Training Date**: December 26, 2025
- **Server Version**: 2.0 (Async Architecture)
- **Last Updated**: December 27, 2025
