"""
Version: 1.0
Analyze validation errors in detail to understand the 1% misclassifications.
This script loads the trained model, runs validation, and identifies specific errors.
"""

from ultralytics import YOLO
import cv2
import os
from pathlib import Path
import yaml
import shutil

# Paths
MODEL_PATH = "/Users/jeremydong/Desktop/Smartice/ASEOfSmartICE/train-model/model_v2/models_sgd/waiter_customer_model_sgd_cpu/weights/best.pt"
DATASET_YAML = "/Users/jeremydong/Desktop/Smartice/ASEOfSmartICE/train-model/model_v2/dataset/data.yaml"
ERROR_OUTPUT_DIR = "/Users/jeremydong/Desktop/Smartice/ASEOfSmartICE/train-model/model_v2/validation_errors"

# Create output directory
os.makedirs(ERROR_OUTPUT_DIR, exist_ok=True)

# Load the model
print("Loading model...")
model = YOLO(MODEL_PATH)

# Load dataset configuration
with open(DATASET_YAML, 'r') as f:
    dataset_config = yaml.safe_load(f)

# Get validation images and labels
dataset_path = Path(dataset_config['path'])
val_images_dir = dataset_path / dataset_config['val']
val_labels_dir = dataset_path / 'labels' / 'val'

print(f"Validation images directory: {val_images_dir}")
print(f"Validation labels directory: {val_labels_dir}")

# Class names
class_names = dataset_config['names']
print(f"Classes: {class_names}")

# Define helper function first
def calculate_iou(bbox1, bbox2):
    """Calculate IoU between two bounding boxes in xywh format"""
    # Convert xywh to xyxy
    x1_min = bbox1[0] - bbox1[2]/2
    y1_min = bbox1[1] - bbox1[3]/2
    x1_max = bbox1[0] + bbox1[2]/2
    y1_max = bbox1[1] + bbox1[3]/2

    x2_min = bbox2[0] - bbox2[2]/2
    y2_min = bbox2[1] - bbox2[3]/2
    x2_max = bbox2[0] + bbox2[2]/2
    y2_max = bbox2[1] + bbox2[3]/2

    # Calculate intersection
    x_inter_min = max(x1_min, x2_min)
    y_inter_min = max(y1_min, y2_min)
    x_inter_max = min(x1_max, x2_max)
    y_inter_max = min(y1_max, y2_max)

    if x_inter_max < x_inter_min or y_inter_max < y_inter_min:
        return 0.0

    inter_area = (x_inter_max - x_inter_min) * (y_inter_max - y_inter_min)

    # Calculate union
    area1 = bbox1[2] * bbox1[3]
    area2 = bbox2[2] * bbox2[3]
    union_area = area1 + area2 - inter_area

    return inter_area / union_area if union_area > 0 else 0.0

# Run validation with detailed output
print("\nRunning detailed validation...")
results = model.val(data=DATASET_YAML, save_json=True, save_hybrid=True)

# Get all validation images
val_images = list(val_images_dir.glob('*.jpg'))
print(f"\nTotal validation images: {len(val_images)}")

# Analyze each image
misclassifications = {
    'waiter_to_customer': [],
    'customer_to_waiter': [],
    'false_positives': [],
    'false_negatives': []
}

error_count = 0
total_detections = 0

print("\nAnalyzing individual predictions...")

for img_path in val_images:
    # Get corresponding label file
    label_path = val_labels_dir / f"{img_path.stem}.txt"

    if not label_path.exists():
        continue

    # Read ground truth labels
    with open(label_path, 'r') as f:
        gt_labels = []
        for line in f.readlines():
            parts = line.strip().split()
            if len(parts) >= 5:
                gt_labels.append({
                    'class': int(parts[0]),
                    'bbox': [float(x) for x in parts[1:5]]
                })

    # Run prediction
    pred_results = model.predict(str(img_path), conf=0.25, verbose=False)

    # Compare predictions with ground truth
    for gt in gt_labels:
        total_detections += 1
        gt_class = gt['class']
        gt_bbox = gt['bbox']

        # Find matching prediction (using IoU threshold)
        matched = False
        pred_class = None
        pred_conf = 0

        if len(pred_results) > 0 and pred_results[0].boxes is not None:
            for box in pred_results[0].boxes:
                # Convert to YOLO format (normalized xywh)
                pred_bbox_xyxy = box.xyxy[0].cpu().numpy()
                img = cv2.imread(str(img_path))
                h, w = img.shape[:2]

                # Convert xyxy to xywh normalized
                x_center = ((pred_bbox_xyxy[0] + pred_bbox_xyxy[2]) / 2) / w
                y_center = ((pred_bbox_xyxy[1] + pred_bbox_xyxy[3]) / 2) / h
                width = (pred_bbox_xyxy[2] - pred_bbox_xyxy[0]) / w
                height = (pred_bbox_xyxy[3] - pred_bbox_xyxy[1]) / h

                pred_bbox_norm = [x_center, y_center, width, height]

                # Calculate IoU
                iou = calculate_iou(gt_bbox, pred_bbox_norm)

                if iou > 0.5:  # Match threshold
                    matched = True
                    pred_class = int(box.cls[0].cpu().numpy())
                    pred_conf = float(box.conf[0].cpu().numpy())

                    # Check if misclassified
                    if pred_class != gt_class:
                        error_count += 1
                        error_info = {
                            'image': str(img_path),
                            'gt_class': class_names[gt_class],
                            'pred_class': class_names[pred_class],
                            'confidence': pred_conf,
                            'bbox': gt_bbox
                        }

                        if gt_class == 0 and pred_class == 1:  # waiter -> customer
                            misclassifications['waiter_to_customer'].append(error_info)
                        elif gt_class == 1 and pred_class == 0:  # customer -> waiter
                            misclassifications['customer_to_waiter'].append(error_info)
                    break

        if not matched:
            # False negative (missed detection)
            error_count += 1
            misclassifications['false_negatives'].append({
                'image': str(img_path),
                'gt_class': class_names[gt_class],
                'bbox': gt_bbox
            })

