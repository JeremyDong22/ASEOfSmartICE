# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ASEOfSmartICE is an ONVIF protocol integration and H.265/H.264 stream analysis project for IP surveillance cameras. This minimal experimental project focuses on camera connectivity testing, ONVIF protocol analysis, and real-time stream preview capabilities.

## Core Architecture

### Components Structure
- **`test/`** - ONVIF discovery and connection testing utilities
- **`sub-stream/`** - Flask-based web interface for camera stream preview
- **`model/`** - YOLO object detection models (YOLOv8s, YOLOv10s)
- **`onvif_profiles_raw.xml`** - Raw ONVIF profile configuration data

### Key Functionality
1. **ONVIF Protocol Testing** - Network discovery and compatibility testing for IP cameras
2. **Web Stream Preview** - Real-time RTSP stream viewing via Flask web interface  
3. **Camera Connection Analysis** - Multi-protocol connectivity assessment

## Tech Stack

### Core Dependencies
- **Python 3.7+** - Primary development language
- **Flask** - Web framework for stream preview interface
- **OpenCV (cv2)** - Video capture and RTSP stream processing
- **NumPy** - Array operations for image processing
- **requests** - HTTP/SOAP communication for ONVIF testing

### System Requirements  
- **FFmpeg** - Required by OpenCV for RTSP stream compatibility
- Network access to target IP cameras (202.168.40.37, 202.168.40.21)

## Common Commands

### Core Operations
```bash
# Generate ONVIF connection analysis report
python3 test/connection_methods_summary.py

# Start web-based camera stream preview
python3 sub-stream/web_stream_preview.py
# Access at: http://localhost:5001
```

### Development and Testing
```bash
# Verify Python environment
python3 --version

# Test camera RTSP connectivity
ffprobe -v quiet -show_streams rtsp://admin:a12345678@IP:554/Streaming/Channels/102

# Manual camera web interface access
open http://202.168.40.37
open http://202.168.40.21
```

### Network Diagnostics
```bash
# Basic connectivity testing
ping 202.168.40.37
telnet 202.168.40.37 554  # RTSP port
telnet 202.168.40.37 80   # HTTP port
```

## Code Conventions

### File Organization
- Descriptive snake_case filenames indicating clear functionality
- Version headers with purpose documentation in all Python files
- Feature-based directory structure for logical separation

### Python Style
- **snake_case** for variables, functions, and filenames
- **UPPER_CASE** for configuration constants (IPs, URLs, passwords)
- **Descriptive naming** that clearly indicates purpose and scope
- **Emoji-enhanced logging** for visual clarity (🎥, ✅, ❌, 🔍)

### Error Handling Pattern
```python
try:
    # Network/camera operation with explicit timeout
    operation(timeout=5)
except SpecificException:
    print("❌ Specific error description")
except Exception as e:
    print(f"❌ General error: {e}")
```

### Threading and Concurrency
- Global variables with threading locks for frame sharing
- Daemon threads for background video capture
- Graceful shutdown handling for network connections

## Camera Configuration

### Verified Working Cameras (8/9 tested)

#### High Resolution Cameras (2592x1944)
- **202.168.40.27**: admin/a12345678 @ 20 FPS
  - RTSP: `rtsp://admin:a12345678@202.168.40.27:554/Streaming/Channels/102`
- **202.168.40.28**: admin/123456 @ 20 FPS  
  - RTSP: `rtsp://admin:123456@202.168.40.28:554/Streaming/Channels/102`

#### Medium Resolution Cameras (1920x1080)
- **202.168.40.36**: admin/123456 @ 20 FPS
- **202.168.40.35**: admin/123456 @ 20 FPS
- **202.168.40.22**: admin/123456 @ 20 FPS

#### Low Resolution Cameras (640x360)
- **202.168.40.24**: admin/a12345678 @ 25 FPS
- **202.168.40.26**: admin/a12345678 @ 25 FPS
- **202.168.40.29**: admin/a12345678 @ 25 FPS

### Authentication Patterns
- **Password 123456**: Works for IPs ending in 28, 36, 35, 22
- **Password a12345678**: Works for IPs ending in 27, 24, 26, 29
- **Failed**: 202.168.40.34 (no response to either password)

### Stream Endpoints
- **Sub-stream (recommended)**: `/Streaming/Channels/102` - Better stability, validated on all cameras
- **Main stream**: `/Streaming/Channels/101` - Higher resolution (not tested)
- **RTSP Port**: 554 (confirmed working on all cameras)
- **Username**: admin (consistent across all cameras)

## Development Notes

### Project Status
This is a minimal experimental codebase focused on ONVIF protocol analysis and camera stream testing. The project contains core functionality for camera connectivity assessment but lacks comprehensive dependency management (no requirements.txt or virtual environment).

### Installation Dependencies
Manual installation required for core libraries:
```bash
pip3 install flask opencv-python numpy requests
```

### ONVIF Protocol Support
Current testing indicates target cameras may not fully support standard ONVIF protocols, requiring fallback to direct RTSP connections for reliable streaming functionality.