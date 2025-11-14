# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Production deployment folder for RTX 3060 machine at 野百灵火锅店 (Ye Bai Ling Hotpot Restaurant) in 1958 Commercial District, Mianyang. This is the **live production environment** running on remote Linux hardware in the restaurant location.

**Purpose:** Real-time restaurant surveillance system using computer vision to monitor table states and staff coverage across multiple camera feeds.

## Quick Start - New Deployment

**For first-time deployment at restaurant location:**

```bash
cd /path/to/production/RTX_3060/scripts/deployment
./initialize_deployment.sh
```

This interactive wizard guides you through prerequisite checks, camera configuration, ROI setup, and system verification with automatic error handling.

## Business Context

**Location:** 1958 Commercial District (1958商圈), Mianyang, Sichuan
**Restaurant:** 野百灵火锅店 (Ye Bai Ling Hotpot)
**Hardware:** NVIDIA RTX 3060 Linux machine deployed on-site
**Cameras:** 10 RTSP cameras covering restaurant floor
**Operating Hours:** 11 AM - 9 PM (10 hours daily)
**Processing Window:** 11 PM - 6 AM (overnight batch processing)

## System Architecture

### Two-Stage Detection Pipeline

**Stage 1: Person Detection**
- Model: `yolov8m.pt` (52 MB)
- Detects all people in frame
- Confidence: 0.3, Min size: 40px
- Performance: 14.5ms/frame

**Stage 2: Staff Classification**
- Model: `waiter_customer_classifier.pt` (3.2 MB)
- Classifies persons as waiter/customer
- Confidence: 0.5, Accuracy: 92.38%
- Performance: 47.2ms/frame

**Total Processing:** 61.7ms/frame (3.24x real-time at 5fps)

### Detection Modes

**1. Table State Detection**
- Monitors individual table states
- States: IDLE (green), BUSY (yellow), CLEANING (blue)
- Tracks customer/waiter presence at each table
- Use cases: Turnover analysis, service response time

**2. Region State Detection**
- Monitors division/area coverage by staff
- States: GREEN (serving), YELLOW (busy), RED (understaffed)
- Tracks staff locations in service/walking areas
- Use cases: Zone coverage, staff allocation

**3. Combined Detection**
- Unified system monitoring both tables AND regions
- Comprehensive restaurant floor monitoring
- Three-layer debug: SQLite DB + Screenshots + H.264 video

## Directory Structure

```
production/RTX_3060/
├── scripts/              # Production scripts (feature-based organization)
│   ├── camera_testing/      # Camera connection testing
│   ├── video_capture/       # RTSP stream recording
│   ├── video_processing/    # Detection and analysis (main system)
│   ├── orchestration/       # Multi-camera batch processing
│   ├── time_sync/           # NTP synchronization
│   ├── maintenance/         # Cleanup and monitoring
│   ├── deployment/          # Setup and configuration
│   ├── config/              # Configuration files
│   │   ├── cameras_config.json       # Camera IP addresses
│   │   └── table_region_config.json  # ROI configuration (5 tables)
│   └── STRUCTURE.md         # Detailed scripts organization guide
├── models/               # Trained YOLO models (53.1 MB total)
│   ├── yolov8m.pt                          # Person detector
│   └── waiter_customer_classifier.pt       # Staff classifier
├── db/                   # SQLite database + screenshots
│   ├── detection_data.db                   # State change logs
│   └── screenshots/[session_id]/           # Auto-saved screenshots
├── results/              # Processed video outputs
└── videos/               # Input video files
```

**Note:** Scripts are organized by feature. See `scripts/STRUCTURE.md` for detailed navigation guide.

## Common Commands

### Interactive ROI Setup
```bash
cd /path/to/production/RTX_3060/scripts
./run_interactive.sh

# Manual version (from scripts/ directory):
python3 video_processing/table_and_region_state_detection.py \
    --video ../videos/camera_35.mp4 \
    --interactive
```

