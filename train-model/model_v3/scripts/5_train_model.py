#!/usr/bin/env python3
# Version: 3.0 - YOLO Classification
# Train YOLOv11 classification model for waiter/customer detection
# Optimized for MacBook M4 with MPS acceleration

import os
import torch
from ultralytics import YOLO
from pathlib import Path
import yaml
import time

# Paths (use absolute paths to avoid working directory issues)
SCRIPT_DIR = Path(__file__).parent.absolute()
DATASET_DIR = str(SCRIPT_DIR.parent / "dataset")  # For classification, pass directory not yaml
DATASET_YAML = str(SCRIPT_DIR.parent / "dataset" / "data.yaml")  # For validation only
OUTPUT_DIR = str(SCRIPT_DIR.parent / "models_cls")
BASE_MODEL = "yolo11n-cls.pt"  # YOLOv11 nano classification model

# Training configuration optimized for M4 MacBook + classification task
# Based on research: transfer learning + aggressive augmentation for 1500-image dataset
TRAIN_CONFIG = {
    # Basic settings
    'epochs': 50,
    'imgsz': 224,           # Standard size for classification (research recommended)
    'batch': 16,            # Optimal for M4 with classification
    'patience': 10,         # Early stopping
    'save': True,
    'device': 'mps',        # Apple Silicon GPU acceleration
    'workers': 8,           # Utilize M4 performance cores
    'project': OUTPUT_DIR,
    'name': 'waiter_customer_yolo11n_cls',
    'exist_ok': True,
    'pretrained': True,     # Transfer learning from ImageNet
    'verbose': True,

    # Optimizer settings (SGD recommended for stability)
    'optimizer': 'SGD',
    'lr0': 0.001,          # Initial learning rate
    'lrf': 0.0001,         # Final learning rate (10x lower for fine-tuning)
    'momentum': 0.9,
    'weight_decay': 0.0005,
    'warmup_epochs': 3.0,
    'warmup_momentum': 0.8,

    # Data augmentation (aggressive to triple effective dataset size)
    # Essential for clothing/uniform detection with limited data
    'hsv_h': 0.015,        # Hue augmentation (slight color variation)
    'hsv_s': 0.1,          # Saturation augmentation
    'hsv_v': 0.2,          # Brightness augmentation
    'degrees': 15,         # Rotation augmentation (-15° to +15°)
    'translate': 0.1,      # Translation augmentation
    'scale': 0.5,          # Scale augmentation (0.5-1.5x)
    'shear': 0.0,          # No shear (people are upright)
    'perspective': 0.0,    # No perspective (people are upright)
    'flipud': 0.0,         # No vertical flip (people are upright)
    'fliplr': 0.5,         # Horizontal flip (50% chance)
    'mosaic': 0.0,         # Disable mosaic for classification
    'mixup': 0.2,          # MixUp augmentation (blend images)
    'copy_paste': 0.0,     # Disable for classification
    'erasing': 0.1,        # Random erasing (10% chance)

    # Training stability
    'close_mosaic': 0,     # Not applicable for classification
    'amp': True,           # Automatic mixed precision for faster training
}

def check_dataset():
    """Verify dataset is ready"""
    if not os.path.exists(DATASET_YAML):
        print("❌ Dataset not found. Please run 4_prepare_dataset.py first")
        return False

    with open(DATASET_YAML, 'r') as f:
        data = yaml.safe_load(f)

    print("📊 Dataset info:")
    print(f"   Classes: {data.get('names', 'Unknown')}")
    print(f"   Training samples: {data.get('train_samples', 'Unknown')}")
    print(f"   Validation samples: {data.get('val_samples', 'Unknown')}")

    # Verify dataset structure
    dataset_path = Path(data['path'])
    train_path = dataset_path / data['train']
    val_path = dataset_path / data['val']

    if not train_path.exists() or not val_path.exists():
        print(f"❌ Dataset directories not found:")
        print(f"   Train: {train_path}")
        print(f"   Val: {val_path}")
        return False

    return True

