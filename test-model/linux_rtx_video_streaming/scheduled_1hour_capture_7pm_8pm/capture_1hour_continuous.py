"""
1-Hour Continuous Video Capture Script
Created: 2025-11-10
Feature: Captures continuous 1-hour video streams from camera_22 and camera_35
         Saves locally, then triggers background upload to Supabase

Purpose: Long-duration video capture for restaurant peak hours (7-8 PM)
Usage: python3 capture_1hour_continuous.py
Output: Local videos (videos/) → Background upload to Supabase
"""

import cv2
import os
from datetime import datetime
import time
import threading
import json

# Camera configurations
# Updated 2025-11-11: Changed to UNV direct camera main stream paths
# Main stream (video1) provides higher quality than sub-stream
# Bitrate: ~5.4 Mbps, Resolution: 2592x1944 @ 20 FPS, Codec: H.264
CAMERAS = {
    'camera_22': {
        'rtsp_url': 'rtsp://admin:123456@202.168.40.22:554/media/video1',  # UNV main stream
        'resolution': (2592, 1944)  # 5MP resolution
    },
    'camera_35': {
        'rtsp_url': 'rtsp://admin:123456@202.168.40.35:554/media/video1',  # UNV main stream
        'resolution': (2592, 1944)  # 5MP resolution
    }
}

# Recording Configuration
RECORD_DURATION = 3600  # 1 hour = 3600 seconds
OUTPUT_DIR = 'videos'
FPS = 20  # Frames per second
UPLOAD_QUEUE_FILE = 'upload_queue.json'

def log_message(msg):
    """Print timestamped log message"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {msg}")

def create_output_directory():
    """Create videos directory if it doesn't exist"""
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        log_message(f"✓ Created output directory: {OUTPUT_DIR}/")
    else:
        log_message(f"✓ Output directory exists: {OUTPUT_DIR}/")

def add_to_upload_queue(video_info):
    """
    Add captured video to upload queue for background processing

    Args:
        video_info: Dict with video metadata
    """
    try:
        # Load existing queue
        queue = []
        if os.path.exists(UPLOAD_QUEUE_FILE):
            with open(UPLOAD_QUEUE_FILE, 'r') as f:
                queue = json.load(f)

        # Add new video
        queue.append(video_info)

        # Save updated queue
        with open(UPLOAD_QUEUE_FILE, 'w') as f:
            json.dump(queue, indent=2, fp=f)

        log_message(f"✓ Added to upload queue: {video_info['filename']}")

    except Exception as e:
        log_message(f"✗ Failed to add to upload queue: {str(e)}")

