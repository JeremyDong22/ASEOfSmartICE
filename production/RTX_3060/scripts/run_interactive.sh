#!/bin/bash
# Interactive ROI setup for table and region state detection

python3 video_processing/table_and_region_state_detection.py \
    --video ../videos/20251022/camera_35/camera_35_20251022_195212.mp4 \
    --interactive
