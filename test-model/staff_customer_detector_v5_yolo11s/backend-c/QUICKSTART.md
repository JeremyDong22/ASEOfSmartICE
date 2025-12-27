# Quick Start Guide - C++ Backend

## Prerequisites

You must have sudo access to install FFmpeg development headers:

```bash
sudo apt-get update
sudo apt-get install -y libavcodec-dev libavformat-dev libavutil-dev libswscale-dev
```

## Build Instructions

```bash
# Navigate to backend directory
cd /home/smartice001/smartice/ASEOfSmartICE/test-model/staff_customer_detector_v5_yolo11s/backend-c

# Create build directory
mkdir -p build && cd build

# Run CMake
~/.local/bin/cmake -DCMAKE_BUILD_TYPE=Release ..

# Build (using all CPU cores)
make -j$(nproc)

# Binary will be created at: ./smartice_server
```

## Running the Server

```bash
# Start server (default port 8001)
./smartice_server

# Or specify custom port and model
./smartice_server 8001 ../models/staff_customer_detector.pt
```

## API Usage

### 1. Start Camera
```bash
curl -X POST http://localhost:8001/api/camera/start \
  -H "Content-Type: application/json" \
  -d '{"channel": 18}'

# Response:
# {
#   "success": true,
#   "channel": 18,
#   "rtsp_url": "rtsp://admin:ybl123456789@192.168.1.3:554/unicast/c18/s0/live",
#   "stream_url": "/stream/mjpeg/18"
# }
```

### 2. Get Statistics
```bash
curl http://localhost:8001/api/stats

# Response:
# {
#   "cameras": [
#     {
#       "channel": 18,
#       "is_running": true,
#       "width": 1920,
#       "height": 1080,
#       "fps": 25.0,
#       "total_frames": 1250,
#       "staff_count": 3,
#       "customer_count": 12,
#       "avg_inference_ms": 12.5
#     }
#   ],
#   "summary": {
#     "num_cameras": 1,
#     "total_staff": 3,
#     "total_customer": 12,
#     "total_frames": 1250
#   }
# }
```

### 3. Get Annotated Frame
```bash
# Download latest frame with detections
curl http://localhost:8001/stream/mjpeg/18 --output frame.jpg

# View in browser
open frame.jpg  # macOS
xdg-open frame.jpg  # Linux
```

### 4. Stop Camera
```bash
curl -X POST http://localhost:8001/api/camera/stop \
  -H "Content-Type: application/json" \
  -d '{"channel": 18}'
```

### 5. Health Check
```bash
curl http://localhost:8001/api/health
```

## Multi-Camera Example

```bash
# Start 5 cameras simultaneously
for ch in 18 14 22 15 19; do
  curl -X POST http://localhost:8001/api/camera/start \
    -H "Content-Type: application/json" \
    -d "{\"channel\": $ch}"
  sleep 1
done

# Get combined statistics
curl http://localhost:8001/api/stats | jq .

# Stop all cameras
for ch in 18 14 22 15 19; do
  curl -X POST http://localhost:8001/api/camera/stop \
    -H "Content-Type: application/json" \
    -d "{\"channel\": $ch}"
done
```

## Performance Testing

```bash
# Test with 20 cameras
#!/bin/bash
for ch in {1..20}; do
  curl -X POST http://localhost:8001/api/camera/start \
    -H "Content-Type: application/json" \
    -d "{\"channel\": $ch}" &
done
wait

# Check FPS
watch -n 1 'curl -s http://localhost:8001/api/stats | jq ".summary"'
```

## Troubleshooting

### Build Errors

**Error: "Package 'libavcodec', required by 'virtual:world', not found"**

Solution: Install FFmpeg development headers
```bash
sudo apt-get install -y libavcodec-dev libavformat-dev libavutil-dev libswscale-dev
```

**Error: "Torch not found"**

Solution: Verify PyTorch installation
```bash
python3 -c "import torch; print(torch.__file__)"
# Update CMAKE_PREFIX_PATH in CMakeLists.txt
```

**Error: "OpenCV not found"**

Solution: Install OpenCV
```bash
sudo apt-get install -y libopencv-dev
```

### Runtime Errors

**Error: "Failed to open RTSP stream"**

Solutions:
1. Check camera is online: `ffprobe -rtsp_transport tcp rtsp://admin:ybl123456789@192.168.1.3:554/unicast/c18/s0/live`
2. Verify NVR credentials are correct
3. Check network connectivity to NVR (192.168.1.3)

**Error: "CUDA out of memory"**

Solution: Reduce number of concurrent cameras or use CPU inference
```bash
# CPU mode (slower but uses less GPU memory)
# Edit main.cpp: InferenceEngine engine(model_path, use_cuda=false);
```

## Logs

Server logs are written to `smartice_backend.log` in the current directory.

```bash
# View logs in real-time
tail -f smartice_backend.log

# Search for errors
grep ERROR smartice_backend.log
```

## Expected Output

When running with camera 18:

```
==============================================
SmartICE C++ Backend Server v1.0.0
YOLO11s Staff/Customer Detection
==============================================
[2025-12-27 21:00:00.123] [info] Configuration:
[2025-12-27 21:00:00.124] [info]   Port: 8001
[2025-12-27 21:00:00.125] [info]   Model: ../models/staff_customer_detector.pt
[2025-12-27 21:00:00.126] [info] Loading YOLO11s model...
[2025-12-27 21:00:01.234] [info] Using CUDA device for inference
[2025-12-27 21:00:02.456] [info] Model loaded successfully
[2025-12-27 21:00:02.457] [info]   Input size: 800x800
[2025-12-27 21:00:02.458] [info] Creating thread pool with 12 threads
[2025-12-27 21:00:02.459] [info] Server started on http://localhost:8001
[2025-12-27 21:00:02.460] [info]
[2025-12-27 21:00:02.461] [info] Available endpoints:
[2025-12-27 21:00:02.462] [info]   GET  /              - API documentation
[2025-12-27 21:00:02.463] [info]   GET  /api/health    - Health check
[2025-12-27 21:00:02.464] [info]   POST /api/camera/start - Start camera
[2025-12-27 21:00:02.465] [info]   POST /api/camera/stop  - Stop camera
[2025-12-27 21:00:02.466] [info]   GET  /api/stats     - All camera statistics
[2025-12-27 21:00:02.467] [info]   GET  /stream/mjpeg/18 - MJPEG frame
[2025-12-27 21:00:02.468] [info]
[2025-12-27 21:00:02.469] [info] Press Ctrl+C to stop
```

## Performance Metrics

Expected performance on RTX 3060:

- **Single camera**: 15-20 FPS with inference
- **20 cameras**: 300+ total FPS (15 FPS each)
- **Inference time**: 10-15ms per frame
- **Memory usage**: <500MB
- **CPU usage**: <20%

Compare this to Python baseline:
- **20 cameras**: 219 total FPS (10.9 FPS each)
- **Memory usage**: 2GB
- **CPU usage**: 30-40%

**C++ improvement: +37% FPS, -75% memory, -50% CPU**
