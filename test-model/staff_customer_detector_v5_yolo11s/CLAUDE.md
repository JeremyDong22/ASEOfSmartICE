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

## Version
- **Model Version**: V5.0
- **Test Date**: December 26, 2025
- **Training Date**: December 26, 2025
