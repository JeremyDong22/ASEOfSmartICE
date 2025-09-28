# Linux Scripts CLAUDE.md

This file provides guidance for Claude Code when working with the Linux automation scripts in this directory.

## System Overview

Automated surveillance camera screenshot capture system running from 11 AM to 10 PM daily, with Supabase cloud storage integration and local backup resilience.

## Architecture

```
Camera Network (8 cameras) → Python Capture Script → Local Backup + Supabase Upload
                                    ↓
                            Cron Scheduler (2-hour segments)
                                    ↓
                            Shell Wrapper (Process Management)
```

## Key Components

### 1. **linux_capture_screenshots_to_supabase_resilient.py** (Main)
- **Purpose**: Resilient camera capture with automatic failover
- **Features**:
  - Captures from 8 cameras every 5 minutes
  - **OpenCV + FFmpeg fallback** for H.265/HEVC compatibility
  - **Enhanced connection testing** (5s timeout, 3 retries per method)
  - Local backup queue for network failures
  - SQLite tracking database
  - Auto-retry mechanism (10-minute intervals)
  - Graceful shutdown at 10 PM
- **Data Flow**: Camera → OpenCV Test → FFmpeg Fallback → Local Save → Upload

### 2. **camera_capture_wrapper.sh**
- **Purpose**: Process management and scheduling enforcement
- **Features**:
  - PID file locking (prevents duplicates)
  - Time-based control (11 AM - 10 PM)
  - Automatic restart every 2 hours
  - Centralized logging
- **Usage**: Called by cron every 2 hours

### 3. **sync_backup_queue.py**
- **Purpose**: Manual recovery tool for failed uploads
- **Commands**:
  - `python3 sync_backup_queue.py` - Upload pending items
  - `python3 sync_backup_queue.py --stats` - Show statistics
  - `python3 sync_backup_queue.py --cleanup` - Remove old records

### 4. **setup_cron.sh**
- **Purpose**: Interactive cron configuration
- **Schedule**: 11 AM, 1 PM, 3 PM, 5 PM, 7 PM, 9 PM

## Data Storage

### Local Storage Structure
```
linux_scripts/
├── capture_tracking.db      # SQLite tracking database
├── backup_queue/            # Local backup directory
│   ├── camera_27/          # High-res camera backups
│   ├── camera_28/          # High-res camera backups
│   ├── camera_36/          # Medium-res camera backups
│   └── ...                 # Other camera folders
└── logs/                   # Local log files (if /var/log unavailable)
```

### Supabase Structure
- **Storage Bucket**: `ASE`
- **Table**: `ASE_Snapshot`
- **Path Format**: `camera_XX/YYYYMMDD_HHMMSS_WIDTH_HEIGHT.jpg`

## Database Schema

### SQLite (capture_tracking.db)
```sql
upload_tracking:
- id (Primary Key)
- filename (Unique)
- camera_name
- local_path
- capture_timestamp
- upload_status (pending/success/failed/missing)
- upload_attempts
- last_attempt
- supabase_url
- error_message
- file_size_kb
- resolution
```

### Supabase (ASE_Snapshot)
```sql
- image_id (UUID, Primary Key)
- image_url (Text)
- camera_name (Text)
- restaurant_id (Text, nullable)
- capture_timestamp (Timestamp WITH TIME ZONE, stored in UTC)
- resolution (Text)
- file_size_kb (Numeric)
```

**⚠️ TIMEZONE NOTE**: Supabase stores `capture_timestamp` in **UTC timezone**, while local SQLite uses Beijing time (UTC+8). When querying Supabase:
- UTC 05:00-07:00 = Beijing 13:00-15:00
- Use `AT TIME ZONE 'Asia/Shanghai'` for Beijing time conversion

## Failure Recovery Mechanism

### Network Failure Handling
1. **Primary Path**: Direct upload to Supabase
2. **Fallback**: Save to local `backup_queue/` directory
3. **Recovery**: Auto-retry every 10 minutes
4. **Manual Sync**: Run `sync_backup_queue.py` when needed

### Process Management
- **PID Locking**: Prevents duplicate processes
- **Stale Lock Recovery**: Auto-removes dead PIDs
- **Time Enforcement**: Auto-stops at 10 PM
- **Crash Recovery**: Cron restarts every 2 hours

## Camera Configuration

