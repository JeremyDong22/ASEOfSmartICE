#!/usr/bin/env python3
"""
Multi-Camera Video Processing Orchestrator with GPU Queue Management
Version: 2.0.0
Last Updated: 2025-11-14

Purpose: Intelligent GPU-aware orchestration of multi-camera video processing
Uses queue-based job management with GPU health monitoring

Major Changes in v2.0.0:
- Replaced simple threading with job queue system
- Added GPU temperature/utilization/memory monitoring via nvidia-smi
- Dynamic parallel job limits based on GPU health
- Smart logging system with bi-weekly rotation
- Separate error logs for debugging
- Performance metrics tracking
- Priority-based queue (older videos first)
- Graceful degradation on macOS (no GPU monitoring)

Features:
- Auto-discovery of videos from videos folder
- Groups videos by camera_id (extracted from filename)
- Queue-based processing with GPU-aware concurrency control
- Batch processing (processes multiple segments per camera)
- Progress tracking and detailed logging
- Non-verbose console output (minimal progress bars)

Author: ASEOfSmartICE Team
"""

import os
import subprocess
import threading
import queue
import time
import logging
import json
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
import argparse
import re
import sys
import platform


# ============================================================================
# CONFIGURATION
# ============================================================================

SCRIPT_DIR = Path(__file__).parent.resolve()
VIDEOS_DIR = SCRIPT_DIR.parent.parent / "videos"
LOGS_DIR = SCRIPT_DIR.parent.parent / "logs"
DETECTION_SCRIPT = SCRIPT_DIR.parent / "video_processing" / "table_and_region_state_detection.py"

# GPU monitoring settings
GPU_CHECK_INTERVAL = 30  # Check GPU health every 30 seconds
GPU_TEMP_WARNING = 70    # Reduce parallelism at this temp
GPU_TEMP_CRITICAL = 80   # Minimal parallelism at this temp
GPU_UTIL_HIGH = 95       # High utilization threshold
GPU_MEM_HIGH = 90        # High memory threshold

# Default parallel job limits
DEFAULT_MAX_PARALLEL = 4     # Healthy GPU
WARM_MAX_PARALLEL = 2        # Warm GPU (70-80°C)
HOT_MAX_PARALLEL = 1         # Hot GPU (>80°C)

# Log rotation settings
LOG_RETENTION_DAYS = 14  # Keep 2 weeks of logs


# ============================================================================
# GPU MONITORING
# ============================================================================

class GPUMonitor:
    """
    Monitor GPU health using nvidia-smi
    Tracks temperature, utilization, and memory usage
    """

    def __init__(self, logger):
        self.logger = logger
        self.is_available = self._check_nvidia_smi()
        self.last_check = None
        self.last_metrics = None

        if not self.is_available:
            self.logger.warning("nvidia-smi not available - GPU monitoring disabled")
            if platform.system() == "Darwin":
                self.logger.info("Running on macOS - GPU monitoring not supported")

    def _check_nvidia_smi(self) -> bool:
        """Check if nvidia-smi is available"""
        try:
            subprocess.run(
                ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader"],
                capture_output=True,
                timeout=5
            )
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def get_metrics(self) -> Optional[Dict]:
        """
        Query GPU metrics using nvidia-smi
        Returns: {temp: int, utilization: int, memory_used: int, memory_total: int}
        """
        if not self.is_available:
            return None

        try:
            # Query multiple metrics in one call
            result = subprocess.run([
                "nvidia-smi",
                "--query-gpu=temperature.gpu,utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits"
            ], capture_output=True, text=True, timeout=5)

            if result.returncode != 0:
                return None

            # Parse output (format: "75, 80, 5000, 12000")
            values = [int(x.strip()) for x in result.stdout.strip().split(',')]

            metrics = {
                'temp': values[0],
                'utilization': values[1],
                'memory_used': values[2],
                'memory_total': values[3],
                'memory_percent': (values[2] / values[3] * 100) if values[3] > 0 else 0,
                'timestamp': datetime.now().isoformat()
            }

            self.last_check = time.time()
            self.last_metrics = metrics

            return metrics

        except Exception as e:
            self.logger.error(f"GPU metrics query failed: {e}")
            return None

    def get_health_status(self) -> Tuple[str, int]:
        """
        Determine GPU health and recommended parallel jobs
        Returns: (status, max_parallel)
        """
        metrics = self.get_metrics()

        if not metrics:
            # No GPU monitoring available - use default
            return ("unknown", DEFAULT_MAX_PARALLEL)

        temp = metrics['temp']
        util = metrics['utilization']
        mem = metrics['memory_percent']

        # Determine status based on thresholds
        if temp >= GPU_TEMP_CRITICAL or util >= GPU_UTIL_HIGH or mem >= GPU_MEM_HIGH:
            return ("critical", HOT_MAX_PARALLEL)
        elif temp >= GPU_TEMP_WARNING:
            return ("warm", WARM_MAX_PARALLEL)
        else:
            return ("healthy", DEFAULT_MAX_PARALLEL)

    def log_metrics(self, metrics: Dict):
        """Log GPU metrics to logger"""
        self.logger.info(
            f"GPU: {metrics['temp']}°C | "
            f"Util: {metrics['utilization']}% | "
            f"Mem: {metrics['memory_used']}MB / {metrics['memory_total']}MB "
            f"({metrics['memory_percent']:.1f}%)"
        )


# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logging(log_level: str = "INFO") -> Tuple[logging.Logger, Path]:
    """
    Setup logging system with file and console handlers
    - Bi-weekly rotation (keep last 14 days)
    - Separate error log
    - Non-verbose console output

    Returns: (logger, log_file_path)
    """
    LOGS_DIR.mkdir(exist_ok=True)

    # Cleanup old logs (older than 14 days)
    cleanup_old_logs(LOGS_DIR, LOG_RETENTION_DAYS)

    # Create session log file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOGS_DIR / f"processing_{timestamp}.log"
    error_log_file = LOGS_DIR / f"errors_{datetime.now().strftime('%Y%m%d')}.log"

    # Create logger
    logger = logging.getLogger("VideoOrchestrator")
    logger.setLevel(getattr(logging, log_level.upper()))
    logger.handlers.clear()  # Clear any existing handlers

    # File handler (detailed logs)
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # Error file handler (errors only)
    error_handler = logging.FileHandler(error_log_file, encoding='utf-8')
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_formatter)
    logger.addHandler(error_handler)

    # Console handler (minimal output)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    logger.info(f"Logging initialized: {log_file}")
    logger.info(f"Error log: {error_log_file}")

    return logger, log_file


def cleanup_old_logs(logs_dir: Path, retention_days: int):
    """Remove log files older than retention period"""
    cutoff_date = datetime.now() - timedelta(days=retention_days)

    for log_file in logs_dir.glob("*.log"):
        try:
            mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
            if mtime < cutoff_date:
                log_file.unlink()
        except Exception:
            pass  # Ignore errors during cleanup


# ============================================================================
# VIDEO DISCOVERY
# ============================================================================

def extract_camera_id(video_filename: str) -> Optional[str]:
    """Extract camera_id from filename (e.g., camera_35_20251114.mp4 -> camera_35)"""
    match = re.match(r'^(camera_\d+)', video_filename)
    if match:
        return match.group(1)
    return None


def extract_timestamp(video_filename: str) -> str:
    """Extract timestamp from filename for sorting (camera_35_20251114_183000.mp4 -> 20251114_183000)"""
    match = re.search(r'(\d{8}_\d{6})', video_filename)
    if match:
        return match.group(1)
    return "00000000_000000"  # Default for sorting


