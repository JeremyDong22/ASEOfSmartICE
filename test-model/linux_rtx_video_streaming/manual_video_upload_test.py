#!/usr/bin/env python3
"""
Manual Video Upload Test - Created 2025-10-22 20:18 CST
Tests uploading a single video file to Supabase with progress tracking
"""

import os
import sys
from datetime import datetime
from supabase import create_client, Client

# Supabase Configuration
SUPABASE_URL = "https://wdpeoyugsxqnpwwtkqsl.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndkcGVveXVnc3hxbnB3d3RrcXNsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDQxNDgwNzgsImV4cCI6MjA1OTcyNDA3OH0.9bUpuZCOZxDSH3KsIu6FwWZyAvnV5xPJGNpO3luxWOE"
STORAGE_BUCKET = "ASE"

def upload_video_with_chunks(video_path):
    """Upload video in chunks to handle large files"""
    try:
        # Initialize Supabase client
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        print(f"✓ Connected to Supabase")

        # Check file exists
        if not os.path.exists(video_path):
            print(f"✗ File not found: {video_path}")
            return False

        # Get file info
        file_size = os.path.getsize(video_path)
        file_size_mb = file_size / (1024 * 1024)
        filename = os.path.basename(video_path)

        print(f"\n📁 File: {filename}")
        print(f"📏 Size: {file_size_mb:.2f} MB ({file_size:,} bytes)")

        # For now, let's try to upload just the first 10MB as a test
        max_size = 10 * 1024 * 1024  # 10 MB limit for test

        if file_size > max_size:
            print(f"⚠️  File too large. Creating a 10MB test sample...")
            # Read only first 10MB
            with open(video_path, 'rb') as f:
                video_data = f.read(max_size)
            test_filename = f"test_sample_{filename}"
            storage_path = f"videos/test/{test_filename}"
        else:
            # Read entire file
            print(f"📖 Reading entire file...")
            with open(video_path, 'rb') as f:
                video_data = f.read()
            storage_path = f"videos/test/{filename}"

        print(f"📤 Uploading to: {storage_path}")
        print(f"   Size to upload: {len(video_data) / (1024*1024):.2f} MB")

        # Upload to Supabase
        response = supabase.storage.from_(STORAGE_BUCKET).upload(
            path=storage_path,
            file=video_data,
            file_options={"content-type": "video/mp4"}
        )

        print(f"✅ Upload successful!")
        print(f"   Response: {response}")

        # Generate public URL
        public_url = f"{SUPABASE_URL}/storage/v1/object/public/{STORAGE_BUCKET}/{storage_path}"
        print(f"🔗 Public URL: {public_url}")

        return True

    except Exception as e:
        print(f"❌ Upload failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main execution"""
    print("=" * 70)
    print("Manual Video Upload Test - Supabase Storage")
    print("=" * 70)

    # List available videos
    video_dir = "videos"
    if os.path.exists(video_dir):
        videos = [f for f in os.listdir(video_dir) if f.endswith('.mp4')]
        if videos:
            print(f"\nFound {len(videos)} video(s) in {video_dir}/:")
            for i, video in enumerate(videos, 1):
                path = os.path.join(video_dir, video)
                size_mb = os.path.getsize(path) / (1024 * 1024)
                print(f"  {i}. {video} ({size_mb:.2f} MB)")

            # Upload the first video as a test
            if videos:
                test_video = os.path.join(video_dir, videos[0])
                print(f"\n🎥 Testing upload with: {videos[0]}")
                upload_video_with_chunks(test_video)
        else:
            print(f"No videos found in {video_dir}/")
    else:
        print(f"Video directory '{video_dir}' not found")

if __name__ == "__main__":
    main()