# Test Folder - Camera Testing & Network Analysis

**Last Updated:** 2025-11-11

## Purpose

This folder contains camera connection testing scripts, RTSP stream analysis, and network bandwidth planning tools. Used for validating camera configurations before deploying to production video capture systems.

---

## Key Findings (2025-11-11)

### ✅ UNV Camera Direct Connection Success

**Discovery:** Successfully identified and tested UNV (宇视/Uniview) direct camera RTSP paths.

**Previous Setup (Incorrect):**
- Path: `/Streaming/Channels/101` (NVR/Hikvision format)
- Issue: Connecting through NVR, not direct camera
- Bitrate: Uncontrollable, very high (~160+ Mbps)

**New Setup (Correct):**
- Path: `/media/video1` (UNV direct camera format)
- Benefit: Direct camera connection
- Bitrate: **5.4 Mbps** (optimal for storage and bandwidth)
- Resolution: **2592x1944 (5MP)**
- FPS: **20**
- Codec: **H.264**

### 📊 Network Bandwidth Analysis

For **10 cameras @ 5.4 Mbps each**:

| Metric | Value |
|--------|-------|
| Total Bandwidth | 54 Mbps |
| Daily Storage | 58.3 GB |
| Monthly Storage | 1.7 TB |
| Network Required | **Gigabit Ethernet** (5.4% utilization) |

**Conclusion:** Gigabit network is more than sufficient. No need for 10G equipment.

---

## Test Scripts

### Main Testing Scripts

#### `test_mainstream_h265_headers.py`
Tests H.265 parameter headers (VPS/SPS/PPS) for UNV cameras.

**Finding:** UNV cameras have incomplete H.265 headers when using Hikvision NVR paths. Using direct camera paths with H.264 codec resolves all issues.

```bash
# Test specific camera
python3 test_mainstream_h265_headers.py 22  # Tests IP .22
python3 test_mainstream_h265_headers.py 35  # Tests IP .35
```

#### `test_resolution_and_bandwidth.py`
Measures actual stream bitrate, resolution, and calculates multi-camera bandwidth requirements.

```bash
python3 test_resolution_and_bandwidth.py
```

**Output:** Bandwidth analysis JSON file + network planning recommendations

#### `test_unv_direct_path.py`
Compares UNV direct camera paths vs NVR paths side-by-side.

```bash
python3 test_unv_direct_path.py
```

**Purpose:** Validates that UNV direct paths work and provides better control.

#### `test_image_quality_corruption.py`
Analyzes video frame quality to detect H.265 corruption artifacts (color blocks, incomplete frames).

```bash
python3 test_image_quality_corruption.py
```

**Use Case:** Verify image quality after codec/bitrate changes.

### Legacy Testing Scripts

- `camera_connection_agent.py` - Tests multiple cameras with password attempts
- `simple_functionality_test.py` - Quick connectivity + YOLO detection test
- `compare_cameras_ucode.py` - Compares UNV cameras with UCode on vs off
- `compare_before_after_adjustment.py` - Compares camera settings before/after changes
- `visual_comparison_report.py` - Generates image quality comparison reports

---

## Correct RTSP Paths (2025-11-11)

### UNV Direct Camera Format ✅ RECOMMENDED

```python
# Main stream (high quality)
rtsp://admin:123456@202.168.40.22:554/media/video1

# Sub stream (lower quality, bandwidth-saving)
rtsp://admin:123456@202.168.40.22:554/media/video2
```

### Old NVR Format ❌ NOT RECOMMENDED

```python
# This connects through NVR, not direct camera
rtsp://admin:123456@202.168.40.22:554/Streaming/Channels/101  # Main
rtsp://admin:123456@202.168.40.22:554/Streaming/Channels/102  # Sub
```

**Why Direct Path is Better:**
- ✅ Lower bitrate (5.4 Mbps vs 160+ Mbps)
- ✅ Direct camera control
- ✅ No NVR transcoding overhead
- ✅ Better for multi-camera systems

---

## Camera Configurations

### Camera 22
- **IP:** `202.168.40.22`
- **RTSP Main:** `rtsp://admin:123456@202.168.40.22:554/media/video1`
- **Resolution:** 2592x1944 (5MP)
- **Codec:** H.264
- **Bitrate:** 5.4 Mbps
- **FPS:** 20

