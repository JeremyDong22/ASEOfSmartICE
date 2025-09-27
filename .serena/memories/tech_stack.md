# ASEOfSmartICE Tech Stack

## Programming Language
- **Python 3** - Primary language for all scripts

## Core Dependencies
Based on code analysis, the project uses:

### Web Framework
- **Flask** - For web stream preview interface (`sub-stream/web_stream_preview.py`)

### Computer Vision & Video Processing
- **OpenCV (cv2)** - For video capture, frame processing, and RTSP stream handling
- **NumPy** - For array operations and image processing

### Network & Protocol Libraries
- **requests** - For HTTP/SOAP requests in ONVIF testing
- **threading** - For concurrent video capture and web serving
- **time** - For timing and delays in stream processing

### Machine Learning
- **YOLO models** - YOLOv8s and YOLOv10s model files present for object detection

## System Requirements
- **FFmpeg** - Required by OpenCV for RTSP stream processing
- **Python 3.7+** - Compatible with modern Python versions
- Network access to IP cameras on local network

## Development Environment
- macOS/Darwin platform (based on system information)
- No virtual environment configuration found
- No requirements.txt or package management files present