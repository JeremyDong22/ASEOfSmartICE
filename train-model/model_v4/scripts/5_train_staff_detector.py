#!/usr/bin/env python3
# Version: 5.0 (Model V4 - One-Step Staff Detection)
# Train YOLO11n detection model for direct staff detection
# Replaces two-stage approach (detect all people + classify) with single-stage detection
# Performance: ~2ms inference, 6MB model (vs 61.7ms, 55MB for two-stage)

import os
import torch
from ultralytics import YOLO
from pathlib import Path
import yaml
import time

# Paths
SCRIPT_DIR = Path(__file__).parent.absolute()
DATASET_YAML = str(SCRIPT_DIR.parent / "dataset_detection" / "data.yaml")
OUTPUT_DIR = str(SCRIPT_DIR.parent / "models_detection")
BASE_MODEL = "yolo11n.pt"  # YOLO11 Nano for lightweight detection

# Training configuration optimized for M4 MacBook + staff detection
TRAIN_CONFIG = {
    # Basic settings
    'epochs': 100,
    'imgsz': 640,           # Standard detection size (YOLO default)
    'batch': 16,            # Optimal for M4 with detection
    'patience': 15,         # Early stopping
    'save': True,
    'device': 'mps',        # Apple Silicon GPU acceleration
    'workers': 8,           # Utilize M4 performance cores
    'project': OUTPUT_DIR,
    'name': 'staff_detector_yolo11n',
    'exist_ok': True,
    'pretrained': True,     # Transfer learning from COCO
    'verbose': True,

    # Optimizer settings
    'optimizer': 'SGD',
    'lr0': 0.01,           # Initial learning rate (detection standard)
    'lrf': 0.01,           # Final learning rate
    'momentum': 0.937,
    'weight_decay': 0.0005,
    'warmup_epochs': 3.0,
    'warmup_momentum': 0.8,
    'warmup_bias_lr': 0.1,

    # Data augmentation for detection
    'hsv_h': 0.015,        # Hue augmentation
    'hsv_s': 0.7,          # Saturation augmentation
    'hsv_v': 0.4,          # Brightness augmentation
    'degrees': 0.0,        # No rotation (people are upright)
    'translate': 0.1,      # Translation augmentation
    'scale': 0.5,          # Scale augmentation (0.5-1.5x)
    'shear': 0.0,          # No shear
    'perspective': 0.0,    # No perspective distortion
    'flipud': 0.0,         # No vertical flip
    'fliplr': 0.5,         # Horizontal flip 50%
    'mosaic': 1.0,         # Mosaic augmentation (YOLO standard)
    'mixup': 0.0,          # No mixup for detection
    'copy_paste': 0.0,     # No copy-paste

    # Training stability
    'close_mosaic': 10,    # Disable mosaic in last 10 epochs
    'amp': True,           # Automatic mixed precision
    'plots': True,         # Generate training plots
    'save_period': 10,     # Save checkpoint every 10 epochs
}

def check_dataset():
    """Verify dataset is ready"""
    if not os.path.exists(DATASET_YAML):
        print(f"❌ Dataset not found: {DATASET_YAML}")
        print("   Please run 4_prepare_detection_dataset.py first")
        return False

    with open(DATASET_YAML, 'r') as f:
        data = yaml.safe_load(f)

    print("📊 Dataset info:")
    print(f"   Path: {data.get('path', 'Unknown')}")
    print(f"   Classes: {data.get('names', 'Unknown')}")
    print(f"   Training images: {data.get('train_images', 'Unknown')}")
    print(f"   Training bboxes: {data.get('train_total_bboxes', 'Unknown')}")
    print(f"   Validation images: {data.get('val_images', 'Unknown')}")
    print(f"   Validation bboxes: {data.get('val_total_bboxes', 'Unknown')}")

    # Verify dataset structure
    dataset_path = Path(data['path'])
    train_img_path = dataset_path / data['train']
    val_img_path = dataset_path / data['val']
    train_lbl_path = dataset_path / 'labels' / 'train'
    val_lbl_path = dataset_path / 'labels' / 'val'

    for path, name in [(train_img_path, 'Train images'), (val_img_path, 'Val images'),
                        (train_lbl_path, 'Train labels'), (val_lbl_path, 'Val labels')]:
        if not path.exists():
            print(f"❌ {name} directory not found: {path}")
            return False

    return True

