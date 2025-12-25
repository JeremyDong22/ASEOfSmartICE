# Model V4 - One-Step Staff Detection

## Overview
Model V4 implements **one-step staff detection** using YOLO11n, replacing the previous two-stage approach (detect all people → classify as staff/customer) with direct staff detection. This redesign provides dramatic improvements in speed and model size while maintaining accuracy.

## Key Features
- **Model Type**: YOLO11n Detection (NOT classification)
- **Task**: Direct staff detection with bounding boxes
- **Data Source**: Smartice 001 location (30 channels)
- **Camera Resolution**: All 1920×1080 (Full HD)
- **Training Strategy**: Single-stage detection of staff members only
- **Performance Target**: ~2ms inference, 6MB model (vs 61.7ms, 55MB for two-stage)

## Architecture Comparison

### OLD Two-Stage Approach (Model V3)
```
Step 1: YOLOv8m detects all people (customers + staff)
Step 2: Crop person images
Step 3: Classifier determines staff vs customer
Result: 61.7ms inference, 55MB total model size
```

### NEW One-Step Approach (Model V4)
```
Single Step: YOLO11n detects ONLY staff members directly
Result: ~2ms inference, 6MB model size
Improvement: 30x faster, ~9x smaller
```

## Training Strategy

### Label Definition
- **Label ONLY staff members** wearing hats/uniforms
- **DO NOT label customers** or non-staff people
- Use bounding boxes (YOLO detection format)
- Single class: "staff" (class_id = 0)

### Why One-Step Detection?
1. **Speed**: Eliminates crop + classify pipeline overhead
2. **Simplicity**: Single model vs two models
3. **Accuracy**: Direct optimization for staff detection
4. **Deployment**: Smaller model, faster inference
5. **Maintenance**: One model to train/update vs two

## Data Collection Summary

### Smartice 001 Deployment
- **Total Images**: 3,088+ images (growing)
- **Collection Period**: Dec 19-20, 2025 onwards
- **Channels**: 30 channels (channel_1 through channel_30)
- **Resolution**: All 1920×1080 (Full HD)
- **Storage**: Supabase ASE bucket under smartice001/ path

## Training Pipeline

### Step 1: Download Raw Images from Supabase
```bash
cd scripts
python3 1_download_from_supabase.py
```
**Purpose**: Download all Smartice 001 images from Supabase storage
- **Source**: ASE bucket, smartice001/ path
- **Structure**: Downloads to raw_images/channel_X/ folders
- **Expected**: ~3,088+ images (growing as collection continues)
- **Parallel Download**: 20 threads for fast execution

### Step 2: Filter Images with People (NEW)
```bash
python3 2_filter_images_with_people.py
```
**Purpose**: Remove images without any people to reduce labeling workload
- **Method**: Use YOLOv8m to detect people in raw images
- **Action**: DELETE images that have NO people
- **Keep**: Images that have at least 1 person
- **Output**: filtered_images_with_people/ directory
- **Expected**: 30-50% reduction in images to label

### Step 3: Label Staff Bounding Boxes (REDESIGNED)
```bash
python3 3_label_staff_bboxes.py
```
**Purpose**: Manually draw bounding boxes around STAFF ONLY (not customers)
- **Interface**: Web UI at http://localhost:5003
- **Features**:
  - Canvas-based bounding box drawing
  - Click and drag to draw boxes
  - Multiple boxes per image (0, 1, or many staff)
  - SQLite database for label storage
  - Navigation: Previous/Next image
  - Undo last box, Clear all boxes
- **Shortcuts**:
  - Enter = Save & Next
  - U = Undo last box
  - S = Skip (no staff in image)
  - ← = Previous image
- **Output**: SQLite database (labeled_staff_bboxes/labels.db)
- **Important**: Label ONLY staff members wearing hats/uniforms, NOT customers

### Step 4: Prepare Detection Dataset (UPDATED)
```bash
python3 4_prepare_detection_dataset.py
```
**Purpose**: Convert SQLite labels to YOLO detection format
- **Format**: YOLO detection (class_id center_x center_y width height, normalized)
- **Structure**:
  - dataset_detection/images/train/
  - dataset_detection/images/val/
  - dataset_detection/labels/train/
  - dataset_detection/labels/val/
