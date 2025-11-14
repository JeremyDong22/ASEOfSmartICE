#!/usr/bin/env python3
"""
RTSP Video Capture Script for Multi-Camera Restaurant Monitoring
Version: 2.0.0
Last Updated: 2025-11-14

Purpose: Capture video streams from multiple UNV cameras via RTSP with robust reconnection
Saves videos with standardized naming: camera_{id}_{date}_{time}.mp4

Features:
- Parallel capture from multiple cameras
- UNV camera RTSP support (media/video1 endpoint)
- Automatic naming with camera_id extraction
- H.264 encoding for efficient storage
- ROBUST NETWORK RECONNECTION (NEW in v2.0.0)
  * Continuous reconnection during recording window
  * Smart video file segmentation for long disconnections
  * Network health monitoring with ping checks
  * RTT-based quality filtering
  * Enhanced logging and metrics
- Local storage with cloud upload capability

Changes in v2.0.0:
- Added continuous reconnection logic during recording
- Implemented network health monitoring (ICMP ping + RTT measurement)
- Smart video segmentation (same file <2min, new segment >2min)
- Recording coverage tracking and reporting
- Cross-platform network utilities (Linux/macOS compatible)

Author: ASEOfSmartICE Team
"""

import cv2
import threading
import time
import os
import subprocess
import platform
from pathlib import Path
from datetime import datetime
import json
import argparse

# Script configuration
SCRIPT_DIR = Path(__file__).parent.resolve()
VIDEOS_DIR = SCRIPT_DIR.parent / "videos"
CAMERAS_CONFIG = SCRIPT_DIR / "cameras_config.json"

# Default camera configurations
DEFAULT_CAMERAS = {
    "camera_35": {
        "ip": "202.168.40.35",
        "port": 554,
        "username": "admin",
        "password": "123456",
        "stream_path": "/media/video1",  # UNV main stream
        "resolution": (2592, 1944),
        "fps": 20,
        "division_name": "A区",
        "enabled": True
    },
    "camera_22": {
        "ip": "202.168.40.22",
        "port": 554,
        "username": "admin",
        "password": "123456",
        "stream_path": "/media/video1",
        "resolution": (2592, 1944),
        "fps": 20,
        "division_name": "B区",
        "enabled": True
    }
}

# ============================================================================
# NETWORK RECONNECTION SETTINGS (NEW in v2.0.0)
# ============================================================================
MAX_RTT_MS = 500  # Maximum acceptable round-trip time in milliseconds
RECONNECT_INTERVAL = 30  # Seconds between reconnection attempts
RECONNECT_SAME_FILE_THRESHOLD = 120  # Seconds - if reconnect faster, resume same file
PING_TIMEOUT = 2  # Seconds for ping timeout
PING_COUNT = 1  # Number of ping packets to send

# Original capture settings
MAX_RETRY_ATTEMPTS = 3
FRAME_READ_TIMEOUT = 10  # seconds before considering connection lost
CONNECTION_TIMEOUT = 30  # seconds to establish connection


# ============================================================================
# NETWORK UTILITIES (NEW in v2.0.0)
# ============================================================================

