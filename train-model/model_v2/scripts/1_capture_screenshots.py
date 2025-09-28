#!/usr/bin/env python3
# Version: 2.0
# Multi-camera screenshot capture agent for training data collection
# Captures screenshots every 5 minutes from multiple verified cameras
# Replaces video recording with efficient image-based training data collection

import cv2
import time
import threading
import json
import os
from datetime import datetime
from pathlib import Path

# Configuration
OUTPUT_DIR = "../raw_images"
CAPTURE_INTERVAL = 300  # 5 minutes in seconds
CONNECTION_TIMEOUT = 5  # seconds
RETRY_ATTEMPTS = 3
CAMERA_CONFIG_FILE = "../../test/camera_connection_results_20250927_230846.json"

# Working camera configurations (loaded from test results)
WORKING_CAMERAS = []

class ScreenshotCaptureAgent:
    def __init__(self):
        self.active_cameras = {}
        self.capture_count = 0
        self.running = False
        self.load_camera_config()
        self.setup_output_directory()
    
    def load_camera_config(self):
        """Load verified camera configurations from connection test results"""
        global WORKING_CAMERAS
        
        try:
            config_path = Path(__file__).parent / CAMERA_CONFIG_FILE
            with open(config_path, 'r') as f:
                data = json.load(f)
                WORKING_CAMERAS = data.get('successful_connections', [])
            
            print(f"📋 Loaded {len(WORKING_CAMERAS)} verified camera configurations")
            
            # Display camera summary
            for i, camera in enumerate(WORKING_CAMERAS, 1):
                print(f"   {i}. {camera['ip']} ({camera['resolution']}) - {camera['status']}")
        
        except FileNotFoundError:
            print("⚠️ Camera config file not found. Using fallback configuration.")
            # Fallback to a working camera from the previous configuration
            WORKING_CAMERAS = [{
                "ip": "202.168.40.35",
                "username": "admin", 
                "password": "123456",
                "rtsp_url": "rtsp://admin:123456@202.168.40.35:554/Streaming/Channels/102",
                "resolution": "1920x1080",
                "status": "stable"
            }]
    
    def setup_output_directory(self):
        """Create raw_images directory structure"""
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        print(f"📁 Output directory: {OUTPUT_DIR}")
    
    def test_camera_connection(self, camera_config):
        """Test if camera is accessible before starting capture"""
        rtsp_url = camera_config['rtsp_url']
        
        try:
            cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            # Test connection with timeout
            start_time = time.time()
            while not cap.isOpened() and (time.time() - start_time) < CONNECTION_TIMEOUT:
                time.sleep(0.1)
            
            if not cap.isOpened():
                cap.release()
                return False, "Connection timeout"
            
            # Test frame capture
            ret, frame = cap.read()
            cap.release()
            
            if ret and frame is not None:
                return True, "Connected successfully"
            else:
                return False, "No frame received"
        
        except Exception as e:
            return False, f"Exception: {str(e)}"
    
    def capture_screenshot_from_camera(self, camera_config):
        """Capture a single screenshot from specified camera"""
        camera_ip = camera_config['ip']
        rtsp_url = camera_config['rtsp_url']
        
        for attempt in range(RETRY_ATTEMPTS):
            try:
                cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                
                # Connection timeout
                start_time = time.time()
                while not cap.isOpened() and (time.time() - start_time) < CONNECTION_TIMEOUT:
                    time.sleep(0.1)
                
                if not cap.isOpened():
                    cap.release()
                    print(f"❌ Camera {camera_ip} - Connection failed (attempt {attempt + 1})")
                    continue
                
                # Capture frame
                ret, frame = cap.read()
                cap.release()
                
                if ret and frame is not None:
                    # Generate filename with timestamp and camera info
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    camera_suffix = camera_ip.split('.')[-1]  # Last octet of IP
                    resolution = camera_config['resolution'].replace('x', '_')
                    filename = f"camera_{camera_suffix}_{resolution}_{timestamp}.jpg"
                    filepath = os.path.join(OUTPUT_DIR, filename)
                    
                    # Save image
                    success = cv2.imwrite(filepath, frame)
                    
                    if success:
                        file_size = os.path.getsize(filepath) / 1024  # KB
                        print(f"📸 {camera_ip}: {filename} ({file_size:.1f} KB)")
                        return True, filepath
                    else:
                        print(f"❌ {camera_ip}: Failed to save image")
                        return False, "Save failed"
                else:
                    print(f"⚠️ Camera {camera_ip} - No frame received (attempt {attempt + 1})")
            
            except Exception as e:
                print(f"❌ Camera {camera_ip} - Exception: {str(e)} (attempt {attempt + 1})")
                
            time.sleep(1)  # Wait before retry
        
        return False, "All attempts failed"
    
    def capture_all_cameras(self):
        """Capture screenshots from all working cameras"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n🎯 Capture round {self.capture_count + 1} at {timestamp}")
        print("-" * 50)
        
        successful_captures = 0
        failed_captures = 0
        
        # Use threading for parallel capture
        threads = []
        results = {}
        
        def capture_worker(camera_config):
            camera_ip = camera_config['ip']
            success, result = self.capture_screenshot_from_camera(camera_config)
            results[camera_ip] = (success, result)
        
        # Start capture threads
        for camera_config in WORKING_CAMERAS:
            thread = threading.Thread(target=capture_worker, args=(camera_config,))
            thread.start()
            threads.append(thread)
        
        # Wait for all captures to complete
        for thread in threads:
            thread.join()
        
        # Process results
        for camera_ip, (success, result) in results.items():
            if success:
                successful_captures += 1
            else:
                failed_captures += 1
                print(f"❌ {camera_ip}: {result}")
        
        self.capture_count += 1
        
        print(f"📊 Round {self.capture_count} Summary: ✅ {successful_captures} success, ❌ {failed_captures} failed")
        
        return successful_captures, failed_captures
    
    def run_continuous_capture(self, duration_hours=None):
        """Run continuous screenshot capture every 5 minutes"""
        global WORKING_CAMERAS

        print("🎥 Starting multi-camera screenshot capture agent...")
        print(f"📋 Monitoring {len(WORKING_CAMERAS)} cameras")
        print(f"⏱️ Capture interval: {CAPTURE_INTERVAL} seconds ({CAPTURE_INTERVAL//60} minutes)")
        print(f"📁 Output directory: {OUTPUT_DIR}")

        if duration_hours:
            print(f"⏰ Will run for {duration_hours} hours")
            end_time = time.time() + (duration_hours * 3600)
        else:
            print("⏰ Running indefinitely (Ctrl+C to stop)")
            end_time = None

        print("=" * 60)

        # Test all cameras before starting
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
        print("=" * 60)

        # Update working cameras list
        WORKING_CAMERAS = working_cameras
        
        self.running = True
        
        try:
            while self.running:
                # Capture from all cameras
                successful, failed = self.capture_all_cameras()
                
                # Check if should continue
                if end_time and time.time() >= end_time:
                    print(f"\n⏰ Duration limit reached. Stopping.")
                    break
                
                # Wait for next capture
                print(f"⏳ Next capture in {CAPTURE_INTERVAL//60} minutes...")
                
                # Sleep with periodic checks for interruption
                sleep_time = 0
                while sleep_time < CAPTURE_INTERVAL and self.running:
                    time.sleep(10)  # Check every 10 seconds
                    sleep_time += 10
                    
                    if end_time and time.time() >= end_time:
                        break
        
        except KeyboardInterrupt:
            print("\n⚠️ Capture stopped by user")
        
        finally:
            self.running = False
            print(f"\n✅ Capture session complete!")
            print(f"📊 Total capture rounds: {self.capture_count}")
            print(f"📁 Images saved to: {OUTPUT_DIR}")

def main():
    """Main function to run screenshot capture agent"""
    agent = ScreenshotCaptureAgent()
    
    # Run for a reasonable duration for testing
    # Change to None for indefinite running or specify hours
    agent.run_continuous_capture(duration_hours=2)  # Run for 2 hours as default

if __name__ == "__main__":
    main()