#!/bin/bash
# Process video with existing config (60 seconds)

python3 video_processing/table_and_region_state_detection.py \
    --video ../videos/20251022/camera_35/camera_35_20251022_195212.mp4 \
    --duration 60
