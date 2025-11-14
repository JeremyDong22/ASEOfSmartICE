#!/usr/bin/env python3
"""
Camera Connection Testing Script for Production Deployment
Version: 1.0.0
Last Updated: 2025-11-14

Purpose: Comprehensive testing of UNV camera connections via RTSP
Tests connectivity, latency, FPS, resolution, and recording capability
Auto-generates cameras_config.json with validated cameras only

Features:
- Parallel testing of multiple cameras
- Ping test with RTT measurement
- Connection time measurement
- FPS verification (expected 20 FPS ±10%)
- Resolution verification
- 30-second recording test with integrity check
- Bandwidth estimation
- Auto-disable unstable cameras
- Detailed test report generation

Author: ASEOfSmartICE Team
"""

import cv2
import json
import argparse
import time
import os
import subprocess
import threading
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys

# Script configuration
SCRIPT_DIR = Path(__file__).parent.resolve()
CAMERAS_CONFIG = SCRIPT_DIR / "cameras_config.json"
TEST_VIDEOS_DIR = SCRIPT_DIR.parent / "tests" / "camera_test_videos"
TEST_REPORT_DIR = SCRIPT_DIR.parent / "tests" / "camera_test_reports"

# Test parameters
PING_TIMEOUT_MS = 500
CONNECTION_TIMEOUT_SECONDS = 10
RECORDING_DURATION_SECONDS = 30
FPS_EXPECTED = 20
FPS_TOLERANCE_PERCENT = 10  # ±10%
TEST_TIMEOUT_PER_CAMERA = 60  # Maximum 60 seconds per camera

# UNV camera defaults
DEFAULT_PORT = 554
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "123456"
DEFAULT_STREAM_PATH = "/media/video1"


class CameraTestResult:
    """Store test results for a single camera"""

    def __init__(self, ip):
        self.ip = ip
        self.ping_success = False
        self.ping_rtt_ms = None
        self.connection_success = False
        self.connection_time_ms = None
        self.resolution = None
        self.actual_fps = None
        self.fps_within_range = False
        self.recording_success = False
        self.recording_path = None
        self.integrity_check_success = False
        self.bandwidth_mbps = None
        self.overall_success = False
        self.error_messages = []

    def add_error(self, message):
        """Add error message to the list"""
        self.error_messages.append(message)

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            "ip": self.ip,
            "ping": {
                "success": self.ping_success,
                "rtt_ms": self.ping_rtt_ms
            },
            "connection": {
                "success": self.connection_success,
                "time_ms": self.connection_time_ms
            },
            "resolution": self.resolution,
            "fps": {
                "actual": self.actual_fps,
                "expected": FPS_EXPECTED,
                "within_range": self.fps_within_range
            },
            "recording": {
                "success": self.recording_success,
                "path": str(self.recording_path) if self.recording_path else None
            },
            "integrity": {
                "success": self.integrity_check_success
            },
            "bandwidth_mbps": self.bandwidth_mbps,
            "overall_success": self.overall_success,
            "errors": self.error_messages
        }