def train_classification_model():
    """Train YOLOv11 classification model for waiter/customer detection"""
    print("=" * 80)
    print("🎯 YOLOv11 Classification Model Training")
    print("   Task: Waiter vs Customer Classification")
    print("   Model: YOLOv11n-cls (Nano - Lightweight)")
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
    print("   Transfer learning from ImageNet weights...")

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
    print(f"   Rotation: ±{TRAIN_CONFIG['degrees']}°")
    print(f"   Horizontal flip: {TRAIN_CONFIG['fliplr']*100}%")
    print(f"   MixUp: {TRAIN_CONFIG['mixup']*100}%")
    print(f"   Random erasing: {TRAIN_CONFIG['erasing']*100}%")

    print("\n⏳ Starting training...")
    print("   Estimated time: 2-3 hours on M4 MacBook")
    print("   Press Ctrl+C to stop (model will be saved)")
    print("\n" + "=" * 80)

    start_time = time.time()

    try:
        # Train the classification model
        # For classification, pass dataset directory (not yaml file)
        results = model.train(
            data=DATASET_DIR,
            **TRAIN_CONFIG
        )

        training_time = time.time() - start_time
        print("\n" + "=" * 80)
        print(f"✅ Training completed in {training_time/60:.1f} minutes!")
        print("=" * 80)

    except KeyboardInterrupt:
        print("\n⚠️  Training interrupted by user")
        print("   Latest checkpoint saved")
        os.system('say "Training interrupted by user. Checkpoint saved"')

    # Save best model
    best_model_path = os.path.join(OUTPUT_DIR, 'waiter_customer_yolo11n_cls', 'weights', 'best.pt')
    if os.path.exists(best_model_path):
        final_path = os.path.join(OUTPUT_DIR, 'waiter_customer_classifier.pt')

        # Load and save final model
        final_model = YOLO(best_model_path)
        final_model.save(final_path)

        print(f"\n🎉 Model saved to: {final_path}")
        print("\n📊 To use your model:")
        print("   Python:")
        print(f"     from ultralytics import YOLO")
        print(f"     model = YOLO('{final_path}')")
        print(f"     results = model('person_image.jpg')")
        print(f"     print(results[0].probs.top1)  # 0=customer, 1=waiter (alphabetical order)")

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
        results_csv = os.path.join(OUTPUT_DIR, 'waiter_customer_yolo11n_cls', 'results.csv')
        if os.path.exists(results_csv):
            import pandas as pd
            df = pd.read_csv(results_csv)
            df.columns = df.columns.str.strip()

            # Get best epoch metrics
            best_epoch = df['metrics/accuracy_top1'].idxmax()
            best_acc = df.loc[best_epoch, 'metrics/accuracy_top1']

            print(f"   Best epoch: {best_epoch + 1}")
            print(f"   Best accuracy: {best_acc:.2%}")
            print(f"   Final train loss: {df['train/loss'].iloc[-1]:.4f}")
            print(f"   Final val loss: {df['val/loss'].iloc[-1]:.4f}")
    else:
        print("❌ Best model not found. Training may have failed.")

def validate_model():
    """Validate the trained model"""
    model_path = os.path.join(OUTPUT_DIR, 'waiter_customer_classifier.pt')

    if not os.path.exists(model_path):
        print("❌ Trained model not found")
        return

    print("\n🔍 Validating model...")
    model = YOLO(model_path)

    # Run validation (use dataset directory for classification)
    metrics = model.val(data=DATASET_DIR)

    print("\n📊 Validation Results:")
    print(f"   Top-1 Accuracy: {metrics.top1:.2%}")
    print(f"   Top-5 Accuracy: {metrics.top5:.2%}")

    # Class-specific metrics (if available)
    if hasattr(metrics, 'confusion_matrix') and metrics.confusion_matrix is not None:
        print("\n🎯 Per-Class Performance:")
        print("   (Based on confusion matrix)")

if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("🍽️  Restaurant Staff Classification Model Training")
    print("   YOLOv11n-cls: Waiter vs Customer Detection")
    print("=" * 80)

    # Device info
    if torch.backends.mps.is_available():
        print("💻 Running on Apple Silicon with MPS acceleration")
    else:
        print("💻 Running on CPU (MPS not available)")

    print("=" * 80)

    # Train model
    try:
        train_classification_model()

        # Validate if successful
        if os.path.exists(os.path.join(OUTPUT_DIR, 'waiter_customer_classifier.pt')):
            validate_model()
            os.system('say "YOLOv11 classification model training completed successfully"')
        else:
            os.system('say "Model training finished but final model not found"')
    except Exception as e:
        print(f"\n❌ Training failed: {e}")
        import traceback
        traceback.print_exc()
        os.system('say "Model training failed with error"')
        raise