### Camera 35
- **IP:** `202.168.40.35`
- **RTSP Main:** `rtsp://admin:123456@202.168.40.35:554/media/video1`
- **Resolution:** 2592x1944 (5MP)
- **Codec:** H.264
- **Bitrate:** 5.4 Mbps
- **FPS:** 20

---

## Test Data Files

### JSON Test Results
- `mainstream_h265_test_*.json` - H.265 parameter header tests
- `bandwidth_analysis_*.json` - Network bandwidth measurements
- `unv_path_test_results.json` - RTSP path comparison
- `*_quality_report.json` - Image quality analysis

### Video Samples
- `test_5sec_original.mp4` - 5-second raw stream capture
- `test_5sec_compressed.mp4` - 5-second re-encoded at lower bitrate
- Used for bitrate validation

### Image Samples
- `image_quality_samples/` - Frame captures for visual quality comparison
  - `IP_35_UCode_ON/` - Frames with UCode enabled
  - `IP_22_UCode_OFF/` - Frames with UCode disabled

---

## Common Commands

### Quick Connection Test
```bash
# Test if camera is reachable
ffprobe -rtsp_transport tcp rtsp://admin:123456@202.168.40.22:554/media/video1

# Capture 5-second test video
ffmpeg -rtsp_transport tcp -i "rtsp://admin:123456@202.168.40.22:554/media/video1" -t 5 -c copy test.mp4
```

### Check All Working Cameras
```bash
python3 camera_connection_agent.py
```

### Bandwidth Planning
```bash
python3 test_resolution_and_bandwidth.py
# Check output JSON for multi-camera bandwidth calculations
```

---

## Integration with Production

### Video Capture System
**Location:** `../test-model/linux_rtx_video_streaming/`

**Update Applied (2025-11-11):**
- Changed from NVR paths to UNV direct camera paths
- Updated to use main stream (`/media/video1`) instead of sub stream
- Resolution upgraded: 1920x1080 → 2592x1944
- Bitrate optimized: ~160 Mbps → 5.4 Mbps

**File Modified:**
```
test-model/linux_rtx_video_streaming/scheduled_1hour_capture_7pm_8pm/capture_1hour_continuous.py
```

---

## Key Learnings

### 1. UNV RTSP Path Discovery
- UNV cameras use `/media/videoX` format, not Hikvision `/Streaming/Channels/XXX`
- Direct camera paths provide better bitrate control
- Agent research confirmed this is standard Uniview format

### 2. Bitrate Optimization
- Original measurement (OpenCV JPEG estimation): 160-230 Mbps ❌
- Actual measurement (direct recording): 5.4 Mbps ✅
- Key learning: Always validate with actual video recording, not frame estimation

### 3. H.264 vs H.265 for UNV
- H.265: Missing VPS/PPS headers, decoder warnings
- H.264: Clean decode, no warnings, similar file size
- **Recommendation:** Use H.264 for UNV cameras

### 4. Network Planning
- 10 cameras @ 5.4 Mbps = 54 Mbps total
- Gigabit network has 20x overhead (1000 Mbps / 54 Mbps)
- Monthly storage: 1.7 TB (manageable with 2-4TB HDD)

---

## Troubleshooting

### Camera Won't Connect
```bash
# Check network connectivity
ping 202.168.40.22

# Test RTSP with ffprobe
ffprobe rtsp://admin:123456@202.168.40.22:554/media/video1

# Try alternate paths
ffprobe rtsp://admin:123456@202.168.40.22:554/Streaming/Channels/101
```

### High Bitrate Issues
1. Confirm using direct camera path (`/media/video1`)
2. Check camera web interface for bitrate settings
3. Verify actual bitrate with 5-second recording:
```bash
ffmpeg -i rtsp://... -t 5 -c copy test.mp4
ls -lh test.mp4  # Should be ~3-4 MB for 5 seconds at 5.4 Mbps
```

### H.265 Header Warnings
- Switch to H.264 codec in camera web interface
- UNV cameras have known H.265 header issues with some decoders
- H.264 provides better compatibility

---

## Related Documentation

- **Main Project:** `../CLAUDE.md`
- **Video Capture System:** `../test-model/linux_rtx_video_streaming/CLAUDE.md`
- **Training Pipeline:** `../train-model/CLAUDE.md`

---

*This test folder validates camera configurations and network requirements before production deployment. All findings from 2025-11-11 testing have been applied to the production video capture system.*
