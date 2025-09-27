# Train Model CLAUDE.md

This file provides guidance for Claude Code when working with the model training pipeline in this directory.

## Training Pipeline Overview

The ASEOfSmartICE training pipeline has been refactored from video-based to image-based data collection for improved efficiency and storage management.

### Pipeline Architecture

1. **Screenshot Capture** (`1_capture_screenshots.py`) - Multi-camera image collection every 5 minutes
2. **Person Extraction** (`2_extract_persons.py`) - YOLO-based person detection from screenshots
3. **Image Labeling** (`3_label_images.py`) - Manual labeling as 'waiter' or 'customer'
4. **Dataset Preparation** (`4_prepare_dataset.py`) - Training dataset creation
5. **Model Training** (`5_train_model.py`) - YOLO fine-tuning for person classification

## Directory Structure

```
train-model/
├── CLAUDE.md                    # This file
├── README.md                    # User documentation
├── raw_images/                  # Screenshot captures from cameras
├── extracted-persons/           # Detected persons from screenshots
│   ├── camera_27/              # High-res camera persons
│   ├── camera_28/              # High-res camera persons
│   ├── camera_36/              # Medium-res camera persons
│   └── ...                     # Other cameras
├── labeled-persons/             # Manually labeled training data
├── dataset/                     # Prepared training dataset
├── models/                      # Trained model outputs
├── videos/                      # Legacy (deprecated)
├── configs/                     # Training configuration files
└── scripts/                     # Training pipeline scripts
    ├── 1_capture_screenshots.py    # NEW: Multi-camera screenshot capture
    ├── 2_extract_persons.py        # UPDATED: Process images instead of videos
    ├── 3_label_images.py          # Manual labeling interface
    ├── 4_prepare_dataset.py       # Dataset preparation
    └── 5_train_model.py           # Model training
```

## Key Changes from Video-Based Pipeline

### Before (Video-Based)
- Recorded 10-minute videos from single camera
- Processed every 5 seconds from video files
- Large storage requirements (GB per video)
- Single camera source

### After (Image-Based)
- Captures screenshots every 5 minutes from 8 cameras
- Direct processing of captured images
- Efficient storage (MB per image)
- Multi-camera data collection

## Camera Configuration

### Verified Working Cameras (8/9 tested)

#### High Resolution Sources (2592x1944)
- **camera_27**: `rtsp://admin:a12345678@202.168.40.27:554/Streaming/Channels/102`
- **camera_28**: `rtsp://admin:123456@202.168.40.28:554/Streaming/Channels/102`

#### Medium Resolution Sources (1920x1080)
- **camera_36**: `rtsp://admin:123456@202.168.40.36:554/Streaming/Channels/102`
- **camera_35**: `rtsp://admin:123456@202.168.40.35:554/Streaming/Channels/102`
- **camera_22**: `rtsp://admin:123456@202.168.40.22:554/Streaming/Channels/102`

#### Low Resolution Sources (640x360)
- **camera_24**: `rtsp://admin:a12345678@202.168.40.24:554/Streaming/Channels/102`
- **camera_26**: `rtsp://admin:a12345678@202.168.40.26:554/Streaming/Channels/102`
- **camera_29**: `rtsp://admin:a12345678@202.168.40.29:554/Streaming/Channels/102`

## Running the Pipeline

### Step 1: Screenshot Capture
```bash
cd train-model/scripts
python3 1_capture_screenshots.py
```
- Captures from all 8 working cameras every 5 minutes
- Saves to `../raw_images/` with timestamp and camera info
- Auto-terminates after 2 hours (configurable)
- Parallel capture using threading for efficiency

### Step 2: Person Extraction
```bash
cd train-model/scripts
python3 2_extract_persons.py
```
- Processes all images in `../raw_images/`
- Uses YOLOv8s for person detection (confidence >= 0.5)
- Organizes by camera: `../extracted-persons/camera_XX/`
- Filters minimum person size (50x50 pixels)

### Step 3: Manual Labeling
```bash
cd train-model/scripts
python3 3_label_images.py
```
- Interactive labeling interface for extracted persons
- Categories: 'waiter', 'customer', 'skip'
- Saves labeled data to `../labeled-persons/`

### Step 4: Dataset Preparation
```bash
cd train-model/scripts
python3 4_prepare_dataset.py
```
- Creates YOLO training format from labeled data
- Splits into train/validation sets
- Generates dataset configuration

### Step 5: Model Training
```bash
cd train-model/scripts
python3 5_train_model.py
```
- Fine-tunes YOLOv8s on person classification
- Saves trained model to `../models/`

## Dependencies

### Required Python Packages
```bash
pip3 install ultralytics opencv-python numpy requests flask
```

### System Requirements
- **FFmpeg**: Required for RTSP stream processing
- **Python 3.7+**: Core runtime
- **CUDA/MPS**: Optional for GPU acceleration during training

## Code Conventions

### File Naming
- Screenshots: `camera_{camera_id}_{resolution}_{timestamp}.jpg`
- Extracted persons: `person_{image_name}_{person_index}_{confidence}_{timestamp}.jpg`
- Organized by camera source for easy identification

### Error Handling
- Connection timeouts (5 seconds)
- Retry mechanisms (3 attempts)
- Graceful degradation if cameras fail
- Comprehensive logging with emoji indicators

### Threading and Concurrency
- Parallel camera capture for efficiency
- Background processing with timeout handling
- Thread-safe file operations

## Troubleshooting

### Common Issues

1. **Camera Connection Failures**
   - Check network connectivity: `ping 202.168.40.XX`
   - Verify RTSP port access: `telnet 202.168.40.XX 554`
   - Confirm credentials in camera config

2. **YOLO Import Errors**
   - Install ultralytics: `pip3 install ultralytics`
   - Check Python environment conflicts
   - Use virtual environment if needed

3. **Storage Issues**
   - Monitor `raw_images/` disk usage
   - Clean up old captures periodically
   - Adjust capture frequency if needed

### Performance Optimization

- **High-resolution cameras**: Best quality, larger files
- **Medium-resolution cameras**: Balanced quality/storage
- **Low-resolution cameras**: Fast processing, smaller storage

## Testing

### Functionality Verification
```bash
cd test
python3 simple_functionality_test.py
```
- Tests camera connections (2 min timeout)
- Verifies screenshot capture
- Validates person extraction
- Comprehensive end-to-end pipeline test

### Expected Results
- ✅ Camera connections: 8/9 cameras working
- ✅ Screenshot capture: ~1.7MB per image
- ✅ Person extraction: Variable based on scene content

## Migration Notes

### From Video Pipeline
1. Replace `1_record_video.py` usage with `1_capture_screenshots.py`
2. Update `2_extract_persons.py` calls (now processes `raw_images/`)
3. Remove dependency on `videos/` directory
4. Update any scripts expecting video input

### Data Format Changes
- **Input**: Individual JPEG images instead of MP4 videos
- **Organization**: Camera-based folders instead of video-based
- **Metadata**: Timestamp and camera info in filenames