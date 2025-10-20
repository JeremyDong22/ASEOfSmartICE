# CLAUDE.md

## Test Model Overview

Staff detection testing for restaurant surveillance. Includes one-stage (direct detection) and two-stage (person detection + classification) approaches using YOLOv8 models trained on different dataset sizes and camera angles.

## Directory Structure

```
test-model/
├── one-stage-detection/                                 # One-stage person detection testing
│   ├── models/
│   │   └── yolov8s.pt                                  # Base YOLO (COCO-trained, person detection)
│   ├── results/                                         # Detection outputs
│   └── yolo_one_stage_detection.py                     # Person detection test script
│
├── two-stage-detection/                                # Two-stage: Standard model (v1.0)
│   ├── models/
│   │   └── yolov8n.pt                                  # COCO person detector
│   ├── results/                                         # Detection outputs
│   ├── yolo_two_stage_sequential.py                    # Sequential detection script
│   └── yolo_two_stage_parallel.py                      # Parallel detection script
│
├── two-stage-detection-advanced/                       # Two-stage: Advanced model (v2.1)
│   ├── models/
│   │   ├── yolov8s.pt                                  # COCO person detector (better than nano)
│   │   └── waiter_customer_advanced.pt                 # Advanced classifier (3000+ images, 6 angles)
│   ├── results/                                         # Detection outputs
│   └── yolo_two_stage_advanced.py                      # Advanced detection script
│
├── two-stage-detection-yolo11-cls/                    # Two-stage: YOLO11 Classification (v3.0) ⭐ NEWEST
│   ├── models/
│   │   ├── yolov8s.pt                                  # COCO person detector
│   │   └── waiter_customer_classifier.pt               # YOLO11n-cls model (1505 images, 1080p quality)
│   ├── results/                                         # Detection outputs
│   └── yolo_two_stage_yolo11_cls.py                   # YOLO11 classification script
│
├── two-stage-detection-plus-area-division/            # Two-stage + ROI filtering
│   ├── models/
│   │   ├── yolov8s.pt                                  # COCO person detector
│   │   └── waiter_customer_advanced.pt                 # Advanced classifier
│   ├── results/                                         # Detection outputs with ROI overlay
│   ├── roi_config.json                                 # Saved ROI polygon coordinates
│   └── yolo_two_stage_roi.py                          # ROI-based detection script
│
├── test_images/                                         # ⭐ Centralized test images folder
│   ├── test_image_one.jpg                              # Original test images
│   ├── test_image_two.jpg
│   ├── test_image_three.jpg
│   ├── test_image_four.jpg
│   ├── test_image_bar_counter_1.jpg
│   ├── test_image_bar_counter_2.jpg
│   ├── camera_22_*.jpg                                 # Images from camera_22 (1080p)
│   └── camera_35_*.jpg                                 # Images from camera_35 (1080p)
│
├── linux_rtx_video_streaming/                          # ⭐ Real-time video streaming scripts
│   └── CLAUDE.md                                        # Video streaming documentation
│
└── CLAUDE.md                                            # This file
```

## Test Images

All test images are now centralized in the `test_images/` folder for easy access across all detection methods:

**Image Sources:**
- **Original test images**: test_image_one.jpg through test_image_four.jpg, plus bar counter images
- **Camera_22 images**: Latest 5 images from camera_22 (1920×1080 resolution)
- **Camera_35 images**: Latest 5 images from camera_35 (1920×1080 resolution)

**Total**: 16 images (6 original + 10 from Supabase)

All detection scripts have been updated to use this centralized folder by default when running in batch mode.

## Linux RTX Video Streaming

The `linux_rtx_video_streaming/` folder contains scripts for real-time video streaming from Linux RTX 3060 machines deployed in restaurants.

**Key Differences from Screenshot Capture:**
- **Location**: `test-model/linux_rtx_video_streaming/` (vs `train-model/linux_rtx_screenshot_capture/`)
- **Purpose**: Real-time model testing and validation (vs training data collection)
- **Cameras**: camera_22 + camera_35 only (vs all 8 cameras)
- **Output**: Live video streams (vs periodic JPG screenshots to Supabase)
- **Schedule**: Continuous on-demand (vs every 5 minutes, 11 AM - 10 PM)

**Target Cameras:**
- **camera_22**: 1920x1080, `rtsp://admin:123456@202.168.40.22:554/Streaming/Channels/102`
- **camera_35**: 1920x1080, `rtsp://admin:123456@202.168.40.35:554/Streaming/Channels/102`

See `linux_rtx_video_streaming/CLAUDE.md` for detailed setup and usage instructions.

**Models**:

### One-Stage Detection (one-stage-detection/)
- Base YOLO person detection: `yolov8s.pt` (COCO-trained)
  - Purpose: Test base YOLO model for person detection accuracy
  - Model: YOLOv8s (small model, better than nano)
  - Detects: People only (no waiter/customer classification)
  - Use case: Evaluate how well base YOLO detects people in restaurant camera footage

