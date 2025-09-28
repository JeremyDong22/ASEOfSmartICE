# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ASEOfSmartICE is an ONVIF protocol integration and H.265/H.264 stream analysis project for IP surveillance cameras. This minimal experimental project focuses on camera connectivity testing, ONVIF protocol analysis, and real-time stream preview capabilities.

## Core Architecture

### Components Structure
- **`test/`** - ONVIF discovery and connection testing utilities
- **`sub-stream/`** - Flask-based web interface for camera stream preview
- **`model/`** - YOLO object detection models (YOLOv8s, YOLOv10s)
- **`onvif_profiles_raw.xml`** - Raw ONVIF profile configuration data

### Key Functionality
1. **ONVIF Protocol Testing** - Network discovery and compatibility testing for IP cameras
2. **Web Stream Preview** - Real-time RTSP stream viewing via Flask web interface  
3. **Camera Connection Analysis** - Multi-protocol connectivity assessment

## Tech Stack

### Core Dependencies
- **Python 3.7+** - Primary development language
- **Flask** - Web framework for stream preview interface
- **OpenCV (cv2)** - Video capture and RTSP stream processing
- **NumPy** - Array operations for image processing
- **requests** - HTTP/SOAP communication for ONVIF testing

### System Requirements  
- **FFmpeg** - Required by OpenCV for RTSP stream compatibility
- Network access to target IP cameras (202.168.40.37, 202.168.40.21)

## Common Commands

### Core Operations
```bash
# Generate ONVIF connection analysis report
python3 test/connection_methods_summary.py

# Start web-based camera stream preview
python3 sub-stream/web_stream_preview.py
# Access at: http://localhost:5001

# 🚀 PRODUCTION: Start complete surveillance system (NEW!)
train-model/linux_scripts/camera_surveillance_master.sh start
# Genius 1hr 59min design eliminates race conditions with smart cron management
```

### Production System Management
```bash
# Start/stop/restart complete surveillance system
./camera_surveillance_master.sh {start|stop|status|restart}

# Monitor system logs
tail -f train-model/linux_scripts/logs/capture_$(date +%Y%m%d).log
tail -f train-model/linux_scripts/logs/master_$(date +%Y%m%d).log

# Check database status
sqlite3 train-model/linux_scripts/capture_tracking.db "SELECT COUNT(*) FROM upload_tracking;"
```

### Development and Testing
```bash
# Verify Python environment
python3 --version

# Test camera RTSP connectivity
ffprobe -v quiet -show_streams rtsp://admin:a12345678@IP:554/Streaming/Channels/102

# Manual camera web interface access
open http://202.168.40.37
open http://202.168.40.21
```

### Network Diagnostics
```bash
# Basic connectivity testing
ping 202.168.40.37
telnet 202.168.40.37 554  # RTSP port
telnet 202.168.40.37 80   # HTTP port
```

## Code Conventions

### File Organization
- Descriptive snake_case filenames indicating clear functionality
- Version headers with purpose documentation in all Python files
- Feature-based directory structure for logical separation

### Python Style
- **snake_case** for variables, functions, and filenames
- **UPPER_CASE** for configuration constants (IPs, URLs, passwords)
- **Descriptive naming** that clearly indicates purpose and scope
- **Emoji-enhanced logging** for visual clarity (🎥, ✅, ❌, 🔍)

### Error Handling Pattern
```python
try:
    # Network/camera operation with explicit timeout
    operation(timeout=5)
except SpecificException:
    print("❌ Specific error description")
except Exception as e:
    print(f"❌ General error: {e}")
```

### Threading and Concurrency
- Global variables with threading locks for frame sharing
- Daemon threads for background video capture
- Graceful shutdown handling for network connections

## Camera Configuration

### Verified Working Cameras (8/9 tested)

#### High Resolution Cameras (2592x1944)
- **202.168.40.27**: admin/a12345678 @ 20 FPS
  - RTSP: `rtsp://admin:a12345678@202.168.40.27:554/Streaming/Channels/102`
- **202.168.40.28**: admin/123456 @ 20 FPS  
  - RTSP: `rtsp://admin:123456@202.168.40.28:554/Streaming/Channels/102`

#### Medium Resolution Cameras (1920x1080)
- **202.168.40.36**: admin/123456 @ 20 FPS
- **202.168.40.35**: admin/123456 @ 20 FPS
- **202.168.40.22**: admin/123456 @ 20 FPS

#### Low Resolution Cameras (640x360)
- **202.168.40.24**: admin/a12345678 @ 25 FPS
- **202.168.40.26**: admin/a12345678 @ 25 FPS
- **202.168.40.29**: admin/a12345678 @ 25 FPS

### Authentication Patterns
- **Password 123456**: Works for IPs ending in 28, 36, 35, 22
- **Password a12345678**: Works for IPs ending in 27, 24, 26, 29
- **Failed**: 202.168.40.34 (no response to either password)

### Stream Endpoints
- **Sub-stream (recommended)**: `/Streaming/Channels/102` - Better stability, validated on all cameras
- **Main stream**: `/Streaming/Channels/101` - Higher resolution (not tested)
- **RTSP Port**: 554 (confirmed working on all cameras)
- **Username**: admin (consistent across all cameras)

## Development Notes

### Project Status
This is a minimal experimental codebase focused on ONVIF protocol analysis and camera stream testing. The project contains core functionality for camera connectivity assessment but lacks comprehensive dependency management (no requirements.txt or virtual environment).

