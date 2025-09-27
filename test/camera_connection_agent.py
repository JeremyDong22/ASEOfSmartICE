#!/usr/bin/env python3
# Version: 1.0
# Camera Connection Testing Agent for Multiple IP Cameras
# Tests RTSP sub-stream connectivity and validates OpenCV decoding stability

import cv2
import time
import threading
from datetime import datetime
import json

# Target camera IP addresses (202.168.40.xx)
CAMERA_IPS = ["27", "28", "36", "24", "26", "29", "34", "35", "22"]
IP_PREFIX = "202.168.40."
PASSWORDS = ["123456", "a12345678"]
USERNAME = "admin"

# Test configuration
RTSP_PORT = 554
SUB_STREAM_PATH = "/Streaming/Channels/102"
TEST_TIMEOUT = 10  # seconds per camera test
STABILITY_TEST_DURATION = 30  # seconds to test stream stability

class CameraConnectionAgent:
    def __init__(self):
        self.results = {}
        self.successful_connections = []
    
    def test_single_camera(self, ip_suffix, password):
        """Test connection to a single camera with given password"""
        camera_ip = f"{IP_PREFIX}{ip_suffix}"
        rtsp_url = f"rtsp://{USERNAME}:{password}@{camera_ip}:{RTSP_PORT}{SUB_STREAM_PATH}"
        
        print(f"🔍 Testing {camera_ip} with password: {password}")
        
        try:
            # Create capture with manual timeout handling
            start_time = time.time()
            cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            # Manual timeout for connection
            connection_timeout = 5  # seconds
            while not cap.isOpened() and (time.time() - start_time) < connection_timeout:
                time.sleep(0.1)
            
            if not cap.isOpened():
                cap.release()
                return False, "Connection timeout - camera not reachable or wrong credentials"
            
            # Test frame capture with timeout
            frame_timeout = 3  # seconds
            frame_start = time.time()
            ret = False
            frame = None
            
            while (time.time() - frame_start) < frame_timeout:
                ret, frame = cap.read()
                if ret and frame is not None:
                    break
                time.sleep(0.1)
            
            if not ret or frame is None:
                cap.release()
                return False, "No frame received within timeout"
            
            # Get stream properties
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS) or 25  # default if unable to get FPS
            
            # Test stream stability (capture multiple frames)
            stable_frames = 0
            stability_test_duration = 3  # reduced to 3 seconds for faster testing
            test_start = time.time()
            
            while time.time() - test_start < stability_test_duration:
                ret, frame = cap.read()
                if ret and frame is not None:
                    stable_frames += 1
                time.sleep(0.1)
            
            cap.release()
            
            expected_frames = stability_test_duration * 10  # at 0.1 second intervals
            stability_ratio = stable_frames / expected_frames
            
            stream_info = {
                "rtsp_url": rtsp_url,
                "resolution": f"{width}x{height}",
                "fps": fps,
                "stable_frames": stable_frames,
                "stability_ratio": f"{stability_ratio:.2f}",
                "status": "stable" if stability_ratio > 0.8 else "unstable"
            }
            
            return True, stream_info
            
        except Exception as e:
            return False, f"Exception: {str(e)}"
    
    def test_all_cameras(self):
        """Test all cameras with all password combinations"""
        print("🎥 Starting camera connection testing agent...")
        print(f"📋 Testing {len(CAMERA_IPS)} cameras with {len(PASSWORDS)} password combinations")
        print("=" * 60)
        
        for ip_suffix in CAMERA_IPS:
            camera_ip = f"{IP_PREFIX}{ip_suffix}"
            print(f"\n🔍 Testing camera: {camera_ip}")
            
            connection_found = False
            for password in PASSWORDS:
                success, result = self.test_single_camera(ip_suffix, password)
                
                if success:
                    print(f"✅ Connection successful with password: {password}")
                    print(f"   📊 Resolution: {result['resolution']}")
                    print(f"   🎯 FPS: {result['fps']}")
                    print(f"   📈 Stability: {result['status']} ({result['stable_frames']} frames)")
                    
                    self.results[camera_ip] = result
                    self.successful_connections.append({
                        "ip": camera_ip,
                        "username": USERNAME,
                        "password": password,
                        "rtsp_url": result["rtsp_url"],
                        "resolution": result["resolution"],
                        "fps": result["fps"],
                        "status": result["status"]
                    })
                    connection_found = True
                    break
                else:
                    print(f"❌ Failed with password {password}: {result}")
            
            if not connection_found:
                print(f"❌ No successful connection found for {camera_ip}")
                self.results[camera_ip] = {"status": "failed", "error": "No valid credentials"}
        
        return self.generate_summary()
    
    def generate_summary(self):
        """Generate a summary report of all tested cameras"""
        print("\n" + "=" * 60)
        print("📊 CAMERA CONNECTION SUMMARY")
        print("=" * 60)
        
        successful = len(self.successful_connections)
        total = len(CAMERA_IPS)
        
        print(f"✅ Successful connections: {successful}/{total}")
        print(f"❌ Failed connections: {total - successful}/{total}")
        
        if self.successful_connections:
            print("\n🔗 WORKING CAMERA CREDENTIALS:")
            for conn in self.successful_connections:
                print(f"   📹 {conn['ip']}: {conn['username']}/{conn['password']}")
                print(f"      🔗 RTSP: {conn['rtsp_url']}")
                print(f"      📊 {conn['resolution']} @ {conn['fps']} FPS - {conn['status']}")
                print()
        
        # Save results to JSON for other agents
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = f"camera_connection_results_{timestamp}.json"
        
        with open(results_file, 'w') as f:
            json.dump({
                "timestamp": timestamp,
                "successful_connections": self.successful_connections,
                "all_results": self.results,
                "summary": {
                    "total_cameras": total,
                    "successful": successful,
                    "failed": total - successful
                }
            }, f, indent=2)
        
        print(f"💾 Results saved to: {results_file}")
        return self.successful_connections

def main():
    agent = CameraConnectionAgent()
    results = agent.test_all_cameras()
    
    if results:
        print(f"\n🎉 Testing complete! Found {len(results)} working cameras.")
        return results
    else:
        print("\n😞 No working cameras found. Check network connectivity and credentials.")
        return []

if __name__ == "__main__":
    main()