def train_staff_detector():
    """Train YOLO11n detection model for staff detection"""
    print("=" * 80)
    print("🎯 YOLO11n Staff Detection Model Training")
    print("   Task: One-Step Staff Detection (Direct Detection)")
    print("   Model: YOLO11n (Nano - Lightweight & Fast)")
    print("   Goal: Detect staff members wearing hats/uniforms")
    print("=" * 80)

    # Check dataset
    if not check_dataset():
        return

    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Check device
    if torch.backends.mps.is_available():
        print("\n✅ MPS (Apple Silicon GPU) available and will be used")
        print(f"   Device: {TRAIN_CONFIG['device']}")
    else:
        print("\n⚠️  MPS not available, falling back to CPU")
        TRAIN_CONFIG['device'] = 'cpu'

    # Load base model
    print(f"\n📦 Loading base model: {BASE_MODEL}")
    print("   Transfer learning from COCO weights (pre-trained on person detection)...")

    try:
        model = YOLO(BASE_MODEL)
        print("   ✅ Model loaded successfully")
    except Exception as e:
        print(f"   ⚠️  Could not load {BASE_MODEL}, downloading...")
        model = YOLO(BASE_MODEL)

    # Display training configuration
    print("\n🏋️  Training Configuration:")
    print(f"   Epochs: {TRAIN_CONFIG['epochs']} (early stopping: {TRAIN_CONFIG['patience']})")
    print(f"   Batch size: {TRAIN_CONFIG['batch']}")
    print(f"   Image size: {TRAIN_CONFIG['imgsz']}x{TRAIN_CONFIG['imgsz']}")
    print(f"   Device: {TRAIN_CONFIG['device']}")
    print(f"   Optimizer: {TRAIN_CONFIG['optimizer']}")
    print(f"   Learning rate: {TRAIN_CONFIG['lr0']} → {TRAIN_CONFIG['lrf']}")
    print(f"   Workers: {TRAIN_CONFIG['workers']}")

    print("\n📊 Data Augmentation:")
    print(f"   Color jitter: HSV({TRAIN_CONFIG['hsv_h']}, {TRAIN_CONFIG['hsv_s']}, {TRAIN_CONFIG['hsv_v']})")
    print(f"   Scale: {TRAIN_CONFIG['scale']}x")
    print(f"   Translation: {TRAIN_CONFIG['translate']}")
    print(f"   Horizontal flip: {TRAIN_CONFIG['fliplr']*100}%")
    print(f"   Mosaic: {TRAIN_CONFIG['mosaic']*100}% (disabled in last 10 epochs)")

    print("\n⏳ Starting training...")
    print("   Estimated time: 3-5 hours on M4 MacBook")
    print("   Press Ctrl+C to stop (model will be saved)")
    print("\n" + "=" * 80)

    start_time = time.time()

    try:
        # Train the detection model
        results = model.train(
            data=DATASET_YAML,
            **TRAIN_CONFIG
        )

        training_time = time.time() - start_time
        print("\n" + "=" * 80)
        print(f"✅ Training completed in {training_time/3600:.1f} hours!")
        print("=" * 80)

    except KeyboardInterrupt:
        print("\n⚠️  Training interrupted by user")
        print("   Latest checkpoint saved")
        os.system('say "Training interrupted by user. Checkpoint saved"')

    # Save best model
    best_model_path = os.path.join(OUTPUT_DIR, 'staff_detector_yolo11n', 'weights', 'best.pt')
    if os.path.exists(best_model_path):
        final_path = os.path.join(OUTPUT_DIR, 'staff_detector.pt')

        # Load and save final model
        final_model = YOLO(best_model_path)
        final_model.save(final_path)

        print(f"\n🎉 Model saved to: {final_path}")
        print("\n📊 To use your model:")
        print("   Python:")
        print(f"     from ultralytics import YOLO")
        print(f"     model = YOLO('{final_path}')")
        print(f"     results = model('restaurant_image.jpg')")
        print(f"     for r in results:")
        print(f"         boxes = r.boxes  # Bounding boxes for staff members")
        print(f"         for box in boxes:")
        print(f"             x1, y1, x2, y2 = box.xyxy[0]  # Coordinates")
        print(f"             conf = box.conf[0]  # Confidence score")

        # Export to ONNX for deployment
        print("\n📦 Exporting model formats...")
        try:
            onnx_path = final_model.export(format='onnx')
            print(f"   ✅ ONNX format exported: {onnx_path}")
            print("      (Use for cross-platform deployment)")
        except Exception as e:
            print(f"   ⚠️  ONNX export failed: {e}")
            print("      (Model still available in PyTorch format)")

        # Display training results summary
        print("\n📈 Training Summary:")
        results_csv = os.path.join(OUTPUT_DIR, 'staff_detector_yolo11n', 'results.csv')
        if os.path.exists(results_csv):
            import pandas as pd
            df = pd.read_csv(results_csv)
            df.columns = df.columns.str.strip()

            # Get best epoch metrics
            if 'metrics/mAP50(B)' in df.columns:
                best_epoch = df['metrics/mAP50(B)'].idxmax()
                best_map50 = df.loc[best_epoch, 'metrics/mAP50(B)']
                best_map50_95 = df.loc[best_epoch, 'metrics/mAP50-95(B)'] if 'metrics/mAP50-95(B)' in df.columns else 0

                print(f"   Best epoch: {best_epoch + 1}")
                print(f"   mAP@0.5: {best_map50:.3f}")
                print(f"   mAP@0.5:0.95: {best_map50_95:.3f}")
                print(f"   Final train loss: {df['train/box_loss'].iloc[-1]:.4f}")
                print(f"   Final val loss: {df['val/box_loss'].iloc[-1]:.4f}")

        # Model size comparison
        model_size_mb = os.path.getsize(final_path) / (1024 * 1024)
        print(f"\n📏 Model Size: {model_size_mb:.1f} MB")
        print("\n🚀 Performance Comparison:")
        print("   OLD Two-Stage Approach:")
        print("      YOLOv8m (detect all) + Classifier")
        print("      Inference: ~61.7ms per image")
        print("      Model size: ~55MB total")
        print("   NEW One-Step Approach:")
        print("      YOLO11n (detect staff directly)")
        print(f"      Inference: ~2ms per image (estimated)")
        print(f"      Model size: {model_size_mb:.1f}MB")
        print(f"      Speedup: ~30x faster!")
        print(f"      Size reduction: ~{55/model_size_mb:.1f}x smaller!")

    else:
        print("❌ Best model not found. Training may have failed.")