### Two-Stage Standard Model (two-stage-detection/)
- Person detection: `yolov8n.pt` (COCO-trained)
- Staff classifier: `../../train-model/models/waiter_customer_model/weights/best.pt`
  - Training data: ~1000 images from single camera angle
  - Performance: mAP50: 93.3%, Precision: 84.3%, Recall: 81.6%

### Two-Stage Advanced Model (two-stage-detection-advanced/) ⭐ Recommended
- Person detection: `yolov8s.pt` (COCO-trained, better than nano)
- Staff classifier: `waiter_customer_advanced.pt`
  - Training data: ~3000 images from 6 different camera angles
  - Performance: **mAP50-95: 99.0%, Precision: 94.1%, Recall: 98.1%**
  - Waiter class: 90.8% precision, 98.3% recall, 98.7% AP50
  - Customer class: 97.3% precision, 97.9% recall, 99.4% AP50
  - Training time: 7.35 hours (47 epochs, early stopped at epoch 37)
  - ✅ **Best for production**: Detects more people with high classification accuracy

### Two-Stage YOLO11 Classification (two-stage-detection-yolo11-cls/) ⭐ NEWEST - v3.0
- Person detection: `yolov8s.pt` (COCO-trained)
- Staff classifier: `waiter_customer_classifier.pt` (YOLO11n-cls)
  - Training data: 1,505 manually labeled images from camera_35 & camera_22 (1920×1080)
  - Performance: **92.38% top-1 accuracy** on validation set
  - Model type: **Classification model** (uses probs API, not boxes API)
  - Average person crop quality: 300px (3-6x better than v2.0)
  - Training: Transfer learning + aggressive augmentation
  - ✅ **Latest model**: Trained on highest quality 1080p footage only

### Two-Stage + Area Division (two-stage-detection-plus-area-division/) - Production Use
- Person detection: `yolov8s.pt` (COCO-trained)
- Staff classifier: `waiter_customer_advanced.pt`
- **ROI Filtering**: Only detects people within defined monitoring areas
- **Use case**: Monitor specific service divisions (Section A, Section B, etc.)
- **Benefits**:
  - Ignore people in irrelevant areas (other sections, kitchen, hallways)
  - Focus detection on specific zones per camera
  - Reduce false positives from non-monitored areas
  - Interactive polygon drawing for custom boundaries
  - One-time setup per camera, reusable for all images from that camera

## Common Commands

### One-Stage Person Detection (Base YOLO Testing)
```bash
# Single image detection
cd test-model/one-stage-detection
python3 yolo_one_stage_detection.py --image ../test_images/test_image_two.jpg

# Batch process all JPG images in test_images
python3 yolo_one_stage_detection.py --batch

# Custom confidence threshold
python3 yolo_one_stage_detection.py --image ../test_images/test.jpg --conf 0.4
```

### Two-Stage Standard Model (v1.0)
```bash
# Single image detection (sequential)
cd test-model/two-stage-detection
python3 yolo_two_stage_sequential.py --image ../test_images/test_image_one.jpg

# Single image detection (parallel/GPU optimized)
python3 yolo_two_stage_parallel.py --image ../test_images/test_image_one.jpg

# Custom thresholds
python3 yolo_two_stage_sequential.py --image ../test_images/test.jpg --person_conf 0.4 --staff_conf 0.6
```

### Two-Stage Advanced Model (v2.1) - Recommended ⭐
```bash
# Single image detection
cd test-model/two-stage-detection-advanced
python3 yolo_two_stage_advanced.py --image ../test_images/test_image_two.jpg

# Batch process all JPG images in test_images directory
python3 yolo_two_stage_advanced.py --batch

# Custom input directory
python3 yolo_two_stage_advanced.py --batch --input_dir /path/to/images

# Custom thresholds
python3 yolo_two_stage_advanced.py --image ../test_images/test.jpg --person_conf 0.4 --staff_conf 0.6
```

### Two-Stage YOLO11 Classification (v3.0) - NEWEST ⭐
```bash
# Single image detection
cd test-model/two-stage-detection-yolo11-cls
python3 yolo_two_stage_yolo11_cls.py --image ../test_images/test_image_two.jpg

# Batch process all JPG images in test_images directory
python3 yolo_two_stage_yolo11_cls.py --batch

# Custom input directory
python3 yolo_two_stage_yolo11_cls.py --batch --input_dir /path/to/images

# Custom thresholds
python3 yolo_two_stage_yolo11_cls.py --image ../test_images/test.jpg --person_conf 0.4 --staff_conf 0.6
```

### Two-Stage + Area Division (ROI Filtering) ⭐
```bash
cd test-model/two-stage-detection-plus-area-division

# Simple one-step workflow - just run!
python3 yolo_two_stage_roi.py

# What happens automatically:
# 1. Interactive window opens with first image from ../test_images/
# 2. Click to draw polygon around monitoring area
# 3. Cmd+Z / Ctrl+Z to undo last point if needed
# 4. Cmd+S / Ctrl+S to save when done (minimum 3 points)
# 5. Script automatically processes ALL images in ../test_images/
# 6. Results saved to results/ folder

# Keyboard shortcuts:
# - Cmd+Z / Ctrl+Z: Undo last point
# - Cmd+S / Ctrl+S: Complete and save ROI
# - 'r': Reset all points and start over
# - 'q': Quit without saving

# Note: Uses centralized test_images folder from parent directory
```

