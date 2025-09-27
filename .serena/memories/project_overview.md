# ASEOfSmartICE Project Overview

## Purpose
ASEOfSmartICE (ONVIF protocol integration and H.265/H.264 stream analysis) is a minimal camera surveillance project focused on IP camera connectivity and stream analysis.

## Project Status
This appears to be an experimental/testing project with very limited codebase:
- Only 2 Python files in the main project
- Focused on ONVIF protocol testing and camera stream preview
- Contains YOLO model files for potential object detection

## Core Functionality
1. **ONVIF Protocol Testing** - Scripts to test ONVIF connectivity for IP cameras
2. **Web Stream Preview** - Flask-based web interface for camera sub-stream viewing
3. **Camera Connection Analysis** - Network discovery and connection method testing

## Key Components
- `test/connection_methods_summary.py` - ONVIF discovery and connection testing
- `sub-stream/web_stream_preview.py` - Flask web interface for camera streaming
- `model/` - YOLO model files (yolov8s.pt, yolov10s.pt)
- `onvif_profiles_raw.xml` - Raw ONVIF profile configuration data

## Target Hardware
- IP Cameras with RTSP support
- Tested with cameras at IP addresses: 202.168.40.37, 202.168.40.21
- Port 554 for RTSP, ports 80/8080/8000 for web interfaces