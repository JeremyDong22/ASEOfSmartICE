#!/usr/bin/env python3
"""
Upload Existing Videos to Supabase - Created 2025-10-22 20:06 CST
Uploads the previously captured videos to Supabase storage
"""

import os
from datetime import datetime
from supabase import create_client, Client
import uuid

# Supabase Configuration (Updated credentials)
SUPABASE_URL = "https://wdpeoyugsxqnpwwtkqsl.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndkcGVveXVnc3hxbnB3d3RrcXNsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDQxNDgwNzgsImV4cCI6MjA1OTcyNDA3OH0.9bUpuZCOZxDSH3KsIu6FwWZyAvnV5xPJGNpO3luxWOE"
STORAGE_BUCKET = "ASE"

# Video files to upload
VIDEO_DIR = "videos"
VIDEO_FILES = [
    ("camera_22_20251022_195212.mp4", "camera_22", (1920, 1080)),
    ("camera_35_20251022_195212.mp4", "camera_35", (1920, 1080))
]

def upload_video(local_file_path, camera_name, resolution):
    """Upload a single video to Supabase"""
    try:
        # Initialize Supabase client
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

        # Get file info
        file_size_mb = os.path.getsize(local_file_path) / (1024 * 1024)
        timestamp = os.path.basename(local_file_path).split('_')[1] + '_' + os.path.basename(local_file_path).split('_')[2].replace('.mp4', '')

        print(f"\n[{camera_name}] Uploading {os.path.basename(local_file_path)}")
        print(f"   File size: {file_size_mb:.2f} MB")

        # Generate storage path
        filename = f"{timestamp}_{resolution[0]}_{resolution[1]}.mp4"
        storage_path = f"videos/{camera_name}/{filename}"

        print(f"   Storage path: {storage_path}")
        print(f"   Reading file...")

        # Read file as binary
        with open(local_file_path, 'rb') as f:
            video_data = f.read()

        print(f"   Uploading to Supabase (this may take a while)...")

        # Upload to Supabase storage
        response = supabase.storage.from_(STORAGE_BUCKET).upload(
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
            'duration_seconds': 300,  # 5 minutes
            'fps': 20
        }

        # Insert to ase_video_stream table
        supabase.table('ase_video_stream').insert(metadata).execute()
        print(f"✓ [{camera_name}] Metadata saved to database")

        return True

    except Exception as e:
        print(f"✗ [{camera_name}] Upload failed: {str(e)}")
        return False

def main():
    """Main execution"""
    print("=" * 70)
    print("Uploading Captured Videos to Supabase")
    print("=" * 70)

    successful_uploads = 0

    for filename, camera_name, resolution in VIDEO_FILES:
        full_path = os.path.join(VIDEO_DIR, filename)

        if os.path.exists(full_path):
            if upload_video(full_path, camera_name, resolution):
                successful_uploads += 1
        else:
            print(f"✗ File not found: {full_path}")

    print("\n" + "=" * 70)
    print(f"Upload Summary: {successful_uploads}/{len(VIDEO_FILES)} successful")
    print("=" * 70)

if __name__ == "__main__":
    main()