#!/usr/bin/env python3
"""
ASE Restaurant Surveillance Service - Automated Daemon
Version: 1.0.0
Created: 2025-11-16

Purpose:
- Fully automated surveillance system that runs continuously
- Automatically captures video during business hours (11 AM - 9 PM)
- Automatically processes video at night (11 PM - 6 AM)
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
    Thread 1: Video capture (11 AM - 9 PM)
    Thread 2: Video processing (11 PM - 6 AM)
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

# Operating hours
CAPTURE_START_HOUR = 11  # 11 AM
CAPTURE_END_HOUR = 21    # 9 PM
PROCESS_START_HOUR = 23  # 11 PM
PROCESS_END_HOUR = 6     # 6 AM

# Monitoring intervals (seconds)
DISK_CHECK_INTERVAL = 3600      # 1 hour
GPU_CHECK_INTERVAL = 300        # 5 minutes
DB_SYNC_INTERVAL = 3600         # 1 hour
HEALTH_CHECK_INTERVAL = 1800    # 30 minutes


class SurveillanceService:
    """
    Automated surveillance service daemon
    Version: 1.0.0
    """

    def __init__(self, foreground=False):
        self.foreground = foreground
        self.running = False
        self.capture_process = None
        self.processing_process = None

        # Monitoring threads
        self.threads = []

        # Setup logging
        self.setup_logging()

        # Signal handlers
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)

    def setup_logging(self):
        """Configure logging"""
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
        """Check if current time is within specified window"""
        now = datetime.now().time()
        current_hour = now.hour

        if start_hour < end_hour:
            # Same day window (e.g., 11 AM - 9 PM)
            return start_hour <= current_hour < end_hour
        else:
            # Overnight window (e.g., 11 PM - 6 AM)
            return current_hour >= start_hour or current_hour < end_hour

    def start_video_capture(self):
        """Start video capture if in operating hours"""
        if not self.is_in_time_window(CAPTURE_START_HOUR, CAPTURE_END_HOUR):
            self.logger.info("Outside capture hours, skipping video capture")
            return

        if self.capture_process and self.capture_process.poll() is None:
            self.logger.info("Video capture already running")
            return

        self.logger.info("Starting video capture...")
        capture_script = PROJECT_ROOT / "scripts" / "video_capture" / "capture_rtsp_streams.py"

        # Calculate duration until end of capture window
        now = datetime.now()
        end_time = now.replace(hour=CAPTURE_END_HOUR, minute=0, second=0, microsecond=0)
        if end_time <= now:
            # Already past end time today
            return

        duration = int((end_time - now).total_seconds())

        try:
            self.capture_process = subprocess.Popen(
                ["python3", str(capture_script), "--duration", str(duration)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            self.logger.info(f"Video capture started (PID: {self.capture_process.pid}, duration: {duration}s)")
        except Exception as e:
            self.logger.error(f"Failed to start video capture: {e}")

    def start_video_processing(self):
        """Start video processing if in processing hours"""
        if not self.is_in_time_window(PROCESS_START_HOUR, PROCESS_END_HOUR):
            self.logger.info("Outside processing hours, skipping video processing")
            return

        if self.processing_process and self.processing_process.poll() is None:
            self.logger.info("Video processing already running")
            return

        self.logger.info("Starting video processing...")
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
                if self.is_in_time_window(CAPTURE_START_HOUR, CAPTURE_END_HOUR):
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
        """Main scheduler loop"""
        self.logger.info("Starting scheduler loop...")

        while self.running:
            try:
                now = datetime.now()
                current_time = now.time()
                current_hour = now.hour

                # Check if we should start video capture
                if current_hour == CAPTURE_START_HOUR and current_time.minute == 0:
                    self.start_video_capture()

                # Check if we should start video processing
                if current_hour == PROCESS_START_HOUR and current_time.minute == 0:
                    self.start_video_processing()

                # Check if capture window ended
                if current_hour == CAPTURE_END_HOUR and current_time.minute == 0:
                    if self.capture_process and self.capture_process.poll() is None:
                        self.logger.info("Capture window ended, stopping capture...")
                        self.capture_process.terminate()

                # Check if processing window ended
                if current_hour == PROCESS_END_HOUR and current_time.minute == 0:
                    if self.processing_process and self.processing_process.poll() is None:
                        self.logger.info("Processing window ended, stopping processing...")
                        self.processing_process.terminate()

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
        self.logger.info("ASE Surveillance Service Starting")
        self.logger.info("=" * 70)
        self.logger.info(f"Capture hours: {CAPTURE_START_HOUR}:00 - {CAPTURE_END_HOUR}:00")
        self.logger.info(f"Processing hours: {PROCESS_START_HOUR}:00 - {PROCESS_END_HOUR}:00")
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
        if self.is_in_time_window(CAPTURE_START_HOUR, CAPTURE_END_HOUR):
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

            in_capture_window = self.is_in_time_window(CAPTURE_START_HOUR, CAPTURE_END_HOUR)
            in_process_window = self.is_in_time_window(PROCESS_START_HOUR, PROCESS_END_HOUR)

            print(f"Capture window: {'🟢 ACTIVE' if in_capture_window else '🔴 INACTIVE'}")
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