**Workflow:**
1. Draw Division boundary (overall monitored area)
2. For each table: Draw table surface → Draw sitting areas → Press 'D'
3. Draw Service Areas (bar, POS, prep stations)
4. Press Ctrl+S to save to `config/table_region_config.json`

**Keyboard Controls:**
- `Enter` - Complete current ROI polygon
- `D` - Finish current table, move to next
- `S` - Skip remaining tables, go to Service Areas
- `Ctrl+Z` or `U` - Undo last point/ROI
- `Ctrl+S` - Save all configurations
- `Q` - Quit

### Process Video with Existing Config
```bash
cd /path/to/production/RTX_3060/scripts
./run_with_config.sh

# Manual version (from scripts/ directory):
python3 video_processing/table_and_region_state_detection.py \
    --video ../videos/camera_35.mp4 \
    --duration 60  # Process only 60 seconds

# Full video:
python3 video_processing/table_and_region_state_detection.py \
    --video ../videos/camera_35.mp4
```

### Check Database State Changes
```bash
# Connect to SQLite database
sqlite3 ../db/detection_data.db

# View all sessions
SELECT * FROM sessions;

# View division state changes
SELECT frame_number, timestamp, state, walking_area_waiters, service_area_waiters
FROM division_states
WHERE session_id = '20251114_194300'
ORDER BY frame_number;

# View table state changes
SELECT frame_number, table_id, state, customers_count, waiters_count
FROM table_states
WHERE session_id = '20251114_194300'
ORDER BY frame_number;
```

### View Screenshots
```bash
# Screenshots saved automatically on every state change
ls -la ../db/screenshots/[session_id]/

# Division state changes
ls -la ../db/screenshots/[session_id]/division_*.jpg

# Table state changes
ls -la ../db/screenshots/[session_id]/T1_*.jpg
```

## Configuration Files

**Location:** All configuration files are stored in `scripts/config/`

### config/table_region_config.json
**Structure:**
```json
{
  "division": [[x1,y1], [x2,y2], ...],
  "tables": [
    {
      "id": "T1",
      "polygon": [[x1,y1], ...],
      "sitting_area_ids": ["SA1", "SA2"]
    }
  ],
  "sitting_areas": [
    {
      "id": "SA1",
      "polygon": [[x1,y1], ...],
      "table_id": "T1"
    }
  ],
  "service_areas": [
    {
      "id": "SV1",
      "polygon": [[x1,y1], ...]
    }
  ],
  "frame_size": [1920, 1080],
  "video": "../videos/camera_35.mp4"
}
```

**Current Setup:** 5 tables, 10 sitting areas, 2 service areas (1920x1080)

## ROI Hierarchy and Logic

### Region Priority (Assignment Order)
1. **Tables** - Individual table surfaces
2. **Sitting Areas** - Chairs/seating (linked to tables)
3. **Service Areas** - Bar, POS, prep stations
4. **Walking Areas** - Implicit (remaining division area)

### Table State Logic
```
IDLE (Green):     customers=0 AND waiters=0
BUSY (Yellow):    customers>0 AND waiters=0
CLEANING (Blue):  waiters>0 (any count)
```

### Division State Logic
```
RED (Understaffed): service_waiters=0 AND walking_waiters=0
YELLOW (Busy):      service_waiters>0 (staff at service area)
GREEN (Serving):    walking_waiters>0 (staff in walking area)
```

**Debouncing:** All state transitions require 1.0s stability to prevent flickering.

## Performance Characteristics

**Validated 2025-11-13 on RTX 3060 Linux:**
- Processing Speed: 3.24x real-time at 5fps
- GPU Utilization: 71.4% (stable)
- Frame Time: 61.7ms/frame average
- Capacity: 100 hours in 17.1 hours (dual-threaded)

**Production Workload:**
- 10 cameras × 10 hours = 100 hours daily footage
- Overnight processing: 11 PM - 6 AM (7 hours available)
- Current performance: Completes in 17.1 hours (needs optimization or dual-threaded)

## Database Schema

