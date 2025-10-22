"""
Video Stream Capture Script with Supabase Upload
Version: 2.0
Date: 2025-10-20

Purpose: Captures 5-minute video streams from camera_22 and camera_35, then uploads to Supabase
Usage: python3 capture_video_streams.py
Output: videos/ folder (local) + Supabase ASE bucket (cloud)
"""

import cv2
import os
from datetime import datetime
import time
import threading
from supabase import create_client, Client
import uuid

# Supabase Configuration (Same as screenshot capture system)
SUPABASE_URL = "https://wdpeoyugsxqnpwwtkqsl.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndkcGVveXVnc3hxbnB3d3RrcXNsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDQxNDgwNzgsImV4cCI6MjA1OTcyNDA3OH0.9bUpuZCOZxDSH3KsIu6FwWZyAvnV5xPJGNpO3luxWOE"
STORAGE_BUCKET = "ASE"

# Camera configurations
CAMERAS = {
    'camera_22': {
        'rtsp_url': 'rtsp://admin:123456@202.168.40.22:554/Streaming/Channels/102',
        'resolution': (1920, 1080)
    },
    'camera_35': {
        'rtsp_url': 'rtsp://admin:123456@202.168.40.35:554/Streaming/Channels/102',
        'resolution': (1920, 1080)
    }
}

# Configuration
RECORD_DURATION = 300  # 5 minutes in seconds
OUTPUT_DIR = 'videos'
FPS = 20  # Frames per second for recording

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

def create_output_directory():
    """Create videos directory if it doesn't exist"""
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"✓ Created output directory: {OUTPUT_DIR}/")
    else:
        print(f"✓ Output directory exists: {OUTPUT_DIR}/")

def upload_to_supabase(local_file_path, camera_name, timestamp, resolution, file_size_mb, duration_seconds):
    """
    Upload video to Supabase storage and record metadata to database

    Args:
        local_file_path: Path to local video file
        camera_name: Camera identifier (e.g., 'camera_22')
        timestamp: Capture timestamp string
        resolution: Resolution tuple (width, height)
        file_size_mb: File size in MB
        duration_seconds: Video duration in seconds

    Returns:
        bool: True if upload successful, False otherwise
    """
    try:
        print(f"\n[{camera_name}] 📤 Uploading to Supabase...")

        # Generate storage path: videos/camera_22/20251020_143052_1920_1080.mp4
        filename = f"{timestamp}_{resolution[0]}_{resolution[1]}.mp4"
        storage_path = f"videos/{camera_name}/{filename}"

        # Read file as binary
        with open(local_file_path, 'rb') as f:
            video_data = f.read()

        # Upload to Supabase storage
        supabase.storage.from_(STORAGE_BUCKET).upload(
            path=storage_path,
            file=video_data,
            file_options={"content-type": "video/mp4"}
        )

        # Generate public URL
        video_url = f"{SUPABASE_URL}/storage/v1/object/public/{STORAGE_BUCKET}/{storage_path}"

        print(f"✓ [{camera_name}] Upload successful!")
        print(f"   URL: {video_url}")

        # Insert metadata to database table
        video_id = str(uuid.uuid4())
        metadata = {
            'video_id': video_id,
            'video_url': video_url,
            'camera_name': camera_name,
            'capture_timestamp': datetime.now().isoformat(),
            'resolution': f"{resolution[0]}x{resolution[1]}",
            'file_size_mb': round(file_size_mb, 2),
            'duration_seconds': int(duration_seconds),
            'fps': FPS
        }

        # Insert to ase_video_stream table
        supabase.table('ase_video_stream').insert(metadata).execute()
        print(f"✓ [{camera_name}] Metadata saved to database")

        return True

    except Exception as e:
        print(f"✗ [{camera_name}] Upload failed: {str(e)}")
        return False

