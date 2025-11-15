#!/usr/bin/env python3
"""
ASE Restaurant Surveillance System - Main Entry Point
Version: 1.0.0
Created: 2025-11-15

Purpose:
- Main entry point for the entire RTX 3060 surveillance application
- Guides user through initial setup or starts monitoring
- Checks prerequisites and system health

Usage:
    python3 start.py

Workflow:
    1. Check if system is initialized (location + cameras registered)
    2. If not initialized → Run deployment wizard
    3. If initialized → Show status and start options
    4. Verify system health before starting
"""

import os
import sys
import sqlite3
from pathlib import Path
from datetime import datetime

# Project paths
PROJECT_ROOT = Path(__file__).parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
DB_PATH = PROJECT_ROOT / "db" / "detection_data.db"

# Add scripts to path
sys.path.insert(0, str(SCRIPTS_DIR))


class SurveillanceApp:
    """
    Main application controller
    Version: 1.0.0
    """

    def __init__(self):
        self.initialized = False
        self.location_id = None
        self.camera_count = 0

    def run(self):
        """Main application flow"""
        self.print_banner()

        # Check initialization status
        if not self.check_initialization():
            print("\n🔧 System Not Initialized")
            print("=" * 70)
            print("\nThis appears to be a fresh installation.")
            print("Let's set up your restaurant location and cameras.\n")

            choice = input("Run initialization wizard? (y/n): ").strip().lower()
            if choice == 'y':
                self.run_initialization()
            else:
                print("\n⚠️  System must be initialized before use.")
                print("Run: python3 scripts/deployment/initialize_restaurant.py")
                sys.exit(0)

        # Show system status
        self.show_status()

        # Main menu
        self.show_main_menu()

    def print_banner(self):
        """Print application banner"""
        print("\n" + "=" * 70)
        print("🏪 ASE Restaurant Surveillance System - RTX 3060")
        print("=" * 70)
        print(f"Location: 野百灵火锅店 (Ye Bai Ling Hotpot)")
        print(f"System: Production RTX 3060 Edge Processing")
        print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70 + "\n")

    def check_initialization(self) -> bool:
        """Check if system is initialized"""
        if not DB_PATH.exists():
            return False

        try:
            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.cursor()

            # Check if locations table exists and has data
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='locations'
            """)
            if not cursor.fetchone():
                conn.close()
                return False

            # Check if location registered
            cursor.execute("SELECT location_id FROM locations LIMIT 1")
            row = cursor.fetchone()
            if not row:
                conn.close()
                return False

            self.location_id = row[0]

            # Check cameras
            cursor.execute("SELECT COUNT(*) FROM cameras WHERE location_id = ?", (self.location_id,))
            self.camera_count = cursor.fetchone()[0]

            conn.close()
            self.initialized = True
            return True

        except Exception as e:
            print(f"⚠️  Database error: {e}")
            return False

    def run_initialization(self):
        """Run deployment initialization wizard"""
        print("\n🚀 Starting Initialization Wizard...")
        print("=" * 70 + "\n")

        # First, migrate database
        print("Step 1: Database Migration")
        migrate_script = SCRIPTS_DIR / "deployment" / "migrate_database.py"
        os.system(f"python3 {migrate_script} --backup")

        print("\nStep 2: Restaurant Setup")
        init_script = SCRIPTS_DIR / "deployment" / "initialize_restaurant.py"
        os.system(f"python3 {init_script}")

        print("\n✅ Initialization complete!")
        print("\nRestarting application...\n")

        # Recheck initialization
        if self.check_initialization():
            self.show_status()
            self.show_main_menu()
        else:
            print("❌ Initialization failed. Please check the errors above.")
            sys.exit(1)

    def show_status(self):
        """Display current system status"""
        print("\n📊 System Status")
        print("=" * 70)
        print(f"✅ Initialized: Yes")
        print(f"📍 Location ID: {self.location_id}")
        print(f"📷 Cameras: {self.camera_count} configured")

        # Check disk space
        try:
            import shutil
            total, used, free = shutil.disk_usage(str(PROJECT_ROOT))
            free_gb = free // (2**30)
            print(f"💾 Disk Space: {free_gb} GB free")
        except:
            print(f"💾 Disk Space: Unable to check")

        print("=" * 70 + "\n")

    def show_main_menu(self):
        """Show main menu and handle user choice"""
        while True:
            print("\n🎯 Main Menu")
            print("=" * 70)
            print("1. 📹 Start Video Capture (RTSP Recording)")
            print("2. 🎬 Process Videos (AI Detection)")
            print("3. 🔧 System Configuration")
            print("4. 📊 View System Logs")
            print("5. 🏥 Health Check")
            print("6. ❌ Exit")
            print("=" * 70)

            choice = input("\nSelect option (1-6): ").strip()

            if choice == '1':
                self.start_video_capture()
            elif choice == '2':
                self.start_video_processing()
            elif choice == '3':
                self.system_configuration()
            elif choice == '4':
                self.view_logs()
            elif choice == '5':
                self.health_check()
            elif choice == '6':
                print("\n👋 Exiting ASE Surveillance System\n")
                sys.exit(0)
            else:
                print("\n❌ Invalid option. Please select 1-6.")

    def start_video_capture(self):
        """Start RTSP video capture"""
        print("\n📹 Starting Video Capture...")
        print("=" * 70)

        capture_script = SCRIPTS_DIR / "video_capture" / "capture_rtsp_streams.py"

        if not capture_script.exists():
            print(f"❌ Capture script not found: {capture_script}")
            return

        print(f"\nStarting: {capture_script}")
        print("Press Ctrl+C to stop\n")

        os.system(f"python3 {capture_script}")

    def start_video_processing(self):
        """Start video processing"""
        print("\n🎬 Video Processing Options")
        print("=" * 70)
        print("1. Process All Unprocessed Videos")
        print("2. Process Specific Video")
        print("3. Interactive ROI Setup")
        print("4. Back to Main Menu")

        choice = input("\nSelect option (1-4): ").strip()

        if choice == '1':
            orchestrator = SCRIPTS_DIR / "orchestration" / "process_videos_orchestrator.py"
            os.system(f"python3 {orchestrator}")
        elif choice == '2':
            video_path = input("Video path: ").strip()
            detection_script = SCRIPTS_DIR / "video_processing" / "table_and_region_state_detection.py"
            os.system(f"python3 {detection_script} --video {video_path}")
        elif choice == '3':
            print("\nLaunching Interactive ROI Setup...")
            os.system(f"cd {SCRIPTS_DIR} && ./run_interactive.sh")
        elif choice == '4':
            return

    def sync_to_cloud(self):
        """Sync data to Supabase"""
        print("\n☁️  Supabase Cloud Sync")
        print("=" * 70)
        print("1. Hourly Sync (last 2 hours)")
        print("2. Full Sync (all unsynced)")
        print("3. Dry Run (test without uploading)")
        print("4. Back to Main Menu")

        choice = input("\nSelect option (1-4): ").strip()

        sync_script = SCRIPTS_DIR / "database_sync" / "sync_to_supabase.py"

        if choice == '1':
            os.system(f"python3 {sync_script} --mode hourly")
        elif choice == '2':
            os.system(f"python3 {sync_script} --mode full")
        elif choice == '3':
            os.system(f"python3 {sync_script} --mode hourly --dry-run")
        elif choice == '4':
            return

    def system_configuration(self):
        """System configuration menu"""
        print("\n🔧 System Configuration")
        print("=" * 70)
        print("1. View Current Configuration")
        print("2. Re-run Restaurant Initialization")
        print("3. Update Camera Configuration")
        print("4. Back to Main Menu")

        choice = input("\nSelect option (1-4): ").strip()

        if choice == '1':
            config_dir = SCRIPTS_DIR / "config"
            os.system(f"ls -lh {config_dir}")
        elif choice == '2':
            init_script = SCRIPTS_DIR / "deployment" / "initialize_restaurant.py"
            os.system(f"python3 {init_script}")
        elif choice == '3':
            print("\nEdit: scripts/config/cameras_config.json")
        elif choice == '4':
            return

    def view_logs(self):
        """View system logs"""
        print("\n📊 System Logs")
        print("=" * 70)

        # Check common log locations
        log_paths = [
            "/var/log/ase_sync.log",
            PROJECT_ROOT / "logs" / "system.log"
        ]

        for log_path in log_paths:
            if Path(log_path).exists():
                print(f"\nShowing: {log_path}")
                os.system(f"tail -50 {log_path}")
                return

        print("\n⚠️  No log files found")

    def health_check(self):
        """Run system health check"""
        print("\n🏥 System Health Check")
        print("=" * 70 + "\n")

        # Disk space
        monitoring_script = SCRIPTS_DIR / "monitoring" / "check_disk_space.py"
        if monitoring_script.exists():
            os.system(f"python3 {monitoring_script} --check")

        # GPU
        gpu_script = SCRIPTS_DIR / "monitoring" / "monitor_gpu.py"
        if gpu_script.exists():
            os.system(f"python3 {gpu_script}")

        # Database
        print("\nDatabase Status:")
        try:
            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM sessions")
            sessions = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM division_states")
            division_states = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM table_states")
            table_states = cursor.fetchone()[0]

            print(f"  Sessions: {sessions}")
            print(f"  Division states: {division_states}")
            print(f"  Table states: {table_states}")

            conn.close()
        except Exception as e:
            print(f"  ❌ Database error: {e}")


def main():
    """Main entry point"""
    app = SurveillanceApp()

    try:
        app.run()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user\n")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
