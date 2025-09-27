# 🎯 Restaurant Staff Detection Training Pipeline

Train a custom YOLO model to detect waiters vs customers using multi-camera screenshot data!

## 📁 Folder Structure
```
train-model/
├── raw_images/          # Screenshots from 8 cameras (NEW)
├── extracted-persons/   # Extracted person images
│   ├── camera_27/      # High-res camera persons
│   ├── camera_28/      # High-res camera persons  
│   ├── camera_36/      # Medium-res camera persons
│   └── ...             # Other cameras
├── labeled-persons/     # Manually labeled training data
├── dataset/            # YOLO format dataset
│   ├── images/
│   │   ├── train/      # Training images
│   │   └── val/        # Validation images
│   └── labels/
│       ├── train/      # Training labels
│       └── val/        # Validation labels
├── models/             # Trained models
├── scripts/            # Training pipeline scripts
├── configs/            # Configuration files
└── videos/             # Legacy (deprecated)
```

## 🚀 Training Pipeline (Updated for Multi-Camera Screenshots)

### Step 1: Capture Screenshots from Multiple Cameras
```bash
cd train-model/scripts
python3 1_capture_screenshots.py
```
- **NEW**: Captures from 8 verified cameras every 5 minutes
- High-resolution sources: cameras 27, 28 (2592x1944)
- Medium-resolution sources: cameras 36, 35, 22 (1920x1080) 
- Low-resolution sources: cameras 24, 26, 29 (640x360)
- Saves to `raw_images/` with camera ID and timestamp
- Parallel capture using threading for efficiency

### Step 2: Extract All Persons from Screenshots
```bash
python3 2_extract_persons.py
```
- **UPDATED**: Processes images from `raw_images/` instead of videos
- Uses YOLOv8s to detect all persons in screenshots
- Organizes by camera source: `extracted-persons/camera_XX/`
- Filters minimum person size (50x50 pixels)

### Step 3: Manual Image Labeling
```bash
python3 3_label_images.py
```
- Interactive labeling interface for extracted persons
- Categories: 'waiter', 'customer', 'skip'
- Saves labeled data to `labeled-persons/`

### Step 4: Prepare Dataset
```bash
python3 4_prepare_dataset.py
```
- Creates YOLO training format from labeled data
- Creates 80/20 train/val split
- Generates dataset configuration

### Step 5: Train Model
```bash
python3 5_train_model.py
```
- Fine-tunes YOLOv8s on person classification
- Trains on MacBook (CPU or Apple Silicon MPS)
- Takes ~1-2 hours for 50 epochs
- Saves best model to `models/waiter_customer_final.pt`

## 💻 MacBook Performance

### Apple Silicon (M1/M2)
- ✅ Uses MPS (Metal Performance Shaders) GPU
- Training time: ~1 hour
- Batch size: 8-16

### Intel MacBook
- ⚠️ CPU-only training
- Training time: ~2-3 hours
- Batch size: 4-8
- Tip: Use Google Colab for faster training

## 📊 Expected Results

With multi-camera screenshot data (1000-2000 person images):
- mAP50: ~0.85-0.92
- Waiter detection: ~90% accuracy
- Customer detection: ~85% accuracy
- Data diversity: 8 different camera angles and resolutions
- Efficiency: 5-minute intervals provide good temporal coverage

## 🔧 Requirements

```bash
pip3 install ultralytics opencv-python scikit-learn
```

## 🎯 Using Trained Model

```python
from ultralytics import YOLO

# Load your custom model
model = YOLO('train-model/models/waiter_customer_final.pt')

# Detect in image
results = model('camera_frame.jpg')

# Process results
for r in results:
    boxes = r.boxes
    for box in boxes:
        cls = int(box.cls[0])
        conf = float(box.conf[0])
        label = 'waiter' if cls == 0 else 'customer'
        print(f"Detected {label} with {conf:.2f} confidence")
```

## 💡 Tips for Better Results

1. **Screenshot Capture**
   - Run during busy restaurant hours for diverse data
   - Ensure all 8 cameras are properly connected
   - Monitor storage space (1.7MB per image × 8 cameras × 12 captures/hour)
   - Use high/medium resolution cameras for best person detection

2. **Person Extraction**
   - Verify YOLO model is properly installed (`pip3 install ultralytics`)
   - Check extracted-persons folders for balanced camera coverage
   - Remove low-quality detections manually if needed

3. **Labeling**
   - Be consistent with waiter uniform identification
   - Include partial views and different poses
   - Balance waiter/customer samples across camera sources
   - Use camera context to help with ambiguous cases

4. **Training**
   - Start with 50 epochs using multi-camera data
   - Monitor validation loss across different camera resolutions
   - Use data augmentation for better generalization
   - Consider camera-specific training if performance varies

5. **Multi-Camera Optimization**
   - Prioritize high-resolution cameras (27, 28) for training
   - Use medium-resolution cameras (36, 35, 22) for validation
   - Low-resolution cameras (24, 26, 29) provide additional diversity
   - Test model performance on each camera resolution separately