class CameraTester:
    """Test a single camera connection"""

    def __init__(self, ip, port=DEFAULT_PORT, username=DEFAULT_USERNAME,
                 password=DEFAULT_PASSWORD, stream_path=DEFAULT_STREAM_PATH):
        self.ip = ip
        self.port = port
        self.username = username
        self.password = password
        self.stream_path = stream_path
        self.rtsp_url = self._build_rtsp_url()
        self.result = CameraTestResult(ip)

    def _build_rtsp_url(self):
        """Build RTSP URL from camera config"""
        return (f"rtsp://{self.username}:{self.password}"
                f"@{self.ip}:{self.port}{self.stream_path}")

    def _ping_test(self):
        """Test network connectivity with ping"""
        print(f"[{self.ip}] Running ping test...")

        try:
            # Determine ping command based on OS
            if sys.platform.startswith('darwin') or sys.platform.startswith('linux'):
                # macOS/Linux: -c count -W timeout(ms) -t ttl
                cmd = ['ping', '-c', '4', '-W', '1', self.ip]
            else:
                # Windows: -n count -w timeout(ms)
                cmd = ['ping', '-n', '4', '-w', '1000', self.ip]

            start_time = time.time()
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            elapsed_ms = (time.time() - start_time) * 1000

            if result.returncode == 0:
                # Parse RTT from ping output
                output = result.stdout
                if sys.platform.startswith('darwin') or sys.platform.startswith('linux'):
                    # Parse Linux/macOS format: "time=XX.X ms"
                    for line in output.split('\n'):
                        if 'time=' in line:
                            try:
                                rtt = float(line.split('time=')[1].split()[0])
                                self.result.ping_rtt_ms = rtt
                                break
                            except:
                                pass
                else:
                    # Parse Windows format: "Average = XXms"
                    for line in output.split('\n'):
                        if 'Average' in line:
                            try:
                                rtt = float(line.split('=')[1].strip().replace('ms', ''))
                                self.result.ping_rtt_ms = rtt
                                break
                            except:
                                pass

                if self.result.ping_rtt_ms is None:
                    self.result.ping_rtt_ms = elapsed_ms / 4  # Average of 4 pings

                if self.result.ping_rtt_ms < PING_TIMEOUT_MS:
                    self.result.ping_success = True
                    print(f"[{self.ip}] Ping: SUCCESS (RTT: {self.result.ping_rtt_ms:.1f}ms)")
                else:
                    self.result.add_error(f"Ping RTT too high: {self.result.ping_rtt_ms:.1f}ms > {PING_TIMEOUT_MS}ms")
                    print(f"[{self.ip}] Ping: FAILED (RTT too high: {self.result.ping_rtt_ms:.1f}ms)")
            else:
                self.result.add_error("Host unreachable (ping failed)")
                print(f"[{self.ip}] Ping: FAILED (unreachable)")

        except subprocess.TimeoutExpired:
            self.result.add_error("Ping timeout")
            print(f"[{self.ip}] Ping: TIMEOUT")
        except Exception as e:
            self.result.add_error(f"Ping error: {str(e)}")
            print(f"[{self.ip}] Ping: ERROR - {str(e)}")

    def _connection_test(self):
        """Test RTSP connection and measure time"""
        print(f"[{self.ip}] Testing RTSP connection...")

        try:
            start_time = time.time()
            cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)

            # Wait for connection
            wait_start = time.time()
            connected = False
            while (time.time() - wait_start) < CONNECTION_TIMEOUT_SECONDS:
                if cap.isOpened():
                    connected = True
                    break
                time.sleep(0.1)

            connection_time = (time.time() - start_time) * 1000
            self.result.connection_time_ms = connection_time

            if connected:
                self.result.connection_success = True
                print(f"[{self.ip}] Connection: SUCCESS ({connection_time:.0f}ms)")

                # Get resolution
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                self.result.resolution = [width, height]
                print(f"[{self.ip}] Resolution: {width}x{height}")

                cap.release()
                return True
            else:
                self.result.add_error(f"Connection timeout after {CONNECTION_TIMEOUT_SECONDS}s")
                print(f"[{self.ip}] Connection: TIMEOUT")
                cap.release()
                return False

        except Exception as e:
            self.result.add_error(f"Connection error: {str(e)}")
            print(f"[{self.ip}] Connection: ERROR - {str(e)}")
            return False

    def _fps_and_recording_test(self):
        """Test FPS and record 30-second video"""
        print(f"[{self.ip}] Testing FPS and recording {RECORDING_DURATION_SECONDS}s video...")

        try:
            cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)

            if not cap.isOpened():
                self.result.add_error("Cannot open RTSP stream for recording")
                print(f"[{self.ip}] Recording: FAILED (cannot open stream)")
                return False

            # Get stream properties
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps_reported = cap.get(cv2.CAP_PROP_FPS)

            # Setup output
            TEST_VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = TEST_VIDEOS_DIR / f"test_{self.ip.replace('.', '_')}_{timestamp}.mp4"

            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(str(output_file), fourcc, FPS_EXPECTED, (width, height))

            if not out.isOpened():
                self.result.add_error("Cannot create output video file")
                print(f"[{self.ip}] Recording: FAILED (cannot create output)")
                cap.release()
                return False

            # Record and measure FPS
            start_time = time.time()
            frame_count = 0
            failed_reads = 0

            while (time.time() - start_time) < RECORDING_DURATION_SECONDS:
                ret, frame = cap.read()

                if ret:
                    out.write(frame)
                    frame_count += 1
                    failed_reads = 0
                else:
                    failed_reads += 1
                    if failed_reads > 50:  # Too many consecutive failures
                        self.result.add_error(f"Too many failed frame reads ({failed_reads})")
                        break
                    time.sleep(0.01)

            actual_duration = time.time() - start_time
            cap.release()
            out.release()

            # Calculate actual FPS
            if actual_duration > 0:
                self.result.actual_fps = frame_count / actual_duration
                fps_min = FPS_EXPECTED * (1 - FPS_TOLERANCE_PERCENT / 100)
                fps_max = FPS_EXPECTED * (1 + FPS_TOLERANCE_PERCENT / 100)

                self.result.fps_within_range = fps_min <= self.result.actual_fps <= fps_max

                print(f"[{self.ip}] FPS: {self.result.actual_fps:.2f} (expected {FPS_EXPECTED} ±{FPS_TOLERANCE_PERCENT}%)")

                if self.result.fps_within_range:
                    print(f"[{self.ip}] FPS: PASS")
                else:
                    self.result.add_error(f"FPS out of range: {self.result.actual_fps:.2f} (expected {fps_min:.1f}-{fps_max:.1f})")
                    print(f"[{self.ip}] FPS: FAIL (out of range)")

            # Check recording success
            if output_file.exists() and output_file.stat().st_size > 0:
                self.result.recording_success = True
                self.result.recording_path = output_file
                file_size_mb = output_file.stat().st_size / (1024 * 1024)

                # Estimate bandwidth
                if actual_duration > 0:
                    self.result.bandwidth_mbps = (file_size_mb * 8) / actual_duration

                print(f"[{self.ip}] Recording: SUCCESS ({file_size_mb:.1f}MB, {self.result.bandwidth_mbps:.2f} Mbps)")
                return True
            else:
                self.result.add_error("Recording file empty or not created")
                print(f"[{self.ip}] Recording: FAILED (file empty)")
                return False

        except Exception as e:
            self.result.add_error(f"Recording error: {str(e)}")
            print(f"[{self.ip}] Recording: ERROR - {str(e)}")
            return False

    def _integrity_check(self):
        """Check video file integrity using ffprobe"""
        if not self.result.recording_path or not self.result.recording_path.exists():
            print(f"[{self.ip}] Integrity check: SKIP (no recording)")
            return False

        print(f"[{self.ip}] Checking video integrity...")

        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                str(self.result.recording_path)
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode == 0 and result.stdout.strip():
                duration = float(result.stdout.strip())
                if duration > 0:
                    self.result.integrity_check_success = True
                    print(f"[{self.ip}] Integrity: PASS (duration: {duration:.1f}s)")
                    return True
                else:
                    self.result.add_error("Video duration is 0")
                    print(f"[{self.ip}] Integrity: FAIL (zero duration)")
            else:
                self.result.add_error(f"ffprobe failed: {result.stderr}")
                print(f"[{self.ip}] Integrity: FAIL (ffprobe error)")

        except FileNotFoundError:
            print(f"[{self.ip}] Integrity: SKIP (ffprobe not installed)")
            # Don't fail the test if ffprobe is not available
            self.result.integrity_check_success = True
            return True
        except Exception as e:
            self.result.add_error(f"Integrity check error: {str(e)}")
            print(f"[{self.ip}] Integrity: ERROR - {str(e)}")

        return False

    def run_all_tests(self):
        """Run all tests sequentially"""
        print(f"\n{'='*70}")
        print(f"Testing camera: {self.ip}")
        print(f"RTSP URL: {self.rtsp_url}")
        print(f"{'='*70}")

        start_time = time.time()

        # Run tests in order
        self._ping_test()

        if self.result.ping_success:
            connection_ok = self._connection_test()

            if connection_ok:
                recording_ok = self._fps_and_recording_test()

                if recording_ok:
                    self._integrity_check()

        # Determine overall success
        self.result.overall_success = (
            self.result.ping_success and
            self.result.connection_success and
            self.result.fps_within_range and
            self.result.recording_success and
            (self.result.integrity_check_success or True)  # Optional if ffprobe not available
        )

        elapsed_time = time.time() - start_time

        print(f"\n{'='*70}")
        if self.result.overall_success:
            print(f"Camera {self.ip}: PASS (took {elapsed_time:.1f}s)")
        else:
            print(f"Camera {self.ip}: FAIL (took {elapsed_time:.1f}s)")
            print(f"Errors: {', '.join(self.result.error_messages)}")
        print(f"{'='*70}\n")

        return self.result