def discover_videos(videos_dir: Path, camera_filter: Optional[List[str]] = None) -> Dict[str, List[str]]:
    """
    Discover all videos in videos directory

    Expected structure: videos/YYYYMMDD/camera_id/camera_id_YYYYMMDD_HHMMSS.mp4

    Returns: dict of {camera_id: [video_paths]} sorted by timestamp (oldest first)
    """
    videos_by_camera = defaultdict(list)

    if not videos_dir.exists():
        return videos_by_camera

    # Find all mp4 files in date/camera_id structure
    for video_file in videos_dir.rglob("*.mp4"):
        camera_id = extract_camera_id(video_file.name)

        if not camera_id:
            continue

        # Filter if specified
        if camera_filter and camera_id not in camera_filter:
            continue

        videos_by_camera[camera_id].append(str(video_file))

    # Sort videos by timestamp within each camera (oldest first for priority queue)
    for camera_id in videos_by_camera:
        videos_by_camera[camera_id].sort(key=lambda v: extract_timestamp(os.path.basename(v)))

    return dict(videos_by_camera)


# ============================================================================
# JOB QUEUE SYSTEM
# ============================================================================

class ProcessingJob:
    """Represents a single video processing job"""

    def __init__(self, camera_id: str, video_path: str, priority: int,
                 duration: Optional[int] = None, config_path: Optional[str] = None):
        self.camera_id = camera_id
        self.video_path = video_path
        self.priority = priority  # Lower number = higher priority (older videos)
        self.duration = duration
        self.config_path = config_path
        self.video_name = os.path.basename(video_path)

    def __lt__(self, other):
        """Compare by priority for queue ordering"""
        return self.priority < other.priority


