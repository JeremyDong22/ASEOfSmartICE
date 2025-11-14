#!/bin/bash
# Run table and region state detection in interactive mode

python3 table_and_region_state_detection.py \
  --video ../test-videos/camera_35_20251022_195212_h265.mp4 \
  --duration 60 \
  --interactive
