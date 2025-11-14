#!/usr/bin/env python3
"""
Disk Space Monitoring and Management
Version: 1.0.0
Last Updated: 2025-11-14

Purpose: Monitor disk space and intelligently manage video storage

Features:
- Check available disk space
- Alert when space < 100GB
- Smart cleanup: delete oldest videos first
- Critical alert: can't store 1 day of videos
- Respects processing schedule (keeps yesterday + today)

Usage:
  python3 check_disk_space.py --check           # Check only
  python3 check_disk_space.py --cleanup         # Check and cleanup if needed
  python3 check_disk_space.py --min-space 150   # Custom threshold (GB)
"""

import os
import shutil
from pathlib import Path
from datetime import datetime, timedelta
import argparse
import sys

# Constants
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_DIR = SCRIPT_DIR.parent.parent
VIDEOS_DIR = PROJECT_DIR / "videos"
RESULTS_DIR = PROJECT_DIR / "results"
DB_DIR = PROJECT_DIR / "db"

MIN_SPACE_GB = 100  # Minimum required space
ESTIMATED_VIDEO_SIZE_PER_DAY_GB = 50  # Estimate: 10 cameras × 7 hours

def get_disk_usage(path):
    """Get disk usage statistics in GB"""
    stat = os.statvfs(str(path))
    total_gb = (stat.f_blocks * stat.f_frsize) / (1024**3)
    free_gb = (stat.f_bavail * stat.f_frsize) / (1024**3)
    used_gb = total_gb - free_gb
    used_percent = (used_gb / total_gb) * 100
    return {
        'total_gb': total_gb,
        'used_gb': used_gb,
        'free_gb': free_gb,
        'used_percent': used_percent
    }

def get_date_folders(directory):
    """Get all YYYYMMDD date folders, sorted oldest first"""
    if not directory.exists():
        return []

    date_folders = []
    for item in directory.iterdir():
        if item.is_dir() and item.name.isdigit() and len(item.name) == 8:
            try:
                date_obj = datetime.strptime(item.name, "%Y%m%d")
                date_folders.append((item, date_obj))
            except ValueError:
                continue

    # Sort by date (oldest first)
    date_folders.sort(key=lambda x: x[1])
    return [folder for folder, _ in date_folders]

def get_folder_size(folder):
    """Calculate total size of folder in GB"""
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(folder):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            if os.path.exists(filepath):
                total_size += os.path.getsize(filepath)
    return total_size / (1024**3)  # Convert to GB

def smart_cleanup(target_free_gb, dry_run=False):
    """
    Intelligently delete old videos to free up space

    Rules:
    - Keep today's videos (currently recording)
    - Keep yesterday's videos (will be processed at midnight)
    - Delete older videos first (oldest → newest)
    - Stop when target space is reached
    """
    today = datetime.now().strftime("%Y%m%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")

    print(f"\n{'='*70}")
    print("SMART CLEANUP")
    print(f"{'='*70}")
    print(f"Today: {today}")
    print(f"Yesterday: {yesterday}")
    print(f"Target free space: {target_free_gb:.1f} GB")
    print(f"{'='*70}\n")

    # Get current space
    current = get_disk_usage(PROJECT_DIR)
    freed_space_gb = 0

    # Get all date folders from videos and results
    video_folders = get_date_folders(VIDEOS_DIR)
    result_folders = get_date_folders(RESULTS_DIR)

    # Combine and deduplicate by date
    all_folders = {}
    for folder in video_folders:
        date_str = folder.name
        if date_str not in all_folders:
            all_folders[date_str] = []
        all_folders[date_str].append(VIDEOS_DIR / date_str)

    for folder in result_folders:
        date_str = folder.name
        if date_str not in all_folders:
            all_folders[date_str] = []
        all_folders[date_str].append(RESULTS_DIR / date_str)

    # Sort by date (oldest first)
    sorted_dates = sorted(all_folders.keys())

    # Delete oldest folders until target is reached
    for date_str in sorted_dates:
        # Skip today and yesterday
        if date_str in [today, yesterday]:
            print(f"⏭  Skipping {date_str} (protected: {'today' if date_str == today else 'yesterday'})")
            continue

        # Calculate space we'll free
        folders_to_delete = all_folders[date_str]
        date_size_gb = sum(get_folder_size(f) for f in folders_to_delete if f.exists())

        if dry_run:
            print(f"[DRY RUN] Would delete {date_str} ({date_size_gb:.2f} GB)")
        else:
            print(f"🗑️  Deleting {date_str} ({date_size_gb:.2f} GB)...")
            for folder in folders_to_delete:
                if folder.exists():
                    shutil.rmtree(folder)
                    print(f"   Deleted: {folder}")

        freed_space_gb += date_size_gb

        # Check if we've freed enough space
        projected_free = current['free_gb'] + freed_space_gb
        if projected_free >= target_free_gb:
            print(f"\n✅ Target reached! Projected free space: {projected_free:.1f} GB")
            break

    print(f"\nTotal space freed: {freed_space_gb:.1f} GB")
    return freed_space_gb

