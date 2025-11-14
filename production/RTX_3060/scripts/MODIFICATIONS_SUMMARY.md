# Modifications Summary - v2.1.0 (5 FPS Processing)

## 🎯 Goal
Process video at 5 FPS instead of every frame for ~4x speedup while maintaining detection quality.

---

## 📝 All Changes with Line Numbers

### 1. Updated Version Header (Lines 2-22)
```python
"""
Table and Region State Detection System
Version: 2.1.0  # ← CHANGED from 2.0.0
Last Updated: 2025-11-14

Changes in v2.1.0:  # ← NEW SECTION
- Added --fps parameter for configurable frame processing rate (default: 5 FPS)
- Smart frame skipping based on video FPS and target FPS
- Maintains original frame numbers in database/screenshots (no renumbering)
- Updated progress display to show processed vs total frames
- ~4x speedup for 5 FPS processing (processes 1 in 4 frames for 20fps video)
"""
```

---

### 2. Enhanced PerformanceTracker Class (Lines 308-327)

#### BEFORE:
```python
def __init__(self, window_size=30):
    # ...
    self.total_frames = 0
    self.total_processing_time = 0.0
    # ...
```

#### AFTER:
```python
def __init__(self, window_size=30):
    # ...
    self.total_frames = 0           # ← MODIFIED: Total frames in video
    self.processed_frames = 0       # ← NEW: Actually processed frames
    self.total_processing_time = 0.0
    # ...

def add_frame(self, frame_time, stage1_time, stage2_time):
    """Add frame processing stats (only for processed frames)"""  # ← UPDATED DOCSTRING
    # ...
    self.processed_frames += 1  # ← CHANGED from self.total_frames += 1
    # ...

def increment_total_frames(self):  # ← NEW METHOD
    """Increment total frame count (including skipped frames)"""
    self.total_frames += 1
```

---

### 3. Updated print_summary() Method (Lines 342-372)

#### BEFORE:
```python
def print_summary(self, video_duration, original_fps):
    """Print final processing summary"""
    total_time = self.total_processing_time
    avg_fps = self.total_frames / total_time if total_time > 0 else 0

    print(f"Video Information:")
    print(f"   Total frames: {self.total_frames}")
    print(f"   Original FPS: {original_fps:.2f}")
```

#### AFTER:
```python
def print_summary(self, video_duration, original_fps, target_fps=None):  # ← ADDED target_fps
    """Print final processing summary"""
    total_time = self.total_processing_time
    avg_fps = self.processed_frames / total_time if total_time > 0 else 0  # ← CHANGED

    print(f"Video Information:")
    print(f"   Total frames: {self.total_frames}")
    print(f"   Processed frames: {self.processed_frames}")  # ← NEW LINE
    if target_fps:  # ← NEW SECTION
        skip_ratio = self.processed_frames / self.total_frames
        print(f"   Frame skip ratio: {skip_ratio:.1%} (processing at {target_fps} FPS)")
    print(f"   Original FPS: {original_fps:.2f}")
```

---

### 4. Updated process_video() Function Signature (Line 1340)

#### BEFORE:
```python
def process_video(video_path, person_detector, staff_classifier, config,
                  output_dir=None, duration_limit=None):
```

#### AFTER:
```python
def process_video(video_path, person_detector, staff_classifier, config,
                  output_dir=None, duration_limit=None, target_fps=5):  # ← ADDED target_fps=5
    """Process video with table and division state detection

    Args:
        # ... existing args ...
        target_fps: Target processing FPS (default: 5). Process at this rate instead of every frame.  # ← NEW ARG
    """
```

---

### 5. Frame Interval Calculation (Lines 1384-1403)

#### NEW CODE BLOCK:
```python
    # Video properties
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    # ... existing code ...

    # ===== MODIFIED: Calculate frame skip interval =====
    # Example: Video is 20 FPS, target is 5 FPS → process every 4th frame (interval=4)
    frame_interval = max(1, int(round(fps / target_fps))) if target_fps > 0 else 1
    expected_processed = max_frames // frame_interval
    # ===================================================

    print(f"Video Properties:")
    print(f"   Resolution: {width}x{height}")
    # ... existing prints ...

    # ===== MODIFIED: Show processing configuration =====
    print(f"\nProcessing Configuration:")
    print(f"   Target FPS: {target_fps}")
    print(f"   Frame interval: {frame_interval} (process 1 in {frame_interval} frames)")
    print(f"   Expected processed: ~{expected_processed} frames")
    print(f"   Speedup: ~{frame_interval}x faster")
    # ====================================================
```

**Example Output:**
```
Processing Configuration:
   Target FPS: 5
   Frame interval: 4 (process 1 in 4 frames)
   Expected processed: ~300 frames
   Speedup: ~4x faster
```