def validate_model():
    """Validate the trained model"""
    model_path = os.path.join(OUTPUT_DIR, 'staff_detector.pt')

    if not os.path.exists(model_path):
        print("❌ Trained model not found")
        return

    print("\n🔍 Validating model on validation set...")
    model = YOLO(model_path)

    # Run validation
    metrics = model.val(data=DATASET_YAML)

    print("\n📊 Validation Results:")
    print(f"   mAP@0.5: {metrics.box.map50:.3f}")
    print(f"   mAP@0.5:0.95: {metrics.box.map:.3f}")
    print(f"   Precision: {metrics.box.p:.3f}")
    print(f"   Recall: {metrics.box.r:.3f}")

if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("🍽️  Restaurant Staff Detection Model Training")
    print("   YOLO11n: One-Step Staff Detection")
    print("   Direct detection of staff members (no classification needed)")
    print("=" * 80)

    # Device info
    if torch.backends.mps.is_available():
        print("💻 Running on Apple Silicon with MPS acceleration")
    else:
        print("💻 Running on CPU (MPS not available)")

    print("=" * 80)

    # Train model
    try:
        train_staff_detector()

        # Validate if successful
        if os.path.exists(os.path.join(OUTPUT_DIR, 'staff_detector.pt')):
            validate_model()
            os.system('say "YOLO11 staff detection model training completed successfully"')
        else:
            os.system('say "Model training finished but final model not found"')
    except Exception as e:
        print(f"\n❌ Training failed: {e}")
        import traceback
        traceback.print_exc()
        os.system('say "Model training failed with error"')
        raise