def check_and_cleanup(min_space_gb, auto_cleanup=False, dry_run=False):
    """Main check and cleanup logic"""
    print(f"\n{'='*70}")
    print("DISK SPACE MONITOR")
    print(f"{'='*70}\n")

    # Get disk usage
    usage = get_disk_usage(PROJECT_DIR)

    print(f"Project Path: {PROJECT_DIR}")
    print(f"Total Space:  {usage['total_gb']:.1f} GB")
    print(f"Used Space:   {usage['used_gb']:.1f} GB ({usage['used_percent']:.1f}%)")
    print(f"Free Space:   {usage['free_gb']:.1f} GB")
    print(f"Minimum Req:  {min_space_gb:.1f} GB")

    # Check status
    if usage['free_gb'] >= min_space_gb:
        print(f"\n✅ STATUS: HEALTHY (Free space > {min_space_gb}GB)")
        return 0

    print(f"\n⚠️  STATUS: LOW DISK SPACE (< {min_space_gb}GB)")

    # Check if we can even store 1 day of videos
    if usage['free_gb'] < ESTIMATED_VIDEO_SIZE_PER_DAY_GB:
        print(f"\n🚨 CRITICAL: Cannot store even 1 day of videos!")
        print(f"   Available: {usage['free_gb']:.1f} GB")
        print(f"   Required:  {ESTIMATED_VIDEO_SIZE_PER_DAY_GB:.1f} GB (estimated per day)")
        print(f"\n❌ ACTION REQUIRED: Manually free up disk space or add more storage")
        return 2  # Critical error

    # Cleanup if requested
    if auto_cleanup:
        print(f"\n🧹 Starting automatic cleanup...")
        freed = smart_cleanup(min_space_gb, dry_run=dry_run)

        if freed > 0:
            print(f"\n✅ Cleanup successful! Freed {freed:.1f} GB")
            return 0
        else:
            print(f"\n⚠️  No files to cleanup (only today + yesterday remain)")
            return 1
    else:
        print(f"\n💡 Run with --cleanup to automatically free space")
        return 1

def main():
    parser = argparse.ArgumentParser(
        description="Monitor disk space and manage video storage"
    )
    parser.add_argument("--check", action="store_true",
                       help="Check disk space only (no cleanup)")
    parser.add_argument("--cleanup", action="store_true",
                       help="Check and cleanup if needed")
    parser.add_argument("--min-space", type=float, default=MIN_SPACE_GB,
                       help=f"Minimum required space in GB (default: {MIN_SPACE_GB})")
    parser.add_argument("--dry-run", action="store_true",
                       help="Simulate cleanup without deleting files")

    args = parser.parse_args()

    # Default to check mode if no flags
    if not args.check and not args.cleanup:
        args.check = True

    exit_code = check_and_cleanup(
        min_space_gb=args.min_space,
        auto_cleanup=args.cleanup,
        dry_run=args.dry_run
    )

    sys.exit(exit_code)

if __name__ == "__main__":
    main()