class ProcessingQueue:
    """
    GPU-aware processing queue with dynamic concurrency control
    """

    def __init__(self, logger: logging.Logger, gpu_monitor: GPUMonitor,
                 max_parallel: int = DEFAULT_MAX_PARALLEL):
        self.logger = logger
        self.gpu_monitor = gpu_monitor
        self.max_parallel = max_parallel
        self.current_parallel = max_parallel

        # Job queue (priority queue - older videos first)
        self.job_queue = queue.PriorityQueue()

        # Active workers tracking
        self.active_workers = {}
        self.worker_lock = threading.Lock()

        # Statistics
        self.jobs_completed = 0
        self.jobs_failed = 0
        self.total_processing_time = 0
        self.start_time = None

        # Shutdown flag
        self.shutdown = False

    def add_job(self, job: ProcessingJob):
        """Add a job to the queue"""
        self.job_queue.put(job)

    def get_queue_status(self) -> Dict:
        """Get current queue status"""
        with self.worker_lock:
            active_count = len(self.active_workers)

        return {
            'jobs_waiting': self.job_queue.qsize(),
            'jobs_running': active_count,
            'jobs_completed': self.jobs_completed,
            'jobs_failed': self.jobs_failed,
            'max_parallel': self.current_parallel
        }

    def adjust_parallelism(self):
        """Adjust max parallel jobs based on GPU health"""
        status, recommended_parallel = self.gpu_monitor.get_health_status()

        if recommended_parallel != self.current_parallel:
            old_parallel = self.current_parallel
            self.current_parallel = recommended_parallel
            self.logger.warning(
                f"GPU health: {status.upper()} - "
                f"Adjusting parallelism: {old_parallel} -> {self.current_parallel}"
            )

    def process_job(self, job: ProcessingJob) -> bool:
        """
        Process a single job
        Returns: True if successful, False if failed
        """
        worker_id = threading.get_ident()

        # Register worker
        with self.worker_lock:
            self.active_workers[worker_id] = job

        try:
            self.logger.info(f"[{job.camera_id}] START: {job.video_name}")

            # Build command
            cmd = [
                "python3",
                str(DETECTION_SCRIPT),
                "--video", job.video_path
            ]

            if job.duration:
                cmd.extend(["--duration", str(job.duration)])

            if job.config_path:
                # Check for camera-specific config
                camera_config = Path(job.config_path).parent / f"table_region_config_{job.camera_id}.json"
                if camera_config.exists():
                    self.logger.debug(f"[{job.camera_id}] Using camera-specific config: {camera_config.name}")
                else:
                    self.logger.debug(f"[{job.camera_id}] Using default config: {Path(job.config_path).name}")

            # Execute
            start_time = time.time()
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=None  # No timeout for long videos
            )
            elapsed = time.time() - start_time

            # Log result
            if result.returncode == 0:
                self.logger.info(
                    f"[{job.camera_id}] SUCCESS: {job.video_name} | "
                    f"Duration: {elapsed:.1f}s"
                )
                self.jobs_completed += 1
                self.total_processing_time += elapsed
                return True
            else:
                self.logger.error(
                    f"[{job.camera_id}] FAILED: {job.video_name} | "
                    f"Duration: {elapsed:.1f}s"
                )
                self.logger.error(f"[{job.camera_id}] Error output: {result.stderr}")
                self.jobs_failed += 1
                return False

        except Exception as e:
            self.logger.error(f"[{job.camera_id}] EXCEPTION: {job.video_name} | {e}")
            self.jobs_failed += 1
            return False

        finally:
            # Unregister worker
            with self.worker_lock:
                self.active_workers.pop(worker_id, None)

    def worker_thread(self):
        """Worker thread that processes jobs from queue"""
        while not self.shutdown:
            try:
                # Wait for a job slot to be available
                while True:
                    with self.worker_lock:
                        active_count = len(self.active_workers)

                    if active_count < self.current_parallel:
                        break

                    time.sleep(1)  # Check every second

                # Get next job (with timeout to check shutdown flag)
                try:
                    job = self.job_queue.get(timeout=1)
                except queue.Empty:
                    continue

                # Process job
                self.process_job(job)
                self.job_queue.task_done()

            except Exception as e:
                self.logger.error(f"Worker thread error: {e}")

    def start_workers(self, num_workers: int):
        """Start worker threads"""
        self.start_time = time.time()
        self.logger.info(f"Starting {num_workers} worker threads")

        threads = []
        for i in range(num_workers):
            t = threading.Thread(target=self.worker_thread, name=f"Worker-{i+1}")
            t.daemon = True
            t.start()
            threads.append(t)

        return threads

    def wait_for_completion(self):
        """Wait for all jobs to complete"""
        self.job_queue.join()
        self.shutdown = True

    def get_statistics(self) -> Dict:
        """Get final processing statistics"""
        total_time = time.time() - self.start_time if self.start_time else 0
        total_jobs = self.jobs_completed + self.jobs_failed

        return {
            'total_jobs': total_jobs,
            'jobs_completed': self.jobs_completed,
            'jobs_failed': self.jobs_failed,
            'total_time': total_time,
            'avg_time_per_job': self.total_processing_time / self.jobs_completed if self.jobs_completed > 0 else 0,
            'success_rate': (self.jobs_completed / total_jobs * 100) if total_jobs > 0 else 0
        }


# ============================================================================
# GPU MONITORING THREAD
# ============================================================================

def gpu_monitoring_thread(gpu_monitor: GPUMonitor, processing_queue: ProcessingQueue,
                         logger: logging.Logger, interval: int = GPU_CHECK_INTERVAL):
    """
    Background thread that monitors GPU health and adjusts parallelism
    """
    logger.info(f"GPU monitoring thread started (interval: {interval}s)")

    while not processing_queue.shutdown:
        try:
            # Get GPU metrics
            metrics = gpu_monitor.get_metrics()

            if metrics:
                # Log metrics
                gpu_monitor.log_metrics(metrics)

                # Adjust parallelism based on GPU health
                processing_queue.adjust_parallelism()

                # Log queue status
                status = processing_queue.get_queue_status()
                logger.info(
                    f"Queue: {status['jobs_running']} running | "
                    f"{status['jobs_waiting']} waiting | "
                    f"{status['jobs_completed']} completed | "
                    f"{status['jobs_failed']} failed | "
                    f"Max parallel: {status['max_parallel']}"
                )

            # Sleep until next check
            time.sleep(interval)

        except Exception as e:
            logger.error(f"GPU monitoring error: {e}")
            time.sleep(interval)


