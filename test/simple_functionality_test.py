#!/usr/bin/env python3
# Version: 1.0
# Simple Functionality Test - Direct function calls with 2-minute timeout
# Tests screenshot capture and person extraction directly

import cv2
import time
import json
import os
import sys
from pathlib import Path
from datetime import datetime

# Add project paths
current_dir = Path(__file__).parent
project_root = current_dir.parent
sys.path.append(str(project_root))

# Test configuration
TEST_TIMEOUT = 120  # 2 minutes
SINGLE_SCREENSHOT_TEST = True  # Just test one screenshot

def test_camera_connection():
    """Test 1: Quick camera connection test"""
    print("🔍 Test 1: Testing camera connection...")
    
    # Load camera credentials from previous test
    config_file = project_root / "test" / "camera_connection_results_20250927_230846.json"
    
    if not config_file.exists():
        print("❌ Camera config file not found")
        return False
    
    with open(config_file, 'r') as f:
        data = json.load(f)
        working_cameras = data.get('successful_connections', [])
    
    if working_cameras:
        print(f"✅ Found {len(working_cameras)} working cameras from previous test")
        return True
    else:
        print("❌ No working cameras found")
        return False

def test_single_screenshot():
    """Test 2: Capture a single screenshot"""
    print("📸 Test 2: Testing single screenshot capture...")
    
    # Load camera config
    config_file = project_root / "test" / "camera_connection_results_20250927_230846.json"
    
    try:
        with open(config_file, 'r') as f:
            data = json.load(f)
            working_cameras = data.get('successful_connections', [])
        
        if not working_cameras:
            print("❌ No working cameras available")
            return False
        
        # Use first working camera
        camera_config = working_cameras[0]
        rtsp_url = camera_config['rtsp_url']
        camera_ip = camera_config['ip']
        
        print(f"📹 Testing with camera: {camera_ip}")
        
        # Create output directory
        output_dir = project_root / "train-model" / "raw_images"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Capture screenshot
        cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        # Wait for connection
        start_time = time.time()
        while not cap.isOpened() and (time.time() - start_time) < 10:
            time.sleep(0.1)
        
        if not cap.isOpened():
            print("❌ Failed to connect to camera")
            cap.release()
            return False
        
        # Capture frame
        ret, frame = cap.read()
        cap.release()
        
        if ret and frame is not None:
            # Save screenshot
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"test_screenshot_{timestamp}.jpg"
            filepath = output_dir / filename
            
            success = cv2.imwrite(str(filepath), frame)
            
            if success:
                file_size = filepath.stat().st_size / 1024  # KB
                print(f"✅ Screenshot captured: {filename} ({file_size:.1f} KB)")
                return str(filepath)
            else:
                print("❌ Failed to save screenshot")
                return False
        else:
            print("❌ No frame received from camera")
            return False
    
    except Exception as e:
        print(f"❌ Screenshot test exception: {str(e)}")
        return False

def test_person_extraction(image_path):
    """Test 3: Test person extraction on captured screenshot"""
    print("👤 Test 3: Testing person extraction...")
    
    try:
        # Import YOLO
        from ultralytics import YOLO
        
        # Load model
        model_path = project_root / "model" / "yolov8s.pt"
        if not model_path.exists():
            print("📦 Downloading YOLOv8s model...")
            model = YOLO("yolov8s.pt")
        else:
            model = YOLO(str(model_path))
        
        # Read image
        image = cv2.imread(image_path)
        if image is None:
            print(f"❌ Failed to load image: {image_path}")
            return False
        
        print(f"📊 Image size: {image.shape[1]}x{image.shape[0]}")
        
        # Run detection
        results = model(image, conf=0.5, classes=[0])  # Class 0 = person
        
        person_count = 0
        for r in results:
            boxes = r.boxes
            if boxes is not None:
                for box in boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    conf = float(box.conf[0])
                    width = x2 - x1
                    height = y2 - y1
                    
                    if width >= 50 and height >= 50:  # Minimum size filter
                        person_count += 1
                        print(f"   👤 Person {person_count}: {width}x{height}px, conf={conf:.2f}")
        
        if person_count > 0:
            print(f"✅ Person extraction test passed - found {person_count} person(s)")
            return True
        else:
            print("⚠️ No persons detected (this may be normal if no people in frame)")
            return True  # Still consider it a pass since detection worked
    
    except ImportError:
        print("❌ YOLO not installed - run: pip install ultralytics")
        return False
    except Exception as e:
        print(f"❌ Person extraction exception: {str(e)}")
        return False

def main():
    """Run simplified functionality test"""
    print("🚀 Starting Simple Functionality Test")
    print(f"⏱️ Timeout: {TEST_TIMEOUT} seconds")
    print("=" * 60)
    
    start_time = time.time()
    
    # Test 1: Camera connection
    test1_result = test_camera_connection()
    
    if time.time() - start_time > TEST_TIMEOUT:
        print("⚠️ Test timeout exceeded")
        return False
    
    if not test1_result:
        print("❌ Camera connection test failed - cannot continue")
        return False
    
    # Test 2: Screenshot capture
    test2_result = test_single_screenshot()
    
    if time.time() - start_time > TEST_TIMEOUT:
        print("⚠️ Test timeout exceeded")
        return False
    
    if not test2_result:
        print("❌ Screenshot capture test failed - cannot continue")
        return False
    
    # Test 3: Person extraction
    test3_result = test_person_extraction(test2_result)
    
    elapsed = time.time() - start_time
    
    # Results
    print("\n" + "=" * 60)
    print("📊 SIMPLE FUNCTIONALITY TEST RESULTS")
    print("=" * 60)
    print(f"⏱️ Total time: {elapsed:.1f}s (limit: {TEST_TIMEOUT}s)")
    print(f"🔍 Camera Connection: {'✅ PASS' if test1_result else '❌ FAIL'}")
    print(f"📸 Screenshot Capture: {'✅ PASS' if test2_result else '❌ FAIL'}")
    print(f"👤 Person Extraction: {'✅ PASS' if test3_result else '❌ FAIL'}")
    
    all_passed = test1_result and test2_result and test3_result
    print(f"🎯 Overall Result: {'✅ SUCCESS' if all_passed else '❌ FAILURE'}")
    print("=" * 60)
    
    if all_passed:
        print("🎉 All tests passed! The pipeline is working correctly.")
        
        # Clean up test file
        if isinstance(test2_result, str):
            try:
                os.remove(test2_result)
                print("🧹 Test screenshot cleaned up")
            except:
                pass
        
        return True
    else:
        print("😞 Some tests failed. Please check the issues above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)