- **Split**: 80/20 train/val
- **Output**: data.yaml with nc: 1, names: ['staff']

### Step 5: Train Staff Detector (UPDATED)
```bash
python3 5_train_staff_detector.py
```
**Purpose**: Train YOLO11n detection model for staff detection

**Training Details:**
- **Model**: yolo11n.pt (Nano - lightweight and fast)
- **Task**: Object detection (not classification)
- **Classes**: 1 class (staff)
- **Device**: MPS (Apple Silicon GPU) with fallback to CPU
- **Epochs**: 100 (early stopping patience=15)
- **Batch Size**: 16
- **Image Size**: 640×640 (YOLO detection standard)
- **Augmentation**: HSV jitter, scale, translation, horizontal flip, mosaic
- **Training Time**: 3-5 hours on M4 MacBook
- **Output**: models_detection/staff_detector.pt

## Directory Structure
```
model_v4/
├── scripts/                   # Training pipeline (5 steps)
│   ├── 1_download_from_supabase.py      # ✅ Download Smartice 001 images
│   ├── 2_filter_images_with_people.py   # ✅ NEW: Filter images with people
│   ├── 3_label_staff_bboxes.py          # ✅ REDESIGNED: Web bbox labeling
│   ├── 4_prepare_detection_dataset.py   # ✅ UPDATED: Detection format
│   └── 5_train_staff_detector.py        # ✅ UPDATED: Train YOLO11n detector
├── raw_images/                # Smartice 001 raw images
│   ├── channel_1/
│   ├── channel_2/
│   └── ... (30 channels total)
├── filtered_images_with_people/ # Images containing people (after filtering)
├── labeled_staff_bboxes/      # Bounding box labels
│   └── labels.db              # SQLite database with bbox coordinates
├── dataset_detection/         # YOLO detection format
│   ├── images/
│   │   ├── train/
│   │   └── val/
│   ├── labels/
│   │   ├── train/             # YOLO format: class_id cx cy w h
│   │   └── val/
│   └── data.yaml              # YOLO detection config
└── models_detection/          # Trained YOLO11n detection model
    └── staff_detector.pt      # Final model
```

## Training Configuration (YOLO11n Detection)

- **Model**: YOLO11n (Nano - smallest YOLO variant)
- **Device**: MPS (Apple Silicon GPU) / fallback to CPU
- **Optimizer**: SGD with momentum=0.937
- **Learning Rate**: 0.01 → 0.01 (constant for detection)
- **Epochs**: 100 (early stopping patience=15)
- **Batch Size**: 16 (optimal for M4)
- **Image Size**: 640×640 (YOLO detection standard)
- **Workers**: 8 (utilize M4 cores)

### Data Augmentation Strategy
- **Color**: HSV jitter (hue=0.015, sat=0.7, val=0.4)
- **Geometric**: Scale 0.5-1.5x, translation 10%
- **Flip**: Horizontal flip 50%
- **Mosaic**: Enabled (disabled in last 10 epochs)
- **Advanced**: No mixup, no copy-paste

## Model Usage

### Inference Example
```python
from ultralytics import YOLO

# Load trained staff detector
model = YOLO('models_detection/staff_detector.pt')

# Detect staff in restaurant image
results = model('restaurant_image.jpg')

# Process results
for r in results:
    boxes = r.boxes  # Bounding boxes for staff members
    for box in boxes:
        # Get coordinates
        x1, y1, x2, y2 = box.xyxy[0]  # Top-left and bottom-right
        confidence = box.conf[0]      # Confidence score
        class_id = box.cls[0]         # Class ID (0 = staff)

        print(f"Staff detected at ({x1}, {y1}, {x2}, {y2}) with confidence {confidence:.2f}")
```

## Performance Comparison