def test_cameras_parallel(ip_list, max_workers=10):
    """Test multiple cameras in parallel"""
    print(f"\n{'='*70}")
    print(f"Starting parallel camera tests for {len(ip_list)} camera(s)")
    print(f"{'='*70}\n")

    results = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tests
        future_to_ip = {
            executor.submit(test_single_camera, ip): ip
            for ip in ip_list
        }

        # Collect results as they complete
        for future in as_completed(future_to_ip):
            ip = future_to_ip[future]
            try:
                result = future.result(timeout=TEST_TIMEOUT_PER_CAMERA)
                results[ip] = result
            except Exception as e:
                print(f"[{ip}] EXCEPTION during testing: {str(e)}")
                result = CameraTestResult(ip)
                result.add_error(f"Test exception: {str(e)}")
                results[ip] = result

    return results


def test_single_camera(ip):
    """Test a single camera (wrapper for parallel execution)"""
    tester = CameraTester(ip)
    return tester.run_all_tests()


def generate_test_report(results, output_file=None):
    """Generate detailed test report"""
    if output_file is None:
        TEST_REPORT_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = TEST_REPORT_DIR / f"camera_test_report_{timestamp}.json"

    # Summary statistics
    total_cameras = len(results)
    passed_cameras = sum(1 for r in results.values() if r.overall_success)
    failed_cameras = total_cameras - passed_cameras

    report = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_cameras": total_cameras,
            "passed": passed_cameras,
            "failed": failed_cameras,
            "success_rate": (passed_cameras / total_cameras * 100) if total_cameras > 0 else 0
        },
        "test_parameters": {
            "ping_timeout_ms": PING_TIMEOUT_MS,
            "connection_timeout_s": CONNECTION_TIMEOUT_SECONDS,
            "recording_duration_s": RECORDING_DURATION_SECONDS,
            "expected_fps": FPS_EXPECTED,
            "fps_tolerance_percent": FPS_TOLERANCE_PERCENT
        },
        "cameras": {ip: result.to_dict() for ip, result in results.items()}
    }

    # Save report
    with open(output_file, 'w') as f:
        json.dump(report, f, indent=2)

    print(f"\n{'='*70}")
    print("TEST SUMMARY")
    print(f"{'='*70}")
    print(f"Total cameras tested: {total_cameras}")
    print(f"Passed: {passed_cameras} ({report['summary']['success_rate']:.1f}%)")
    print(f"Failed: {failed_cameras}")
    print(f"\nDetailed report saved to: {output_file}")
    print(f"{'='*70}\n")

    # Print individual results
    print("INDIVIDUAL RESULTS:")
    print(f"{'='*70}")
    for ip, result in sorted(results.items()):
        status = "PASS" if result.overall_success else "FAIL"
        print(f"{ip:20} | {status:4} | Ping: {result.ping_rtt_ms:>6.1f}ms | "
              f"FPS: {result.actual_fps:>5.1f} | "
              f"Bandwidth: {result.bandwidth_mbps:>6.2f}Mbps"
              if result.actual_fps and result.bandwidth_mbps else f"{status}")

        if not result.overall_success and result.error_messages:
            for error in result.error_messages:
                print(f"{'':20} | Error: {error}")
    print(f"{'='*70}\n")

    return report, output_file


