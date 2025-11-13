# Linux RTX Video Streaming

**Last Updated:** 2025-11-13

## Business Purpose

Video capture system for Linux RTX 3060 machines in restaurants. Three main systems:
1. **5-minute quick captures** (legacy, for testing)
2. **1-hour continuous captures** (production, for peak hours 7-8 PM)
3. **Performance testing** (RTX 3060 GPU analysis for table-state-detection) ⭐ NEW

All systems support camera_22 and camera_35 (1920x1080 resolution) with Supabase cloud storage integration.

---

## Folder Structure

```
linux_rtx_video_streaming/
├── CLAUDE.md                              # This file
│
├── previous_5min_captures/                # Legacy: 5-minute capture system
│   ├── capture_video_streams.py           # Original 5-min capture script
│   ├── background_upload.py               # Background upload utilities
│   ├── compress_and_upload*.py            # Compression tools
│   ├── upload_*.py                        # Various upload strategies
│   ├── videos/                            # Old video storage
│   └── upload_logs/                       # Old upload logs
│
├── scheduled_1hour_capture_7pm_8pm/       # 1-hour scheduled system
│   ├── capture_1hour_continuous.py        # 1-hour continuous capture
│   ├── background_upload_worker.py        # Upload with 5-8 hour timeout
│   ├── run_scheduled_1hour_capture.sh     # Main runner script
│   ├── setup_cron_7pm.sh                  # Cron setup helper
│   ├── README.md                          # Detailed documentation
│   ├── videos/                            # Video storage (~3-5 GB per camera)
│   ├── logs/                              # Execution logs
│   └── upload_queue.json                  # Upload queue tracker
│
└── performance_test_20251113/             # ⭐ NEW: Performance test results
    ├── README.md                          # Complete test report
    ├── performance_analysis.py            # Full performance analysis
    ├── performance_comparison_5fps.py     # 20fps vs 5fps comparison
    └── timing_log.txt                     # Test execution timing
```

---

## System Comparison

### Previous System (5-Minute Captures)

**Location:** `previous_5min_captures/`

| Feature | Value |
|---------|-------|
| **Duration** | 5 minutes per capture |
| **File Size** | ~400-600 MB per video |
| **Upload** | Immediate (often timed out) |
| **Use Case** | Quick testing, ad-hoc captures |
| **Status** | Legacy / archived |

**Key Script:** `capture_video_streams.py`

```bash
cd previous_5min_captures
python3 capture_video_streams.py
```

---

### New System (1-Hour Continuous) ⭐ RECOMMENDED

**Location:** `scheduled_1hour_capture_7pm_8pm/`

| Feature | Value |
|---------|-------|
| **Duration** | 1 hour continuous (7-8 PM) |
| **File Size** | ~3-5 GB per camera |
| **Upload** | Background with 5-8 hour timeout |
| **Use Case** | Production peak-hour data collection |
| **Status** | Active / production-ready |

**Key Features:**
- ✅ Captures full hour of restaurant activity
- ✅ Large file handling (~6-10 GB total)
- ✅ Non-blocking background upload
- ✅ Automatic daily scheduling via cron
- ✅ Local backup always saved first
- ✅ Extended upload timeout (configurable 5-8 hours)

**Quick Start:**
```bash
cd scheduled_1hour_capture_7pm_8pm

# Setup automatic daily capture at 7 PM
./setup_cron_7pm.sh

# Or manual test run
./run_scheduled_1hour_capture.sh
```

**See:** `scheduled_1hour_capture_7pm_8pm/README.md` for complete documentation

---

## Key Differences from Screenshot Capture

| Feature | Screenshot Capture | Video Streaming (5-min) | Video Streaming (1-hour) |
|---------|-------------------|------------------------|-------------------------|
| **Location** | `train-model/linux_rtx_screenshot_capture/` | `previous_5min_captures/` | `scheduled_1hour_capture_7pm_8pm/` |
| **Purpose** | Training data | Quick testing | Production data |
| **Cameras** | All 8 cameras | camera_22 + camera_35 | camera_22 + camera_35 |
| **Output** | JPG images | MP4 videos (5 min) | MP4 videos (1 hour) |
| **Schedule** | Every 5 min, 11 AM-10 PM | On-demand | Daily 7-8 PM |
| **File Size** | ~100-800 KB | ~400-600 MB | ~3-5 GB |
| **Upload** | Immediate | Immediate | Background (5-8 hr timeout) |

---

## Target Cameras

### camera_22 (1920x1080)
- **RTSP URL**: `rtsp://admin:123456@202.168.40.22:554/Streaming/Channels/102`
- **Resolution**: 1920x1080
- **Password**: `123456`
- **FPS**: 20

### camera_35 (1920x1080)
- **RTSP URL**: `rtsp://admin:123456@202.168.40.35:554/Streaming/Channels/102`
- **Resolution**: 1920x1080
- **Password**: `123456`
- **FPS**: 20

---

## Recommended Usage

### For Production (Peak Hours Monitoring)
Use the **1-hour scheduled system**:
```bash
cd scheduled_1hour_capture_7pm_8pm
./setup_cron_7pm.sh  # One-time setup
# System runs automatically every day at 7 PM
```

### For Quick Testing
Use the **5-minute system**:
```bash
cd previous_5min_captures
python3 capture_video_streams.py
```

---

## Supabase Configuration

### Storage
- **Bucket**: `ASE` (shared with screenshot system)
- **Path (5-min)**: `videos/camera_XX/YYYYMMDD_HHMMSS_1920_1080.mp4`
- **Path (1-hour)**: `videos/camera_XX/YYYYMMDD_HHMMSS_1920_1080_1hour.mp4`
- **Public URL**: `https://wdpeoyugsxqnpwwtkqsl.supabase.co/storage/v1/object/public/ASE/videos/...`

