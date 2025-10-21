#!/usr/bin/env python3
# Version: 1.0
# Download all camera images from Supabase storage to raw_images folder
# Uses parallel downloading for faster execution

import os
import sys
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from supabase import create_client, Client

# Supabase Configuration
SUPABASE_URL = "https://wdpeoyugsxqnpwwtkqsl.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndkcGVveXVnc3hxbnB3d3RrcXNsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MjY1NDE5MjUsImV4cCI6MjA0MjExNzkyNX0.BtNj2CRr_ybJe5LssJyeNa2eSOBxVWrb3h8HdFEb51w"
STORAGE_BUCKET = "ASE"

# Paths
OUTPUT_DIR = Path("../raw_images")
OUTPUT_DIR.mkdir(exist_ok=True)

# Download settings
MAX_WORKERS = 20  # Parallel download threads

def download_image(supabase: Client, record: dict) -> tuple:
    """Download a single image from Supabase storage"""
    try:
        image_url = record['image_url']
        camera_name = record['camera_name']
        timestamp = record['capture_timestamp']

        # Parse timestamp to create filename
        ts = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        filename = f"{camera_name}_{ts.strftime('%Y%m%d_%H%M%S')}.jpg"
        filepath = OUTPUT_DIR / filename

        # Skip if already exists
        if filepath.exists():
            return (True, filename, "Already exists")

        # Extract storage path from URL
        storage_path = image_url.split(f'{STORAGE_BUCKET}/')[-1]

        # Download from Supabase storage
        image_data = supabase.storage.from_(STORAGE_BUCKET).download(storage_path)

        # Save to file
        with open(filepath, 'wb') as f:
            f.write(image_data)

        return (True, filename, "Downloaded")

    except Exception as e:
        return (False, record.get('camera_name', 'unknown'), str(e))

def main():
    print(f"🚀 Starting Supabase image download")
    print(f"Output directory: {OUTPUT_DIR.absolute()}")
    print(f"Parallel workers: {MAX_WORKERS}\n")

    # Initialize Supabase client
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

    # Query all image records
    print("📊 Querying Supabase database...")
    response = supabase.table('ase_snapshot').select('*').execute()
    records = response.data

    total_images = len(records)
    print(f"Found {total_images} images to download\n")

    # Download images in parallel
    success_count = 0
    failed_count = 0
    skipped_count = 0

    start_time = datetime.now()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(download_image, supabase, record): record for record in records}

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
