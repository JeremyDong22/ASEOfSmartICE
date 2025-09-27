#!/usr/bin/env python3
# Version: 1.0
# Manual sync script to upload pending screenshots from backup queue to Supabase
# Run this independently to clear the backup queue when network is available

import sqlite3
import os
import sys
import requests
from pathlib import Path
from datetime import datetime

# Supabase Configuration (Private repo - credentials are safe)
SUPABASE_URL = "https://wdpeoyugsxqnpwwtkqsl.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndkcGVveXVnc3hxbnB3d3RrcXNsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTMwNDM3NjQsImV4cCI6MjA2ODYxOTc2NH0.jLJSzCcawdMOBXvz-W6vvqzxJdLJmRBqLWXeTKPJLN0"
STORAGE_BUCKET = "ASE"

DATABASE_FILE = Path(__file__).parent / "capture_tracking.db"
BACKUP_DIR = Path(__file__).parent / "backup_queue"

def upload_to_supabase(image_data, filename):
    """Upload image to Supabase storage"""
    try:
        headers = {
            'apikey': SUPABASE_ANON_KEY,
            'Authorization': f'Bearer {SUPABASE_ANON_KEY}',
            'Content-Type': 'image/jpeg'
        }

        upload_url = f"{SUPABASE_URL}/storage/v1/object/{STORAGE_BUCKET}/{filename}"
        response = requests.post(upload_url, headers=headers, data=image_data, timeout=30)

        if response.status_code in [200, 201]:
            public_url = f"{SUPABASE_URL}/storage/v1/object/public/{STORAGE_BUCKET}/{filename}"
            return True, public_url
        else:
            return False, f"Upload failed: {response.status_code}"

    except Exception as e:
        return False, str(e)

def insert_database_record(image_url, camera_name, resolution, file_size_kb):
    """Insert record into ASE_Snapshot table"""
    try:
        headers = {
            'apikey': SUPABASE_ANON_KEY,
            'Authorization': f'Bearer {SUPABASE_ANON_KEY}',
            'Content-Type': 'application/json',
            'Prefer': 'return=minimal'
        }

        data = {
            'image_url': image_url,
            'camera_name': camera_name,
            'resolution': resolution,
            'file_size_kb': file_size_kb,
            'restaurant_id': None
        }

        url = f"{SUPABASE_URL}/rest/v1/ASE_Snapshot"
        response = requests.post(url, headers=headers, json=data, timeout=10)

        return response.status_code in [200, 201]

    except:
        return False