**sessions** - Video processing sessions
```sql
session_id TEXT PRIMARY KEY
video_file TEXT
start_time TEXT
end_time TEXT
total_frames INTEGER
fps REAL
resolution TEXT
config_file TEXT
```

**division_states** - Division state changes
```sql
session_id TEXT
frame_number INTEGER
timestamp REAL
state TEXT (RED/YELLOW/GREEN)
walking_area_waiters INTEGER
service_area_waiters INTEGER
screenshot_path TEXT
```

**table_states** - Table state changes
```sql
session_id TEXT
frame_number INTEGER
timestamp REAL
table_id TEXT
state TEXT (IDLE/BUSY/CLEANING)
customers_count INTEGER
waiters_count INTEGER
screenshot_path TEXT
```

## Output Files

**Video Output:**
- Location: `../results/`
- Format: H.264 MP4 (hardware accelerated)
- Naming: `table_and_region_state_detection_[input_name].mp4`
- Compression: ~90% smaller than raw (H.264 vs uncompressed)

**Database Output:**
- Location: `../db/detection_data.db`
- All state transitions logged with timestamps
- Indexed for fast queries by session/frame/table

**Screenshots:**
- Location: `../db/screenshots/[session_id]/`
- Saved automatically on every state change
- Quality: 95% JPEG
- Naming: `[prefix]frame_[number].jpg`

## Development Notes

**Model Paths:**
- Relative to script location: `../models/yolov8m.pt`
- Relative to script location: `../models/waiter_customer_classifier.pt`
- Both models must exist or script fails on startup

**Detection Parameters:**
```python
PERSON_CONF_THRESHOLD = 0.3  # Person detection confidence
STAFF_CONF_THRESHOLD = 0.5   # Staff classification confidence
MIN_PERSON_SIZE = 40         # Minimum bbox size (pixels)
STATE_DEBOUNCE_SECONDS = 1.0 # State transition debounce
```

**Color Coding:**
```python
# Table states
IDLE: (0, 255, 0)      # Green
BUSY: (0, 255, 255)    # Yellow
CLEANING: (255, 0, 0)  # Blue

# Division states
RED: (0, 0, 255)       # Understaffed
YELLOW: (0, 255, 255)  # Busy
GREEN: (0, 255, 0)     # Serving

# ROI boundaries
Division: (255, 255, 0)     # Cyan
Service: (255, 0, 255)      # Magenta
Sitting: (128, 128, 128)    # Gray
```

## Deployment Checklist

**Before deploying to RTX 3060:**
1. ✅ Models present in `models/` directory
2. ✅ Configuration file created (run interactive mode first)
3. ⏳ 10-camera RTSP connections configured
4. ⏳ Cloud upload pipeline (Supabase) setup
5. ⏳ Cron job for automated scheduling
6. ⏳ Error handling and health monitoring
7. ⏳ Disk space monitoring (videos + screenshots + DB)

## Important Warnings

1. **Scripts reorganized into feature directories** - See `scripts/STRUCTURE.md` for navigation
2. **DO NOT modify production scripts directly** - Test in `tests/test-scripts/` first
3. **DO NOT run interactive mode on production videos** - Use pre-created configs
4. **Monitor disk space** - H.264 videos + screenshots + DB can grow quickly
5. **Database grows infinitely** - Implement rotation/cleanup policy
6. **Screenshot directory grows** - Consider cleanup after video upload
7. **GPU memory leak risk** - Monitor long-running processes
8. **RTSP connection stability** - Handle reconnection gracefully

## Next Steps for Production

1. **Batch Processing Scripts** - Process 10 cameras sequentially/parallel
2. **RTSP Integration** - Live camera feeds vs recorded video
3. **Cloud Upload Pipeline** - Results to Supabase after processing
4. **Cron Scheduling** - Automated daily processing (11 PM - 6 AM)
5. **Error Handling** - Graceful failures, retry logic, alerts
6. **Monitoring Dashboard** - Real-time status, GPU usage, disk space
7. **Database Cleanup** - Auto-rotate old sessions, compress screenshots
