# Scripts Directory Structure

Version: 2.0.0
Last Updated: 2025-11-14

## Overview

Scripts are organized by feature for easy navigation and maintenance. This structure replaces the previous flat organization where all scripts were in a single directory.

## Directory Organization

### Feature-Based Subdirectories

#### `camera_testing/`
Camera connection testing and validation scripts.

**Scripts:**
- `test_camera_connections.py` - Test RTSP camera connections, validate configuration
- `run_camera_test.sh` - Interactive camera test runner (menu-based)
- `quick_camera_test.sh` - Quick command-line camera test

**Usage:**
```bash
# Interactive testing
cd camera_testing && ./run_camera_test.sh

# Quick test specific IPs
cd camera_testing && ./quick_camera_test.sh 202.168.40.35 202.168.40.22
```

---

#### `video_capture/`
RTSP stream capture and recording scripts.

**Scripts:**
- `capture_rtsp_streams.py` - Multi-camera RTSP recording with H.264 encoding

**Usage:**
```bash
# Record from all cameras (duration in seconds)
cd video_capture && python3 capture_rtsp_streams.py --duration 3600
```

---

#### `video_processing/`
Video detection and analysis scripts.

**Scripts:**
- `table_and_region_state_detection.py` - Unified table and region state detection system

**Usage:**
```bash
# Interactive ROI setup
cd video_processing && python3 table_and_region_state_detection.py --video ../videos/camera_35.mp4 --interactive

# Process with existing config
cd video_processing && python3 table_and_region_state_detection.py --video ../videos/camera_35.mp4 --duration 60
```

---

#### `orchestration/`
Multi-component coordination and batch processing scripts.

**Scripts:**
- `process_videos_orchestrator.py` - GPU-aware batch video processing with queue management

**Usage:**
```bash
# Process all videos with GPU queue management
cd orchestration && python3 process_videos_orchestrator.py --max-parallel 4

# Process specific cameras only
cd orchestration && python3 process_videos_orchestrator.py --cameras camera_35 camera_22
```

---

#### `time_sync/`
NTP and time synchronization scripts.

**Scripts:**
- `setup_ntp.sh` - Configure NTP for Beijing time (Asia/Shanghai)
- `verify_time_sync.sh` - Verify NTP synchronization status

**Usage:**
```bash
# Setup NTP (requires sudo)
cd time_sync && sudo ./setup_ntp.sh

# Verify time sync
cd time_sync && ./verify_time_sync.sh
```

---

#### `maintenance/`
System cleanup and monitoring scripts.

**Scripts:**
- `cleanup_old_videos.sh` - Remove videos older than retention period

**Usage:**
```bash
# Interactive cleanup (prompts before deletion)
cd maintenance && ./cleanup_old_videos.sh

# Force cleanup (no prompts, for cron jobs)
cd maintenance && ./cleanup_old_videos.sh --force
```

---

#### `deployment/`
Initial setup and configuration management scripts.

**Scripts:**
- `initialize_deployment.sh` - Interactive deployment wizard for first-time setup
- `install_cron_jobs.sh` - Install/manage automated cron schedules

**Usage:**
```bash
# First-time deployment setup
cd deployment && ./initialize_deployment.sh

# Install cron jobs
cd deployment && ./install_cron_jobs.sh --install

# Check cron job status
cd deployment && ./install_cron_jobs.sh --status
```

---

### Quick Start Scripts (Root Level)

Frequently-used convenience scripts remain in the scripts root for easy access:

- `run_interactive.sh` - Quick launcher for interactive ROI setup
- `run_with_config.sh` - Quick launcher for processing with existing config (60s test)
- `run_parallel_processing.sh` - Quick launcher for GPU-aware batch processing

**Usage:**
```bash
# From scripts/ directory
./run_interactive.sh
./run_with_config.sh
./run_parallel_processing.sh
```

---

### Configuration Files (Root Level)

Configuration files remain in the scripts root for easy access:

- `cameras_config.json` - Camera IP addresses and connection settings
- `table_region_config.json` - ROI configuration for tables and service areas

---

## Migration from Old Structure

### Before (v1.0.0 - Flat Structure)
```
scripts/
├── test_camera_connections.py
├── capture_rtsp_streams.py
├── table_and_region_state_detection.py
├── process_videos_orchestrator.py
├── setup_ntp.sh
├── verify_time_sync.sh
├── cleanup_old_videos.sh
├── initialize_deployment.sh
├── install_cron_jobs.sh
├── run_camera_test.sh
├── quick_camera_test.sh
├── run_interactive.sh
├── run_with_config.sh
└── run_parallel_processing.sh
```

### After (v2.0.0 - Feature-Based Structure)
```
scripts/
├── camera_testing/
│   ├── test_camera_connections.py
│   ├── run_camera_test.sh
│   └── quick_camera_test.sh
├── video_capture/
│   └── capture_rtsp_streams.py
├── video_processing/
│   └── table_and_region_state_detection.py
├── orchestration/
│   └── process_videos_orchestrator.py
├── time_sync/
│   ├── setup_ntp.sh
│   └── verify_time_sync.sh
├── maintenance/
│   └── cleanup_old_videos.sh
├── deployment/
│   ├── initialize_deployment.sh
│   └── install_cron_jobs.sh
├── run_interactive.sh (root)
├── run_with_config.sh (root)
├── run_parallel_processing.sh (root)
├── cameras_config.json (root)
└── table_region_config.json (root)
```

---

## Path References

All scripts have been updated to use the new directory structure:

### Python Scripts
- Orchestrator references detection script: `SCRIPT_DIR.parent / "video_processing" / "table_and_region_state_detection.py"`

### Shell Scripts
- Convenience scripts reference subdirectories: `python3 video_processing/table_and_region_state_detection.py`
- Deployment scripts reference subdirectories: `$SCRIPTS_ROOT/camera_testing/test_camera_connections.py`
- Cron jobs reference subdirectories: `cd $SCRIPT_DIR && python3 video_capture/capture_rtsp_streams.py`

### Configuration Files
- Config files remain in scripts root: `../cameras_config.json`, `../table_region_config.json`

---

## Common Operations

### First-Time Deployment
```bash
cd deployment
./initialize_deployment.sh
```

### Daily Operations
```bash
# Test cameras
cd camera_testing && ./run_camera_test.sh

# Capture footage
cd video_capture && python3 capture_rtsp_streams.py --duration 36000

# Process videos
cd orchestration && python3 process_videos_orchestrator.py

# Cleanup old files
cd maintenance && ./cleanup_old_videos.sh
```

### Automated Scheduling
```bash
# Install cron jobs
cd deployment && ./install_cron_jobs.sh --install

# Check status
cd deployment && ./install_cron_jobs.sh --status
```

---

## Design Principles

1. **Feature Grouping**: Scripts are grouped by their primary function
2. **Easy Access**: Frequently-used scripts remain in root
3. **Clear Naming**: Directory names describe the feature area
4. **Minimal Nesting**: Maximum 1 level of subdirectories
5. **Config Stability**: Configuration files stay in predictable locations

---

## Notes

- All relative paths (../models/, ../videos/, ../results/) continue to work correctly
- Cron jobs have been updated to reference new paths
- Deployment scripts handle both old and new path structures
- No breaking changes to external integrations
