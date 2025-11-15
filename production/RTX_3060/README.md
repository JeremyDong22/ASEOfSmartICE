# ASE Restaurant Surveillance System - RTX 3060

Production deployment system for real-time restaurant monitoring using AI computer vision.

Version: 2.0.0
Last Updated: 2025-11-15

---

## 🚀 Quick Start (New Deployment)

### Step 1: Clone Repository on RTX Machine

```bash
# On remote RTX 3060 Linux machine
cd /path/to/
git clone <your-repo-url>
cd ASEOfSmartICE/production/RTX_3060
```

### Step 2: Install Dependencies

```bash
# Install Python packages
pip install opencv-python ultralytics numpy

# Optional (for future cloud sync):
# pip install supabase
```

### Step 3: Run Main Application

```bash
python3 start.py
```

That's it! The system will guide you through initialization.

---

## 📋 What start.py Does

`start.py` is the **main entry point** for the entire surveillance system. It provides:

### ✅ **Included Features:**

1. **📹 Video Capture**
   - Start RTSP recording from all cameras
   - Runs: `scripts/video_capture/capture_rtsp_streams.py`

2. **🎬 Video Processing**
   - Process all unprocessed videos (orchestrator)
   - Process specific video
   - Interactive ROI setup
   - Runs: `scripts/orchestration/process_videos_orchestrator.py`
   - Runs: `scripts/video_processing/table_and_region_state_detection.py`

3. **🔧 System Configuration**
   - View current configuration
   - Re-run restaurant initialization
   - Guided setup for cameras and location

4. **📊 View Logs**
   - Check system logs
   - View recent activity

5. **🏥 Health Check**
   - Disk space monitoring
   - GPU status
   - Database statistics

### ⚠️ **Manual Setup Required (One-Time):**

Some features require manual command-line setup (one time only):

#### **Camera Testing** (Recommended before first recording)
```bash
cd scripts/camera_testing
python3 test_camera_connections.py --validate-config ../config/cameras_config.json
```

#### **Cron Jobs** (For 24/7 automation)
```bash
cd scripts/deployment
./install_cron_jobs.sh --install
```

This sets up automated:
- Recording schedules (lunch & dinner hours)
- Nightly video processing
- Daily cleanup
- System monitoring

#### **Time Synchronization** (Beijing Time)
```bash
cd scripts/time_sync
./setup_ntp.sh  # One-time setup
```

---

## 🗄️ Database (Local Only)

**Important:** Each RTX machine has its **own local SQLite database**.

### Database Files (Ignored by Git):
```
db/detection_data.db           ← Your local database (not pushed)
db/screenshots/                ← Your local screenshots (not pushed)
```

### What Gets Pushed to GitHub:
```
db/database_schema.sql         ← Schema file (version controlled)
db/CLAUDE.md                   ← Documentation (version controlled)
```

### When You Pull on Another Machine:
1. ✅ Schema file is pulled
2. ✅ Scripts are pulled
3. ❌ Database is NOT pulled (you start fresh)
4. ❌ Screenshots are NOT pulled

**This is correct!** Each restaurant location should have its own independent database.

---

## ☁️ Cloud Sync (Disabled by Default)

Cloud synchronization to Supabase is **disabled** in this version.

To enable in the future:
1. Set environment variables:
   ```bash
   export SUPABASE_URL="your-url"
   export SUPABASE_ANON_KEY="your-key"
   ```

2. Edit `scripts/deployment/initialize_restaurant.py`:
   - Remove `return` on line 416 to enable sync

3. Use `scripts/database_sync/sync_to_supabase.py` manually if needed

---

## 📁 Directory Structure

```
production/RTX_3060/
├── start.py                 # 🚀 MAIN ENTRY POINT - Run this!
├── models/                  # AI models (tracked in git)
│   ├── yolov8m.pt
│   └── waiter_customer_classifier.pt
├── scripts/                 # All Python scripts
│   ├── deployment/          # Initial setup
│   ├── database_sync/       # Cloud sync (disabled)
│   ├── video_capture/       # RTSP recording
│   ├── video_processing/    # AI detection
│   ├── orchestration/       # Multi-camera processing
│   ├── monitoring/          # Health checks
│   └── config/              # Configuration files
├── db/                      # Database (local only)
│   ├── database_schema.sql  # Schema (tracked)
│   ├── detection_data.db    # Data (ignored)
│   ├── screenshots/         # Images (ignored)
│   └── CLAUDE.md            # Documentation (tracked)
├── videos/                  # Raw recordings (ignored)
├── results/                 # Processed videos (ignored)
└── logs/                    # System logs (ignored)
```

