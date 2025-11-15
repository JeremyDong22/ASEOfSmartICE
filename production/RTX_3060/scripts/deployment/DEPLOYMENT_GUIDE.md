# Deployment Guide - Multi-Restaurant Setup

Quick reference for deploying ASE surveillance system to new restaurant locations.

Version: 1.0.0
Last Updated: 2025-11-15

---

## Prerequisites

1. **Hardware:**
   - NVIDIA RTX 3060 machine (Linux)
   - Network access to restaurant cameras
   - Internet connection for Supabase sync

2. **Software:**
   - Python 3.7+
   - SQLite3
   - Supabase Python client
   - OpenCV (for camera testing)

3. **Credentials:**
   - Supabase URL and anon key (in environment variables)

---

## Deployment Steps

### Step 1: Install Dependencies

```bash
# Install Python packages
pip install supabase opencv-python ultralytics

# Set environment variables
export SUPABASE_URL="https://wdpeoyugsxqnpwwtkqsl.supabase.co"
export SUPABASE_ANON_KEY="your_key_here"

# Add to ~/.bashrc for persistence
echo 'export SUPABASE_URL="https://wdpeoyugsxqnpwwtkqsl.supabase.co"' >> ~/.bashrc
echo 'export SUPABASE_ANON_KEY="your_key_here"' >> ~/.bashrc
```

---

### Step 2: Migrate Database (First Time Only)

```bash
cd /path/to/production/RTX_3060/scripts/deployment

# Migrate to new schema (creates backup automatically)
python3 migrate_database.py --backup
```

**Output:**
- Adds `locations`, `cameras`, `camera_rois` tables
- Adds `location_id` columns to existing tables
- Creates `sync_queue` and `sync_status` tables

---

### Step 3: Initialize Restaurant

```bash
cd /path/to/production/RTX_3060/scripts/deployment

# Run interactive wizard
python3 initialize_restaurant.py
```

**The wizard will ask:**

1. **City:** e.g., "Mianyang", "Chengdu"
2. **Restaurant Name:** e.g., "YeBaiLingHotpot"
3. **Commercial Area:** e.g., "1958CommercialDistrict"
4. **Address:** (optional)
5. **Region/Province:** (optional, default: "Sichuan")

**Then for each camera:**

1. **IP Address:** e.g., "202.168.40.35"
2. **Camera Name:** (optional, default: "Camera #")
3. **Division/Area Name:** (optional, e.g., "A区")
4. **Resolution:** (optional, e.g., "2592x1944")
5. **RTSP Endpoint:** (optional, uses default if blank)

Press Enter on empty IP to finish camera input.

**What it does:**
- Generates unique `location_id` (e.g., `mianyang_yebailinghotpot_1958commercialdistrict`)
- Generates `camera_id` from IP (e.g., `202.168.40.35` → `camera_35`)
- Tests camera connections (if OpenCV installed)
- Registers in local database
- Syncs to Supabase cloud
- Creates configuration files

---

### Step 4: Set Up ROI Configuration

```bash
cd /path/to/production/RTX_3060/scripts

# Run interactive ROI setup
./run_interactive.sh

# Or manually:
python3 video_processing/table_and_region_state_detection.py \
    --video ../videos/camera_35.mp4 \
    --interactive
```

**Workflow:**
1. Draw Division boundary (overall monitored area)
2. For each table: Draw table surface → Draw sitting areas → Press 'D'
3. Draw Service Areas (bar, POS, prep stations)
4. Press Ctrl+S to save to `config/table_region_config.json`

**See:** `CLAUDE.md` for detailed ROI setup instructions

---

### Step 5: Test Video Processing

```bash
cd /path/to/production/RTX_3060/scripts

# Process test video with existing config
python3 video_processing/table_and_region_state_detection.py \
    --video ../videos/camera_35.mp4 \
    --duration 60  # Process only 60 seconds for testing
```

**Check outputs:**
- `../results/YYYYMMDD/camera_XX/` - Processed video
- `../db/detection_data.db` - State changes
- `../db/screenshots/camera_XX/` - Auto-saved screenshots

---

### Step 6: Set Up Supabase Sync

```bash
cd /path/to/production/RTX_3060/scripts/database_sync

# Dry run (test without uploading)
python3 sync_to_supabase.py --mode hourly --dry-run

# Actual sync
python3 sync_to_supabase.py --mode hourly
```

**Install cron job for automatic hourly sync:**

```bash
# Edit crontab
crontab -e

# Add these lines:
# Hourly sync during operating + processing hours
0 11-23 * * * cd /path/to/production/RTX_3060/scripts/database_sync && python3 sync_to_supabase.py --mode hourly >> /var/log/ase_sync.log 2>&1

# Full sync at 3 AM (catch-up)
0 3 * * * cd /path/to/production/RTX_3060/scripts/database_sync && python3 sync_to_supabase.py --mode full >> /var/log/ase_sync.log 2>&1
```

---

### Step 7: Start Recording

```bash
cd /path/to/production/RTX_3060/scripts/video_capture

# Start RTSP stream capture
python3 capture_rtsp_streams.py
```

