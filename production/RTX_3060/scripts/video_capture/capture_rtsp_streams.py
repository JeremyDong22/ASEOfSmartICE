#!/usr/bin/env python3
"""
RTSP Video Capture Script for Multi-Camera Restaurant Monitoring
Version: 3.1.1
Last Updated: 2025-11-19
Modified: Fixed graceful shutdown bug - removed sys.exit(0) from signal handler - 2025-11-19
  - Allows finally blocks to execute properly for VideoWriter.release()
  - Prevents video corruption on SIGTERM
  - Process now exits naturally after cleanup completes

Modified: Added 10-minute periodic checkpoint mechanism to prevent video corruption - 2025-11-17

Purpose: Capture video streams from multiple UNV cameras via RTSP with robust reconnection
Saves videos with standardized naming: camera_{id}_{date}_{time}.mp4

Features:
- Parallel capture from multiple cameras
- UNV camera RTSP support (media/video1 endpoint)
- Automatic naming with camera_id extraction
- H.264 encoding for efficient storage
- IMMEDIATE SEGMENTATION ON DISCONNECT (NEW in v3.0.0)
  * FPS-based disconnect detection (< 2fps)
  * No delay between disconnect and new file creation
  * Prevents missing state changes during network issues
  * Faster reconnection attempts (10s interval)
  * Network health monitoring with ping checks
  * RTT-based quality filtering
  * Enhanced logging and metrics
- PERIODIC CHECKPOINT MECHANISM (NEW in v3.1.0)
  * Force file rotation every 10 minutes (600 seconds)
  * Prevents moov atom loss if network interrupts
  * Maximum 10 minutes data loss instead of entire session
  * Independent of network status or FPS
  * Graceful shutdown with signal handlers (SIGTERM/SIGINT)
- Local storage with cloud upload capability

Changes in v3.1.0:
- Added 10-minute periodic checkpoint for corruption prevention
- Force VideoWriter.release() and create new segment every 600 seconds
- Added SIGTERM and SIGINT signal handlers for graceful shutdown
- Enhanced logging to show checkpoint triggers and statistics
- Reset checkpoint timer on reconnection

Changes in v3.0.0:
- IMMEDIATE segmentation on FPS drop (< 2fps) - no 30s delay
- No delay between disconnect detection and new file creation
- Prevents missing state changes during network interruptions
- Faster reconnection retry interval (10s instead of 30s)
- FPS-based disconnect detection (more accurate than timeout)
- Real-time FPS monitoring with sliding window calculation

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
import signal
import sys
from pathlib import Path
from datetime import datetime
import json
import argparse

# Script configuration
SCRIPT_DIR = Path(__file__).parent.resolve()
VIDEOS_DIR = SCRIPT_DIR.parent.parent / "videos"
CAMERAS_CONFIG = SCRIPT_DIR.parent / "config" / "cameras_config.json"

# Camera configurations loaded from JSON file
# All camera settings must be defined in scripts/config/cameras_config.json
# No hardcoded defaults - production systems must use proper configuration files

# ============================================================================
# NETWORK RECONNECTION SETTINGS (UPDATED in v3.0.0)
# ============================================================================
MAX_RTT_MS = 500  # Maximum acceptable round-trip time in milliseconds
PING_TIMEOUT = 2  # Seconds for ping timeout
PING_COUNT = 1  # Number of ping packets to send

# Frame rate thresholds for disconnect detection (NEW in v3.0.0)
NORMAL_FPS_MIN = 15  # Minimum FPS considered "connected" (camera is 20fps)
DISCONNECT_FPS_THRESHOLD = 2  # FPS below this = immediate disconnect

# Immediate segmentation on disconnect (NEW in v3.0.0)
IMMEDIATE_SEGMENT_ON_DISCONNECT = True  # Always create new file on disconnect
RECONNECT_RETRY_INTERVAL = 10  # Seconds between reconnection attempts (reduced from 30)

# Periodic checkpoint settings (NEW in v3.1.0)
CHECKPOINT_INTERVAL_SECONDS = 600  # 10 minutes - force file rotation to prevent corruption

# Original capture settings
MAX_RETRY_ATTEMPTS = 3
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
    Creates new segments immediately on disconnect (v3.0.0).
    """

    def __init__(self, base_filename, output_path, resolution, fps, camera_id, expected_duration):
        self.base_filename = base_filename  # Without extension
        self.output_path = Path(output_path)
        self.resolution = resolution
        self.fps = fps
        self.camera_id = camera_id
        self.total_expected_duration = expected_duration

        self.segment_number = 1
        self.current_file = None
        self.current_writer = None

        # Tracking metrics (NEW in v3.0.0)
        self.segments = []  # List of segment info
        self.disconnection_count = 0
        self.current_segment_start = None

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
            # Record segment duration before closing
            if self.current_segment_start is not None:
                duration = time.time() - self.current_segment_start
                self.segments.append({
                    'filename': self.current_file,
                    'segment_number': self.segment_number,
                    'duration': duration
                })

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
            self.current_segment_start = time.time()
            print(f"[{self.camera_id}] 📁 Created segment {self.segment_number}: {self.current_file}")
            return writer
        else:
            print(f"[{self.camera_id}] ❌ Failed to create segment: {self.current_file}")
            return None

    def next_segment(self):
        """Move to next segment number and create new file"""
        self.segment_number += 1
        self.disconnection_count += 1
        return self.create_new_segment()

    def record_reconnection(self, disconnected_duration):
        """Record successful reconnection"""
        print(f"[{self.camera_id}] ✅ Reconnected after {disconnected_duration:.1f}s disconnection")

    def release(self):
        """Release current video writer and finalize segment tracking"""
        if self.current_writer is not None:
            # Record final segment
            if self.current_segment_start is not None:
                duration = time.time() - self.current_segment_start
                self.segments.append({
                    'filename': self.current_file,
                    'segment_number': self.segment_number,
                    'duration': duration
                })

            self.current_writer.release()
            self.current_writer = None

    def get_coverage_report(self):
        """Generate coverage report"""
        total_duration = self.total_expected_duration
        recorded_duration = sum(seg['duration'] for seg in self.segments)
        gap_duration = total_duration - recorded_duration

        coverage_percent = (recorded_duration / total_duration) * 100 if total_duration > 0 else 0

        return {
            'total_expected': total_duration,
            'recorded': recorded_duration,
            'gaps': gap_duration,
            'coverage_percent': coverage_percent,
            'segment_count': len(self.segments),
            'disconnections': self.disconnection_count,
            'segments': self.segments
        }


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

    # ========================================================================
    # FPS MONITORING (NEW in v3.0.0)
    # ========================================================================

    def _calculate_fps(self, frame_timestamps):
        """
        Calculate current FPS from frame timestamps.

        Args:
            frame_timestamps: List of recent frame timestamps

        Returns:
            float: Current FPS
        """
        if len(frame_timestamps) < 2:
            return 0.0

        time_span = frame_timestamps[-1] - frame_timestamps[0]
        if time_span == 0:
            return 0.0

        return (len(frame_timestamps) - 1) / time_span

    def _is_disconnected(self, current_fps):
        """
        Detect if camera is disconnected based on FPS.

        Returns True if:
        - FPS drops below 2 (critical threshold)

        Args:
            current_fps: Current calculated FPS

        Returns:
            bool: True if disconnected
        """
        return current_fps < DISCONNECT_FPS_THRESHOLD

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
    # RECONNECTION LOGIC (UPDATED in v3.0.0)
    # ========================================================================

    def _attempt_reconnection(self, disconnection_start_time):
        """
        Attempt to reconnect to RTSP stream.
        Immediate segmentation already handled - this just tries to reconnect.

        Returns:
            cv2.VideoCapture or None: New capture object or None on failure
        """
        self.reconnection_attempts += 1
        disconnected_duration = time.time() - disconnection_start_time

        print(f"\n[{self.camera_id}] 🔄 RECONNECTION ATTEMPT #{self.reconnection_attempts}")
        print(f"[{self.camera_id}]    Disconnected for: {disconnected_duration:.1f}s")

        # Test network health first
        success, rtt, error = ping_host(self.config['ip'])

        if success and (rtt is None or rtt < MAX_RTT_MS):
            rtt_msg = f"RTT: {rtt:.0f}ms" if rtt is not None else "RTT: unknown"
            print(f"[{self.camera_id}] 🌐 Network OK ({rtt_msg}), attempting RTSP...")

            # Try RTSP connection
            cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)

            # Brief wait for connection
            start_wait = time.time()
            while not cap.isOpened() and (time.time() - start_wait) < 5:
                time.sleep(0.2)

            if cap.isOpened():
                print(f"[{self.camera_id}] ✅ RTSP reconnected!")
                self.successful_reconnections += 1
                return cap
            else:
                print(f"[{self.camera_id}] ❌ RTSP connection failed")
                cap.release()
                return None
        else:
            error_msg = f"RTT too high: {rtt:.0f}ms" if rtt and rtt >= MAX_RTT_MS else error
            print(f"[{self.camera_id}] ❌ Network unreachable: {error_msg}")
            return None

    # ========================================================================
    # MAIN CAPTURE LOOP (HEAVILY MODIFIED in v3.0.0)
    # ========================================================================

    def capture_video(self, duration_seconds, output_dir):
        """
        Capture video for specified duration with immediate segmentation on disconnect.

        NEW BEHAVIOR (v3.0.0):
        - FPS-based disconnect detection (< 2fps)
        - IMMEDIATE segmentation when disconnect detected (no delay)
        - Continuous reconnection attempts every 10 seconds
        - Prevents missing state changes during network issues
        - Real-time FPS monitoring with sliding window
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
            self.camera_id,
            duration_seconds
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
        disconnection_start_time = None
        is_disconnected = False
        last_reconnect_attempt = None

        # Checkpoint tracking (NEW in v3.1.0)
        segment_start_time = time.time()
        checkpoint_count = 0

        # FPS tracking (NEW in v3.0.0)
        frame_timestamps = []  # Track last N frame times
        fps_window = 20  # Calculate FPS over last 20 frames
        last_fps_check = time.time()
        fps_check_interval = 1.0  # Check FPS every second
        current_fps = self.config['fps']  # Initialize to expected FPS

        fps = self.config['fps']
        self.is_capturing = True

        try:
            while self.is_capturing:
                # Check if we've reached target duration
                elapsed_total = time.time() - session_start_time
                if elapsed_total >= duration_seconds:
                    print(f"[{self.camera_id}] ⏱️  Target duration reached: {duration_seconds}s")
                    break

                # ========== PERIODIC CHECKPOINT (NEW in v3.1.0) ==========
                # Force file rotation every 10 minutes to prevent corruption
                current_time = time.time()
                time_since_checkpoint = current_time - segment_start_time

                if time_since_checkpoint >= CHECKPOINT_INTERVAL_SECONDS and not is_disconnected:
                    checkpoint_count += 1
                    print(f"\n[{self.camera_id}] ⏰ CHECKPOINT #{checkpoint_count} TRIGGERED")
                    print(f"[{self.camera_id}]    Time since last checkpoint: {time_since_checkpoint:.1f}s")
                    print(f"[{self.camera_id}]    Forcing file rotation to prevent corruption...")

                    # Force segment rotation
                    writer = segment_manager.next_segment()
                    segment_start_time = current_time

                    if writer is None:
                        print(f"[{self.camera_id}] ❌ Failed to create checkpoint segment!")
                        break

                    print(f"[{self.camera_id}] ✅ Checkpoint segment created: {segment_manager.get_current_filename()}")

                # Try to read frame
                ret, frame = cap.read()

                if ret:
                    # ========== SUCCESSFUL FRAME READ ==========
                    now = time.time()

                    # Track frame timestamp for FPS calculation
                    frame_timestamps.append(now)

                    # Keep only recent frames for FPS window
                    if len(frame_timestamps) > fps_window:
                        frame_timestamps.pop(0)

                    # Calculate FPS every second
                    if now - last_fps_check >= fps_check_interval:
                        if len(frame_timestamps) >= 2:
                            current_fps = self._calculate_fps(frame_timestamps)
                            last_fps_check = now

                    # Check if we were disconnected and just reconnected
                    if is_disconnected:
                        reconnect_duration = time.time() - disconnection_start_time
                        self.total_disconnected_time += reconnect_duration
                        print(f"[{self.camera_id}] ✅ Streaming resumed after {reconnect_duration:.1f}s")
                        is_disconnected = False
                        disconnection_start_time = None
                        frame_timestamps = []  # Reset FPS tracking
                        current_fps = self.config['fps']
                        segment_start_time = time.time()  # Reset checkpoint timer (NEW in v3.1.0)
                        segment_manager.record_reconnection(reconnect_duration)

                    # Write frame to current segment
                    writer.write(frame)
                    frame_count += 1

                    # Update recording time
                    self.total_recording_time = time.time() - recording_start_time

                    # Progress update every 10 seconds
                    if frame_count % (fps * 10) == 0:
                        progress = (elapsed_total / duration_seconds) * 100
                        coverage = (self.total_recording_time / elapsed_total) * 100 if elapsed_total > 0 else 0
                        print(f"[{self.camera_id}] 📊 Progress: {progress:.1f}% | "
                              f"Frames: {frame_count} | "
                              f"FPS: {current_fps:.1f} | "
                              f"Coverage: {coverage:.1f}% | "
                              f"Segment: {segment_manager.segment_number}")

                else:
                    # ========== FAILED FRAME READ ==========
                    print(f"[{self.camera_id}] ⚠️  No frame received")

                    # Check if this is a disconnect based on FPS (NEW in v3.0.0)
                    if not is_disconnected and self._is_disconnected(current_fps):
                        # First detection of disconnect - IMMEDIATE ACTION
                        print(f"\n[{self.camera_id}] ❌ DISCONNECT DETECTED (FPS: {current_fps:.1f})")
                        print(f"[{self.camera_id}] 💾 Saving current segment...")

                        # IMMEDIATELY close current file
                        writer.release()

                        # Mark as disconnected
                        is_disconnected = True
                        disconnection_start_time = time.time()
                        last_reconnect_attempt = time.time()

                        # IMMEDIATELY create new segment
                        print(f"[{self.camera_id}] 📄 Creating new segment...")
                        writer = segment_manager.next_segment()

                        if writer is None:
                            print(f"[{self.camera_id}] ❌ Failed to create new segment!")
                            break

                        print(f"[{self.camera_id}] ✅ New segment created: {segment_manager.get_current_filename()}")
                        print(f"[{self.camera_id}] 🔄 Attempting reconnection...")

                        # Release current connection
                        cap.release()

                    # ========== CONTINUOUS RECONNECTION LOOP (v3.0.0) ==========
                    if is_disconnected:
                        disconnected_duration = time.time() - disconnection_start_time
                        time_since_last_attempt = time.time() - last_reconnect_attempt

                        # Try reconnection every RECONNECT_RETRY_INTERVAL seconds
                        if time_since_last_attempt >= RECONNECT_RETRY_INTERVAL:
                            last_reconnect_attempt = time.time()
                            print(f"[{self.camera_id}] 🔄 Reconnection attempt #{self.reconnection_attempts + 1}...")

                            new_cap = self._attempt_reconnection(disconnection_start_time)

                            if new_cap is not None:
                                # Reconnection successful - replace capture object
                                cap = new_cap
                                print(f"[{self.camera_id}] ▶️  Resuming recording to {segment_manager.get_current_filename()}")
                                # Next iteration will read frame and update state
                                continue
                            else:
                                print(f"[{self.camera_id}] ❌ Reconnection failed")
                                print(f"[{self.camera_id}]    Next attempt in {RECONNECT_RETRY_INTERVAL}s...")

                        # Sleep briefly to avoid busy loop
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
        # SESSION SUMMARY (ENHANCED in v3.0.0)
        # ========================================================================

        session_duration = time.time() - session_start_time
        coverage_report = segment_manager.get_coverage_report()

        print(f"\n{'='*70}")
        print(f"[{self.camera_id}] 📊 CAPTURE SESSION COMPLETE")
        print(f"{'='*70}")
        print(f"   Frames captured: {frame_count}")
        print(f"   Target duration: {duration_seconds}s")
        print(f"   Session duration: {session_duration:.1f}s")
        print(f"   Recording time: {coverage_report['recorded']:.1f}s")
        print(f"   Disconnected time: {self.total_disconnected_time:.1f}s")
        print(f"   Recording coverage: {coverage_report['coverage_percent']:.1f}%")

        if frame_count > 0 and coverage_report['recorded'] > 0:
            print(f"   Average FPS: {frame_count / coverage_report['recorded']:.2f}")

        print(f"\n   Reconnection stats:")
        print(f"   - Attempts: {self.reconnection_attempts}")
        print(f"   - Successful: {self.successful_reconnections}")
        if self.reconnection_attempts > 0:
            success_rate = (self.successful_reconnections / self.reconnection_attempts * 100)
            print(f"   - Success rate: {success_rate:.1f}%")

        print(f"\n   Checkpoint stats:")
        print(f"   - Periodic checkpoints: {checkpoint_count}")
        print(f"   - Checkpoint interval: {CHECKPOINT_INTERVAL_SECONDS}s ({CHECKPOINT_INTERVAL_SECONDS/60:.0f} minutes)")

        print(f"\n   Video segments created: {coverage_report['segment_count']}")
        print(f"   Disconnections (new segments): {coverage_report['disconnections']}")
        for seg_info in coverage_report['segments']:
            filepath = output_path / seg_info['filename']
            if filepath.exists():
                size_mb = filepath.stat().st_size / (1024 * 1024)
                print(f"   - {seg_info['filename']}: {size_mb:.1f} MB ({seg_info['duration']:.1f}s)")

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
# SIGNAL HANDLERS FOR GRACEFUL SHUTDOWN (NEW in v3.1.0)
# ============================================================================

# Global registry for active captures (for signal handler cleanup)
_active_captures = []

def signal_handler(sig, frame):
    """
    Handle SIGTERM and SIGINT for graceful shutdown.
    Ensures video files are properly closed to prevent corruption.

    Modified: 2025-11-19 - Removed sys.exit(0) to allow finally blocks to execute
    """
    signal_name = "SIGTERM" if sig == signal.SIGTERM else "SIGINT"
    print(f"\n⚠️  Received {signal_name}, initiating graceful shutdown...")

    # Stop all active captures
    for capture in _active_captures:
        try:
            print(f"[{capture.camera_id}] Stopping capture...")
            capture.is_capturing = False
        except Exception as e:
            print(f"[{capture.camera_id}] Error stopping capture: {e}")

    print("✅ Graceful shutdown initiated (waiting for cleanup...)")
    # NOTE: Removed sys.exit(0) to allow finally blocks to execute properly
    # The capture loop will exit naturally when is_capturing becomes False


# Register signal handlers
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


# ============================================================================
# CONFIGURATION AND MAIN FUNCTIONS (UNCHANGED)
# ============================================================================

def load_cameras_config():
    """
    Load cameras configuration from JSON file

    Raises:
        FileNotFoundError: If cameras_config.json does not exist
        json.JSONDecodeError: If config file has invalid JSON
    """
    if not CAMERAS_CONFIG.exists():
        raise FileNotFoundError(
            f"❌ Camera configuration file not found: {CAMERAS_CONFIG}\n"
            f"   Please create the configuration file using:\n"
            f"   - python3 scripts/deployment/initialize_restaurant.py (first-time setup)\n"
            f"   - python3 scripts/deployment/manage_cameras.py (add/edit cameras)"
        )

    print(f"📂 Loading camera config from: {CAMERAS_CONFIG}")
    try:
        with open(CAMERAS_CONFIG, 'r') as f:
            cameras = json.load(f)

        if not cameras:
            raise ValueError("❌ Camera configuration is empty")

        print(f"✅ Loaded {len(cameras)} camera(s)")
        return cameras

    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(
            f"❌ Invalid JSON in camera configuration file: {CAMERAS_CONFIG}\n"
            f"   Error: {str(e)}",
            e.doc,
            e.pos
        )


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
    print(f"Disconnect detection: FPS < {DISCONNECT_FPS_THRESHOLD} (immediate segmentation)")
    print(f"Reconnection interval: {RECONNECT_RETRY_INTERVAL}s")
    print(f"Checkpoint interval: {CHECKPOINT_INTERVAL_SECONDS}s ({CHECKPOINT_INTERVAL_SECONDS/60:.0f} minutes)")
    print(f"Network RTT threshold: {MAX_RTT_MS}ms")
    print(f"{'='*70}\n")

    # Create capture objects
    captures = {}
    threads = []

    for camera_id, config in cameras.items():
        capture = CameraCapture(camera_id, config)
        captures[camera_id] = capture
        _active_captures.append(capture)  # Register for signal handler (NEW in v3.1.0)
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

Reconnection Features (v3.0.0):
  - FPS-based disconnect detection (< 2fps = immediate disconnect)
  - IMMEDIATE segmentation when disconnect detected (no delay)
  - Prevents missing state changes during network interruptions
  - Continuously retries connection every 10s during recording window
  - Checks network health before attempting RTSP connection
  - Aborts if RTT > 500ms (network too slow)
  - Creates new segment (_part2, _part3) on every disconnect
  - Reports recording coverage % at end of session

Checkpoint Features (v3.1.0):
  - Periodic file rotation every 10 minutes (600 seconds)
  - Prevents moov atom corruption if network fails
  - Maximum 10 minutes data loss instead of entire session
  - Graceful shutdown on SIGTERM/SIGINT signals
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
    print(f"\n🎥 RTSP Video Capture System v3.0.0 (Immediate Segmentation)")
    print(f"{'='*70}")
    print(f"Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

    capture_all_cameras(args.duration, output_dir, args.cameras)

    end_time = datetime.now()
    total_duration = (end_time - start_time).total_seconds()
    print(f"End time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total runtime: {total_duration:.1f}s ({total_duration/60:.1f} minutes)\n")


if __name__ == "__main__":
    main()