---

### 6. Frame Processing Loop with Smart Skipping (Lines 1485-1579)

#### BEFORE:
```python
    frame_idx = 0

    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame_idx >= max_frames:
                break

            frame_start = time.time()
            current_time = time.time()

            # Stage 1: Detect persons
            person_detections = detect_persons(person_detector, frame)
            # ... process frame ...

            tracker.add_frame(frame_time, stage1_time, stage2_time)
            frame_idx += 1

            # Progress
            if frame_idx % 30 == 0:
                print(f"   Progress: {progress:.1f}% | Frame {frame_idx}/{max_frames}")
```

#### AFTER:
```python
    frame_idx = 0

    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame_idx >= max_frames:
                break

            # ===== MODIFIED: Increment total frames (including skipped) =====
            tracker.increment_total_frames()
            # ================================================================

            # ===== MODIFIED: Smart frame skipping =====
            # Skip frames if not at the interval (e.g., skip frames 1,2,3 but process frame 0,4,8,12...)
            if frame_idx % frame_interval != 0:
                frame_idx += 1
                continue  # ← SKIP THIS FRAME
            # ==========================================

            frame_start = time.time()
            current_time = time.time()

            # Stage 1: Detect persons
            person_detections = detect_persons(person_detector, frame)
            # ... process frame ...

            tracker.add_frame(frame_time, stage1_time, stage2_time)

            # ===== MODIFIED: Maintain original frame numbers in database/screenshots =====
            # Save screenshots with ORIGINAL frame_idx (e.g., 0, 4, 8, 12 not 0, 1, 2, 3)
            screenshot_path = save_screenshot(
                annotated_frame, screenshot_dir, camera_id, session_id,
                frame_idx, prefix=f"{table.id}_")  # ← Uses original frame_idx

            log_table_state_change(
                conn, session_id, camera_id, frame_idx, current_time,  # ← Original frame_idx
                table.id, table.state.value, customers, waiters, screenshot_path)
            # ===========================================================================

            frame_idx += 1

            # ===== MODIFIED: Updated progress display =====
            if tracker.processed_frames % 30 == 0:  # ← CHANGED from frame_idx % 30
                print(f"   Progress: {progress:.1f}% | Frame {frame_idx}/{max_frames} "
                      f"(Processed: {tracker.processed_frames}/{expected_processed}) | "  # ← NEW
                      f"FPS: {tracker.get_current_fps():.2f} | DIV:{div_state} | {table_states}")
            # ===============================================
```

**Example Progress Output:**
```
Progress: 20.5% | Frame 240/1200 (Processed: 60/300) | FPS: 3.24 | DIV:GRE | T1:IDL
         ↑ Total frame number       ↑ Actually processed frames
```

---

### 7. Summary Call Update (Line 1596-1599)

#### BEFORE:
```python
        # Print summary
        tracker.print_summary(duration if duration_limit is None else duration_limit, fps)
```

#### AFTER:
```python
        # ===== MODIFIED: Pass target_fps to summary =====
        # Print summary
        tracker.print_summary(duration if duration_limit is None else duration_limit, fps, target_fps)
        # =================================================
```

---

### 8. Command Line Arguments (Lines 1670-1672)

#### NEW ARGUMENT:
```python
    # ===== MODIFIED: Added --fps parameter =====
    parser.add_argument("--fps", type=float, default=5.0,
                       help="Target processing FPS (default: 5.0). Process at this rate instead of every frame.")
    # ===========================================
```

---

### 9. Updated Examples in Help Text (Lines 1645-1660)

#### BEFORE:
```python
Examples:
  # Interactive setup mode
  python3 table_and_region_state_detection.py --video ../videos/camera_35.mp4 --interactive

  # Process with existing config
  python3 table_and_region_state_detection.py --video ../videos/camera_35.mp4 --duration 60

  # Process full video
  python3 table_and_region_state_detection.py --video ../videos/camera_35.mp4
```

#### AFTER:
```python
Examples:
  # Interactive setup mode
  python3 table_and_region_state_detection.py --video ../videos/camera_35.mp4 --interactive

  # Process with existing config at 5 FPS (default)  # ← UPDATED
  python3 table_and_region_state_detection.py --video ../videos/camera_35.mp4 --duration 60

  # Process at 10 FPS (higher quality, slower)  # ← NEW
  python3 table_and_region_state_detection.py --video ../videos/camera_35.mp4 --fps 10

  # Process at 2 FPS (emergency fast mode)  # ← NEW
  python3 table_and_region_state_detection.py --video ../videos/camera_35.mp4 --fps 2

  # Process full video
  python3 table_and_region_state_detection.py --video ../videos/camera_35.mp4
```

---