**Note:** Large files (videos, database, screenshots) are NOT tracked in Git.

---

## 🔄 Typical Deployment Workflow

### **On First RTX Machine (Mianyang Restaurant)**

```bash
# 1. Clone repo
git clone <repo-url>
cd production/RTX_3060

# 2. Run start.py
python3 start.py

# 3. Follow initialization wizard:
#    - City: Mianyang
#    - Restaurant: YeBaiLingHotpot
#    - Commercial Area: 1958CommercialDistrict
#    - Cameras: 202.168.40.35, 202.168.40.22, ...

# 4. Database created locally (detection_data.db)
# 5. Configuration saved (cameras_config.json)

# 6. Optional: Set up automation
cd scripts/deployment
./install_cron_jobs.sh --install
```

### **On Second RTX Machine (Chengdu Restaurant)**

```bash
# 1. Clone SAME repo
git clone <repo-url>
cd production/RTX_3060

# 2. Run start.py
python3 start.py

# 3. Follow initialization wizard:
#    - City: Chengdu
#    - Restaurant: YeBaiLingHotpot
#    - Commercial Area: ChunxiRoad
#    - Cameras: 192.168.1.35, 192.168.1.40, ...

# 4. NEW database created (detection_data.db)
#    → Independent from Mianyang!
# 5. NEW configuration (cameras_config.json)
#    → Different cameras, same structure
```

**Result:** Two independent systems, same codebase. ✅

---

## ❓ FAQ

### Q: Do I need to install anything besides Python packages?
A: No. The system uses SQLite (built-in), OpenCV, and YOLO (via ultralytics).

### Q: Will pulling latest code overwrite my database?
A: No. Your database (`.db` files) is ignored by Git and won't be affected.

### Q: Can I push my videos/screenshots to GitHub?
A: No. They're too large and are automatically ignored (see `.gitignore`).

### Q: What happens if I delete my local database?
A: You'll lose historical data but can reinitialize with `python3 start.py`.

### Q: How do I update the code?
A:
```bash
git pull
# Your local database and configs are preserved
# Only scripts and schema files are updated
```

### Q: Can two restaurants share one database?
A: No. Each location has independent database. This is by design for data isolation.

### Q: Where's the cloud sync?
A: Disabled by default. Each location runs independently with local database.

---

## 📊 System Status Files (Ignored by Git)

These files are created locally and NOT pushed:

```
db/detection_data.db           # SQLite database
db/screenshots/**/*.jpg        # All screenshots
videos/**/*.mp4                # Raw recordings
results/**/*.mp4               # Processed videos
logs/**/*.log                  # System logs
scripts/config/cameras_config.json  # May contain IPs (ignored)
```

Safe to push:
```
db/database_schema.sql         # Schema definition
db/CLAUDE.md                   # Documentation
scripts/**/*.py                # All Python scripts
models/*.pt                    # AI models (exception to *.pt rule)
CLAUDE.md                      # Project documentation
```

---

## 🔐 Security Notes

- **Camera IPs**: `cameras_config.json` is ignored to prevent exposing internal network
- **Database**: Local SQLite contains business data, not pushed for privacy
- **Credentials**: Never commit API keys or passwords

---

## 📖 Documentation

- **`CLAUDE.md`** - Complete project documentation
- **`db/CLAUDE.md`** - Database schema and cloud sync details
- **`scripts/deployment/DEPLOYMENT_GUIDE.md`** - Full deployment guide
- **`SUMMARY_zh.md`** - 中文总结（Chinese summary）

---

## 🆘 Support

Having issues? Check:
1. `python3 start.py` - Should guide you through setup
2. `scripts/deployment/DEPLOYMENT_GUIDE.md` - Complete instructions
3. Logs in `/var/log/` or `logs/` folder

---

**Version:** 2.0.0
**Entry Point:** `python3 start.py`
**Database:** Local SQLite (not synced)
**Cloud Sync:** Disabled (can enable later)