def ping_host(host_ip, timeout=PING_TIMEOUT, count=PING_COUNT):
    """
    Ping a host to check network connectivity and measure RTT.
    Cross-platform implementation (Linux/macOS/Windows).

    Returns:
        tuple: (success: bool, rtt_ms: float or None, error_msg: str or None)
    """
    system = platform.system().lower()

    try:
        # Build ping command based on OS
        if system == "windows":
            # Windows: ping -n count -w timeout_ms host
            cmd = ["ping", "-n", str(count), "-w", str(timeout * 1000), host_ip]
        else:
            # Linux/macOS: ping -c count -W timeout_secs host
            cmd = ["ping", "-c", str(count), "-W", str(timeout), host_ip]

        # Execute ping
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout + 1  # Add 1s buffer to subprocess timeout
        )

        if result.returncode == 0:
            # Parse RTT from output
            output = result.stdout

            if system == "windows":
                # Windows format: "Average = XXXms" or "time=XXXms"
                for line in output.split('\n'):
                    if 'Average' in line and '=' in line:
                        rtt_str = line.split('=')[-1].strip().replace('ms', '')
                        try:
                            rtt_ms = float(rtt_str)
                            return True, rtt_ms, None
                        except ValueError:
                            pass
                    elif 'time=' in line:
                        parts = line.split('time=')
                        if len(parts) > 1:
                            rtt_str = parts[1].split('ms')[0].strip()
                            try:
                                rtt_ms = float(rtt_str)
                                return True, rtt_ms, None
                            except ValueError:
                                pass
            else:
                # Linux/macOS format: "time=XX.X ms" or "rtt min/avg/max/mdev = "
                for line in output.split('\n'):
                    if 'time=' in line:
                        parts = line.split('time=')
                        if len(parts) > 1:
                            rtt_str = parts[1].split('ms')[0].strip()
                            try:
                                rtt_ms = float(rtt_str)
                                return True, rtt_ms, None
                            except ValueError:
                                pass
                    elif 'rtt' in line.lower() and '=' in line:
                        # Format: "rtt min/avg/max/mdev = 1.234/2.345/3.456/0.123 ms"
                        parts = line.split('=')
                        if len(parts) > 1:
                            values = parts[1].split('/')[0:2]  # Get min/avg
                            if len(values) > 1:
                                try:
                                    avg_rtt = float(values[1].strip())
                                    return True, avg_rtt, None
                                except ValueError:
                                    pass

            # Ping succeeded but couldn't parse RTT
            return True, None, "Could not parse RTT from ping output"
        else:
            # Ping failed
            error_msg = result.stderr.strip() if result.stderr else "Host unreachable"
            return False, None, error_msg

    except subprocess.TimeoutExpired:
        return False, None, f"Ping timeout after {timeout}s"
    except FileNotFoundError:
        return False, None, "Ping command not found on system"
    except Exception as e:
        return False, None, f"Ping error: {str(e)}"


def check_network_quality(host_ip, max_rtt_ms=MAX_RTT_MS):
    """
    Check if network connection to host meets quality requirements.

    Returns:
        tuple: (is_healthy: bool, rtt_ms: float or None, message: str)
    """
    success, rtt_ms, error = ping_host(host_ip)

    if not success:
        return False, None, f"❌ Network unreachable: {error}"

    if rtt_ms is None:
        # Ping succeeded but no RTT - accept it
        return True, None, "✅ Network reachable (RTT unknown)"

    if rtt_ms > max_rtt_ms:
        return False, rtt_ms, f"❌ Network too slow: {rtt_ms:.1f}ms > {max_rtt_ms}ms threshold"

    return True, rtt_ms, f"✅ Network healthy: {rtt_ms:.1f}ms RTT"


# ============================================================================
# VIDEO FILE MANAGEMENT (NEW in v2.0.0)
# ============================================================================

class VideoSegmentManager:
    """
    Manages video file segmentation for handling network disconnections.
    Creates new segments when reconnection takes too long.
    """

    def __init__(self, base_filename, output_path, resolution, fps, camera_id):
        self.base_filename = base_filename  # Without extension
        self.output_path = Path(output_path)
        self.resolution = resolution
        self.fps = fps
        self.camera_id = camera_id

        self.segment_number = 1
        self.current_file = None
        self.current_writer = None

    def get_current_filename(self):
        """Generate filename for current segment"""
        if self.segment_number == 1:
            return f"{self.base_filename}.mp4"
        else:
            return f"{self.base_filename}_part{self.segment_number}.mp4"

    def get_full_path(self):
        """Get full path to current segment file"""
        return str(self.output_path / self.get_current_filename())

    def create_new_segment(self):
        """
        Create a new video segment file.
        Returns the VideoWriter object or None on failure.
        """
        # Close previous writer if exists
        if self.current_writer is not None:
            self.current_writer.release()
            print(f"[{self.camera_id}] 📁 Closed segment: {self.current_file}")

        # Generate new filename
        self.current_file = self.get_current_filename()
        full_path = self.get_full_path()

        # Create new writer
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # H.264 codec
        writer = cv2.VideoWriter(full_path, fourcc, self.fps, self.resolution)

        if writer.isOpened():
            self.current_writer = writer
            print(f"[{self.camera_id}] 📁 Created segment {self.segment_number}: {self.current_file}")
            return writer
        else:
            print(f"[{self.camera_id}] ❌ Failed to create segment: {self.current_file}")
            return None

    def next_segment(self):
        """Move to next segment number and create new file"""
        self.segment_number += 1
        return self.create_new_segment()

    def release(self):
        """Release current video writer"""
        if self.current_writer is not None:
            self.current_writer.release()
            self.current_writer = None