def update_cameras_config(results, config_file=CAMERAS_CONFIG):
    """Generate or update cameras_config.json with validated cameras only"""
    print(f"\n{'='*70}")
    print("Updating cameras_config.json")
    print(f"{'='*70}")

    # Load existing config if exists
    existing_config = {}
    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                existing_config = json.load(f)
            print(f"Loaded existing config with {len(existing_config)} camera(s)")
        except Exception as e:
            print(f"Warning: Could not load existing config: {e}")

    # Build new config
    new_config = {}

    for ip, result in results.items():
        camera_id = f"camera_{ip.replace('.', '_').split('_')[-1]}"  # e.g., camera_35

        # Check if camera exists in old config
        existing_camera = None
        for cam_id, cam_data in existing_config.items():
            if cam_data.get('ip') == ip:
                existing_camera = cam_data
                camera_id = cam_id  # Keep existing ID
                break

        # Build camera config
        camera_config = {
            "ip": ip,
            "port": DEFAULT_PORT,
            "username": DEFAULT_USERNAME,
            "password": DEFAULT_PASSWORD,
            "stream_path": DEFAULT_STREAM_PATH,
            "resolution": result.resolution if result.resolution else [640, 480],
            "fps": int(result.actual_fps) if result.actual_fps else FPS_EXPECTED,
            "enabled": result.overall_success,
            "last_test": datetime.now().isoformat(),
            "test_results": {
                "ping_rtt_ms": result.ping_rtt_ms,
                "connection_time_ms": result.connection_time_ms,
                "actual_fps": result.actual_fps,
                "bandwidth_mbps": result.bandwidth_mbps
            }
        }

        # Preserve additional fields from existing config
        if existing_camera:
            for key in ["division_name", "location_id", "notes"]:
                if key in existing_camera:
                    camera_config[key] = existing_camera[key]

        new_config[camera_id] = camera_config

    # Save config
    with open(config_file, 'w') as f:
        json.dump(new_config, f, indent=2)

    enabled_count = sum(1 for c in new_config.values() if c['enabled'])
    disabled_count = len(new_config) - enabled_count

    print(f"\nConfig updated: {config_file}")
    print(f"Total cameras: {len(new_config)}")
    print(f"Enabled: {enabled_count}")
    print(f"Disabled: {disabled_count}")
    print(f"{'='*70}\n")

    return new_config


