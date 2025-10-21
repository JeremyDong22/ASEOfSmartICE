#!/usr/bin/env python3
# Version: 1.0
# Train custom YOLO model for waiter/customer detection
# Optimized for MacBook (CPU/MPS training)

import os
import torch
from ultralytics import YOLO
from pathlib import Path
import yaml
import time

# Paths
DATASET_YAML = "../dataset/data.yaml"
OUTPUT_DIR = "../models_sgd"  # New folder for SGD training
BASE_MODEL = "yolov8n.pt"  # Use nano model for faster training on CPU

# Training configuration for MacBook M4 - SGD Optimized
TRAIN_CONFIG = {
    'epochs': 50,           # Training rounds with early stopping
    'imgsz': 640,          # Standard image size
    'batch': 6,            # Reduced for better stability with SGD
    'patience': 10,        # Early stopping patience
    'save': True,
    'device': 'cpu',       # Use CPU - MPS has memory leak issues
    'workers': 2,          # Dual workers for M4 performance
    'project': OUTPUT_DIR,
    'name': 'waiter_customer_model_sgd_cpu',
    'exist_ok': True,
    'pretrained': True,
    'optimizer': 'SGD',    # Changed from Adam to SGD
    'lr0': 0.01,          # Initial learning rate
    'lrf': 0.01,          # Final learning rate
    'momentum': 0.937,
    'weight_decay': 0.0005,
    'warmup_epochs': 3.0,
    'warmup_momentum': 0.8,
    'box': 7.5,           # Box loss gain
    'cls': 0.5,           # Class loss gain
    'mosaic': 1.0,        # Mosaic augmentation
    'mixup': 0.0,         # Mixup augmentation
    'copy_paste': 0.0,    # Copy-paste augmentation
    'degrees': 0.0,       # Rotation augmentation
    'translate': 0.1,     # Translation augmentation
    'scale': 0.5,         # Scale augmentation
    'fliplr': 0.5,        # Horizontal flip
    'flipud': 0.0,        # Vertical flip
}

def check_dataset():
    """Verify dataset is ready"""
    if not os.path.exists(DATASET_YAML):
        print("❌ Dataset not found. Please run 4_prepare_dataset.py first")
        return False
    
    with open(DATASET_YAML, 'r') as f:
        data = yaml.safe_load(f)
    
    print("📊 Dataset info:")
    print(f"   Classes: {data['names']}")
    print(f"   Training samples: {data.get('train_samples', 'Unknown')}")
    print(f"   Validation samples: {data.get('val_samples', 'Unknown')}")
    
    return True

def train_model():
    """Train YOLO model for waiter/customer detection"""
    print("🚀 Starting model training...")
    print(f"🖥️ Device: {TRAIN_CONFIG['device']}")
    
    # Dataset check moved inside training loop
    
    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Load base model
    print(f"📦 Loading base model: {BASE_MODEL}")
    model = YOLO(BASE_MODEL)
    
    # Start training
    print("\n🏋️ Training configuration:")
    print(f"   Epochs: {TRAIN_CONFIG['epochs']}")
    print(f"   Batch size: {TRAIN_CONFIG['batch']}")
    print(f"   Image size: {TRAIN_CONFIG['imgsz']}")
    print(f"   Device: {TRAIN_CONFIG['device']}")
    
    print("\n⏳ Starting training... (this may take 1-2 hours on MacBook)")
    print("   Check progress in the terminal output")
    print("   Press Ctrl+C to stop early (model will be saved)")
    
    start_time = time.time()
    
    try:
        # Add additional safety checks
        print("🔍 Validating dataset before training...")

        # Check if dataset files exist
        try:
            from ultralytics.data.utils import check_dataset
            check_dataset(DATASET_YAML)
            print("✅ Dataset validation passed")
        except Exception as e:
            print(f"⚠️  Dataset validation warning: {e}")

        # Train the model
        results = model.train(
            data=DATASET_YAML,
            **TRAIN_CONFIG
        )
        
        training_time = time.time() - start_time
        print(f"\n✅ Training completed in {training_time/60:.1f} minutes!")
        
    except KeyboardInterrupt:
        print("\n⚠️ Training interrupted by user")
        print("   Latest checkpoint saved")
        os.system('say "Training interrupted by user. Checkpoint saved"')
    
    # Save best model
    best_model_path = os.path.join(OUTPUT_DIR, 'waiter_customer_model_sgd_cpu', 'weights', 'best.pt')
    if os.path.exists(best_model_path):
        final_path = os.path.join(OUTPUT_DIR, 'waiter_customer_final_sgd_cpu.pt')
        
        # Load and save final model
        final_model = YOLO(best_model_path)
        final_model.save(final_path)
        
        print(f"\n🎉 Model saved to: {final_path}")
        print("\n📊 To test your model:")
        print(f"   model = YOLO('{final_path}')")
        print("   results = model('image.jpg')")
        
        # Export to other formats
        print("\n📦 Exporting model formats...")
        try:
            # Export to ONNX for deployment
            final_model.export(format='onnx')
            print("   ✅ ONNX format exported")
        except:
            print("   ⚠️ ONNX export failed (optional)")
    else:
        print("❌ Best model not found. Training may have failed.")

def validate_model():
    """Validate the trained model"""
    model_path = os.path.join(OUTPUT_DIR, 'waiter_customer_final_sgd_cpu.pt')
    
    if not os.path.exists(model_path):
        print("❌ Trained model not found")
        return
    
    print("\n🔍 Validating model...")
    model = YOLO(model_path)
    
    # Run validation
    metrics = model.val(data=DATASET_YAML)
    
    print("\n📊 Validation Results:")
    print(f"   mAP50: {metrics.box.map50:.3f}")
    print(f"   mAP50-95: {metrics.box.map:.3f}")
    
    # Class-specific metrics
    for i, name in enumerate(['waiter', 'customer']):
        if i < len(metrics.box.ap50):
            print(f"   {name} AP50: {metrics.box.ap50[i]:.3f}")

if __name__ == "__main__":
    print("=" * 60)
    print("🎯 Restaurant Staff Detection Model Training")
    print("=" * 60)
    
    # CPU mode for stability
    print("💻 Running on CPU mode (MPS disabled due to memory leak issues)")
    print("   This provides stable training without memory accumulation")
    
    print("-" * 60)
    
    # Train model
    try:
        train_model()

        # Validate if successful
        if os.path.exists(os.path.join(OUTPUT_DIR, 'waiter_customer_final_sgd_cpu.pt')):
            validate_model()
            os.system('say "CPU S G D model training completed successfully"')
        else:
            os.system('say "CPU S G D model training finished but final model not found"')
    except Exception as e:
        print(f"\n❌ Training failed: {e}")
        os.system('say "Model training failed with error"')
        raise