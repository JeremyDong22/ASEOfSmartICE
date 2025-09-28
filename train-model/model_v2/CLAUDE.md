# Model V2 - Ready to Train

## Overview
Clean template for training the next version of employee/customer classifier. All directories are empty and ready for new data collection.

## Quick Start

### 1. Collect New Data
```bash
cd scripts
python3 1_capture_screenshots.py
```

### 2. Run Full Pipeline
```bash
python3 2_extract_persons.py
python3 3_label_images.py
python3 4_prepare_dataset.py
python3 5_train_model.py
```

## Improvements from V1
- [ ] To be determined based on V1 performance
- [ ] More training data
- [ ] Better labeling accuracy
- [ ] Enhanced model architecture

## Directory Structure
```
model_v2/
├── scripts/              # Training pipeline (ready to use)
├── raw_images/          # Empty - for new captures
├── extracted-persons/   # Empty - for person crops
├── labeled-persons/     # Empty - for labeled data
├── dataset/            # Empty - for training format
└── models/             # Empty - for trained output
```

## Training Configuration
Edit parameters in scripts as needed:
- Capture duration
- Camera selection
- Model epochs
- Batch size