def capture_video_stream(camera_name, rtsp_url, resolution):
    """
    Capture video stream from a single camera and upload to Supabase

    Args:
        camera_name: Name identifier for the camera
        rtsp_url: RTSP stream URL
        resolution: Tuple of (width, height)
    """
    print(f"\n[{camera_name}] Starting capture...")

    # Generate output filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = os.path.join(OUTPUT_DIR, f'{camera_name}_{timestamp}.mp4')

    # Initialize video capture
    cap = cv2.VideoCapture(rtsp_url)

    if not cap.isOpened():
        print(f"✗ [{camera_name}] Failed to connect to camera")
        return False

    print(f"✓ [{camera_name}] Connected successfully")

    # Set up video writer
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_file, fourcc, FPS, resolution)

    if not out.isOpened():
        print(f"✗ [{camera_name}] Failed to initialize video writer")
        cap.release()
        return False

    # Recording loop
    start_time = time.time()
    frame_count = 0
    last_progress_time = start_time

    print(f"🎥 [{camera_name}] Recording to: {output_file}")
    print(f"⏱️  [{camera_name}] Duration: {RECORD_DURATION} seconds")

    while True:
        elapsed_time = time.time() - start_time

        # Check if recording duration reached
        if elapsed_time >= RECORD_DURATION:
            break

        # Read frame
        ret, frame = cap.read()

        if not ret:
            print(f"⚠️  [{camera_name}] Failed to read frame at {elapsed_time:.1f}s")
            time.sleep(0.1)  # Brief pause before retry
            continue

        # Write frame to video
        out.write(frame)
        frame_count += 1

        # Progress update every 30 seconds
        if time.time() - last_progress_time >= 30:
            progress_pct = (elapsed_time / RECORD_DURATION) * 100
            print(f"📊 [{camera_name}] Progress: {elapsed_time:.0f}/{RECORD_DURATION}s ({progress_pct:.1f}%) - {frame_count} frames")
            last_progress_time = time.time()

    # Cleanup
    cap.release()
    out.release()

    # Final statistics
    actual_duration = time.time() - start_time
    file_size_mb = os.path.getsize(output_file) / (1024 * 1024)

    print(f"✅ [{camera_name}] Recording complete!")
    print(f"   Duration: {actual_duration:.1f}s")
    print(f"   Frames: {frame_count}")
    print(f"   File: {output_file}")
    print(f"   Size: {file_size_mb:.2f} MB")

    # Upload to Supabase
    upload_success = upload_to_supabase(
        local_file_path=output_file,
        camera_name=camera_name,
        timestamp=timestamp,
        resolution=resolution,
        file_size_mb=file_size_mb,
        duration_seconds=actual_duration
    )

    if upload_success:
        print(f"✓ [{camera_name}] Full pipeline complete (capture + upload)")
    else:
        print(f"⚠️  [{camera_name}] Capture complete but upload failed (video saved locally)")

    return upload_success

def main():
    """Main execution function"""
    print("=" * 70)
    print("Video Stream Capture with Supabase Upload - Camera 22 & 35")
    print("=" * 70)
    print(f"Record Duration: {RECORD_DURATION} seconds ({RECORD_DURATION/60:.1f} minutes)")
    print(f"Output Directory: {OUTPUT_DIR}/")
    print(f"Target FPS: {FPS}")
    print(f"Supabase Bucket: {STORAGE_BUCKET}")
    print("=" * 70)

    # Create output directory
    create_output_directory()

    # Start time
    total_start = time.time()

    # Create threads for parallel recording
    threads = []

    for camera_name, config in CAMERAS.items():
        thread = threading.Thread(
            target=capture_video_stream,
            args=(camera_name, config['rtsp_url'], config['resolution'])
        )
        threads.append(thread)
        thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    # Total execution time
    total_duration = time.time() - total_start

    print("\n" + "=" * 70)
    print(f"✅ All recordings complete!")
    print(f"⏱️  Total execution time: {total_duration:.1f}s ({total_duration/60:.1f} minutes)")
    print(f"📁 Local videos: {OUTPUT_DIR}/")
    print(f"☁️  Cloud storage: {SUPABASE_URL}/storage/v1/object/public/{STORAGE_BUCKET}/videos/")
    print("=" * 70)

if __name__ == "__main__":
    main()