def sync_backup_queue():
    """Sync all pending uploads from backup queue"""
    db_path = DATABASE_FILE

    if not db_path.exists():
        print("❌ No backup database found")
        return

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Get all pending uploads
    cursor.execute('''
        SELECT filename, local_path, camera_name, resolution, file_size_kb, upload_attempts
        FROM upload_tracking
        WHERE upload_status = 'pending'
        ORDER BY capture_timestamp ASC
    ''')

    pending_uploads = cursor.fetchall()

    if not pending_uploads:
        print("✅ No pending uploads in queue")
        conn.close()
        return

    print(f"📦 Found {len(pending_uploads)} pending uploads")
    print("=" * 50)

    successful = 0
    failed = 0
    missing = 0

    for filename, local_path, camera_name, resolution, file_size_kb, attempts in pending_uploads:
        print(f"📤 Uploading: {filename} (attempt #{attempts + 1})")

        if not os.path.exists(local_path):
            print(f"   ❌ File missing: {local_path}")
            cursor.execute('''
                UPDATE upload_tracking
                SET upload_status = 'missing', last_attempt = ?
                WHERE filename = ?
            ''', (datetime.now(), filename))
            missing += 1
            continue

        try:
            with open(local_path, 'rb') as f:
                image_data = f.read()

            # Upload to Supabase
            supabase_filename = f"{camera_name}/{filename}"
            upload_success, result = upload_to_supabase(image_data, supabase_filename)

            if upload_success:
                # Insert database record
                db_success = insert_database_record(result, camera_name, resolution, file_size_kb)

                if db_success:
                    print(f"   ✅ Successfully uploaded")
                    cursor.execute('''
                        UPDATE upload_tracking
                        SET upload_status = 'success', supabase_url = ?, last_attempt = ?
                        WHERE filename = ?
                    ''', (result, datetime.now(), filename))

                    # Delete local file after successful upload
                    try:
                        os.remove(local_path)
                        print(f"   🗑️ Local file deleted")
                    except:
                        pass

                    successful += 1
                else:
                    print(f"   ⚠️ Upload OK but database insert failed")
                    cursor.execute('''
                        UPDATE upload_tracking
                        SET upload_attempts = upload_attempts + 1, last_attempt = ?,
                            error_message = 'Database insert failed'
                        WHERE filename = ?
                    ''', (datetime.now(), filename))
                    failed += 1
            else:
                print(f"   ❌ Upload failed: {result}")
                cursor.execute('''
                    UPDATE upload_tracking
                    SET upload_attempts = upload_attempts + 1, last_attempt = ?,
                        error_message = ?
                    WHERE filename = ?
                ''', (datetime.now(), result, filename))
                failed += 1

        except Exception as e:
            print(f"   ❌ Error: {str(e)}")
            cursor.execute('''
                UPDATE upload_tracking
                SET upload_attempts = upload_attempts + 1, last_attempt = ?,
                    error_message = ?
                WHERE filename = ?
            ''', (datetime.now(), str(e), filename))
            failed += 1

        conn.commit()

    conn.close()

    print("=" * 50)
    print("📊 Sync Complete:")
    print(f"   ✅ Successful: {successful}")
    print(f"   ❌ Failed: {failed}")
    print(f"   ⚠️ Missing: {missing}")

    # Show remaining statistics
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute('''
        SELECT COUNT(*) FROM upload_tracking WHERE upload_status = 'pending'
    ''')
    remaining = cursor.fetchone()[0]
    conn.close()

    if remaining > 0:
        print(f"   📦 Still pending: {remaining}")

def show_statistics():
    """Show backup queue statistics"""
    db_path = DATABASE_FILE

    if not db_path.exists():
        print("❌ No backup database found")
        return

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute('''
        SELECT
            upload_status,
            COUNT(*) as count,
            SUM(file_size_kb) / 1024 as size_mb
        FROM upload_tracking
        GROUP BY upload_status
    ''')

    print("\n📊 Backup Queue Statistics:")
    print("=" * 50)

    for status, count, size_mb in cursor.fetchall():
        size_mb = size_mb or 0
        print(f"   {status.upper()}: {count} files ({size_mb:.1f} MB)")

    # Get oldest pending
    cursor.execute('''
        SELECT capture_timestamp
        FROM upload_tracking
        WHERE upload_status = 'pending'
        ORDER BY capture_timestamp ASC
        LIMIT 1
    ''')

    oldest = cursor.fetchone()
    if oldest:
        print(f"\n   Oldest pending: {oldest[0]}")

    conn.close()

def cleanup_old_backups(days=7):
    """Remove successfully uploaded backups older than specified days"""
    db_path = DATABASE_FILE

    if not db_path.exists():
        print("❌ No backup database found")
        return

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cutoff_date = datetime.now().timestamp() - (days * 24 * 3600)

    cursor.execute('''
        DELETE FROM upload_tracking
        WHERE upload_status = 'success'
        AND julianday('now') - julianday(capture_timestamp) > ?
    ''', (days,))

    deleted = cursor.rowcount
    conn.commit()
    conn.close()

    if deleted > 0:
        print(f"🗑️ Cleaned up {deleted} old successful uploads")

def main():
    """Main function for manual sync"""
    if len(sys.argv) > 1:
        if sys.argv[1] == "--stats":
            show_statistics()
        elif sys.argv[1] == "--cleanup":
            cleanup_old_backups()
        elif sys.argv[1] == "--help":
            print("Usage:")
            print("  python3 sync_backup_queue.py          # Sync pending uploads")
            print("  python3 sync_backup_queue.py --stats  # Show statistics")
            print("  python3 sync_backup_queue.py --cleanup # Clean old records")
        else:
            print("Unknown option. Use --help for usage")
    else:
        sync_backup_queue()

if __name__ == "__main__":
    main()