### Working Cameras (8 verified)
```json
High Resolution (2592x1944):
- 202.168.40.27: admin/a12345678
- 202.168.40.28: admin/123456

Medium Resolution (1920x1080):
- 202.168.40.36: admin/123456
- 202.168.40.35: admin/123456
- 202.168.40.22: admin/123456

Low Resolution (640x360):
- 202.168.40.24: admin/a12345678
- 202.168.40.26: admin/a12345678
- 202.168.40.29: admin/a12345678
```

## Credentials (Private Repository)

Hardcoded in scripts for simplicity (safe for private repo):
- **Supabase URL**: wdpeoyugsxqnpwwtkqsl.supabase.co
- **Anon Key**: Embedded in Python scripts
- **Camera Passwords**: In configuration

## Cron Schedule Logic

```
11:00 AM → Run 2 hours → Stop at 1:00 PM
 1:00 PM → Run 2 hours → Stop at 3:00 PM
 3:00 PM → Run 2 hours → Stop at 5:00 PM
 5:00 PM → Run 2 hours → Stop at 7:00 PM
 7:00 PM → Run 2 hours → Stop at 9:00 PM
 9:00 PM → Run 1 hour  → Stop at 10:00 PM
```

## Daily Statistics

- **Capture Frequency**: Every 5 minutes
- **Camera Success Rate**: 6/8 cameras (75% with FFmpeg fallback)
- **Daily Images**: ~864 (108 per active camera)
- **Storage Usage**: 8-12 GB/day
- **Upload Success Rate**: Typically >95%
- **Backup Queue Size**: <100 MB (temporary)

### Camera Compatibility Status
- **✅ Working**: camera_22, 24, 26, 29, 35, 36 (6/8)
- **❌ H.265 Issues**: camera_27, 28 (OpenCV + FFmpeg both struggle)

## Troubleshooting Guide

### Common Issues

1. **Camera Connection Failures**
   ```bash
   ping 202.168.40.XX
   telnet 202.168.40.XX 554
   ffprobe -v quiet -show_streams rtsp://admin:password@IP:554/Streaming/Channels/102
   ```
   **Note**: H.265/HEVC cameras may fail OpenCV tests but work with FFmpeg fallback

2. **Supabase Upload Failures**
   - Check: `python3 sync_backup_queue.py --stats`
   - Manual sync: `python3 sync_backup_queue.py`

3. **Process Not Starting**
   ```bash
   rm /tmp/camera_capture.pid
   ./camera_capture_wrapper.sh
   ```

4. **Disk Space Issues**
   ```bash
   df -h
   python3 sync_backup_queue.py --cleanup
   ```

## Testing Commands

### Manual Test Run
```bash
cd train-model/linux_scripts
python3 linux_capture_screenshots_to_supabase_resilient.py
```

### Check Status
```bash
# View logs
tail -f logs/capture_$(date +%Y%m%d).log

# Check backup queue
python3 sync_backup_queue.py --stats

# Monitor process
ps aux | grep linux_capture
```

## Performance Metrics

- **CPU Usage**: ~5% during capture, idle between
- **Memory**: ~200 MB Python process
- **Network**: 8 cameras × 1.5 MB = ~12 MB per round
- **Disk I/O**: Minimal (SQLite + JPEG writes)

## Future Enhancements

### Planned Features
- Restaurant ID integration for multi-location support
- Real-time alerting for camera failures
- Web dashboard for monitoring
- Motion detection triggers
- Compressed archive exports

### Optimization Opportunities
- Implement image compression before upload
- Add WebP format support
- Create hourly summary reports
- Implement smart retry backoff

## Dependencies

```bash
# Required Python packages
pip3 install opencv-python requests

# System requirements
- Python 3.7+
- FFmpeg (for OpenCV)
- SQLite3
- 20 GB free disk space (recommended)
```

## Security Notes

- Private repository deployment (credentials safe)
- Row Level Security enabled on Supabase tables
- Local backup encryption (future enhancement)
- PID file in /tmp (world-writable, process-specific)

## Maintenance Tasks

### Weekly
- Check backup queue: `sync_backup_queue.py --stats`
- Clean old records: `sync_backup_queue.py --cleanup`

### Monthly
- Review camera connectivity logs
- Analyze upload failure patterns
- Archive old backup images

### Quarterly
- Update camera configurations
- Review storage usage trends
- Test disaster recovery procedures