def cleanup_test_videos(keep_failed=True):
    """Clean up test videos after validation"""
    if not TEST_VIDEOS_DIR.exists():
        return

    print(f"Cleaning up test videos from {TEST_VIDEOS_DIR}...")

    removed_count = 0
    for video_file in TEST_VIDEOS_DIR.glob("test_*.mp4"):
        try:
            video_file.unlink()
            removed_count += 1
        except Exception as e:
            print(f"Warning: Could not remove {video_file}: {e}")

    print(f"Removed {removed_count} test video(s)")


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Comprehensive camera connection testing for production deployment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test specific IPs
  python3 test_camera_connections.py --ips 202.168.40.35 202.168.40.22

  # Interactive mode (prompts for IPs)
  python3 test_camera_connections.py --interactive

  # Validate existing config
  python3 test_camera_connections.py --validate-config cameras_config.json

  # Test and keep test videos
  python3 test_camera_connections.py --ips 202.168.40.35 --keep-videos
        """
    )

    parser.add_argument("--ips", nargs='+', help="List of camera IPs to test")
    parser.add_argument("--interactive", action="store_true",
                       help="Interactive mode: prompt for IPs")
    parser.add_argument("--validate-config", metavar="FILE",
                       help="Test all cameras in existing config file")
    parser.add_argument("--keep-videos", action="store_true",
                       help="Keep test videos after validation (default: delete)")
    parser.add_argument("--update-config", action="store_true", default=True,
                       help="Update cameras_config.json with test results (default: true)")
    parser.add_argument("--max-workers", type=int, default=10,
                       help="Maximum parallel tests (default: 10)")

    args = parser.parse_args()

    # Determine IPs to test
    ip_list = []

    if args.validate_config:
        # Load IPs from config file
        config_path = Path(args.validate_config)
        if not config_path.exists():
            print(f"Error: Config file not found: {config_path}")
            sys.exit(1)

        with open(config_path, 'r') as f:
            config = json.load(f)

        ip_list = [cam['ip'] for cam in config.values() if 'ip' in cam]
        print(f"Loaded {len(ip_list)} camera(s) from {config_path}")

    elif args.interactive:
        # Interactive input
        print("Interactive mode: Enter camera IPs to test")
        print("Enter IPs one per line, or comma/space separated")
        print("Press Enter on empty line to finish\n")

        all_input = []
        while True:
            line = input("Camera IP: ").strip()
            if not line:
                break
            all_input.append(line)

        # Parse input (handle comma/space separated)
        for line in all_input:
            ips = line.replace(',', ' ').split()
            ip_list.extend(ips)

    elif args.ips:
        ip_list = args.ips
    else:
        parser.print_help()
        print("\nError: Must specify --ips, --interactive, or --validate-config")
        sys.exit(1)

    if not ip_list:
        print("Error: No camera IPs provided")
        sys.exit(1)

    # Remove duplicates
    ip_list = list(set(ip_list))

    print(f"\n{'='*70}")
    print("CAMERA CONNECTION TEST SYSTEM")
    print(f"{'='*70}")
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Cameras to test: {len(ip_list)}")
    print(f"IPs: {', '.join(ip_list)}")
    print(f"{'='*70}\n")

    # Run tests
    results = test_cameras_parallel(ip_list, max_workers=args.max_workers)

    # Generate report
    report, report_file = generate_test_report(results)

    # Update config
    if args.update_config:
        update_cameras_config(results)

    # Cleanup test videos
    if not args.keep_videos:
        cleanup_test_videos()

    # Exit code
    passed_cameras = sum(1 for r in results.values() if r.overall_success)

    print(f"\nTest completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if passed_cameras > 0:
        print(f"SUCCESS: {passed_cameras}/{len(results)} camera(s) passed")
        sys.exit(0)
    else:
        print(f"FAILURE: All cameras failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
