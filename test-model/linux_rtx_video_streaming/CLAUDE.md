# Linux RTX Video Streaming

## Business Purpose

Video capture system for Linux RTX 3060 machines in restaurants. Records 5-minute video streams from camera_22 and camera_35 (both 1920x1080 resolution) and uploads to Supabase cloud storage for model testing and validation.

## Key Differences from Screenshot Capture

| Feature | Screenshot Capture | Video Streaming |
|---------|-------------------|-----------------|
| **Location** | `train-model/linux_rtx_screenshot_capture/` | `test-model/linux_rtx_video_streaming/` |
| **Purpose** | Collect training data | Real-time testing |
| **Cameras** | All 8 cameras | camera_22 + camera_35 only |
| **Output** | JPG screenshots to Supabase | Live video stream |
| **Schedule** | Every 5 minutes, 11 AM - 10 PM | Continuous on-demand |

## Target Cameras

### camera_22 (1920x1080)
- **RTSP URL**: `rtsp://admin:123456@202.168.40.22:554/Streaming/Channels/102`
- **Resolution**: 1920x1080
- **Password**: `123456`

### camera_35 (1920x1080)
- **RTSP URL**: `rtsp://admin:123456@202.168.40.35:554/Streaming/Channels/102`
- **Resolution**: 1920x1080
- **Password**: `123456`

## Scripts

### `capture_video_streams.py`
Main video capture script that records 5-minute streams from both cameras simultaneously.

**Features:**
- ✅ Parallel recording from camera_22 and camera_35
- ✅ 5-minute duration per camera
- ✅ Automatic Supabase upload after capture
- ✅ Database metadata tracking
- ✅ Automatic timestamp naming
- ✅ Progress updates every 30 seconds
- ✅ MP4 format output (H.264 compatible)
- ✅ Local backup if upload fails

**Configuration:**
- Duration: 300 seconds (5 minutes)
- FPS: 20 frames per second
- Resolution: 1920x1080
- Output: `videos/camera_XX_YYYYMMDD_HHMMSS.mp4`

## Usage

### Basic Recording
```bash
cd test-model/linux_rtx_video_streaming
python3 capture_video_streams.py
```

### Output
- Videos saved to: `videos/`
- Filename format: `camera_22_20251020_143052.mp4`
- File size: ~400-600 MB per 5-minute video

### What Happens
1. Script connects to both cameras simultaneously
2. Records for 5 minutes from each camera in parallel
3. Shows progress updates every 30 seconds
4. Saves timestamped MP4 files to `videos/` folder
5. Uploads videos to Supabase storage (`ASE/videos/camera_XX/`)
6. Saves metadata to `ase_video_stream` database table
7. Displays final statistics (duration, frames, file size, upload status)

## Supabase Configuration

### Storage
- **Bucket**: `ASE` (same as screenshot system)
- **Path**: `videos/camera_XX/YYYYMMDD_HHMMSS_1920_1080.mp4`
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
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Note**: All timestamps stored in UTC (UTC+0). Beijing time = UTC + 8 hours.

## Notes

This folder is specifically for testing models with video streams from high-quality 1080p cameras. Videos are automatically uploaded to cloud storage for easy access and model validation testing.
