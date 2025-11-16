# Automated Surveillance System - Deployment Guide

**Version:** 2.0.0
**Created:** 2025-11-16
**System:** Fully Automated Production Deployment

## Overview

This is a **fully automated restaurant surveillance system**. After the one-time initialization, the entire system runs automatically with NO manual intervention required.

### What Changed (v2.0.0)

**Before (Manual Operation):**
- Start script shows interactive menu
- User manually selects "Start Video Capture"
- User manually selects "Process Videos"
- User manually runs monitoring scripts
- ❌ Requires constant manual management

**Now (Fully Automated):**
- Initialize once → Everything runs automatically
- Video capture: Auto-starts at 11 AM, auto-stops at 9 PM
- Video processing: Auto-starts at 11 PM, auto-stops at 6 AM
- System monitoring: Runs continuously in background
- Database sync: Syncs hourly automatically
- ✅ ZERO manual intervention after initialization

---

## Quick Start (3 Steps)

### Step 1: Initialize System (One-Time)

```bash
cd /home/smartahc/smartice/ASEOfSmartICE/production/RTX_3060
python3 start.py
```

This will:
1. Run database migration
2. Register restaurant location
3. Configure cameras
4. Generate configuration files

### Step 2: Install Auto-Start Service (One-Time)

```bash
cd scripts/deployment
sudo bash install_service.sh
```

This will:
1. Install systemd service
2. Enable auto-start on boot
3. Configure proper permissions

### Step 3: Start the Service

```bash
python3 start.py
```

**That's it!** The system is now fully automated.

---

## System Architecture

### Automated Components

```
Main Service (surveillance_service.py)
├─ Scheduler Thread
│  ├─ 11:00 AM → Start video capture
│  ├─ 9:00 PM → Stop video capture
│  ├─ 11:00 PM → Start video processing
│  └─ 6:00 AM → Stop video processing
│
├─ Monitoring Threads (Background)
│  ├─ Disk Space Check (every 1 hour)
│  ├─ GPU Monitoring (every 5 minutes)
│  ├─ Database Sync (every 1 hour)
│  └─ Health Check (every 30 minutes)
│
└─ Auto-Recovery
   ├─ Restart capture if crashes
   ├─ Restart processing if crashes
   └─ Auto-cleanup disk space
```

### Daily Workflow (Automatic)

```
11:00 AM ───────────────── 9:00 PM
   ↓                          ↓
   Start Capture          Stop Capture
   (10 cameras)          (10 hours footage)

11:00 PM ───────────────── 6:00 AM
   ↓                          ↓
   Start Processing      Processing Complete
   (100 hours footage)   (Ready for next day)

Continuous (24/7)
├─ Monitor disk space
├─ Monitor GPU temperature
├─ Sync database to cloud
└─ Auto-cleanup old files
```

---

## Service Management

### Basic Commands

```bash
# Start service (runs in background)
python3 start.py

# Check service status
python3 start.py --status

# Stop service
python3 start.py --stop

# Restart service
python3 start.py --restart

# Run in foreground (debug mode)
python3 start.py --foreground
```

### Systemd Commands (Linux)

```bash
# Start service
sudo systemctl start ase_surveillance

# Stop service
sudo systemctl stop ase_surveillance

# Restart service
sudo systemctl restart ase_surveillance

# Check status
sudo systemctl status ase_surveillance

# View live logs
sudo journalctl -u ase_surveillance -f

# Disable auto-start on boot
sudo systemctl disable ase_surveillance

# Enable auto-start on boot
sudo systemctl enable ase_surveillance
```

---

## Monitoring & Logs

### Log Files

```bash
# Main service log
tail -f logs/surveillance_service.log

# System journal (if using systemd)
sudo journalctl -u ase_surveillance -f

# Individual component logs
tail -f /var/log/ase_*.log
```

### Health Checks

The system automatically monitors:
- **Disk Space**: Checks every hour, auto-cleanup if < 100GB
- **GPU Temperature**: Monitors every 5 minutes, alerts if > 80°C
- **Process Health**: Checks every 30 minutes, auto-restart if crashed
- **Database Sync**: Syncs to Supabase every hour

### Manual Health Check

```bash
# Check system health
python3 start.py --status

# Check disk space manually
python3 scripts/monitoring/check_disk_space.py --check

# Check GPU manually
python3 scripts/monitoring/monitor_gpu.py
```

---

## Automatic Behaviors

### Video Capture
- **Start Time**: 11:00 AM (automatic)
- **End Time**: 9:00 PM (automatic)
- **Cameras**: All enabled cameras (from config)
- **Auto-Restart**: If capture crashes, restarts automatically
- **Auto-Segmentation**: Creates new segment on network disconnect

### Video Processing
- **Start Time**: 11:00 PM (automatic)
- **End Time**: 6:00 AM (automatic)
- **Target**: All unprocessed videos from previous day
- **GPU Scaling**: Automatically scales workers based on temperature
- **Auto-Skip**: Skips already processed videos

### Disk Space Management
- **Check Frequency**: Every hour
- **Prediction**: Calculates remaining space needed
- **Auto-Cleanup**: Deletes old files if space < 100GB
- **Protected**: Always keeps today + yesterday

### Database Sync
- **Frequency**: Every hour
- **Mode**: Incremental (last 2 hours only)
- **Target**: Supabase cloud database
- **Retry**: Auto-retries on failure

