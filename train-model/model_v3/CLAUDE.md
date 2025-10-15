# Model V3 - High-Quality 1080p Training

## Overview
Model V3 focuses exclusively on high-quality 1080p camera data from camera_35 and camera_22. This version uses the same training pipeline as V2 but with superior image quality for better feature recognition.

## Key Differences from V2
- **Camera Selection**: Only camera_35 and camera_22 (1920×1080 resolution)
- **Quality Threshold**: MIN_PERSON_SIZE = 220px (ensures excellent feature clarity)
- **Dataset Strategy**: Randomly sampled 2,000 from 3,972 extracted (for manageable labeling)
- **Data Quality**: Average 300px person crops vs V2's 50-90px from low-res cameras
- **Rationale**: Superior quality over quantity - every image has clear uniform/face details

## Camera Statistics

### camera_35 (1920×1080)
- Total images: 1,730
- Average person size: 171×235 pixels
- Status: Most productive camera

### camera_22 (1920×1080)
- Total images: 1,550
- Average person size: 238×166 pixels
- Status: Largest person crops

## Training Pipeline

### 1. Download Raw Images (COMPLETED)
```bash
cd scripts
python3 1_download_from_supabase.py
```
**Status**: ✅ 3,280 images downloaded from Supabase

### 2. Extract Persons (COMPLETED)
```bash
python3 2_extract_persons.py
```
**Status**: ✅ Extracted and randomly sampled 2,000 high-quality person images
- **Threshold**: MIN_PERSON_SIZE = 220px
- **Initial extraction**: 3,972 persons (avg 300px)
- **Random sampling**: Selected 2,000 for labeling convenience
- **Distribution**: camera_22 (1,111), camera_35 (889)

### 3. Label Images
```bash
python3 3_label_images.py
```
Opens web interface at http://localhost:5002 for manual labeling:
- Keyboard shortcuts: Space (toggle), Enter (save & next), ← (previous)
- Default label: Customer
- Output: labeled-persons/waiters/ and labeled-persons/customers/

### 4. Prepare Dataset
```bash
python3 4_prepare_dataset.py
```
Creates YOLO training format with 80/20 train/val split.

### 5. Train Model
```bash
python3 5_train_model.py
```
Trains custom YOLO model with SGD optimizer on CPU.

## Extraction Results & Quality Metrics

### Actual Extraction (Completed)
- **Initial extraction**: 3,972 high-quality persons (220px threshold)
- **Final dataset**: 2,000 persons (randomly sampled for labeling convenience)
- **Quality metrics**:
  - Average min dimension: 300px
  - Median min dimension: 287px
  - Range: 230px - 563px
  - All images ≥220px threshold ✅

### Expected Training Results
- **Target labeled**: 2,000 total (manageable workload)
- **Training split**: ~1,600 train / ~400 validation (80/20)
- **Model accuracy**: >90% mAP50 (improved from V2 due to superior resolution)
- **Quality advantage**: 3-6x better resolution than V2 (300px vs 50-90px)

## Directory Structure
```
model_v3/
├── scripts/              # Training pipeline
│   ├── 1_download_from_supabase.py  # ✅ Camera-filtered download
│   ├── 2_extract_persons.py
│   ├── 3_label_images.py
│   ├── 4_prepare_dataset.py
│   └── 5_train_model.py
├── raw_images/          # ✅ 3,280 images (camera_35 + camera_22 only)
├── extracted-persons/   # ✅ 2,000 persons (220px threshold, randomly sampled)
├── labeled-persons/     # Empty - for labeled data
│   ├── waiters/
│   └── customers/
├── dataset/            # Empty - for training format
│   ├── images/{train,val}
│   └── labels/{train,val}
├── models/             # Empty - for trained output
└── configs/            # Configuration files
```

## Advantages Over V2

1. **Better Feature Recognition**
   - Uniform colors and logos more visible
   - Facial features clearer
   - Body posture details enhanced

2. **Stable Data Source**
   - Both cameras have consistent 18-day capture history
   - No connection issues (unlike camera_27/28)
   - Balanced coverage from different restaurant areas

3. **Reduced Noise**
   - No low-quality 640×360 data
   - Consistent lighting conditions
   - Fewer false detections

## Next Steps After Training

1. Test model on validation set
2. Compare with V2 performance metrics
3. Deploy best model to production
4. Consider data augmentation if accuracy < 90%

## Training Configuration

- **Optimizer**: SGD (more stable than Adam)
- **Epochs**: 50 with early stopping
- **Batch size**: 6
- **Device**: CPU (MPS disabled for stability)
- **Base model**: YOLOv8n (nano for speed)
