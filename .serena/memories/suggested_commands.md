# ASEOfSmartICE - Suggested Commands

## Running Core Scripts

### ONVIF Testing and Discovery
```bash
# Run connection methods summary report
python3 test/connection_methods_summary.py

# Note: Additional ONVIF scripts were created during testing but cleaned up
# Main functionality preserved in connection_methods_summary.py
```

### Web Stream Preview
```bash
# Start Flask web interface for camera sub-stream
python3 sub-stream/web_stream_preview.py

# Access web interface at: http://localhost:5001
```

## Development and Testing

### Python Environment
```bash
# No virtual environment configured - run directly with system Python
python3 --version  # Verify Python 3 is available

# Install dependencies manually if needed:
# pip3 install flask opencv-python numpy requests
```

### Camera Testing
```bash
# Test RTSP streams with FFmpeg (if available)
ffprobe -v quiet -show_streams rtsp://admin:a12345678@202.168.40.37:554/Streaming/Channels/102

# Test camera web interfaces in browser
open http://202.168.40.37
open http://202.168.40.21
```

### File Management
```bash
# List project structure
ls -la
tree  # If available

# Check model files
ls -la model/
```

## Network and Camera Operations

### Port Scanning (Manual)
```bash
# Test camera connectivity
ping 202.168.40.37
telnet 202.168.40.37 554  # Test RTSP port
telnet 202.168.40.37 80   # Test HTTP port
```

### System Requirements
```bash
# Check OpenCV installation
python3 -c "import cv2; print(cv2.__version__)"

# Check FFmpeg availability (required for RTSP)
ffmpeg -version
```

## Project Maintenance

### Cleaning
```bash
# Remove test files (as done during development)
rm test/onvif_discovery_test.py  # Example cleanup
```

### Backup Model Files
```bash
# YOLO models are large - backup if needed
cp model/*.pt /backup/location/
```