# Print results
print("\n" + "="*80)
print("VALIDATION ERROR ANALYSIS")
print("="*80)
print(f"\nTotal detections analyzed: {total_detections}")
print(f"Total errors found: {error_count}")
if total_detections > 0:
    print(f"Error rate: {error_count/total_detections*100:.2f}%")
else:
    print("Error rate: N/A (no detections found)")

print(f"\n\nError Breakdown:")
print(f"  Waiter → Customer: {len(misclassifications['waiter_to_customer'])}")
print(f"  Customer → Waiter: {len(misclassifications['customer_to_waiter'])}")
print(f"  False Negatives (missed): {len(misclassifications['false_negatives'])}")

# Show specific examples
if misclassifications['waiter_to_customer']:
    print(f"\n\nWaiter misclassified as Customer ({len(misclassifications['waiter_to_customer'])} cases):")
    for i, error in enumerate(misclassifications['waiter_to_customer'][:5], 1):
        print(f"  {i}. {Path(error['image']).name} (confidence: {error['confidence']:.3f})")

if misclassifications['customer_to_waiter']:
    print(f"\n\nCustomer misclassified as Waiter ({len(misclassifications['customer_to_waiter'])} cases):")
    for i, error in enumerate(misclassifications['customer_to_waiter'][:5], 1):
        print(f"  {i}. {Path(error['image']).name} (confidence: {error['confidence']:.3f})")

if misclassifications['false_negatives']:
    print(f"\n\nMissed Detections ({len(misclassifications['false_negatives'])} cases):")
    for i, error in enumerate(misclassifications['false_negatives'][:5], 1):
        print(f"  {i}. {Path(error['image']).name} - {error['gt_class']}")

# Save detailed report
report_path = os.path.join(ERROR_OUTPUT_DIR, "error_report.txt")
with open(report_path, 'w') as f:
    f.write("="*80 + "\n")
    f.write("VALIDATION ERROR ANALYSIS - DETAILED REPORT\n")
    f.write("="*80 + "\n\n")
    f.write(f"Total detections analyzed: {total_detections}\n")
    f.write(f"Total errors found: {error_count}\n")
    if total_detections > 0:
        f.write(f"Error rate: {error_count/total_detections*100:.2f}%\n\n")
    else:
        f.write("Error rate: N/A (no detections found)\n\n")

    f.write("Error Breakdown:\n")
    f.write(f"  Waiter → Customer: {len(misclassifications['waiter_to_customer'])}\n")
    f.write(f"  Customer → Waiter: {len(misclassifications['customer_to_waiter'])}\n")
    f.write(f"  False Negatives: {len(misclassifications['false_negatives'])}\n\n")

    f.write("\n" + "="*80 + "\n")
    f.write("WAITER → CUSTOMER ERRORS\n")
    f.write("="*80 + "\n")
    for error in misclassifications['waiter_to_customer']:
        f.write(f"\nImage: {Path(error['image']).name}\n")
        f.write(f"  Ground Truth: {error['gt_class']}\n")
        f.write(f"  Prediction: {error['pred_class']}\n")
        f.write(f"  Confidence: {error['confidence']:.3f}\n")

    f.write("\n" + "="*80 + "\n")
    f.write("CUSTOMER → WAITER ERRORS\n")
    f.write("="*80 + "\n")
    for error in misclassifications['customer_to_waiter']:
        f.write(f"\nImage: {Path(error['image']).name}\n")
        f.write(f"  Ground Truth: {error['gt_class']}\n")
        f.write(f"  Prediction: {error['pred_class']}\n")
        f.write(f"  Confidence: {error['confidence']:.3f}\n")

    f.write("\n" + "="*80 + "\n")
    f.write("MISSED DETECTIONS\n")
    f.write("="*80 + "\n")
    for error in misclassifications['false_negatives']:
        f.write(f"\nImage: {Path(error['image']).name}\n")
        f.write(f"  Ground Truth: {error['gt_class']}\n")

print(f"\n\nDetailed report saved to: {report_path}")

# Copy error images to output directory
print("\nCopying misclassified images...")
for error_type, errors in misclassifications.items():
    if errors:
        type_dir = os.path.join(ERROR_OUTPUT_DIR, error_type)
        os.makedirs(type_dir, exist_ok=True)

        for error in errors[:20]:  # Copy first 20 of each type
            src_path = error['image']
            dst_path = os.path.join(type_dir, Path(src_path).name)
            shutil.copy(src_path, dst_path)

print(f"\nMisclassified images copied to: {ERROR_OUTPUT_DIR}")
print("\nAnalysis complete!")
