#!/usr/bin/env python3
# Version: 4.0 (Model V4)
# Download Smartice 001 images from Supabase storage (30 channels, 1920x1080)
# Fine-tuning dataset for employee/customer classifier
# Uses parallel downloading for faster execution

import os
import sys
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from supabase import create_client, Client

# Supabase Configuration
SUPABASE_URL = "https://wdpeoyugsxqnpwwtkqsl.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndkcGVveXVnc3hxbnB3d3RrcXNsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDQxNDgwNzgsImV4cCI6MjA1OTcyNDA3OH0.9bUpuZCOZxDSH3KsIu6FwWZyAvnV5xPJGNpO3luxWOE"
STORAGE_BUCKET = "ASE"

# Paths
OUTPUT_DIR = Path("../raw_images")
OUTPUT_DIR.mkdir(exist_ok=True)

# Download settings
MAX_WORKERS = 20  # Parallel download threads
STORAGE_PREFIX = "smartice001/"  # Smartice 001 data path in storage

def download_image(supabase: Client, storage_path: str) -> tuple:
    """Download a single image from Supabase storage"""
    try:
        # Extract filename from storage path (e.g., smartice001/channel_1/20251220_195132_1920_1080.jpg)
        # Create organized folder structure: raw_images/channel_1/filename.jpg
        path_parts = storage_path.split('/')
        channel_folder = path_parts[1]  # e.g., channel_1
        filename = path_parts[-1]  # e.g., 20251220_195132_1920_1080.jpg

        # Create channel subfolder
        channel_dir = OUTPUT_DIR / channel_folder
        channel_dir.mkdir(exist_ok=True)

        filepath = channel_dir / filename

        # Skip if already exists
        if filepath.exists():
            return (True, filename, "Already exists")

        # Download from Supabase storage
        image_data = supabase.storage.from_(STORAGE_BUCKET).download(storage_path)

        # Save to file
        with open(filepath, 'wb') as f:
            f.write(image_data)

        return (True, filename, "Downloaded")

    except Exception as e:
        return (False, storage_path, str(e))

def main():
    print(f"🚀 Starting Supabase image download for Smartice 001")
    print(f"Output directory: {OUTPUT_DIR.absolute()}")
    print(f"Parallel workers: {MAX_WORKERS}")
    print(f"Storage path: {STORAGE_PREFIX}\n")

    # Initialize Supabase client
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

    # List all files in smartice001/ folder from storage
    print(f"📊 Listing files from {STORAGE_BUCKET}/{STORAGE_PREFIX}...")

    file_list = supabase.storage.from_(STORAGE_BUCKET).list(STORAGE_PREFIX)

    # Flatten all files from all channel folders
    all_files = []
    for item in file_list:
        if item.get('name') and item['name'].startswith('channel_'):
            channel_name = item['name']
            # List files in each channel folder
            channel_files = supabase.storage.from_(STORAGE_BUCKET).list(f"{STORAGE_PREFIX}{channel_name}")
            for file_item in channel_files:
                file_name = file_item.get('name')
                if file_name and file_name.endswith('.jpg'):
                    storage_path = f"{STORAGE_PREFIX}{channel_name}/{file_name}"
                    all_files.append(storage_path)

    total_images = len(all_files)
    print(f"Found {total_images} images from Smartice 001 to download\n")

    # Download images in parallel
    success_count = 0
    failed_count = 0
    skipped_count = 0

    start_time = datetime.now()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(download_image, supabase, file_path): file_path for file_path in all_files}

        for i, future in enumerate(as_completed(futures), 1):
            success, filename, message = future.result()

            if success:
                if message == "Already exists":
                    skipped_count += 1
                    status = "⏭️"
                else:
                    success_count += 1
                    status = "✅"
            else:
                failed_count += 1
                status = "❌"

            # Progress indicator
            if i % 100 == 0 or i == total_images:
                elapsed = (datetime.now() - start_time).total_seconds()
                rate = i / elapsed if elapsed > 0 else 0
                print(f"Progress: {i}/{total_images} ({rate:.1f} img/s) | ✅{success_count} ⏭️{skipped_count} ❌{failed_count}")

    # Summary
    duration = (datetime.now() - start_time).total_seconds()
    print(f"\n{'='*60}")
    print(f"✅ Download Complete!")
    print(f"{'='*60}")
    print(f"Total images:     {total_images}")
    print(f"Downloaded:       {success_count}")
    print(f"Already existed:  {skipped_count}")
    print(f"Failed:           {failed_count}")
    print(f"Duration:         {duration:.1f}s ({duration/60:.1f} minutes)")
    print(f"Average speed:    {total_images/duration:.1f} images/second")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