---

## Troubleshooting

### Service Won't Start

```bash
# Check if already running
python3 start.py --status

# Check logs for errors
tail -50 logs/surveillance_service.log

# Try foreground mode to see errors
python3 start.py --foreground
```

### Capture Not Starting

```bash
# Check if in capture window (11 AM - 9 PM)
date

# Check camera configuration
cat scripts/config/cameras_config.json

# Test camera connections
python3 scripts/camera_testing/test_camera_connections.py
```

### Processing Not Starting

```bash
# Check if in processing window (11 PM - 6 AM)
date

# Check if videos exist
ls -la videos/$(date +%Y%m%d)/

# Check GPU availability
python3 scripts/monitoring/monitor_gpu.py
```

### Disk Space Issues

```bash
# Check disk space
df -h

# Run manual cleanup
python3 scripts/monitoring/check_disk_space.py --cleanup

# See what's using space
du -sh videos/* results/* db/screenshots/*
```

---

## Configuration Files

### Main Configuration

```
scripts/config/
├── cameras_config.json          # Camera IP addresses and settings
├── table_region_config.json     # ROI configuration for detection
└── ybl_mianyang_location.json   # Restaurant location info
```

### Editing Configuration

```bash
# Edit camera configuration
nano scripts/config/cameras_config.json

# After editing, restart service
python3 start.py --restart
```

---

## Auto-Start on Boot

### Installation

```bash
# Install systemd service (one-time)
cd scripts/deployment
sudo bash install_service.sh
```

### Verification

```bash
# Check if enabled
sudo systemctl is-enabled ase_surveillance

# Should output: enabled
```

### Testing Auto-Start

```bash
# Reboot system
sudo reboot

# After reboot, check if service started
sudo systemctl status ase_surveillance
```

---

## Performance Metrics

### Expected Behavior

**Daily Video Volume:**
- 10 cameras × 10 hours = 100 hours raw footage
- ~200 GB/day raw video storage
- ~20 GB/day processed video storage

**Processing Capacity:**
- RTX 3060: 3.24x real-time at 5fps
- 100 hours processed in ~17 hours
- Fits within 7-hour overnight window with dual workers

**Disk Space Usage:**
- Raw videos: Deleted after processing (2-day retention max)
- Processed videos: 2-day retention
- Screenshots: 30-day retention
- Database: Permanent (never deleted)

### Monitoring Dashboard

```bash
# Watch service status
watch -n 5 'python3 start.py --status'

# Watch GPU temperature
watch -n 5 'python3 scripts/monitoring/monitor_gpu.py'

# Watch disk space
watch -n 60 'df -h'
```

---

## Emergency Procedures

### Stop Everything Immediately

```bash
# Method 1: Via start.py
python3 start.py --stop

# Method 2: Via systemd
sudo systemctl stop ase_surveillance

# Method 3: Kill process
pkill -f surveillance_service.py
```

### Free Disk Space Urgently

```bash
# Auto-cleanup with prediction
python3 scripts/monitoring/check_disk_space.py --cleanup

# Manual cleanup (delete processed videos)
rm -rf results/$(date -d "3 days ago" +%Y%m%d)/
```

### Reset Service

```bash
# Stop service
python3 start.py --stop

# Remove PID file
rm -f surveillance_service.pid

# Start fresh
python3 start.py
```

---

## Maintenance Schedule

### Daily (Automatic)
- Video capture during business hours
- Video processing overnight
- Disk space monitoring and cleanup
- Database sync to cloud

### Weekly (Manual - Optional)
- Review service logs for errors
- Check database integrity
- Verify cloud sync status

### Monthly (Manual - Optional)
- Review disk space trends
- Update camera configurations if needed
- Check GPU performance metrics

---

## Key Differences from v1.0

| Feature | v1.0 (Manual) | v2.0 (Automated) |
|---------|---------------|------------------|
| Video Capture | Manual start via menu | Auto-start at 11 AM |
| Video Processing | Manual start via menu | Auto-start at 11 PM |
| Monitoring | Manual execution | Background threads |
| Database Sync | Manual trigger | Hourly automatic |
| Disk Cleanup | Manual check | Predictive auto-cleanup |
| Service Start | Interactive menu | Single command |
| Recovery | Manual restart | Auto-restart on failure |
| Boot Behavior | Manual start | Auto-start with system |

---

## Support

### View Logs

```bash
# Service log
tail -100 logs/surveillance_service.log

# System journal
sudo journalctl -u ase_surveillance -n 100

# All logs
tail -f logs/*.log
```

### Common Questions

**Q: How do I know if it's working?**
```bash
python3 start.py --status
```

**Q: How do I stop it temporarily?**
```bash
python3 start.py --stop
```

**Q: How do I add a new camera?**
1. Edit `scripts/config/cameras_config.json`
2. Restart service: `python3 start.py --restart`

**Q: What if it crashes?**
- Service auto-restarts automatically
- Check logs to see what happened
- Report issue if recurring

---

## Summary

**One-Time Setup:**
1. `python3 start.py` (initialize)
2. `sudo bash scripts/deployment/install_service.sh` (install service)
3. Done! ✅

**Daily Operation:**
- Nothing! System runs automatically
- Optional: Check status occasionally

**That's it! The system is now fully automated.**

No more manual menu selections. No more manual script execution. Just initialize once and let it run! 🚀
