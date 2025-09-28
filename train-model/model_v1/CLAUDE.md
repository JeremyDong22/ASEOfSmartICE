# Model V1 - Employee/Customer Classifier

## Overview
First version of the waiter/customer classification model based on YOLOv8. This model performs two-stage detection:
1. Detect all persons in the frame
2. Classify each person as employee (waiter) or customer

## Training Pipeline

### Step 1: Capture Screenshots
```bash
cd scripts
python3 1_capture_screenshots.py
```
- Captures from 8 restaurant cameras every 5 minutes
- Saves to `raw_images/` folder
- Runs for 2 hours (configurable)

### Step 2: Extract Persons
```bash
python3 2_extract_persons.py
```
- Uses YOLOv8 to detect people in screenshots
- Crops person bounding boxes
- Saves to `extracted-persons/camera_XX/`
- Filters small detections (<50px)

### Step 3: Label Images
```bash
python3 3_label_images.py
```
- Interactive GUI for manual labeling
- Categories: waiter, customer, skip
- Saves to `labeled-persons/waiters/` and `labeled-persons/customers/`

### Step 4: Prepare Dataset
```bash
python3 4_prepare_dataset.py
```
- Creates YOLO training format
- 80/20 train/validation split
- Generates `dataset/` structure

### Step 5: Train Model
```bash
python3 5_train_model.py
```
- Fine-tunes YOLOv8n on labeled data
- Outputs to `models/waiter_customer_model/`
- Training for 50 epochs

## Directory Structure
```
model_v1/
├── scripts/              # Training pipeline scripts (1-5)
├── raw_images/          # Camera screenshots
├── extracted-persons/   # Detected person crops
├── labeled-persons/     # Manually labeled data
│   ├── waiters/        # Employee images
│   └── customers/      # Customer images
├── dataset/            # YOLO training format
│   ├── images/
│   └── labels/
├── models/             # Trained model output
└── configs/            # Training configurations
```

## Model Performance
- **mAP50**: 93.3%
- **Precision**: 84.3%
- **Recall**: 81.6%
- **Classes**: 2 (waiter, customer)

## Usage
```python
from ultralytics import YOLO

# Load model
model = YOLO('models/waiter_customer_model/weights/best.pt')

# Inference
results = model('path/to/image.jpg')
```