**Default behavior:**
- Records from all cameras in `cameras_config.json`
- Saves to `videos/YYYYMMDD/camera_XX/`
- Auto-reconnects on network failures
- Segmented files (new file every 10 minutes or on disconnect)

---

## Configuration Files

**After initialization, you'll have:**

```
production/RTX_3060/scripts/config/
├── {location_id}_location.json       # Location details
├── {location_id}_cameras.json        # All cameras for this location
├── cameras_config.json               # Simple camera_id → IP mapping
└── table_region_config.json          # ROI configuration (per camera)
```

**Example `{location_id}_cameras.json`:**
```json
[
  {
    "camera_id": "camera_35",
    "location_id": "mianyang_yebailinghotpot_1958commercialdistrict",
    "camera_name": "Front Area Camera",
    "camera_ip_address": "202.168.40.35",
    "rtsp_endpoint": "rtsp://202.168.40.35:554/cam/realmonitor?...",
    "camera_type": "UNV",
    "resolution": "2592x1944",
    "division_name": "A区",
    "status": "active"
  }
]
```

---

## Database Structure

**Local SQLite (`db/detection_data.db`):**
- 24-hour transactional buffer
- Fast writes during processing
- Auto-cleanup after sync

**Supabase Cloud:**
- `ASE_locations` - Restaurant master data
- `ASE_cameras` - Camera configurations
- `ASE_division_states` - Division state changes (90 days)
- `ASE_table_states` - Table state changes (90 days)
- `ASE_sessions` - Processing sessions (90 days)

**See:** `db/CLAUDE.md` for complete schema documentation

---

## Multi-Location Support

**Unique Restaurant Identification:**

Each restaurant is uniquely identified by:
1. City
2. Restaurant Name
3. Commercial Area

**Generated `location_id`:**
```
{city}_{restaurant}_{area}
```
Example: `mianyang_yebailinghotpot_1958commercialdistrict`

**Why this matters:**
- Different restaurants can have same camera IP addresses (e.g., 192.168.1.100)
- `location_id` ensures cameras are distinguished by restaurant
- Supabase cloud database can manage multiple locations simultaneously

**Example scenario:**
```
Location 1: mianyang_yebailinghotpot_1958commercialdistrict
  ├── camera_35 (202.168.40.35)
  └── camera_22 (202.168.40.22)

Location 2: chengdu_yebailinghotpot_chunxilu
  ├── camera_35 (192.168.1.35)  ← Same camera_id, different IP, different location
  └── camera_40 (192.168.1.40)

Supabase query to distinguish:
SELECT * FROM ASE_cameras WHERE location_id = 'mianyang_yebailinghotpot_1958commercialdistrict';
```

---

## Common Issues

### Issue: "No location found in database"

**Solution:**
```bash
python3 scripts/deployment/initialize_restaurant.py
```

### Issue: Supabase sync fails

**Check:**
```bash
# Environment variables set?
echo $SUPABASE_URL
echo $SUPABASE_ANON_KEY

# Internet connectivity?
ping supabase.co

# Python package installed?
pip list | grep supabase
```

### Issue: Camera connection fails

**Check:**
1. Camera IP reachable: `ping 202.168.40.35`
2. RTSP endpoint correct (check camera manual)
3. Network allows RTSP traffic (port 554)

---

## Performance Optimization

**New in v2.0.0:**

1. **Batch Database Commits** (100× faster)
   - Used automatically in video processing
   - Reduces database writes from 37 minutes → 22 seconds

2. **Smart Sync Strategy**
   - Local: 24-hour buffer (fast writes)
   - Cloud: Hourly upload (lightweight, database-only)
   - No media files uploaded (screenshots/videos stay local)

3. **Intelligent Disk Cleanup**
   - Predictive space monitoring
   - Proactive cleanup before running out
   - See: `scripts/monitoring/check_disk_space.py`

---

## Monitoring

**Check system health:**
```bash
cd /path/to/production/RTX_3060/scripts/monitoring

# Disk space
python3 check_disk_space.py --check

# GPU status
python3 monitor_gpu.py

# Full health check
python3 system_health.py
```

**Check sync status:**
```bash
# In SQLite
sqlite3 db/detection_data.db "SELECT * FROM sync_status ORDER BY created_at DESC LIMIT 5;"

# In Supabase (via web UI)
# https://app.supabase.com → Table Editor → ASE_sync_status
```

---

## Next Steps After Deployment

1. **Verify data flow:**
   - Local database receiving state changes?
   - Supabase receiving synced data?
   - Screenshots being saved?

2. **Set up monitoring:**
   - Cron jobs for disk space checks
   - Email alerts on failures
   - Dashboard for real-time status

3. **Configure retention:**
   - Adjust cleanup policies if needed
   - Set up automated reports
   - Plan for long-term analytics

---

## Support

**Documentation:**
- `production/RTX_3060/CLAUDE.md` - System overview
- `production/RTX_3060/db/CLAUDE.md` - Cloud database schema
- `production/RTX_3060/scripts/STRUCTURE.md` - Scripts organization

**Troubleshooting:**
- Check logs: `/var/log/ase_sync.log`
- Run with `--dry-run` flag to test without changes
- Use `--help` on any script for detailed usage

**Schema Version:** 2.0.0
**Last Updated:** 2025-11-15