def capture_video_stream(camera_name, rtsp_url, resolution):
    """
    Capture continuous 1-hour video stream from a single camera

    Args:
        camera_name: Name identifier for the camera
        rtsp_url: RTSP stream URL
        resolution: Tuple of (width, height)

    Returns:
        dict: Video information if successful, None otherwise
    """
    log_message(f"[{camera_name}] Starting 1-hour capture...")

    # Generate output filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = os.path.join(OUTPUT_DIR, f'{camera_name}_{timestamp}_1hour.mp4')

    # Initialize video capture
    cap = cv2.VideoCapture(rtsp_url)

    if not cap.isOpened():
        log_message(f"✗ [{camera_name}] Failed to connect to camera")
        return None

    log_message(f"✓ [{camera_name}] Connected successfully")

    # Set up video writer with H.264 codec
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_file, fourcc, FPS, resolution)

    if not out.isOpened():
        log_message(f"✗ [{camera_name}] Failed to initialize video writer")
        cap.release()
        return None

    # Recording loop
    start_time = time.time()
    frame_count = 0
    last_progress_time = start_time
    failed_frames = 0

    log_message(f"🎥 [{camera_name}] Recording to: {output_file}")
    log_message(f"⏱️  [{camera_name}] Duration: {RECORD_DURATION} seconds (1 hour)")
    log_message(f"📊 [{camera_name}] Progress updates every 5 minutes")

    while True:
        elapsed_time = time.time() - start_time

        # Check if recording duration reached
        if elapsed_time >= RECORD_DURATION:
            break

        # Read frame
        ret, frame = cap.read()

        if not ret:
            failed_frames += 1
            if failed_frames % 100 == 0:  # Log every 100 failures
                log_message(f"⚠️  [{camera_name}] Frame read failures: {failed_frames}")
            time.sleep(0.05)  # Brief pause before retry
            continue

        # Write frame to video
        out.write(frame)
        frame_count += 1
        failed_frames = 0  # Reset on success

        # Progress update every 5 minutes (300 seconds)
        if time.time() - last_progress_time >= 300:
            elapsed_minutes = elapsed_time / 60
            total_minutes = RECORD_DURATION / 60
            progress_pct = (elapsed_time / RECORD_DURATION) * 100
            log_message(f"📊 [{camera_name}] Progress: {elapsed_minutes:.1f}/{total_minutes:.0f} min ({progress_pct:.1f}%) - {frame_count:,} frames")
            last_progress_time = time.time()

    # Cleanup
    cap.release()
    out.release()

    # Final statistics
    actual_duration = time.time() - start_time
    file_size_bytes = os.path.getsize(output_file)
    file_size_mb = file_size_bytes / (1024 * 1024)
    file_size_gb = file_size_mb / 1024

    log_message(f"✅ [{camera_name}] Recording complete!")
    log_message(f"   Duration: {actual_duration:.1f}s ({actual_duration/60:.1f} min)")
    log_message(f"   Frames: {frame_count:,}")
    log_message(f"   File: {output_file}")
    log_message(f"   Size: {file_size_mb:.2f} MB ({file_size_gb:.2f} GB)")

    # Prepare video info for upload queue
    video_info = {
        'camera_name': camera_name,
        'filename': os.path.basename(output_file),
        'filepath': output_file,
        'timestamp': timestamp,
        'resolution': f"{resolution[0]}x{resolution[1]}",
        'duration_seconds': int(actual_duration),
        'file_size_mb': round(file_size_mb, 2),
        'file_size_gb': round(file_size_gb, 3),
        'fps': FPS,
        'frame_count': frame_count,
        'capture_completed': datetime.now().isoformat(),
        'upload_status': 'pending'
    }

    return video_info

def main():
    """Main execution function"""
    log_message("=" * 80)
    log_message("1-Hour Continuous Video Capture - Camera 22 & 35")
    log_message("=" * 80)
    log_message(f"Duration: {RECORD_DURATION} seconds ({RECORD_DURATION/60:.0f} minutes)")
    log_message(f"Cameras: {', '.join(CAMERAS.keys())}")
    log_message(f"Output Directory: {OUTPUT_DIR}/")
    log_message(f"Target FPS: {FPS}")
    log_message(f"Expected file size: ~3-5 GB per camera")
    log_message("=" * 80)

    # Create output directory
    create_output_directory()

    # Start time
    total_start = time.time()

    # Store results
    results = {}

    # Create threads for parallel recording
    threads = []

    def capture_and_store(camera_name, config):
        """Wrapper function to capture and store results"""
        result = capture_video_stream(camera_name, config['rtsp_url'], config['resolution'])
        results[camera_name] = result

    for camera_name, config in CAMERAS.items():
        thread = threading.Thread(
            target=capture_and_store,
            args=(camera_name, config)
        )
        threads.append(thread)
        thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    # Total execution time
    total_duration = time.time() - total_start

    log_message("\n" + "=" * 80)
    log_message("✅ All recordings complete!")
    log_message(f"⏱️  Total execution time: {total_duration:.1f}s ({total_duration/60:.1f} minutes)")
    log_message("=" * 80)

    # Add successful captures to upload queue
    successful_uploads = 0
    for camera_name, video_info in results.items():
        if video_info:
            add_to_upload_queue(video_info)
            successful_uploads += 1
            log_message(f"✓ [{camera_name}] Video ready for upload: {video_info['file_size_gb']:.2f} GB")
        else:
            log_message(f"✗ [{camera_name}] Recording failed")

    log_message("\n" + "=" * 80)
    log_message(f"📁 Local videos saved: {OUTPUT_DIR}/")
    log_message(f"📋 Upload queue: {UPLOAD_QUEUE_FILE} ({successful_uploads} videos)")
    log_message(f"▶️  Next step: Run background_upload_worker.py to upload to Supabase")
    log_message("=" * 80)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log_message("\n⚠️  Recording interrupted by user")
        log_message("   Partial videos may be saved locally")
    except Exception as e:
        log_message(f"\n✗ Error: {str(e)}")
        import traceback
        traceback.print_exc()