### Database Table: `ase_video_stream`
```sql
CREATE TABLE ase_video_stream (
    video_id UUID PRIMARY KEY,
    video_url TEXT,                -- Supabase storage URL
    camera_name TEXT,              -- 'camera_22' or 'camera_35'
    capture_timestamp TIMESTAMPTZ, -- Stored in UTC (UTC+0)
    resolution TEXT,               -- '1920x1080'
    file_size_mb NUMERIC,          -- File size in MB
    duration_seconds INTEGER,      -- Video duration
    fps INTEGER,                   -- Frames per second (20)
    upload_duration_seconds INT,   -- Upload time (for 1-hour system)
    video_type TEXT,               -- '5min' or '1hour_continuous'
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Note**: All timestamps stored in UTC (UTC+0). Beijing time = UTC + 8 hours.

---

## Migration Notes

**2025-11-10:** Reorganized folder structure
- Moved all 5-minute capture scripts to `previous_5min_captures/`
- Created new `scheduled_1hour_capture_7pm_8pm/` for production system
- Old videos and logs archived in respective folders
- Both systems remain functional and independent

**Usage Recommendation:**
- **New projects**: Use `scheduled_1hour_capture_7pm_8pm/`
- **Legacy compatibility**: `previous_5min_captures/` still works
- **Testing**: Either system works, 1-hour system preferred for production

---

## Common Commands

### 1-Hour System (Recommended)
```bash
cd scheduled_1hour_capture_7pm_8pm

# Setup automatic scheduling
./setup_cron_7pm.sh

# Manual run (full pipeline)
./run_scheduled_1hour_capture.sh

# Capture only (no upload)
./run_scheduled_1hour_capture.sh --no-upload

# Background upload with custom timeout
python3 background_upload_worker.py --timeout 10  # 10 hours

# Check logs
tail -f logs/run_$(date +%Y%m%d).log
```

### 5-Minute System (Legacy)
```bash
cd previous_5min_captures

# Single 5-minute capture
python3 capture_video_streams.py

# Test Supabase connection
python3 test_supabase_upload.py

# Upload existing videos
python3 upload_existing_videos.py
```

### Performance Testing (2025-11-13) ⭐ NEW
```bash
cd performance_test_20251113

# Run full performance analysis
python3 performance_analysis.py

# Run 20fps vs 5fps comparison
python3 performance_comparison_5fps.py

# View complete test report
cat README.md

# View test timing log
cat timing_log.txt
```

**Quick Results Summary:**
- **Test Video**: 5 minutes, 1920x1080, 395 MB
- **20fps Processing**: 8 minutes (0.62x real-time)
- **5fps Processing**: 1.5 minutes (3.24x real-time) ⚡
- **Speedup**: 5.2x faster with 5fps
- **Production**: Dual-threaded 5fps can process 100 hours in 17.1 hours ✅

See `performance_test_20251113/README.md` for detailed analysis.

---

## Troubleshooting

### For 1-Hour System Issues
See: `scheduled_1hour_capture_7pm_8pm/README.md` (comprehensive troubleshooting guide)

### For 5-Minute System Issues
See: `previous_5min_captures/SUPABASE_STATUS.md` (legacy documentation)

### Common Issues (Both Systems)

**Camera Connection Failed:**
```bash
# Test RTSP connection
python3 -c "import cv2; cap = cv2.VideoCapture('rtsp://admin:123456@202.168.40.22:554/Streaming/Channels/102'); print(cap.isOpened())"
```

**Upload Timeout:**
- 5-min system: Often fails with large files (400+ MB)
- 1-hour system: Use `--timeout` flag to extend (default 8 hours)

**Disk Space Full:**
```bash
# Check space
df -h .

# Clean old videos (5-min system)
find previous_5min_captures/videos/ -name "*.mp4" -mtime +7 -delete

# Clean old videos (1-hour system)
find scheduled_1hour_capture_7pm_8pm/videos/ -name "*.mp4" -mtime +7 -delete
```

---

## Documentation Links

- **Main Project**: `../../CLAUDE.md` (root documentation)
- **Test Model**: `../CLAUDE.md` (test-model folder)
- **1-Hour System**: `scheduled_1hour_capture_7pm_8pm/README.md` ⭐
- **5-Min System**: `previous_5min_captures/SUPABASE_STATUS.md`
- **Performance Test**: `performance_test_20251113/README.md` ⭐ NEW

---

## Performance Test Results (2025-11-13) ⭐

### Test Overview
Comprehensive RTX 3060 GPU performance analysis for table-state-detection system, comparing full-frame (20fps) vs frame-skipping (5fps) processing.

### Key Findings
✅ **5fps processing is production-ready**
- Processing speed: **3.24x faster than real-time**
- 5-minute video processed in **1.5 minutes**
- Bottleneck: Staff classification (76.5% of processing time)

### Production Scenario (10 cameras × 10 hours/day)
| Configuration | Processing Time | Status |
|--------------|----------------|--------|
| Single-thread 20fps | 160 hours | ❌ Not feasible |
| Single-thread 5fps | 31 hours | ❌ Exceeds 24h |
| **Dual-thread 5fps** | **17.1 hours** | ✅ **Recommended** |
| Five-thread 5fps | 8.8 hours | ✅ Optimal |

### Optimization Potential
- YOLOv8n (lighter model): **2-3x** additional speedup
- TensorRT optimization: **1.5-2x** additional speedup
- Combined: **10-15x total** speedup possible

**See full report:** `performance_test_20251113/README.md`

---

*This folder contains three systems: legacy 5-minute captures for testing, 1-hour continuous captures for production peak-hour monitoring, and performance test results for table-state-detection optimization.*
