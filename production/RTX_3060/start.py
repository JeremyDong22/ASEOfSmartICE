#!/usr/bin/env python3
"""
ASE Restaurant Surveillance System - Main Entry Point
Version: 2.0.0
Created: 2025-11-15
Updated: 2025-11-16

Purpose:
- Main entry point for the AUTOMATED RTX 3060 surveillance system
- Guides user through initial setup OR starts automated service
- Fully automated operation after initialization

Usage:
    python3 start.py                    # Start automated service
    python3 start.py --status           # Check service status
    python3 start.py --stop             # Stop service
    python3 start.py --foreground       # Run in foreground (debug mode)

Workflow:
    1. Check if system is initialized (location + cameras registered)
    2. If not initialized → Run deployment wizard
    3. If initialized → Start automated surveillance service
    4. Service automatically manages:
       - Video capture (11 AM - 9 PM)
       - Video processing (11 PM - 6 AM)
       - System monitoring (disk, GPU)
       - Database sync (hourly)

Changes in v2.0.0:
- Removed interactive menu (was manual operation)
- Added automated service daemon
- Auto-starts all components based on time schedule
- Background monitoring threads
- No manual intervention needed
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
    Version: 2.0.0
    """

    def __init__(self, mode='start', foreground=False):
        self.initialized = False
        self.location_id = None
        self.camera_count = 0
        self.mode = mode
        self.foreground = foreground

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
                # After initialization, continue to start service
            else:
                print("\n⚠️  System must be initialized before use.")
                print("Run: python3 scripts/deployment/initialize_restaurant.py")
                sys.exit(0)

        # Show system status
        self.show_status()

        # Execute command based on mode
        if self.mode == 'start':
            self.start_service()
        elif self.mode == 'stop':
            self.stop_service()
        elif self.mode == 'status':
            self.check_service_status()
        elif self.mode == 'restart':
            self.restart_service()

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

    def start_service(self):
        """Start the automated surveillance service"""
        print("\n🚀 Starting Automated Surveillance Service")
        print("=" * 70)
        print("\n📋 Service will automatically:")
        print("  ✅ Capture video: 11 AM - 9 PM")
        print("  ✅ Process video: 11 PM - 6 AM")
        print("  ✅ Monitor disk space: Every hour")
        print("  ✅ Monitor GPU: Every 5 minutes")
        print("  ✅ Sync database: Every hour")
        print("=" * 70)

        service_script = SCRIPTS_DIR / "orchestration" / "surveillance_service.py"

        if not service_script.exists():
            print(f"\n❌ Service script not found: {service_script}")
            print("Please ensure the automated service is installed.")
            sys.exit(1)

        print("\nStarting service...")

        if self.foreground:
            print("\n🔍 Running in FOREGROUND mode (Ctrl+C to stop)")
            print("Logs will be displayed below:\n")
            os.system(f"python3 {service_script} start --foreground")
        else:
            print("\n🔄 Running in BACKGROUND mode")
            print("View logs: tail -f logs/surveillance_service.log")
            print("Check status: python3 start.py --status")
            print("Stop service: python3 start.py --stop\n")

            # Start in background
            os.system(f"nohup python3 {service_script} start > /dev/null 2>&1 &")

            # Wait a moment and check if it started
            import time
            time.sleep(2)

            pid_file = PROJECT_ROOT / "surveillance_service.pid"
            if pid_file.exists():
                with open(pid_file) as f:
                    pid = f.read().strip()
                print(f"✅ Service started successfully (PID: {pid})")
                print("\n💡 The system is now fully automated. No manual intervention needed!")
            else:
                print("❌ Service failed to start. Check logs/surveillance_service.log")

    def stop_service(self):
        """Stop the surveillance service"""
        print("\n🛑 Stopping Surveillance Service")
        print("=" * 70)

        service_script = SCRIPTS_DIR / "orchestration" / "surveillance_service.py"
        os.system(f"python3 {service_script} stop")

    def check_service_status(self):
        """Check service status"""
        print("\n📊 Service Status Check")
        print("=" * 70 + "\n")

        service_script = SCRIPTS_DIR / "orchestration" / "surveillance_service.py"
        os.system(f"python3 {service_script} status")

        # Show recent logs
        log_file = PROJECT_ROOT / "logs" / "surveillance_service.log"
        if log_file.exists():
            print("\n📋 Recent Logs (last 20 lines):")
            print("=" * 70)
            os.system(f"tail -20 {log_file}")

    def restart_service(self):
        """Restart the surveillance service"""
        print("\n🔄 Restarting Surveillance Service")
        print("=" * 70)

        service_script = SCRIPTS_DIR / "orchestration" / "surveillance_service.py"
        os.system(f"python3 {service_script} restart")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="ASE Restaurant Surveillance System - Automated Service",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start automated service (default)
  python3 start.py

  # Check service status
  python3 start.py --status

  # Stop service
  python3 start.py --stop

  # Restart service
  python3 start.py --restart

  # Run in foreground (debug mode)
  python3 start.py --foreground

After initialization, the system runs FULLY AUTOMATICALLY:
- Video capture: 11 AM - 9 PM (automatic)
- Video processing: 11 PM - 6 AM (automatic)
- System monitoring: Continuous (automatic)
- Database sync: Hourly (automatic)

NO manual intervention required!
        """
    )

    parser.add_argument("--status", action="store_true",
                       help="Check service status")
    parser.add_argument("--stop", action="store_true",
                       help="Stop service")
    parser.add_argument("--restart", action="store_true",
                       help="Restart service")
    parser.add_argument("--foreground", action="store_true",
                       help="Run in foreground (don't daemonize)")

    args = parser.parse_args()

    # Determine mode
    if args.status:
        mode = 'status'
    elif args.stop:
        mode = 'stop'
    elif args.restart:
        mode = 'restart'
    else:
        mode = 'start'

    app = SurveillanceApp(mode=mode, foreground=args.foreground)

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