### 10. Main Function Update (Lines 1716-1719)

#### BEFORE:
```python
    success = process_video(args.video, person_detector, staff_classifier, config,
                           args.output, args.duration)
```

#### AFTER:
```python
    # ===== MODIFIED: Pass target_fps to process_video =====
    success = process_video(args.video, person_detector, staff_classifier, config,
                           args.output, args.duration, target_fps=args.fps)
    # =======================================================
```

---

## 🔍 Key Implementation Details

### Frame Number Preservation
**CRITICAL:** Original frame numbers are preserved in database and screenshots:
- Processing at 5 FPS from 20 FPS video: processes frames 0, 4, 8, 12, 16, 20...
- Database stores: frame_number = 0, 4, 8, 12, 16, 20... (NOT 0, 1, 2, 3, 4, 5...)
- Screenshot filenames: `frame_000000.jpg`, `frame_000004.jpg`, `frame_000008.jpg`...

**Why?** Temporal accuracy for event correlation and debugging.

### Frame Skipping Logic
```python
# Video FPS = 20, Target FPS = 5
# Interval = 20 / 5 = 4
# Process frames: 0, 4, 8, 12, 16, 20... (every 4th frame)

if frame_idx % frame_interval != 0:
    frame_idx += 1
    continue  # Skip this frame
```

### State Detection Validity
The 1-second debounce (`STATE_DEBOUNCE_SECONDS = 1.0`) ensures state changes are still valid:
- **At 5 FPS:** 5 consecutive frames = 1 second ✅
- **At 20 FPS (old):** 20 consecutive frames = 1 second ✅
- **Result:** Same temporal stability, valid detection

---

## 📊 Expected Performance

### Test Video (60 seconds, 20 FPS, 1200 frames)

| Mode | Frames Processed | Processing Time | Speedup |
|------|-----------------|-----------------|---------|
| Every frame (20 FPS) | 1200 | ~74s (61.7ms/frame) | 1x |
| 10 FPS | 600 | ~37s | 2x |
| **5 FPS (default)** | **300** | **~18.5s** | **4x** |
| 2 FPS (fast) | 120 | ~7.4s | 10x |

### Production Workload (10 cameras × 10 hours = 100 hours daily)

| Mode | Processing Time | Fits in 7hr Window? |
|------|----------------|---------------------|
| Every frame | ~171 hours | ❌ No |
| 10 FPS | ~85.5 hours | ❌ No |
| **5 FPS (default)** | **~42.8 hours** | ❌ No (needs dual-thread) |
| 2 FPS (fast) | **~17.1 hours** | ✅ **YES!** |

---

## ✅ Testing Checklist

Run these tests to validate the changes:

```bash
cd /Users/jeremydong/Desktop/Smartice/ASEOfSmartICE/production/RTX_3060/scripts

# Test 1: Default 5 FPS processing
python3 table_and_region_state_detection.py \
    --video ../videos/20251022/camera_35/camera_35_20251022_195212.mp4 \
    --duration 60

# Test 2: Compare with 10 FPS (should be slower, more frames)
python3 table_and_region_state_detection.py \
    --video ../videos/20251022/camera_35/camera_35_20251022_195212.mp4 \
    --duration 60 \
    --fps 10

# Test 3: Emergency fast mode (2 FPS)
python3 table_and_region_state_detection.py \
    --video ../videos/20251022/camera_35/camera_35_20251022_195212.mp4 \
    --duration 60 \
    --fps 2
```

**Verify:**
- [ ] Processing time decreases with lower FPS
- [ ] Frame numbers in database are original (0, 4, 8... not 0, 1, 2...)
- [ ] Screenshot filenames use original frame numbers
- [ ] Progress shows "Processed: X/Y" correctly
- [ ] Summary includes skip ratio and target FPS
- [ ] State changes still detected correctly

---

## 🚀 Usage Examples

```bash
# Default: 5 FPS
python3 table_and_region_state_detection.py --video video.mp4

# Higher quality: 10 FPS (2x slower, 2x more frames)
python3 table_and_region_state_detection.py --video video.mp4 --fps 10

# Emergency fast: 2 FPS (10x faster, may miss rapid changes)
python3 table_and_region_state_detection.py --video video.mp4 --fps 2

# Process every frame (v2.0.0 behavior)
python3 table_and_region_state_detection.py --video video.mp4 --fps 20  # Match video FPS
```

---

## 📌 Notes

1. **Default changed:** v2.1.0 processes at 5 FPS by default (breaking change from v2.0.0)
2. **Config files:** No changes needed, fully backward compatible
3. **Database schema:** No changes, existing databases work without modification
4. **State detection:** 1-second debounce remains valid at all FPS settings
5. **Frame preservation:** Original frame numbers maintained for temporal accuracy
