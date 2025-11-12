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

- **8 Working Cameras**: Various resolutions (640x360 to 2592x1944)
- **Sub-stream Protocol**: Always uses `/102` endpoints for stability
- **RTSP Connections**: Direct streaming via `rtsp://` protocol

## Common Commands

```bash
# Start surveillance system (on Linux machines)
train-model/linux_rtx_screenshot_capture/camera_surveillance_master.sh start

# Test camera connections
python3 sub-stream/web_stream_preview.py

# Run model testing
python3 test-model/[specific_test_script].py
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