# ============================================================================
# MAIN PROCESSING ORCHESTRATOR
# ============================================================================

def process_with_queue(videos_by_camera: Dict[str, List[str]], logger: logging.Logger,
                      duration: Optional[int] = None, config_path: Optional[str] = None,
                      max_parallel: int = DEFAULT_MAX_PARALLEL,
                      gpu_temp_limit: int = GPU_TEMP_CRITICAL):
    """
    Process videos using GPU-aware job queue
    """
    if not videos_by_camera:
        logger.error("No videos to process")
        return

    # Initialize GPU monitor
    gpu_monitor = GPUMonitor(logger)

    # Initialize processing queue
    processing_queue = ProcessingQueue(logger, gpu_monitor, max_parallel)

    # Update GPU temp limit if specified
    global GPU_TEMP_CRITICAL
    GPU_TEMP_CRITICAL = gpu_temp_limit

    # Create jobs (priority = timestamp, older videos first)
    total_jobs = 0
    for camera_id, video_paths in videos_by_camera.items():
        for video_path in video_paths:
            timestamp = extract_timestamp(os.path.basename(video_path))
            priority = int(timestamp.replace('_', ''))  # Convert to int for priority

            job = ProcessingJob(camera_id, video_path, priority, duration, config_path)
            processing_queue.add_job(job)
            total_jobs += 1

    logger.info("="*80)
    logger.info("MULTI-CAMERA VIDEO PROCESSING WITH GPU QUEUE MANAGEMENT")
    logger.info("="*80)
    logger.info(f"Cameras: {len(videos_by_camera)}")
    logger.info(f"Total jobs: {total_jobs}")
    logger.info(f"Max parallel jobs: {max_parallel}")
    logger.info(f"GPU temp limit: {gpu_temp_limit}°C")
    if duration:
        logger.info(f"Processing duration: {duration}s per video")
    logger.info("="*80)

    # Show job details
    for camera_id, video_paths in videos_by_camera.items():
        logger.info(f"{camera_id}: {len(video_paths)} video(s)")
        for video_path in video_paths:
            logger.debug(f"   - {os.path.basename(video_path)}")

    logger.info("="*80)
    logger.info("Starting processing...")
    logger.info("="*80)

    # Start GPU monitoring thread
    gpu_thread = threading.Thread(
        target=gpu_monitoring_thread,
        args=(gpu_monitor, processing_queue, logger),
        name="GPU-Monitor"
    )
    gpu_thread.daemon = True
    gpu_thread.start()

    # Start worker threads (pool of workers that pull from queue)
    worker_threads = processing_queue.start_workers(max_parallel)

    # Wait for all jobs to complete
    processing_queue.wait_for_completion()

    # Get statistics
    stats = processing_queue.get_statistics()

    logger.info("="*80)
    logger.info("PROCESSING COMPLETE")
    logger.info("="*80)
    logger.info(f"Total jobs: {stats['total_jobs']}")
    logger.info(f"Completed: {stats['jobs_completed']}")
    logger.info(f"Failed: {stats['jobs_failed']}")
    logger.info(f"Success rate: {stats['success_rate']:.1f}%")
    logger.info(f"Total time: {stats['total_time']:.1f}s ({stats['total_time']/60:.1f} minutes)")
    logger.info(f"Avg time per job: {stats['avg_time_per_job']:.1f}s")
    logger.info("="*80)

    # Log final GPU metrics
    final_metrics = gpu_monitor.get_metrics()
    if final_metrics:
        logger.info("Final GPU state:")
        gpu_monitor.log_metrics(final_metrics)


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Orchestrate GPU-aware parallel processing of multi-camera videos",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process all videos with GPU queue management (default)
  python3 process_videos_orchestrator.py

  # Process only specific cameras
  python3 process_videos_orchestrator.py --cameras camera_35 camera_22

  # Process first 60 seconds of each video (for testing)
  python3 process_videos_orchestrator.py --duration 60

  # Custom max parallel jobs and GPU temp limit
  python3 process_videos_orchestrator.py --max-parallel 2 --gpu-temp-limit 75

  # Enable debug logging
  python3 process_videos_orchestrator.py --log-level DEBUG

