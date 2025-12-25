#!/bin/bash
# Model V4 Training Pipeline - One-Step Staff Detection
# Complete workflow from raw images to trained YOLO11n detector

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================================================"
echo "Model V4 Training Pipeline - One-Step Staff Detection"
echo "========================================================================"
echo ""

# Step 1: Download images from Supabase
echo "Step 1/5: Download raw images from Supabase..."
echo "------------------------------------------------------------------------"
python3 1_download_from_supabase.py
echo ""

# Step 2: Filter images with people
echo "Step 2/5: Filter images containing people..."
echo "------------------------------------------------------------------------"
python3 2_filter_images_with_people.py
echo ""

# Step 3: Label staff bounding boxes (manual - launches web tool)
echo "Step 3/5: Label staff bounding boxes (MANUAL STEP)"
echo "------------------------------------------------------------------------"
echo "This step requires manual labeling via web interface."
echo "Please run: python3 3_label_staff_bboxes.py"
echo "Then open http://localhost:5003 in your browser"
echo "Label ONLY staff members (people with hats/uniforms)"
echo ""
echo "Press ENTER when labeling is complete to continue..."
read

# Step 4: Prepare detection dataset
echo "Step 4/5: Prepare YOLO detection dataset..."
echo "------------------------------------------------------------------------"
python3 4_prepare_detection_dataset.py
echo ""

# Step 5: Train staff detector
echo "Step 5/5: Train YOLO11n staff detector..."
echo "------------------------------------------------------------------------"
python3 5_train_staff_detector.py
echo ""

echo "========================================================================"
echo "Training pipeline complete!"
echo "========================================================================"
echo "Next steps:"
echo "  1. Validate model on test set"
echo "  2. Benchmark inference speed"
echo "  3. Compare with V3 two-stage approach"
echo "  4. Deploy to production for testing"
echo ""