| Metric | Two-Stage (V3) | One-Step (V4) | Improvement |
|--------|----------------|---------------|-------------|
| Inference Time | ~61.7ms | ~2ms | 30x faster |
| Model Size | ~55MB | ~6MB | 9x smaller |
| Complexity | 2 models | 1 model | Simpler |
| Maintenance | High | Low | Easier |

## Deployment Strategy

### Testing Phase
1. Evaluate V4 on held-out test set
2. Compare detection accuracy with V3 classification
3. Measure inference speed on production hardware
4. Validate on diverse restaurant scenarios

### Production Rollout
1. A/B testing: V3 vs V4 side-by-side
2. Monitor detection accuracy and false positives
3. Gradual rollout to all Smartice locations
4. Collect edge cases for continuous improvement

### Continuous Improvement
1. Collect false positives/negatives from production
2. Label new edge cases
3. Periodic retraining (V4.1, V4.2, etc.)
4. Monitor mAP metrics over time

## Expected Results

### Accuracy Targets
- **mAP@0.5**: > 0.85 (85% detection accuracy at IoU=0.5)
- **mAP@0.5:0.95**: > 0.70 (70% across IoU thresholds)
- **Precision**: > 0.90 (low false positives)
- **Recall**: > 0.85 (catch most staff members)

### Edge Cases to Handle
- Staff without hats (if applicable)
- Partially occluded staff members
- Staff in non-standard poses
- Varying lighting conditions
- Crowded scenes with many people

## Next Steps After Training

1. **Validate Model**: Test on held-out Smartice 001 data
2. **Benchmark Speed**: Measure actual inference time on target hardware
3. **Compare with V3**: Quantitative accuracy comparison
4. **Analyze Errors**: Identify false positives and false negatives
5. **Production Testing**: Deploy to Smartice 001 for live validation
6. **Iterate**: Collect failure cases, label, and retrain

## Key Advantages

### 1. Simplified Pipeline
- **Old**: Detect → Crop → Classify (3 steps)
- **New**: Detect staff directly (1 step)

### 2. Faster Inference
- **Old**: 61.7ms per image
- **New**: ~2ms per image (30x speedup)

### 3. Smaller Model
- **Old**: 55MB total (detector + classifier)
- **New**: 6MB single model (9x smaller)

### 4. Better for Deployment
- Lower memory footprint
- Faster processing for real-time applications
- Easier to deploy on edge devices
- Single model to version/update

### 5. Direct Optimization
- Model learns staff-specific features directly
- No information loss from cropping
- Context-aware detection (uniform, surroundings)

## Notes

- **Critical**: Label ONLY staff members (people with hats/uniforms)
- **Do NOT**: Label customers or non-staff people
- **Web Tool**: Canvas-based labeling is intuitive and fast
- **Database**: SQLite provides reliable label storage with easy export
- **Format**: YOLO detection format (normalized coordinates)
- **Multi-boxing**: Support 0, 1, or many staff per image

## Troubleshooting

### If images aren't filtering correctly:
- Check MIN_PERSON_SIZE in 2_filter_images_with_people.py
- Adjust CONFIDENCE_THRESHOLD if needed
- Review rejected images to verify accuracy

### If labeling tool won't start:
- Ensure filtered_images_with_people/ exists
- Check port 5003 is available
- Verify Flask is installed

### If training fails:
- Check dataset_detection/ structure
- Verify data.yaml paths are correct
- Ensure labels are in YOLO format (normalized 0-1)
- Check GPU/MPS availability

### If model accuracy is low:
- Label more diverse training data
- Check for labeling errors (customers labeled as staff)
- Increase training epochs
- Try YOLO11s (small) instead of YOLO11n (nano)

## Version History

- **V1**: Initial employee/customer classifier (basic)
- **V2**: Improved architecture and training (retired)
- **V3**: YOLOv11-cls two-stage (detect + classify), 90-95% accuracy, production
- **V4**: YOLO11n one-step detection, 30x faster, 9x smaller, simplified pipeline

## References

- **YOLO11 Docs**: https://docs.ultralytics.com/models/yolo11/
- **Detection Training**: https://docs.ultralytics.com/modes/train/
- **Detection Format**: https://docs.ultralytics.com/datasets/detect/