Workflow:
1. Script scans videos/ folder for all .mp4 files
2. Groups videos by camera_id (extracted from filename)
3. Creates priority queue (older videos first)
4. Starts GPU monitoring thread (checks every 30s)
5. Starts worker threads that pull jobs from queue
6. Dynamically adjusts parallelism based on GPU health:
   - Healthy GPU (<70°C): 4 parallel jobs
   - Warm GPU (70-80°C): 2 parallel jobs
   - Hot GPU (>80°C): 1 job at a time
7. Logs all events to logs/processing_YYYYMMDD_HHMMSS.log
8. Generates statistics report at completion

Video Naming Convention:
  camera_{id}_{date}_{time}.mp4
  Example: camera_35_20251114_183000.mp4

Log Files:
  - logs/processing_YYYYMMDD_HHMMSS.log (main log)
  - logs/errors_YYYYMMDD.log (errors only)
  - Bi-weekly rotation (keeps last 14 days)
        """
    )

    parser.add_argument("--videos-dir", default=str(VIDEOS_DIR),
                       help=f"Videos directory (default: {VIDEOS_DIR})")
    parser.add_argument("--cameras", nargs='+',
                       help="Process only specific camera IDs (e.g., camera_35 camera_22)")
    parser.add_argument("--duration", type=int,
                       help="Process only first N seconds of each video (for testing)")
    parser.add_argument("--config", default=str(SCRIPT_DIR.parent / "config" / "table_region_config.json"),
                       help="Path to ROI config file")
    parser.add_argument("--list", action="store_true",
                       help="List all discovered videos and exit")
    parser.add_argument("--max-parallel", type=int, default=DEFAULT_MAX_PARALLEL,
                       help=f"Maximum parallel jobs on healthy GPU (default: {DEFAULT_MAX_PARALLEL})")
    parser.add_argument("--gpu-temp-limit", type=int, default=GPU_TEMP_CRITICAL,
                       help=f"GPU temperature limit for minimal parallelism (default: {GPU_TEMP_CRITICAL}°C)")
    parser.add_argument("--log-level", default="INFO",
                       choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                       help="Logging level (default: INFO)")

    args = parser.parse_args()

    # Setup logging
    logger, log_file = setup_logging(args.log_level)

    logger.info(f"Python version: {sys.version}")
    logger.info(f"Platform: {platform.system()} {platform.release()}")
    logger.info(f"Script directory: {SCRIPT_DIR}")

    videos_dir = Path(args.videos_dir)
    config_path = args.config

    # Discover videos
    logger.info(f"Scanning for videos in: {videos_dir}")
    videos_by_camera = discover_videos(videos_dir, args.cameras)

    if not videos_by_camera:
        logger.error("No videos found")
        return

    # List mode
    if args.list:
        print(f"\n📹 Discovered Videos:")
        for camera_id, video_paths in videos_by_camera.items():
            print(f"\n{camera_id}: {len(video_paths)} video(s)")
            for video_path in video_paths:
                video_name = os.path.basename(video_path)
                timestamp = extract_timestamp(video_name)
                print(f"   {timestamp} - {video_name}")
        print()
        return

    # Process with queue
    start_time = datetime.now()
    logger.info(f"Session start: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

    process_with_queue(
        videos_by_camera,
        logger,
        args.duration,
        config_path,
        args.max_parallel,
        args.gpu_temp_limit
    )

    end_time = datetime.now()
    total_duration = (end_time - start_time).total_seconds()

    logger.info(f"Session end: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Total session time: {total_duration:.1f}s ({total_duration/60:.1f} minutes)")
    logger.info(f"Log file: {log_file}")


if __name__ == "__main__":
    main()
