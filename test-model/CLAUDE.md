# CLAUDE.md

## Test Model Overview

Two-stage staff detection testing for restaurant surveillance using YOLOv8 person detection + custom waiter/customer classifier.

## Directory Structure

```
test-model/
├── yolo_human_detection_plus_employee_detection.py.py  # Two-stage detection script
├── test_with_screenshot.py                             # Test script for camera screenshots
├── test_camera_image.jpg                              # Current test image
├── yolov8n.pt                                         # COCO-trained person detector
├── results/                                            # Detection output images
└── CLAUDE.md                                          # This file
```

**Models**:
- Person detection: `yolov8n.pt` (COCO)
- Staff classifier: `../train-model/models/waiter_customer_model/weights/best.pt`
- General YOLO: `../model/yolov8s.pt`

## Common Commands

```bash
# Test with camera screenshot
python3 test_with_screenshot.py

# Run two-stage detection on specific image
python3 yolo_human_detection_plus_employee_detection.py.py --image path/to/image.jpg

# Custom thresholds
python3 yolo_human_detection_plus_employee_detection.py.py --image image.jpg --person_conf 0.4 --staff_conf 0.6
```

## Detection Pipeline

1. **Stage 1**: Detect all persons (conf=0.3, min_size=50px)
2. **Stage 2**: Classify each person as waiter/customer (conf=0.5)

**Visual**: 🟢 Green=Waiter, 🔴 Red=Customer, ⚫ Gray=Unknown

## Performance

- mAP50: 93.3%
- Precision: 84.3%
- Recall: 81.6%