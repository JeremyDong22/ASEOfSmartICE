# Staff Detector V4 - YOLO11n One-Stage Detection Test

## Overview
This folder contains performance testing for the newly trained YOLO11n one-stage staff detection model. This model represents a complete redesign from the previous two-stage approach (detect people → classify), achieving 30x faster inference and 9x smaller model size.

## Model Information

### Model Details
- **Model Type**: YOLO11n Detection (Nano variant)
- **Architecture**: One-stage direct staff detection
- **Model Size**: ~5.4MB (vs 55MB for two-stage approach)
- **Training Data**: 500+ labeled images from Smartice 001 location
- **Classes**: 1 class (staff)
- **Input Size**: 640×640
- **Device**: MPS (Apple Silicon optimized)

### Performance Comparison with Two-Stage (V3)
| Metric | Two-Stage (V3) | One-Stage (V4) | Improvement |
|--------|----------------|----------------|-------------|
| Inference Time | ~61.7ms | ~2ms target | 30x faster |
| Model Size | ~55MB | ~5.4MB | 10x smaller |
| Pipeline | 2 models | 1 model | Simpler |

## Test Files

### Models
- `models/staff_detector.pt` - Trained YOLO11n detection model

### Test Data
- `test_images/` - 5 validation images from training dataset
  - val_00000.jpg through val_00004.jpg
- `test_videos/` - Sample video for FPS testing
  - test_video.mp4

### Results
- `results/images/` - Annotated test images with bounding boxes
- `results/videos/` - Processed videos with detections
- `results/performance_report.txt` - Detailed timing and FPS metrics

## Test Script

### Main Testing Script
`test_staff_detector.py` - Comprehensive performance testing script

**Features:**
- Load and validate YOLO11n model
- Test on individual images with timing
- Process video and measure FPS
- Generate visual outputs with bounding boxes
- Export detailed performance metrics
- MPS (Apple Silicon) acceleration support

**Key Metrics:**
- **Inference Time**: Per-image processing time
- **FPS**: Frames per second for video processing
- **Detection Count**: Number of staff detected per frame
- **Confidence Scores**: Average/min/max confidence values

## Usage

### Run Complete Test Suite
```bash
cd /Users/jeremydong/Desktop/Smartice/APPs/ASEOfSmartICE/test-model/staff_detector_v4_yolo11n
python3 test_staff_detector.py
```

This will:
1. Load the YOLO11n model
2. Test on 5 validation images
3. Process test video and measure FPS
4. Save annotated outputs to results/
5. Generate performance report

### Output Files
After running tests, you'll find:
- `results/images/val_00000_detected.jpg` - Images with staff bounding boxes
- `results/videos/test_video_detected.mp4` - Video with real-time detection
- `results/performance_report.txt` - Complete timing statistics and FPS metrics

## Visual Output

### Bounding Box Colors
- **Green**: Detected staff member (with confidence score)

### Label Format
```
Staff: 95.3%  [confidence percentage]
```

## Expected Performance

### Image Processing
- **Target**: ~2-5ms per image on M4 MacBook with MPS
- **Batch**: 5 images should complete in <50ms total

### Video Processing
- **Target**: >100 FPS on M4 MacBook with MPS
- **Real-time**: Should easily handle 30 FPS live streams

## Model Path
Trained model location: `/Users/jeremydong/Desktop/Smartice/APPs/ASEOfSmartICE/train-model/model_v4/models_detection/staff_detector_yolo11n/weights/best.pt`

Copied to test folder as: `models/staff_detector.pt`

## Notes

- This is a **detection model**, not classification
- Detects staff members directly with bounding boxes
- No need for person cropping or classification step
- Optimized for production deployment
- MPS acceleration provides significant speedup on Apple Silicon

## Next Steps

After reviewing test results:
1. Evaluate detection accuracy on test images
2. Verify FPS meets production requirements (>30 FPS)
3. Compare with two-stage V3 model performance
4. Identify any false positives or missed detections
5. Deploy to production if metrics are satisfactory

## Real-Time Detection Server

### Files
- `realtime_detection_server.py` - Flask-based real-time detection server
- `templates/detection_dashboard.html` - Web dashboard UI

### Features
- Connects to RTSP stream (Channel 18 from SmartICE NVR)
- Runs YOLO11n inference in real-time
- Displays comprehensive metrics via web dashboard
- Auto-reconnect on stream failures

### Stats Displayed
- **Performance**: FPS, inference time, latency grade
- **Detection**: Current count, average per frame, confidence scores
- **Video Quality**: Resolution, stream FPS, estimated bitrate, frame size
- **Health**: Frame drops, drop rate, uptime, thresholds

### Usage
```bash
cd test-model/staff_detector_v4_yolo11n
python3 realtime_detection_server.py

# Open http://localhost:5018 in browser
```

## Version
- **Model Version**: V4.0
- **Test Date**: December 25, 2025
- **Training Date**: December 24, 2025
- **Real-Time Server Added**: December 25, 2025
