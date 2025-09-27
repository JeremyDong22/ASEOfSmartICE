#!/usr/bin/env python3
# Version: 4.0 - Resilient version with local backup queue
# Linux automated multi-camera screenshot capture with Supabase integration and local backup
# Features: Local backup queue, automatic retry mechanism, failure recovery
# Captures screenshots every 5 minutes from multiple cameras and stores in Supabase

import cv2
import time
import threading
import json
import os
import sys
import signal
import sqlite3
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
import requests
from queue import Queue
import shutil

# Supabase Configuration (Private repo - credentials are safe)
SUPABASE_URL = "https://wdpeoyugsxqnpwwtkqsl.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndkcGVveXVnc3hxbnB3d3RrcXNsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDQxNDgwNzgsImV4cCI6MjA1OTcyNDA3OH0.9bUpuZCOZxDSH3KsIu6FwWZyAvnV5xPJGNpO3luxWOE"
STORAGE_BUCKET = "ASE"

# Configuration
CAPTURE_INTERVAL = 300  # 5 minutes in seconds
CONNECTION_TIMEOUT = 5  # seconds
RETRY_ATTEMPTS = 3
CAMERA_CONFIG_FILE = "../../test/camera_connection_results_20250927_230846.json"
MAX_RUNTIME_HOURS = 2  # Maximum runtime per execution (for cron restarts)
STOP_TIME = 22  # Stop at 10 PM (22:00)

# Local backup configuration
BACKUP_DIR = Path(__file__).parent / "backup_queue"
DATABASE_FILE = Path(__file__).parent / "capture_tracking.db"
MAX_RETRY_ATTEMPTS = 5
RETRY_INTERVAL = 600  # 10 minutes in seconds

# Working camera configurations
WORKING_CAMERAS = []

