#!/usr/bin/env python3
"""
ASE Restaurant Surveillance Service - Automated Daemon
Version: 2.0.0
Created: 2025-11-16
Modified: 2025-11-16 - v2.0.0: Multiple capture windows and midnight processing

Purpose:
- Fully automated surveillance system that runs continuously
- Automatically captures video during business hours (11:30 AM - 2 PM, 5 PM - 10 PM)
- Automatically processes video overnight (12:00 AM - 11:00 PM target completion)
- Continuously monitors system health (GPU, disk, database)
- Syncs data to cloud hourly
- No manual intervention required after initialization

Usage:
    # Start service
    python3 surveillance_service.py start

    # Stop service
    python3 surveillance_service.py stop

    # Check status
    python3 surveillance_service.py status

    # Run in foreground (for debugging)
    python3 surveillance_service.py --foreground

Architecture:
    Main Thread: Service controller and scheduler
    Thread 1: Video capture (11:30 AM - 2 PM, 5 PM - 10 PM - dual windows)
    Thread 2: Video processing (12:00 AM - 11:00 PM target completion)
    Thread 3: Disk space monitoring (every hour)
    Thread 4: GPU monitoring (every 5 minutes)
    Thread 5: Database sync (every hour)
"""

import os
import sys
import time
import signal
import threading
import subprocess
from pathlib import Path
from datetime import datetime, time as dt_time
from typing import Optional
import logging
import json

# Project paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

# Configuration
PID_FILE = PROJECT_ROOT / "surveillance_service.pid"
LOG_FILE = PROJECT_ROOT / "logs" / "surveillance_service.log"
CONFIG_DIR = PROJECT_ROOT / "scripts" / "config"

# Operating hours - Multiple capture windows per day
CAPTURE_WINDOWS = [
    {"start_hour": 11, "start_minute": 30, "end_hour": 14, "end_minute": 0},  # 11:30 AM - 2:00 PM (morning)
    {"start_hour": 17, "start_minute": 0, "end_hour": 22, "end_minute": 0}    # 5:00 PM - 10:00 PM (evening)
]
PROCESS_START_HOUR = 0   # 12:00 AM (midnight)
PROCESS_END_HOUR = 23    # 11:00 PM (target completion time - warning if exceeded)

# Monitoring intervals (seconds)
DISK_CHECK_INTERVAL = 3600      # 1 hour
GPU_CHECK_INTERVAL = 300        # 5 minutes
DB_SYNC_INTERVAL = 3600         # 1 hour
HEALTH_CHECK_INTERVAL = 1800    # 30 minutes