## Detection Pipeline

### One-Stage Approach (Base YOLO Testing)
1. **Person Detection**: Detect all persons using base YOLOv8s model (conf=0.3)
   - Uses COCO-trained yolov8s.pt model
   - Only detects people (no classification)
   - For testing base YOLO accuracy on restaurant footage

### Two-Stage Approach (Recommended for Production)
1. **Stage 1**: Detect all persons using COCO-trained YOLO (conf=0.3, min_size=40px)
2. **Stage 2**: Classify each detected person as waiter/customer (conf=0.5)

### Two-Stage + ROI Filtering (Production - Service Division Monitoring)
1. **Step 0**: Define monitoring area (polygon ROI) - one-time setup
2. **Stage 1**: Detect all persons using YOLOv8s (conf=0.3, min_size=40px)
3. **ROI Filter**: Keep only persons with center point inside ROI polygon
4. **Stage 2**: Classify filtered persons as waiter/customer (conf=0.5)

**Visual**:
- One-stage: 🟢 Green=Person
- Two-stage: 🟢 Green=Waiter, 🔴 Red=Customer, ⚫ Gray=Unknown
- Two-stage + ROI: 🟢 Green=Waiter, 🔴 Red=Customer, 🔵 Cyan=ROI boundary

## One-Stage vs Two-Stage Comparison

### Purpose Comparison

**One-Stage (Base YOLO Testing):**
- 🔍 **Purpose**: Test and evaluate base YOLO person detection accuracy
- ✅ Uses YOLOv8s (better than nano)
- ✅ Only detects people (no classification)
- ✅ Good for understanding base YOLO performance on your camera footage
- 📊 **Best for**: Testing and benchmarking person detection capabilities

**Two-Stage (Production System):**
- 🎯 **Purpose**: Production-ready staff detection and classification
- ✅ Stage 1: Detect all people (YOLO)
- ✅ Stage 2: Classify as waiter/customer (custom trained model)
- ✅ Provides actionable staff vs customer information
- 📊 **Best for**: Production surveillance where you need to distinguish staff from customers

## Performance Comparison

### Standard Model (v1.0)
- Training: ~1000 images, single camera angle
- mAP50: 93.3%
- Precision: 84.3%
- Recall: 81.6%

### Advanced Model (v2.0) ⭐ Production-Ready
- Training: ~3000 images, 6 camera angles
- **mAP50-95: 99.0%**
- **Precision: 94.1%**
- **Recall: 98.1%**
- Waiter detection: 98.7% AP50
- Customer detection: 99.4% AP50

### YOLO11 Classification Model (v3.0) ⭐ NEWEST - 1080p Quality
- Training: 1,505 images, 2 cameras (1920×1080 resolution only)
- **Top-1 Accuracy: 92.38%** (validation set)
- **Average crop quality**: 300px (3-6x better than v2.0)
- Model type: YOLO11n-cls (classification, not detection)
- Camera sources: camera_35 & camera_22 (highest quality cameras)

## Model Selection Guide

### Approach Selection

**Use One-Stage (Base YOLO Testing)** when:
- Testing base YOLO person detection accuracy
- Benchmarking detection performance on your camera footage
- Evaluating if you need a better person detector
- Not concerned with waiter/customer classification yet

**Use Two-Stage Advanced (Recommended for Production)** when:
- Need to detect ALL people in the scene
- Need to classify people as waiter/customer
- Production surveillance deployment
- Maximum detection coverage is critical

**Use Two-Stage + ROI Filtering (Best for Multi-Division Restaurants)** when:
- Camera covers multiple service divisions (Section A, B, C, etc.)
- Need to monitor specific zones only
- Want to reduce false positives from irrelevant areas
- Each camera monitors different divisions with distinct boundaries
- Same camera setup across multiple images (fixed position/resolution)

### Model Version Selection

**Use YOLO11 Classification Model (v3.0) - NEWEST** when:
- Using 1080p cameras (camera_35, camera_22)
- Need highest quality person crops (300px average)
- Want latest YOLO11 architecture with classification
- Deploying to production with high-resolution footage
- Prefer classification accuracy over detection mAP metrics

**Use Advanced Model (v2.0)** when:
- Deploying to production environments
- Need highest accuracy (99% mAP)
- Working with multiple camera angles
- Require robust performance across different viewing angles
- Using mixed resolution cameras

**Use Standard Model (v1.0)** when:
- Testing basic functionality
- Limited to single camera angle
- Experimenting with detection parameters

## Key Features

### Advanced Model Benefits
✅ **Multi-angle training**: Trained on 6 different camera perspectives
✅ **Large dataset**: 3000+ labeled images vs 1000 images
✅ **Production-ready**: 99% accuracy validated
✅ **Batch processing**: Can process multiple images automatically
✅ **Robust classification**: Minimal confusion between waiter/customer (4-6%)
✅ **High recall**: 98% detection rate ensures minimal missed detections