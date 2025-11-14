#!/bin/bash
# Process all videos from all cameras in parallel

python3 orchestration/process_videos_orchestrator.py "$@"