class ResilientSupabaseAgent:
    def __init__(self):
        self.active_cameras = {}
        self.capture_count = 0
        self.running = False
        self.start_time = datetime.now()
        self.upload_queue = Queue()
        self.failed_uploads = 0
        self.successful_uploads = 0

        # Setup components
        self.setup_directories()
        self.setup_database()
        self.load_camera_config()
        self.setup_signal_handlers()

        # Start background retry thread
        self.start_retry_thread()

    def setup_directories(self):
        """Create necessary directories for backup"""
        self.backup_dir = BACKUP_DIR
        self.backup_dir.mkdir(exist_ok=True)

        # Create subdirectories for each camera
        for i in range(20, 40):  # Potential camera IPs
            camera_dir = self.backup_dir / f"camera_{i}"
            camera_dir.mkdir(exist_ok=True)

        print(f"📁 Backup directory ready: {self.backup_dir}")

    def setup_database(self):
        """Setup SQLite database for tracking uploads"""
        self.db_path = DATABASE_FILE
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Create tracking table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS upload_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT UNIQUE NOT NULL,
                camera_name TEXT NOT NULL,
                local_path TEXT NOT NULL,
                capture_timestamp DATETIME NOT NULL,
                upload_status TEXT DEFAULT 'pending',
                upload_attempts INTEGER DEFAULT 0,
                last_attempt DATETIME,
                supabase_url TEXT,
                error_message TEXT,
                file_size_kb REAL,
                resolution TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create index for faster queries
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_upload_status
            ON upload_tracking(upload_status)
        ''')

        conn.commit()
        conn.close()

        print(f"📊 Database initialized: {self.db_path}")

    def setup_signal_handlers(self):
        """Setup graceful shutdown handlers"""
        signal.signal(signal.SIGTERM, self.handle_shutdown)
        signal.signal(signal.SIGINT, self.handle_shutdown)

    def handle_shutdown(self, signum, frame):
        """Handle graceful shutdown"""
        print(f"\n⚠️ Received shutdown signal. Saving state and cleaning up...")
        self.running = False
        self.sync_pending_uploads()  # Try to upload any remaining items
        sys.exit(0)

    def load_camera_config(self):
        """Load verified camera configurations from connection test results"""
        global WORKING_CAMERAS

        try:
            config_path = Path(__file__).parent.parent.parent / "test" / "camera_connection_results_20250927_230846.json"
            with open(config_path, 'r') as f:
                data = json.load(f)
                WORKING_CAMERAS = data.get('successful_connections', [])

            print(f"📋 Loaded {len(WORKING_CAMERAS)} verified camera configurations")

            for i, camera in enumerate(WORKING_CAMERAS, 1):
                print(f"   {i}. {camera['ip']} ({camera['resolution']}) - {camera['status']}")

        except FileNotFoundError:
            print("⚠️ Camera config file not found. Using fallback configuration.")
            WORKING_CAMERAS = [{
                "ip": "202.168.40.35",
                "username": "admin",
                "password": "123456",
                "rtsp_url": "rtsp://admin:123456@202.168.40.35:554/Streaming/Channels/102",
                "resolution": "1920x1080",
                "status": "stable"
            }]

    def save_to_database(self, filename, camera_name, local_path, resolution, file_size_kb, status='pending'):
        """Save capture information to database"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT OR REPLACE INTO upload_tracking
                (filename, camera_name, local_path, capture_timestamp, upload_status,
                 file_size_kb, resolution, upload_attempts)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0)
            ''', (filename, camera_name, local_path, datetime.now(), status, file_size_kb, resolution))

            conn.commit()
            return True
        except Exception as e:
            print(f"❌ Database error: {e}")
            return False
        finally:
            conn.close()

    def update_upload_status(self, filename, status, url=None, error=None):
        """Update upload status in database"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        try:
            if status == 'success' and url:
                cursor.execute('''
                    UPDATE upload_tracking
                    SET upload_status = ?, supabase_url = ?, last_attempt = ?
                    WHERE filename = ?
                ''', (status, url, datetime.now(), filename))
            else:
                cursor.execute('''
                    UPDATE upload_tracking
                    SET upload_status = ?, error_message = ?,
                        upload_attempts = upload_attempts + 1, last_attempt = ?
                    WHERE filename = ?
                ''', (status, error, datetime.now(), filename))

            conn.commit()
        except Exception as e:
            print(f"❌ Database update error: {e}")
        finally:
            conn.close()

    def upload_to_supabase_storage(self, image_data, filename, retry_count=0):
        """Upload image to Supabase storage with retry logic"""
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
                return False, f"Upload failed: {response.status_code} - {response.text}"

        except requests.exceptions.Timeout:
            return False, "Upload timeout"
        except requests.exceptions.ConnectionError:
            return False, "Connection error"
        except Exception as e:
            return False, f"Exception during upload: {str(e)}"

    def insert_snapshot_record(self, image_url, camera_name, resolution, file_size_kb):
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

            url = f"{SUPABASE_URL}/rest/v1/ase_snapshot"
            response = requests.post(url, headers=headers, json=data, timeout=10)

            if response.status_code in [200, 201]:
                return True, "Record inserted successfully"
            else:
                return False, f"Insert failed: {response.status_code} - {response.text}"

        except Exception as e:
            return False, f"Exception during insert: {str(e)}"

    def save_local_backup(self, image_data, camera_name, timestamp, resolution):
        """Save image to local backup directory"""
        try:
            filename = f"{timestamp}_{resolution.replace('x', '_')}.jpg"
            local_path = self.backup_dir / camera_name / filename

            # Write image to file
            with open(local_path, 'wb') as f:
                f.write(image_data)

            return True, str(local_path), filename
        except Exception as e:
            print(f"❌ Local save failed: {e}")
            return False, None, None

    def test_camera_connection(self, camera_config):
        """Test if camera is accessible before starting capture"""
        rtsp_url = camera_config['rtsp_url']

        try:
            cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            start_time = time.time()
            while not cap.isOpened() and (time.time() - start_time) < CONNECTION_TIMEOUT:
                time.sleep(0.1)

            if not cap.isOpened():
                cap.release()
                return False, "Connection timeout"

            ret, frame = cap.read()
            cap.release()

            if ret and frame is not None:
                return True, "Connected successfully"
            else:
                return False, "No frame received"

        except Exception as e:
            return False, f"Exception: {str(e)}"

    def capture_and_process_screenshot(self, camera_config):
        """Capture screenshot with local backup and Supabase upload"""
        camera_ip = camera_config['ip']
        rtsp_url = camera_config['rtsp_url']

        for attempt in range(RETRY_ATTEMPTS):
            try:
                cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

                start_time = time.time()
                while not cap.isOpened() and (time.time() - start_time) < CONNECTION_TIMEOUT:
                    time.sleep(0.1)

                if not cap.isOpened():
                    cap.release()
                    print(f"❌ Camera {camera_ip} - Connection failed (attempt {attempt + 1})")
                    continue

                ret, frame = cap.read()
                cap.release()

                if ret and frame is not None:
                    # Encode image
                    success, buffer = cv2.imencode('.jpg', frame)
                    if not success:
                        print(f"❌ {camera_ip}: Failed to encode image")
                        continue

                    image_data = buffer.tobytes()
                    file_size_kb = len(image_data) / 1024

                    # Prepare metadata
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    camera_suffix = camera_ip.split('.')[-1]
                    camera_name = f"camera_{camera_suffix}"
                    resolution = camera_config['resolution']

                    # Step 1: Always save local backup first
                    local_success, local_path, local_filename = self.save_local_backup(
                        image_data, camera_name, timestamp, resolution
                    )

                    if not local_success:
                        print(f"❌ {camera_ip}: Failed to save local backup")
                        continue

                    # Step 2: Try Supabase upload
                    supabase_filename = f"{camera_name}/{timestamp}_{resolution.replace('x', '_')}.jpg"
                    upload_success, result = self.upload_to_supabase_storage(image_data, supabase_filename)

                    if upload_success:
                        # Step 3: Insert database record
                        db_success, db_result = self.insert_snapshot_record(
                            result, camera_name, resolution, file_size_kb
                        )

                        if db_success:
                            print(f"✅ {camera_ip}: Uploaded to Supabase ({file_size_kb:.1f} KB)")
                            self.successful_uploads += 1

                            # Update tracking database
                            self.save_to_database(local_filename, camera_name, local_path,
                                                resolution, file_size_kb, 'success')
                            self.update_upload_status(local_filename, 'success', result)

                            # Delete local backup after successful upload
                            try:
                                os.remove(local_path)
                            except:
                                pass

                            return True, supabase_filename
                        else:
                            print(f"⚠️ {camera_ip}: Upload OK but database insert failed")
                            self.save_to_database(local_filename, camera_name, local_path,
                                                resolution, file_size_kb, 'pending')
                    else:
                        # Upload failed - keep local backup
                        print(f"💾 {camera_ip}: Saved to local backup (Supabase unavailable)")
                        self.failed_uploads += 1
                        self.save_to_database(local_filename, camera_name, local_path,
                                            resolution, file_size_kb, 'pending')
                        return True, local_path  # Still considered success (saved locally)

                else:
                    print(f"⚠️ Camera {camera_ip} - No frame received (attempt {attempt + 1})")

            except Exception as e:
                print(f"❌ Camera {camera_ip} - Exception: {str(e)} (attempt {attempt + 1})")

            time.sleep(1)

        return False, "All attempts failed"

    def start_retry_thread(self):
        """Start background thread for retrying failed uploads"""
        def retry_worker():
            while self.running:
                time.sleep(RETRY_INTERVAL)
                self.sync_pending_uploads()

        retry_thread = threading.Thread(target=retry_worker, daemon=True)
        retry_thread.start()
        print("🔄 Background retry thread started")

    def sync_pending_uploads(self):
        """Retry uploading pending items from local backup"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Get pending uploads (max 5 attempts)
        cursor.execute('''
            SELECT filename, local_path, camera_name, resolution, file_size_kb
            FROM upload_tracking
            WHERE upload_status = 'pending'
            AND upload_attempts < ?
            ORDER BY capture_timestamp ASC
            LIMIT 20
        ''', (MAX_RETRY_ATTEMPTS,))

        pending_uploads = cursor.fetchall()
        conn.close()

        if pending_uploads:
            print(f"🔄 Retrying {len(pending_uploads)} pending uploads...")

            for filename, local_path, camera_name, resolution, file_size_kb in pending_uploads:
                if not os.path.exists(local_path):
                    self.update_upload_status(filename, 'missing')
                    continue

                try:
                    with open(local_path, 'rb') as f:
                        image_data = f.read()

                    supabase_filename = f"{camera_name}/{filename}"
                    upload_success, result = self.upload_to_supabase_storage(image_data, supabase_filename)

                    if upload_success:
                        db_success, _ = self.insert_snapshot_record(result, camera_name, resolution, file_size_kb)
                        if db_success:
                            print(f"✅ Retry successful: {filename}")
                            self.update_upload_status(filename, 'success', result)
                            os.remove(local_path)  # Clean up after success
                        else:
                            self.update_upload_status(filename, 'pending', error="DB insert failed")
                    else:
                        self.update_upload_status(filename, 'pending', error=result)

                except Exception as e:
                    self.update_upload_status(filename, 'pending', error=str(e))

    def capture_all_cameras(self):
        """Capture screenshots from all working cameras with resilience"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n🎯 Capture round {self.capture_count + 1} at {timestamp}")
        print(f"📊 Stats: ✅ {self.successful_uploads} uploaded | 💾 {self.failed_uploads} in backup")
        print("-" * 50)

        successful_captures = 0
        failed_captures = 0

        threads = []
        results = {}

        def capture_worker(camera_config):
            camera_ip = camera_config['ip']
            success, result = self.capture_and_process_screenshot(camera_config)
            results[camera_ip] = (success, result)

        for camera_config in WORKING_CAMERAS:
            thread = threading.Thread(target=capture_worker, args=(camera_config,))
            thread.start()
            threads.append(thread)

        for thread in threads:
            thread.join()

        for camera_ip, (success, result) in results.items():
            if success:
                successful_captures += 1
            else:
                failed_captures += 1

        self.capture_count += 1

        print(f"📊 Round {self.capture_count} Summary: ✅ {successful_captures} captured, ❌ {failed_captures} failed")

        return successful_captures, failed_captures

    def get_backup_statistics(self):
        """Get statistics about backup queue"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute('''
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN upload_status = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN upload_status = 'success' THEN 1 ELSE 0 END) as success,
                SUM(CASE WHEN upload_status = 'failed' THEN 1 ELSE 0 END) as failed
            FROM upload_tracking
        ''')

        stats = cursor.fetchone()
        conn.close()

        return stats

    def should_continue_running(self):
        """Check if the script should continue running"""
        current_time = datetime.now()

        if current_time.hour >= STOP_TIME:
            print(f"⏰ Reached stop time (10 PM). Shutting down.")
            return False

        runtime_hours = (current_time - self.start_time).total_seconds() / 3600
        if runtime_hours >= MAX_RUNTIME_HOURS:
            print(f"⏰ Reached maximum runtime ({MAX_RUNTIME_HOURS} hours). Exiting for restart.")
            return False

        return True

    def run_continuous_capture(self):
        """Run continuous screenshot capture with resilience"""
        print("🎥 Starting RESILIENT Linux camera capture with Supabase integration...")
        print(f"📋 Monitoring {len(WORKING_CAMERAS)} cameras")
        print(f"⏱️ Capture interval: {CAPTURE_INTERVAL} seconds ({CAPTURE_INTERVAL//60} minutes)")
        print(f"☁️ Supabase storage: {STORAGE_BUCKET} bucket")
        print(f"💾 Local backup: {self.backup_dir}")
        print(f"🔄 Retry interval: {RETRY_INTERVAL} seconds")
        print(f"⏰ Will run until 10 PM or {MAX_RUNTIME_HOURS} hours")
        print("=" * 60)

        # Test cameras
        print("🔍 Testing camera connections...")
        working_cameras = []
        for camera_config in WORKING_CAMERAS:
            success, message = self.test_camera_connection(camera_config)
            if success:
                working_cameras.append(camera_config)
                print(f"✅ {camera_config['ip']}: {message}")
            else:
                print(f"❌ {camera_config['ip']}: {message}")

        if not working_cameras:
            print("😞 No working cameras found. Exiting.")
            return

        print(f"\n🎯 Starting capture with {len(working_cameras)} working cameras")

        # Show backup statistics
        stats = self.get_backup_statistics()
        if stats and stats[0] > 0:
            print(f"📊 Backup queue: {stats[1]} pending, {stats[2]} uploaded, {stats[3]} failed")

        print("=" * 60)

        WORKING_CAMERAS[:] = working_cameras
        self.running = True

        try:
            while self.running and self.should_continue_running():
                successful, failed = self.capture_all_cameras()

                if not self.should_continue_running():
                    break

                print(f"⏳ Next capture in {CAPTURE_INTERVAL//60} minutes...")

                sleep_time = 0
                while sleep_time < CAPTURE_INTERVAL and self.running:
                    time.sleep(10)
                    sleep_time += 10

                    if not self.should_continue_running():
                        break

        except KeyboardInterrupt:
            print("\n⚠️ Capture stopped by user")

        finally:
            self.running = False
            runtime = (datetime.now() - self.start_time).total_seconds() / 60

            # Final statistics
            stats = self.get_backup_statistics()

            print(f"\n✅ Capture session complete!")
            print(f"📊 Session Summary:")
            print(f"   • Total rounds: {self.capture_count}")
            print(f"   • Runtime: {runtime:.1f} minutes")
            print(f"   • Successful uploads: {self.successful_uploads}")
            print(f"   • Failed (in backup): {self.failed_uploads}")
            if stats:
                print(f"   • Backup queue: {stats[1]} pending for retry")
            print(f"☁️ Images in Supabase: {STORAGE_BUCKET} bucket")
            print(f"💾 Local backups: {self.backup_dir}")

def main():
    """Main function to run resilient Supabase-integrated screenshot capture"""
    agent = ResilientSupabaseAgent()
    agent.run_continuous_capture()

if __name__ == "__main__":
    main()