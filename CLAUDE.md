# CLAUDE.md

## Project Overview

Restaurant surveillance automation system using computer vision to distinguish between customers and employees, built on YOLO object detection models. The system captures real-time footage from multiple cameras across restaurant locations and applies progressive AI analysis.

## Business Objective

Build a multi-stage personnel detection system:
1. **Stage 1**: Detect all people in restaurant spaces
2. **Stage 2**: Distinguish between employees and customers
3. **Stage 3**: Analyze employee activities and behaviors (future)
4. **Stage 4**: Generate operational insights and metrics (future)

## Folder Structure

### Core Directories

#### `sub-stream/`
Camera connection testing using sub-streams (ending with /102). Contains OpenCV-based utilities for testing RTSP connections to all restaurant cameras.

#### `test/`
General testing utilities for camera connectivity and miscellaneous experiments that don't fit elsewhere.

#### `test-model/`
Model validation and testing environment. When new models are developed, they're tested here in dedicated subdirectories. See internal CLAUDE.md for detailed testing procedures.

#### `train-model/`
Primary model training pipeline. Frequently used for developing custom YOLO-based models. Key subdirectories:
- `dataset/` - Training datasets
- `extracted-persons/` - Person detections from raw footage
- `labeled-persons/` - Manually annotated training data
- `models/` - Trained model outputs
- `raw_images/` - Local image storage
- `scripts/` - Model training execution scripts
- `linux_rtx_screenshot_capture/` - **Critical**: Automated screenshot capture scripts for Linux RTX 3060 machines in restaurants

#### `unv-camera-detection/`
UNV (Uniview) camera detection and network discovery tools. Contains:
- `detect_cameras.py` - Python script to detect UNV cameras on local network using ONVIF, LAPI, and ARP scanning
- `requirements.txt` - Python dependencies (requests)
- `CAMERA_SETUP_GUIDE.md` - Complete documentation of camera discovery workflow and RTSP URLs

## System Architecture

### Development Environment
- **MacBook M4**: Model training and remote management
- **Linux 3060 Machines**: Deployed in each restaurant for data collection
- **Data Flow**: Linux scripts capture footage → Upload to cloud → Download to MacBook for training

### Linux Scripts Purpose
The `train-model/linux_rtx_screenshot_capture/` folder contains automation for the restaurant Linux machines:
- Shell scripts and Python scripts for automated data capture
- Runs continuously on restaurant hardware
- Captures frames/images from multiple cameras
- Uploads to Supabase cloud storage for training pipeline

## Camera Configuration

### SmartICE Network (Current)
- **NVR IP**: 192.168.1.3
- **Total Cameras**: 30 (connected via NVR internal PoE)
- **NVR Credentials**: admin / 123456
- **RTSP URL Pattern**: `rtsp://admin:123456@192.168.1.3:554/unicast/c{1-30}/s0/live`
- **Stream Types**: `s0` = main stream (high quality), `s1` = sub stream (lower bandwidth)
- **Network Type**: Dedicated private surveillance network

### Previous Configuration (Ye Bai Ling)
- **RTSP Cameras**: Currently testing with 1 camera (camera_35)
- **Resolution**: 2592x1944 (5MP)
- **Sub-stream Protocol**: Always uses `/102` endpoints for stability
- **RTSP Connections**: Direct streaming via `rtsp://` protocol
- **Production Deployment**: Testing at Ye Bai Ling Hotpot (Mianyang, 1958 District)

## Common Commands

```bash
# Start surveillance system (on Linux machines)
train-model/linux_rtx_screenshot_capture/camera_surveillance_master.sh start

# Test camera connections
python3 sub-stream/web_stream_preview.py

# Run model testing
python3 test-model/[specific_test_script].py

# Detect UNV cameras on network
python3 unv-camera-detection/detect_cameras.py

# Test single RTSP stream
ffplay -rtsp_transport tcp rtsp://admin:123456@192.168.1.3:554/unicast/c1/s0/live

# Test all 30 camera channels
for ch in $(seq 1 30); do
  timeout 3 ffprobe -v quiet "rtsp://admin:123456@192.168.1.3:554/unicast/c${ch}/s0/live" && echo "Channel $ch: Online"
done
```

## Tech Stack

- **Python 3.7+** - Core language
- **YOLO (v8/v10)** - Object detection framework
- **OpenCV** - Video processing
- **Supabase** - Cloud storage for captured data
- **Flask** - Web interfaces for monitoring

## Notes

Each major directory contains its own CLAUDE.md with detailed implementation specifics. This root document provides the high-level business context and folder organization.
Do not write Markdown files on your own if I don't ask you to do that. 