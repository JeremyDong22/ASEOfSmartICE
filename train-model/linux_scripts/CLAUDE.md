# Linux Scripts CLAUDE.md

## Business Purpose

Automated screenshot capture system for RTX 3060 machines deployed in restaurants. Captures screenshots from 8 surveillance cameras every 5 minutes and uploads to Supabase cloud storage for AI model training.

## How to Run

### 1. Start Complete System (Recommended)
```bash
./camera_surveillance_master.sh start    # Start everything
./camera_surveillance_master.sh status   # Check if running
./camera_surveillance_master.sh stop     # Stop everything
./camera_surveillance_master.sh restart  # Restart system
```

### 2. Manual Capture (Testing)
```bash
python3 linux_capture_screenshots_to_supabase_resilient.py
```

### 3. Sync Failed Uploads
```bash
python3 sync_backup_queue.py         # Upload pending files
python3 sync_backup_queue.py --stats # Check backup queue status
```

## How Each File Works

### `camera_surveillance_master.sh`
- **Purpose**: Master controller that manages everything
- **What it does**:
  - Installs cron job (runs every hour 11 AM - 9 PM)
  - Monitors system health continuously
  - Auto-restarts failed processes
  - Creates logs in `logs/master_YYYYMMDD.log`

### `camera_capture_wrapper.sh`
- **Purpose**: Process manager called by cron
- **What it does**:
  - Checks if capture is already running (PID lock)
  - Starts Python capture script if needed
  - Enforces 11 AM - 10 PM operating hours
  - Creates logs in `logs/capture_YYYYMMDD.log`

### `linux_capture_screenshots_to_supabase_resilient.py`
- **Purpose**: Main capture script
- **What it does**:
  - Captures from 8 cameras every 5 minutes
  - Uploads to Supabase storage
  - Saves locally if upload fails (`backup_queue/`)
  - Runs max 1hr 59min or until 10 PM
  - Tracks uploads in SQLite database

### `sync_backup_queue.py`
- **Purpose**: Recovery tool for failed uploads
- **What it does**:
  - Reads SQLite tracking database
  - Retries failed uploads from `backup_queue/`
  - Deletes local files after successful upload

## Camera Credentials

### High Resolution (2592x1944)
- **camera_27**: `rtsp://admin:a12345678@202.168.40.27:554/Streaming/Channels/102`
- **camera_28**: `rtsp://admin:123456@202.168.40.28:554/Streaming/Channels/102`

### Medium Resolution (1920x1080)
- **camera_36**: `rtsp://admin:123456@202.168.40.36:554/Streaming/Channels/102`
- **camera_35**: `rtsp://admin:123456@202.168.40.35:554/Streaming/Channels/102`
- **camera_22**: `rtsp://admin:123456@202.168.40.22:554/Streaming/Channels/102`

### Low Resolution (640x360)
- **camera_24**: `rtsp://admin:a12345678@202.168.40.24:554/Streaming/Channels/102`
- **camera_26**: `rtsp://admin:a12345678@202.168.40.26:554/Streaming/Channels/102`
- **camera_29**: `rtsp://admin:a12345678@202.168.40.29:554/Streaming/Channels/102`

**Pattern**: Password is either `123456` or `a12345678` depending on camera IP

## Supabase Configuration

### Credentials (Hardcoded - Private Repo)
```python
SUPABASE_URL = "https://wdpeoyugsxqnpwwtkqsl.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
STORAGE_BUCKET = "ASE"
```

### Database Table: `ase_snapshot`
```sql
CREATE TABLE ase_snapshot (
    image_id        UUID PRIMARY KEY,
    image_url       TEXT,           -- Supabase storage URL
    camera_name     TEXT,           -- e.g., 'camera_27'
    capture_timestamp TIMESTAMP,
    resolution      TEXT,           -- e.g., '2592x1944'
    file_size_kb    NUMERIC
);
```

### Storage Structure
```
ASE/ (bucket)
├── camera_27/YYYYMMDD_HHMMSS_2592_1944.jpg
├── camera_28/YYYYMMDD_HHMMSS_2592_1944.jpg
├── camera_36/YYYYMMDD_HHMMSS_1920_1080.jpg
└── ... (other cameras)
```

## Local Backup System

### SQLite Database: `capture_tracking.db`
Tracks all capture attempts and upload status:
- `pending` - Waiting to upload
- `success` - Uploaded successfully
- `failed` - Upload failed (will retry)

### Backup Directory: `backup_queue/`
Temporarily stores images when Supabase is unreachable. Auto-deleted after successful upload.

## Schedule

- **Operating Hours**: 11 AM - 10 PM daily
- **Cron Check**: Every hour (health monitoring)
- **Capture Frequency**: Every 5 minutes
- **Script Runtime**: Max 1hr 59min per session
- **Daily Output**: ~1,056 images (132 per camera)

## Troubleshooting

```bash
# Check if running
ps aux | grep linux_capture

# View logs
tail -f logs/capture_$(date +%Y%m%d).log

# Check backup queue
python3 sync_backup_queue.py --stats

# Manual test single camera
python3 -c "import cv2; print(cv2.VideoCapture('rtsp://admin:123456@202.168.40.36:554/Streaming/Channels/102').isOpened())"

# Fix stuck process
rm /tmp/camera_capture.pid
./camera_surveillance_master.sh restart
```

## Quick Start

1. **First Time Setup**:
```bash
cd train-model/linux_scripts
chmod +x *.sh
./camera_surveillance_master.sh start
```

2. **Daily Operations**:
- System runs automatically 11 AM - 10 PM
- Check status: `./camera_surveillance_master.sh status`
- Manual sync if needed: `python3 sync_backup_queue.py`

3. **Data Flow**:
```
RTX 3060 Machine → Capture → Supabase → AI Training Pipeline
                       ↓ (if fail)
                  Local Backup → Retry Upload
```