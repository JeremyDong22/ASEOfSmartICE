# Linux Camera Capture Automation

This directory contains scripts for automated surveillance camera screenshot capture with Supabase integration.

## Overview

The system captures screenshots from 8 surveillance cameras every 5 minutes from 11 AM to 10 PM daily, automatically uploading them to Supabase cloud storage.

## Components

### 1. `linux_capture_screenshots_to_supabase.py`
- Main Python script that captures screenshots from cameras
- Uploads images to Supabase storage bucket "ASE"
- Records metadata in ASE_Snapshot table
- Runs for maximum 2 hours per execution (designed for cron restart)
- Automatically stops at 10 PM

### 2. `camera_capture_wrapper.sh`
- Shell wrapper that manages the Python script execution
- Handles process management with PID files
- Creates logs in `/var/log/camera_capture/` or local `logs/` directory
- Checks operating hours (11 AM - 10 PM)
- Prevents duplicate processes

### 3. `setup_cron.sh`
- Interactive setup script for cron job configuration
- Schedules execution at: 11 AM, 1 PM, 3 PM, 5 PM, 7 PM, 9 PM
- Each execution runs for up to 2 hours, ensuring continuous coverage

## Installation

### Prerequisites
```bash
# Install required Python packages
pip3 install opencv-python requests

# Ensure Python 3 is installed
python3 --version
```

### Setup Steps

1. **Make scripts executable:**
```bash
chmod +x camera_capture_wrapper.sh
chmod +x setup_cron.sh
```

2. **Run the setup script:**
```bash
./setup_cron.sh
```

3. **Verify cron installation:**
```bash
crontab -l
```

## Manual Execution

### Test single run:
```bash
./camera_capture_wrapper.sh
```

### Run Python script directly:
```bash
python3 linux_capture_screenshots_to_supabase.py
```

## Monitoring

### View real-time logs:
```bash
# If using system logs
tail -f /var/log/camera_capture/capture_$(date +%Y%m%d).log

# If using local logs
tail -f logs/capture_$(date +%Y%m%d).log
```

### Check process status:
```bash
ps aux | grep linux_capture_screenshots
```

### Check PID file:
```bash
cat /tmp/camera_capture.pid
```

## Supabase Configuration

- **URL:** https://wdpeoyugsxqnpwwtkqsl.supabase.co
- **Storage Bucket:** ASE
- **Table:** ASE_Snapshot
- **Image Path Format:** camera_XX/YYYYMMDD_HHMMSS_WIDTHxHEIGHT.jpg

## Database Schema

```sql
ASE_Snapshot:
- image_id (UUID, Primary Key)
- image_url (Text)
- camera_name (Text)
- restaurant_id (Text, nullable)
- capture_timestamp (Timestamp)
- resolution (Text)
- file_size_kb (Numeric)
- created_at (Timestamp)
```

## Cron Schedule

```
0 11,13,15,17,19,21 * * * /path/to/camera_capture_wrapper.sh
```

**Schedule Breakdown:**
- 11:00 AM - Runs for 2 hours (until 1:00 PM)
- 1:00 PM - Runs for 2 hours (until 3:00 PM)
- 3:00 PM - Runs for 2 hours (until 5:00 PM)
- 5:00 PM - Runs for 2 hours (until 7:00 PM)
- 7:00 PM - Runs for 2 hours (until 9:00 PM)
- 9:00 PM - Runs for 1 hour (stops at 10:00 PM)

## Troubleshooting

### Camera connection issues:
- Check network connectivity: `ping 202.168.40.XX`
- Verify RTSP port: `telnet 202.168.40.XX 554`
- Check camera credentials in configuration file

### Supabase upload failures:
- Verify API keys in Python script
- Check storage bucket permissions
- Ensure internet connectivity

### Process management:
- Remove stale PID file: `rm /tmp/camera_capture.pid`
- Kill stuck process: `pkill -f linux_capture_screenshots`
- Check disk space: `df -h`

## Stop/Disable

### Remove cron job:
```bash
crontab -e
# Delete the line containing camera_capture_wrapper.sh
```

### Stop running process:
```bash
# Check PID
cat /tmp/camera_capture.pid

# Stop gracefully
kill -TERM <PID>

# Or use the wrapper
./camera_capture_wrapper.sh stop
```

## Expected Results

- **Daily captures:** ~1,056 images (132 per camera)
- **Storage usage:** ~10-15 GB per day
- **Supabase records:** 1,056 database entries daily
- **Network load:** Minimal (5-minute intervals)