# ============================================================================
# CAMERA CAPTURE WITH RECONNECTION (MODIFIED in v2.0.0)
# ============================================================================

class CameraCapture:
    """Handles video capture from a single RTSP camera with robust reconnection"""

    def __init__(self, camera_id, config):
        self.camera_id = camera_id
        self.config = config
        self.rtsp_url = self._build_rtsp_url()
        self.is_capturing = False
        self.capture_thread = None

        # Recording metrics (NEW)
        self.total_recording_time = 0.0  # Actual time recorded with frames
        self.total_disconnected_time = 0.0  # Time spent reconnecting
        self.reconnection_attempts = 0
        self.successful_reconnections = 0

    def _build_rtsp_url(self):
        """Build RTSP URL from camera config"""
        return (f"rtsp://{self.config['username']}:{self.config['password']}"
                f"@{self.config['ip']}:{self.config['port']}"
                f"{self.config['stream_path']}")

    def _generate_filename(self):
        """Generate standardized filename: camera_{id}_{date}_{time}.mp4"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{self.camera_id}_{timestamp}"  # Without extension

    # ========================================================================
    # CONNECTION ESTABLISHMENT (ENHANCED in v2.0.0)
    # ========================================================================

    def _connect_with_health_check(self, attempt_num=1):
        """
        Attempt to connect to RTSP stream with network health check.

        Returns:
            cv2.VideoCapture or None: Opened capture object or None on failure
        """
        # Step 1: Check network health
        print(f"[{self.camera_id}] 🔍 Checking network to {self.config['ip']}...")
        is_healthy, rtt_ms, msg = check_network_quality(self.config['ip'])
        print(f"[{self.camera_id}]    {msg}")

        if not is_healthy:
            print(f"[{self.camera_id}] ⏭️  Skipping connection attempt (unhealthy network)")
            return None

        # Step 2: Attempt RTSP connection
        print(f"[{self.camera_id}] 🔌 Connecting to RTSP (attempt {attempt_num})...")
        cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)

        # Wait for connection
        start_wait = time.time()
        while not cap.isOpened() and (time.time() - start_wait) < CONNECTION_TIMEOUT:
            time.sleep(0.5)

        if cap.isOpened():
            print(f"[{self.camera_id}] ✅ RTSP connected successfully")
            return cap
        else:
            print(f"[{self.camera_id}] ❌ RTSP connection failed")
            if cap:
                cap.release()
            return None

    # ========================================================================
    # RECONNECTION LOGIC (NEW in v2.0.0)
    # ========================================================================

    def _attempt_reconnection(self, segment_manager, disconnection_start_time):
        """
        Attempt to reconnect to RTSP stream.
        Decides whether to resume same file or create new segment.

        Returns:
            tuple: (cap: VideoCapture or None, writer: VideoWriter or None, should_create_new_segment: bool)
        """
        self.reconnection_attempts += 1
        disconnected_duration = time.time() - disconnection_start_time

        print(f"\n[{self.camera_id}] 🔄 RECONNECTION ATTEMPT #{self.reconnection_attempts}")
        print(f"[{self.camera_id}]    Disconnected for: {disconnected_duration:.1f}s")

        # Try to connect with health check
        cap = self._connect_with_health_check(attempt_num=self.reconnection_attempts)

        if cap is None:
            return None, None, False

        # Connection successful
        self.successful_reconnections += 1

        # Decide: same file or new segment?
        if disconnected_duration <= RECONNECT_SAME_FILE_THRESHOLD:
            # Resume to same file (if writer still valid)
            print(f"[{self.camera_id}] ✅ Reconnected within {RECONNECT_SAME_FILE_THRESHOLD}s")
            print(f"[{self.camera_id}]    Resuming to same file: {segment_manager.current_file}")

            # Try to reuse existing writer
            if segment_manager.current_writer is not None and segment_manager.current_writer.isOpened():
                writer = segment_manager.current_writer
                return cap, writer, False
            else:
                # Writer closed, need to recreate (but same segment number)
                writer = segment_manager.create_new_segment()
                return cap, writer, False
        else:
            # Create new segment
            print(f"[{self.camera_id}] ⚠️  Reconnection took >{RECONNECT_SAME_FILE_THRESHOLD}s")
            print(f"[{self.camera_id}]    Creating new segment file")
            writer = segment_manager.next_segment()
            return cap, writer, True

    # ========================================================================
    # MAIN CAPTURE LOOP (HEAVILY MODIFIED in v2.0.0)
    # ========================================================================

    def capture_video(self, duration_seconds, output_dir):
        """
        Capture video for specified duration with continuous reconnection.

        NEW BEHAVIOR:
        - Continuously attempts reconnection if stream drops during recording
        - Creates new video segments for long disconnections
        - Tracks recording coverage and quality metrics
        """
        # Create output directory structure
        date_str = datetime.now().strftime("%Y%m%d")
        output_path = Path(output_dir) / date_str / self.camera_id
        output_path.mkdir(parents=True, exist_ok=True)

        base_filename = self._generate_filename()

        print(f"\n{'='*70}")
        print(f"[{self.camera_id}] 🎥 STARTING CAPTURE SESSION")
        print(f"{'='*70}")
        print(f"   RTSP: {self.rtsp_url}")
        print(f"   Base name: {base_filename}.mp4")
        print(f"   Duration: {duration_seconds}s ({duration_seconds/60:.1f} minutes)")
        print(f"   Output dir: {output_path}")
        print(f"{'='*70}\n")

        # Initialize video segment manager
        segment_manager = VideoSegmentManager(
            base_filename, output_path,
            self.config['resolution'],
            self.config['fps'],
            self.camera_id
        )

        # Initial connection with retries
        cap = None
        for attempt in range(MAX_RETRY_ATTEMPTS):
            cap = self._connect_with_health_check(attempt_num=attempt + 1)
            if cap is not None:
                break
            if attempt < MAX_RETRY_ATTEMPTS - 1:
                print(f"[{self.camera_id}] ⏳ Retrying in 2s...")
                time.sleep(2)

        if cap is None:
            print(f"[{self.camera_id}] ❌ FAILED TO CONNECT after {MAX_RETRY_ATTEMPTS} attempts")
            return False

        # Create initial video segment
        writer = segment_manager.create_new_segment()
        if writer is None:
            cap.release()
            return False

        # Recording loop variables
        session_start_time = time.time()
        recording_start_time = time.time()  # Tracks active recording time
        frame_count = 0
        failed_reads = 0
        last_success_time = time.time()
        disconnection_start_time = None
        is_disconnected = False

        fps = self.config['fps']
        self.is_capturing = True

        try:
            while self.is_capturing:
                # Check if we've reached target duration
                elapsed_total = time.time() - session_start_time
                if elapsed_total >= duration_seconds:
                    print(f"[{self.camera_id}] ⏱️  Target duration reached: {duration_seconds}s")
                    break

                # Try to read frame
                ret, frame = cap.read()

                if ret:
                    # ========== SUCCESSFUL FRAME READ ==========

                    # If we were disconnected, we just reconnected
                    if is_disconnected:
                        reconnect_duration = time.time() - disconnection_start_time
                        self.total_disconnected_time += reconnect_duration
                        print(f"[{self.camera_id}] ✅ Streaming resumed after {reconnect_duration:.1f}s")
                        is_disconnected = False
                        disconnection_start_time = None

                    # Write frame to current segment
                    writer.write(frame)
                    frame_count += 1
                    failed_reads = 0
                    last_success_time = time.time()

                    # Update recording time
                    self.total_recording_time = time.time() - recording_start_time

                    # Progress update every 10 seconds
                    if frame_count % (fps * 10) == 0:
                        progress = (elapsed_total / duration_seconds) * 100
                        coverage = (self.total_recording_time / elapsed_total) * 100 if elapsed_total > 0 else 0
                        print(f"[{self.camera_id}] 📊 Progress: {progress:.1f}% | "
                              f"Frames: {frame_count} | "
                              f"Coverage: {coverage:.1f}% | "
                              f"Segment: {segment_manager.segment_number}")

                else:
                    # ========== FAILED FRAME READ ==========
                    failed_reads += 1
                    time_since_last = time.time() - last_success_time

                    # Mark as disconnected if timeout exceeded
                    if not is_disconnected and time_since_last > FRAME_READ_TIMEOUT:
                        print(f"\n[{self.camera_id}] ⚠️  CONNECTION LOST")
                        print(f"[{self.camera_id}]    No frames for {time_since_last:.1f}s")
                        print(f"[{self.camera_id}]    Failed reads: {failed_reads}")
                        is_disconnected = True
                        disconnection_start_time = time.time()

                        # Release current connection
                        cap.release()
                        print(f"[{self.camera_id}] 🔌 Released current connection")

                    # ========== CONTINUOUS RECONNECTION LOOP ==========
                    if is_disconnected:
                        disconnected_duration = time.time() - disconnection_start_time

                        # Check if we should attempt reconnection
                        if disconnected_duration % RECONNECT_INTERVAL < 1.0:  # Avoid multiple attempts per second
                            print(f"\n[{self.camera_id}] 🔄 Attempting reconnection...")
                            print(f"[{self.camera_id}]    Time disconnected: {disconnected_duration:.1f}s")

                            new_cap, new_writer, created_segment = self._attempt_reconnection(
                                segment_manager, disconnection_start_time
                            )

                            if new_cap is not None:
                                # Reconnection successful
                                cap = new_cap
                                if new_writer is not None:
                                    writer = new_writer

                                # Continue loop - next iteration will read frame
                                continue
                            else:
                                print(f"[{self.camera_id}] ❌ Reconnection failed")
                                print(f"[{self.camera_id}]    Next attempt in {RECONNECT_INTERVAL}s...")

                        # Wait before next reconnection attempt
                        time.sleep(1)
                    else:
                        # Not yet marked as disconnected, brief pause
                        time.sleep(0.1)

        except KeyboardInterrupt:
            print(f"\n[{self.camera_id}] ⚠️  INTERRUPTED BY USER")

        finally:
            # Cleanup
            self.is_capturing = False
            if cap is not None:
                cap.release()
            segment_manager.release()

        # ========================================================================
        # SESSION SUMMARY (ENHANCED in v2.0.0)
        # ========================================================================

        session_duration = time.time() - session_start_time
        recording_coverage = (self.total_recording_time / duration_seconds) * 100 if duration_seconds > 0 else 0

        print(f"\n{'='*70}")
        print(f"[{self.camera_id}] 📊 CAPTURE SESSION COMPLETE")
        print(f"{'='*70}")
        print(f"   Frames captured: {frame_count}")
        print(f"   Target duration: {duration_seconds}s")
        print(f"   Session duration: {session_duration:.1f}s")
        print(f"   Recording time: {self.total_recording_time:.1f}s")
        print(f"   Disconnected time: {self.total_disconnected_time:.1f}s")
        print(f"   Recording coverage: {recording_coverage:.1f}%")

        if frame_count > 0:
            print(f"   Average FPS: {frame_count / self.total_recording_time:.2f}")

        print(f"\n   Reconnection stats:")
        print(f"   - Attempts: {self.reconnection_attempts}")
        print(f"   - Successful: {self.successful_reconnections}")
        print(f"   - Success rate: {(self.successful_reconnections / self.reconnection_attempts * 100) if self.reconnection_attempts > 0 else 0:.1f}%")

        print(f"\n   Video segments created: {segment_manager.segment_number}")
        for i in range(1, segment_manager.segment_number + 1):
            if i == 1:
                filename = f"{base_filename}.mp4"
            else:
                filename = f"{base_filename}_part{i}.mp4"
            filepath = output_path / filename
            if filepath.exists():
                size_mb = filepath.stat().st_size / (1024 * 1024)
                print(f"   - {filename}: {size_mb:.1f} MB")

        print(f"{'='*70}\n")

        return frame_count > 0  # Success if any frames captured

    def start_capture_async(self, duration_seconds, output_dir):
        """Start capture in background thread"""
        self.capture_thread = threading.Thread(
            target=self.capture_video,
            args=(duration_seconds, output_dir),
            daemon=False
        )
        self.capture_thread.start()
        return self.capture_thread

    def stop_capture(self):
        """Stop ongoing capture"""
        self.is_capturing = False
        if self.capture_thread:
            self.capture_thread.join(timeout=5)


# ============================================================================
# CONFIGURATION AND MAIN FUNCTIONS (UNCHANGED)
# ============================================================================

def load_cameras_config():
    """Load cameras configuration from JSON file or use defaults"""
    if CAMERAS_CONFIG.exists():
        print(f"📂 Loading camera config from: {CAMERAS_CONFIG}")
        with open(CAMERAS_CONFIG, 'r') as f:
            return json.load(f)
    else:
        print("📂 Using default camera configuration")
        print(f"   (Create {CAMERAS_CONFIG} to customize)")
        return DEFAULT_CAMERAS


def save_default_config():
    """Save default camera configuration to JSON file"""
    with open(CAMERAS_CONFIG, 'w') as f:
        json.dump(DEFAULT_CAMERAS, f, indent=2)
    print(f"✅ Default config saved to: {CAMERAS_CONFIG}")


def capture_all_cameras(duration_seconds, output_dir, camera_filter=None):
    """Capture from all enabled cameras in parallel"""
    cameras = load_cameras_config()

    # Filter cameras if specified
    if camera_filter:
        cameras = {k: v for k, v in cameras.items()
                  if k in camera_filter and v.get('enabled', True)}
    else:
        cameras = {k: v for k, v in cameras.items() if v.get('enabled', True)}

    if not cameras:
        print("❌ No cameras configured or enabled")
        return

    print(f"\n{'='*70}")
    print(f"🎥 Starting parallel capture from {len(cameras)} camera(s)")
    print(f"{'='*70}")
    print(f"Duration: {duration_seconds}s ({duration_seconds/60:.1f} minutes)")
    print(f"Output: {output_dir}")
    print(f"Cameras: {', '.join(cameras.keys())}")
    print(f"Reconnection: Every {RECONNECT_INTERVAL}s during recording window")
    print(f"Network RTT threshold: {MAX_RTT_MS}ms")
    print(f"{'='*70}\n")

    # Create capture objects
    captures = {}
    threads = []

    for camera_id, config in cameras.items():
        capture = CameraCapture(camera_id, config)
        captures[camera_id] = capture
        thread = capture.start_capture_async(duration_seconds, output_dir)
        threads.append(thread)

    # Wait for all to complete
    print("⏳ Waiting for all captures to complete...\n")
    for thread in threads:
        thread.join()

    print(f"\n{'='*70}")
    print("✅ ALL CAPTURES COMPLETE!")
    print(f"{'='*70}\n")


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Capture RTSP video streams from multiple cameras with robust reconnection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Capture 1 hour from all cameras (with auto-reconnection)
  python3 capture_rtsp_streams.py --duration 3600

  # Capture 5 minutes from specific camera
  python3 capture_rtsp_streams.py --duration 300 --cameras camera_35

  # Capture from multiple specific cameras
  python3 capture_rtsp_streams.py --duration 1800 --cameras camera_35 camera_22

  # Generate default config file
  python3 capture_rtsp_streams.py --save-config

  # Test connection and reconnection (10 seconds)
  python3 capture_rtsp_streams.py --duration 10 --cameras camera_35

Reconnection Features (v2.0.0):
  - Continuously retries connection every 30s during recording window
  - Checks network health before attempting RTSP connection
  - Aborts if RTT > 500ms (network too slow)
  - Resumes same file if reconnect within 2 minutes
  - Creates new segment (_part2, _part3) for longer disconnections
  - Reports recording coverage % at end of session
        """
    )

    parser.add_argument("--duration", type=int, default=3600,
                       help="Capture duration in seconds (default: 3600 = 1 hour)")
    parser.add_argument("--output", default=str(VIDEOS_DIR),
                       help=f"Output directory (default: {VIDEOS_DIR})")
    parser.add_argument("--cameras", nargs='+',
                       help="Specific camera IDs to capture (default: all enabled)")
    parser.add_argument("--save-config", action="store_true",
                       help="Save default configuration to cameras_config.json and exit")

    args = parser.parse_args()

    if args.save_config:
        save_default_config()
        return

    # Ensure output directory exists
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Start capture
    start_time = datetime.now()
    print(f"\n🎥 RTSP Video Capture System v2.0.0 (with Reconnection)")
    print(f"{'='*70}")
    print(f"Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

    capture_all_cameras(args.duration, output_dir, args.cameras)

    end_time = datetime.now()
    total_duration = (end_time - start_time).total_seconds()
    print(f"End time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total runtime: {total_duration:.1f}s ({total_duration/60:.1f} minutes)\n")


if __name__ == "__main__":
    main()