### Installation Dependencies
Manual installation required for core libraries:
```bash
pip3 install flask opencv-python numpy requests
```

### ONVIF Protocol Support
Current testing indicates target cameras may not fully support standard ONVIF protocols, requiring fallback to direct RTSP connections for reliable streaming functionality.

## Supabase Integration

### Database Configuration
- **Project URL**: `https://wdpeoyugsxqnpwwtkqsl.supabase.co`
- **Anon Key**: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndkcGVveXVnc3hxbnB3d3RrcXNsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDQxNDgwNzgsImV4cCI6MjA1OTcyNDA3OH0.9bUpuZCOZxDSH3KsIu6FwWZyAvnV5xPJGNpO3luxWOE`
- **Storage Bucket**: `ASE` (public bucket for camera screenshots)

### Database Schema

#### Table: `ase_snapshot` (lowercase!)
Stores metadata for all surveillance camera screenshots:

```sql
CREATE TABLE public.ase_snapshot (
    image_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    image_url TEXT NOT NULL,                    -- Supabase storage URL
    camera_name TEXT NOT NULL,                  -- e.g., 'camera_27', 'camera_36'
    restaurant_id TEXT,                          -- NULL for now, future multi-location support
    capture_timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    resolution TEXT,                             -- e.g., '2592x1944', '1920x1080'
    file_size_kb NUMERIC,                        -- File size in KB
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_ase_snapshot_camera_name ON public.ase_snapshot(camera_name);
CREATE INDEX idx_ase_snapshot_capture_timestamp ON public.ase_snapshot(capture_timestamp);
CREATE INDEX idx_ase_snapshot_restaurant_id ON public.ase_snapshot(restaurant_id);

-- Row Level Security enabled with public access policies
```

### Storage Structure
```
ASE/ (bucket)
├── camera_27/           # High-res camera (2592x1944)
│   └── YYYYMMDD_HHMMSS_2592_1944.jpg
├── camera_28/           # High-res camera (2592x1944)
├── camera_36/           # Medium-res camera (1920x1080)
├── camera_35/           # Medium-res camera (1920x1080)
├── camera_22/           # Medium-res camera (1920x1080)
├── camera_24/           # Low-res camera (640x360)
├── camera_26/           # Low-res camera (640x360)
├── camera_29/           # Low-res camera (640x360)
└── test/                # Test uploads
```

### Local Backup Database (SQLite)
Location: `train-model/linux_scripts/capture_tracking.db`

```sql
CREATE TABLE upload_tracking (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT UNIQUE NOT NULL,
    camera_name TEXT NOT NULL,
    local_path TEXT NOT NULL,
    capture_timestamp DATETIME NOT NULL,
    upload_status TEXT DEFAULT 'pending',  -- pending/success/failed/missing
    upload_attempts INTEGER DEFAULT 0,
    last_attempt DATETIME,
    supabase_url TEXT,
    error_message TEXT,
    file_size_kb REAL,
    resolution TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Upload Flow
1. Camera capture → Save locally to `backup_queue/camera_XX/`
2. Try Supabase upload → If success, delete local copy
3. If fail → Keep local, mark as 'pending' in SQLite
4. Background retry every 10 minutes or manual sync

### Important Notes
- **Table name is lowercase**: Use `ase_snapshot` not `ASE_Snapshot`
- **Credentials are hardcoded**: Safe for private repository
- **Resilient design**: Never loses data even if Supabase is down
- **Auto-retry mechanism**: Failed uploads retry automatically

## 🧠 Genius 1hr 59min Design

### The Race Condition Problem (Solved!)
Previous system had a critical race condition:
1. Python script runs for exactly 2 hours, then exits
2. Cron runs every 2 hours to restart script
3. **Race condition**: When script exits at same time cron checks if it's running
4. Result: 2-hour gaps in surveillance (13:00-15:00, etc.)

### The Genius Solution
- **Python runtime**: Changed from 2.0 hours to **1.98 hours (1hr 59min)**
- **Smart timing**: Script exits 1 minute BEFORE cron restart
- **Master controller**: `camera_surveillance_master.sh` provides monitoring and auto-recovery
- **Result**: Zero gaps, perfect continuity, self-healing system

### Production Architecture (2-Script System)
```
camera_surveillance_master.sh (main controller)
├── Auto-installs cron: 0 11,13,15,17,19,21 * * *
├── Continuous monitoring and auto-recovery
├── Calls camera_capture_wrapper.sh when needed
└── Logs: master_YYYYMMDD.log

camera_capture_wrapper.sh (process manager)
├── Cron-triggered every 2 hours (11AM-10PM)
├── Manages Python process lifecycle (PID files, logging)
├── Time-based control and graceful shutdown
└── Logs: capture_YYYYMMDD.log

linux_capture_screenshots_to_supabase_resilient.py (worker)
├── Runs for 1.98 hours then gracefully exits
├── Captures every 5 minutes from 8 cameras
└── Uploads to Supabase with local backup resilience
```

### Script Dependencies
- **setup_cron.sh**: ❌ **Removed** - Master script handles cron installation automatically
- **camera_surveillance_master.sh**: ✅ **Required** - Main system controller
- **camera_capture_wrapper.sh**: ✅ **Required** - Called by master for process management