class SurveillanceService:
    """
    Automated surveillance service daemon
    Version: 2.0.0
    """

    def __init__(self, foreground=False):
        self.foreground = foreground
        self.running = False
        self.capture_process = None
        self.processing_process = None
        self.current_capture_window = None  # Track which window is currently active

        # Monitoring threads
        self.threads = []

        # Setup logging
        self.setup_logging()

        # Signal handlers
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)

    def setup_logging(self):
        """Configure logging

        Note: Log cleanup is handled by scripts/maintenance/cleanup_logs.sh
        """
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(LOG_FILE),
                logging.StreamHandler() if self.foreground else logging.NullHandler()
            ]
        )
        self.logger = logging.getLogger('SurveillanceService')

    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.stop()
        sys.exit(0)

    def is_in_time_window(self, start_hour: int, end_hour: int) -> bool:
        """Check if current time is within specified window (legacy method for processing window)"""
        now = datetime.now().time()
        current_hour = now.hour

        if start_hour < end_hour:
            # Same day window (e.g., 0 AM - 11 PM)
            return start_hour <= current_hour < end_hour
        else:
            # Overnight window (e.g., 11 PM - 6 AM)
            return current_hour >= start_hour or current_hour < end_hour

    def is_in_capture_window(self) -> tuple:
        """
        Check if current time is within any capture window
        Returns: (bool, dict or None) - (in_window, window_config)
        """
        now = datetime.now()
        current_hour = now.hour
        current_minute = now.minute

        for window in CAPTURE_WINDOWS:
            start_hour = window["start_hour"]
            start_minute = window["start_minute"]
            end_hour = window["end_hour"]
            end_minute = window["end_minute"]

            # Convert to minutes since midnight for easier comparison
            current_total_minutes = current_hour * 60 + current_minute
            start_total_minutes = start_hour * 60 + start_minute
            end_total_minutes = end_hour * 60 + end_minute

            if start_total_minutes <= current_total_minutes < end_total_minutes:
                return (True, window)

        return (False, None)

    def start_video_capture(self):
        """Start video capture if in any capture window"""
        in_window, window = self.is_in_capture_window()

        if not in_window:
            self.logger.info("Outside capture windows, skipping video capture")
            return

        if self.capture_process and self.capture_process.poll() is None:
            self.logger.info("Video capture already running")
            return

        # Determine which window (morning or evening)
        window_name = "morning" if window["start_hour"] == 11 else "evening"
        self.logger.info(f"Starting video capture ({window_name} window)...")
        capture_script = PROJECT_ROOT / "scripts" / "video_capture" / "capture_rtsp_streams.py"

        # Calculate duration until end of current capture window
        now = datetime.now()
        end_time = now.replace(
            hour=window["end_hour"],
            minute=window["end_minute"],
            second=0,
            microsecond=0
        )

        if end_time <= now:
            # Already past end time for this window
            self.logger.warning(f"Already past end time for {window_name} window")
            return

        duration = int((end_time - now).total_seconds())

        try:
            self.capture_process = subprocess.Popen(
                ["python3", str(capture_script), "--duration", str(duration)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            self.current_capture_window = window  # Track active window
            self.logger.info(f"Video capture started (PID: {self.capture_process.pid}, {window_name} window, duration: {duration}s)")
        except Exception as e:
            self.logger.error(f"Failed to start video capture: {e}")

    def start_video_processing(self):
        """
        Start video processing if in processing hours
        Processes previous day's videos captured during 11:30 AM - 2 PM and 5 PM - 10 PM
        Target completion: 11 PM (warning logged if exceeded)
        """
        if not self.is_in_time_window(PROCESS_START_HOUR, PROCESS_END_HOUR):
            self.logger.info("Outside processing hours, skipping video processing")
            return

        if self.processing_process and self.processing_process.poll() is None:
            self.logger.info("Video processing already running")
            return

        self.logger.info("Starting video processing (previous day's footage)...")
        self.logger.info(f"Target completion: {PROCESS_END_HOUR:02d}:00 (warning if exceeded)")
        orchestrator_script = PROJECT_ROOT / "scripts" / "orchestration" / "process_videos_orchestrator.py"

        try:
            self.processing_process = subprocess.Popen(
                ["python3", str(orchestrator_script)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            self.logger.info(f"Video processing started (PID: {self.processing_process.pid})")
        except Exception as e:
            self.logger.error(f"Failed to start video processing: {e}")

    def monitor_disk_space(self):
        """Monitor disk space continuously"""
        while self.running:
            try:
                self.logger.info("Running disk space check...")
                check_script = PROJECT_ROOT / "scripts" / "monitoring" / "check_disk_space.py"

                result = subprocess.run(
                    ["python3", str(check_script), "--check"],
                    capture_output=True,
                    text=True
                )

                if result.returncode == 2:  # Critical
                    self.logger.error("CRITICAL: Disk space issue detected!")
                    # Auto-cleanup
                    subprocess.run(["python3", str(check_script), "--cleanup"])
                elif result.returncode == 1:  # Warning
                    self.logger.warning("Disk space warning")

            except Exception as e:
                self.logger.error(f"Disk check failed: {e}")

            # Wait for next check
            time.sleep(DISK_CHECK_INTERVAL)

    def monitor_gpu(self):
        """Monitor GPU continuously"""
        while self.running:
            try:
                self.logger.debug("Checking GPU status...")
                gpu_script = PROJECT_ROOT / "scripts" / "monitoring" / "monitor_gpu.py"

                result = subprocess.run(
                    ["python3", str(gpu_script)],
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                # Parse GPU temperature from output
                if "Temperature:" in result.stdout:
                    temp_line = [line for line in result.stdout.split('\n') if 'Temperature:' in line]
                    if temp_line:
                        self.logger.debug(f"GPU: {temp_line[0].strip()}")

            except Exception as e:
                self.logger.error(f"GPU check failed: {e}")

            time.sleep(GPU_CHECK_INTERVAL)

    def sync_database(self):
        """Sync database to cloud hourly"""
        while self.running:
            try:
                self.logger.info("Syncing database to Supabase...")
                sync_script = PROJECT_ROOT / "scripts" / "database_sync" / "sync_to_supabase.py"

                result = subprocess.run(
                    ["python3", str(sync_script), "--mode", "hourly"],
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minute timeout
                )

                if result.returncode == 0:
                    self.logger.info("Database sync completed")
                else:
                    self.logger.error(f"Database sync failed: {result.stderr}")

            except Exception as e:
                self.logger.error(f"Database sync failed: {e}")

            time.sleep(DB_SYNC_INTERVAL)

    def health_check(self):
        """Periodic health check"""
        while self.running:
            try:
                status = {
                    'timestamp': datetime.now().isoformat(),
                    'capture_running': self.capture_process and self.capture_process.poll() is None,
                    'processing_running': self.processing_process and self.processing_process.poll() is None,
                    'threads_alive': sum(1 for t in self.threads if t.is_alive())
                }

                self.logger.info(f"Health check: {status}")

                # Restart capture if it should be running but isn't
                in_window, window = self.is_in_capture_window()
                if in_window:
                    if not status['capture_running']:
                        self.logger.warning("Capture stopped unexpectedly, restarting...")
                        self.start_video_capture()

                # Restart processing if it should be running but isn't
                if self.is_in_time_window(PROCESS_START_HOUR, PROCESS_END_HOUR):
                    if not status['processing_running']:
                        self.logger.warning("Processing stopped unexpectedly, restarting...")
                        self.start_video_processing()

            except Exception as e:
                self.logger.error(f"Health check failed: {e}")

            time.sleep(HEALTH_CHECK_INTERVAL)

    def scheduler_loop(self):
        """Main scheduler loop - handles multiple capture windows per day"""
        self.logger.info("Starting scheduler loop...")

        while self.running:
            try:
                now = datetime.now()
                current_hour = now.hour
                current_minute = now.minute

                # Check each capture window
                for window in CAPTURE_WINDOWS:
                    start_hour = window["start_hour"]
                    start_minute = window["start_minute"]
                    end_hour = window["end_hour"]
                    end_minute = window["end_minute"]

                    # Check if we should start this capture window
                    if current_hour == start_hour and current_minute == start_minute:
                        self.start_video_capture()

                    # Check if this capture window ended
                    if current_hour == end_hour and current_minute == end_minute:
                        if self.capture_process and self.capture_process.poll() is None:
                            window_name = "morning" if start_hour == 11 else "evening"
                            self.logger.info(f"{window_name.capitalize()} capture window ended, stopping capture...")
                            self.capture_process.terminate()
                            self.current_capture_window = None

                # Check if we should start video processing (midnight)
                if current_hour == PROCESS_START_HOUR and current_minute == 0:
                    self.start_video_processing()

                # Check if processing should have completed (11 PM warning)
                if current_hour == PROCESS_END_HOUR and current_minute == 0:
                    if self.processing_process and self.processing_process.poll() is None:
                        self.logger.warning("⚠️  WARNING: Video processing still running after 11 PM target completion time!")
                        self.logger.warning("⚠️  Processing may not finish before next day's capture window starts.")

            except Exception as e:
                self.logger.error(f"Scheduler error: {e}")

            # Sleep for 30 seconds before next check
            time.sleep(30)

    def start(self):
        """Start the service"""
        # Check if already running
        if PID_FILE.exists():
            with open(PID_FILE) as f:
                old_pid = int(f.read().strip())

            # Check if process is actually running
            try:
                os.kill(old_pid, 0)
                print(f"Service already running (PID: {old_pid})")
                return False
            except OSError:
                # Process not running, remove stale PID file
                PID_FILE.unlink()

        # Write PID file
        with open(PID_FILE, 'w') as f:
            f.write(str(os.getpid()))

        self.running = True
        self.logger.info("=" * 70)
        self.logger.info("ASE Surveillance Service Starting v2.0.0")
        self.logger.info("=" * 70)
        self.logger.info("Capture windows (dual schedule):")
        for i, window in enumerate(CAPTURE_WINDOWS, 1):
            window_name = "Morning" if window["start_hour"] == 11 else "Evening"
            self.logger.info(f"  {window_name}: {window['start_hour']:02d}:{window['start_minute']:02d} - {window['end_hour']:02d}:{window['end_minute']:02d}")
        self.logger.info(f"Processing hours: {PROCESS_START_HOUR:02d}:00 - {PROCESS_END_HOUR:02d}:00 (target completion)")
        self.logger.info("=" * 70)

        # Start monitoring threads
        self.threads = [
            threading.Thread(target=self.monitor_disk_space, name="DiskMonitor", daemon=True),
            threading.Thread(target=self.monitor_gpu, name="GPUMonitor", daemon=True),
            threading.Thread(target=self.sync_database, name="DBSync", daemon=True),
            threading.Thread(target=self.health_check, name="HealthCheck", daemon=True)
        ]

        for thread in self.threads:
            thread.start()
            self.logger.info(f"Started thread: {thread.name}")

        # Start initial processes if in time windows
        in_capture_window, _ = self.is_in_capture_window()
        if in_capture_window:
            self.start_video_capture()

        if self.is_in_time_window(PROCESS_START_HOUR, PROCESS_END_HOUR):
            self.start_video_processing()

        # Run scheduler loop
        try:
            self.scheduler_loop()
        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received")
        finally:
            self.stop()

    def stop(self):
        """Stop the service"""
        self.logger.info("Stopping surveillance service...")
        self.running = False

        # Stop capture process
        if self.capture_process and self.capture_process.poll() is None:
            self.logger.info("Stopping video capture...")
            self.capture_process.terminate()
            self.capture_process.wait(timeout=10)

        # Stop processing process
        if self.processing_process and self.processing_process.poll() is None:
            self.logger.info("Stopping video processing...")
            self.processing_process.terminate()
            self.processing_process.wait(timeout=10)

        # Wait for threads to finish
        self.logger.info("Waiting for monitoring threads to stop...")
        for thread in self.threads:
            thread.join(timeout=5)

        # Remove PID file
        if PID_FILE.exists():
            PID_FILE.unlink()

        self.logger.info("Service stopped")

    def status(self):
        """Check service status"""
        if not PID_FILE.exists():
            print("❌ Service is not running")
            return False

        with open(PID_FILE) as f:
            pid = int(f.read().strip())

        try:
            os.kill(pid, 0)
            print(f"✅ Service is running (PID: {pid})")

            # Show current status
            print("\n📊 Current Status:")
            now = datetime.now()
            print(f"Time: {now.strftime('%Y-%m-%d %H:%M:%S')}")

            # Check which capture window we're in
            in_capture_window, current_window = self.is_in_capture_window()
            if in_capture_window:
                window_name = "Morning" if current_window["start_hour"] == 11 else "Evening"
                print(f"Capture window: 🟢 ACTIVE ({window_name})")
            else:
                print(f"Capture window: 🔴 INACTIVE")
                # Show next window
                print("Next capture windows:")
                for window in CAPTURE_WINDOWS:
                    window_name = "Morning" if window["start_hour"] == 11 else "Evening"
                    print(f"  {window_name}: {window['start_hour']:02d}:{window['start_minute']:02d} - {window['end_hour']:02d}:{window['end_minute']:02d}")

            in_process_window = self.is_in_time_window(PROCESS_START_HOUR, PROCESS_END_HOUR)
            print(f"Processing window: {'🟢 ACTIVE' if in_process_window else '🔴 INACTIVE'}")

            return True
        except OSError:
            print(f"❌ Service not running (stale PID file)")
            PID_FILE.unlink()
            return False


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="ASE Surveillance Service Daemon")
    parser.add_argument("command", nargs='?', choices=['start', 'stop', 'status', 'restart'],
                       default='start', help="Service command")
    parser.add_argument("--foreground", action="store_true",
                       help="Run in foreground (don't daemonize)")

    args = parser.parse_args()

    service = SurveillanceService(foreground=args.foreground)

    if args.command == 'start':
        service.start()
    elif args.command == 'stop':
        if PID_FILE.exists():
            with open(PID_FILE) as f:
                pid = int(f.read().strip())
            try:
                os.kill(pid, signal.SIGTERM)
                print(f"Sent stop signal to service (PID: {pid})")
            except OSError:
                print("Service not running")
                PID_FILE.unlink()
        else:
            print("Service not running")
    elif args.command == 'status':
        service.status()
    elif args.command == 'restart':
        # Stop first
        if PID_FILE.exists():
            with open(PID_FILE) as f:
                pid = int(f.read().strip())
            try:
                os.kill(pid, signal.SIGTERM)
                time.sleep(2)
            except OSError:
                pass
        # Then start
        service.start()


if __name__ == "__main__":
    main()
