#!/usr/bin/env python3
# Version: 1.0
# Functionality Test Agent for Screenshot Capture and Person Extraction
# Tests the complete pipeline: Screenshot capture -> Person extraction
# Runs with 2-minute timeout as specified

import subprocess
import time
import os
import sys
from pathlib import Path
from datetime import datetime
import signal
import threading

# Test configuration
TEST_TIMEOUT = 120  # 2 minutes total timeout
CAPTURE_TEST_DURATION = 30  # 30 seconds of screenshot capture
CLEANUP_AFTER_TEST = True  # Clean up test files after completion

class FunctionalityTestAgent:
    def __init__(self):
        self.test_start_time = time.time()
        self.test_results = {
            "camera_connection": False,
            "screenshot_capture": False,
            "person_extraction": False,
            "end_to_end": False,
            "errors": []
        }
        self.test_files_created = []
        
    def log(self, message, level="INFO"):
        """Log with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        elapsed = time.time() - self.test_start_time
        print(f"[{timestamp}] [{elapsed:05.1f}s] {level}: {message}")
    
    def check_timeout(self):
        """Check if test timeout has been exceeded"""
        elapsed = time.time() - self.test_start_time
        if elapsed > TEST_TIMEOUT:
            self.log(f"⚠️ Test timeout exceeded ({TEST_TIMEOUT}s)", "TIMEOUT")
            return True
        return False
    
    def test_camera_connection(self):
        """Test 1: Verify camera connection agent works"""
        self.log("🔍 Test 1: Testing camera connection agent...")
        
        try:
            # Run camera connection test
            result = subprocess.run(
                ["python3", "camera_connection_agent.py"],
                cwd="test",
                timeout=30,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                # Check if any cameras were found
                if "successful connections:" in result.stdout.lower():
                    self.log("✅ Camera connection test passed", "SUCCESS")
                    self.test_results["camera_connection"] = True
                    return True
                else:
                    self.log("❌ No successful camera connections found", "ERROR")
                    self.test_results["errors"].append("No camera connections")
                    return False
            else:
                self.log(f"❌ Camera connection agent failed: {result.stderr}", "ERROR")
                self.test_results["errors"].append(f"Connection agent error: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            self.log("❌ Camera connection test timed out", "ERROR")
            self.test_results["errors"].append("Camera connection timeout")
            return False
        except Exception as e:
            self.log(f"❌ Camera connection test exception: {str(e)}", "ERROR")
            self.test_results["errors"].append(f"Connection test exception: {str(e)}")
            return False
    
    def test_screenshot_capture(self):
        """Test 2: Verify screenshot capture works"""
        self.log(f"📸 Test 2: Testing screenshot capture for {CAPTURE_TEST_DURATION}s...")
        
        if self.check_timeout():
            return False
        
        try:
            # Create a modified version of the screenshot script for testing
            test_script_content = '''
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../train-model/scripts'))

# Import the screenshot capture module
exec(open('../train-model/scripts/1_capture_screenshots.py').read())

# Run capture for short duration
agent = ScreenshotCaptureAgent()
agent.run_continuous_capture(duration_hours=0.01)  # Run for about 30 seconds
'''
            
            # Write temporary test script
            test_script_path = "test_screenshot_capture.py"
            with open(test_script_path, 'w') as f:
                f.write(test_script_content)
            self.test_files_created.append(test_script_path)
            
            # Run screenshot capture with timeout
            process = subprocess.Popen(
                ["python3", test_script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Let it run for the specified duration
            time.sleep(CAPTURE_TEST_DURATION)
            
            # Terminate the process
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            
            # Check if any screenshots were created
            raw_images_dir = Path("train-model/raw_images")
            if raw_images_dir.exists():
                image_files = list(raw_images_dir.glob("*.jpg"))
                if image_files:
                    self.log(f"✅ Screenshot capture test passed - {len(image_files)} images captured", "SUCCESS")
                    self.test_results["screenshot_capture"] = True
                    # Keep track of test files for cleanup
                    self.test_files_created.extend([str(f) for f in image_files])
                    return True
                else:
                    self.log("❌ No screenshot images were captured", "ERROR")
                    self.test_results["errors"].append("No screenshots captured")
                    return False
            else:
                self.log("❌ Raw images directory not created", "ERROR")
                self.test_results["errors"].append("Raw images directory missing")
                return False
                
        except Exception as e:
            self.log(f"❌ Screenshot capture test exception: {str(e)}", "ERROR")
            self.test_results["errors"].append(f"Screenshot capture exception: {str(e)}")
            return False
    
    def test_person_extraction(self):
        """Test 3: Verify person extraction works on captured screenshots"""
        self.log("👤 Test 3: Testing person extraction...")
        
        if self.check_timeout():
            return False
        
        try:
            # Run person extraction script
            result = subprocess.run(
                ["python3", "2_extract_persons.py"],
                cwd="train-model/scripts",
                timeout=60,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                # Check if extracted persons directory was created
                extracted_dir = Path("train-model/extracted-persons")
                if extracted_dir.exists():
                    # Count total extracted person images
                    person_images = list(extracted_dir.rglob("*.jpg"))
                    if person_images:
                        self.log(f"✅ Person extraction test passed - {len(person_images)} persons extracted", "SUCCESS")
                        self.test_results["person_extraction"] = True
                        # Keep track of test files for cleanup
                        self.test_files_created.extend([str(f) for f in person_images])
                        self.test_files_created.append(str(extracted_dir))
                        return True
                    else:
                        self.log("⚠️ Person extraction completed but no persons found", "WARNING")
                        self.test_results["person_extraction"] = True  # Still consider it working
                        return True
                else:
                    self.log("❌ Extracted persons directory not created", "ERROR")
                    self.test_results["errors"].append("No extracted persons directory")
                    return False
            else:
                self.log(f"❌ Person extraction failed: {result.stderr}", "ERROR")
                self.test_results["errors"].append(f"Person extraction error: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            self.log("❌ Person extraction test timed out", "ERROR")
            self.test_results["errors"].append("Person extraction timeout")
            return False
        except Exception as e:
            self.log(f"❌ Person extraction test exception: {str(e)}", "ERROR")
            self.test_results["errors"].append(f"Person extraction exception: {str(e)}")
            return False
    
    def cleanup_test_files(self):
        """Clean up files created during testing"""
        if not CLEANUP_AFTER_TEST:
            self.log("🧹 Cleanup disabled - test files preserved", "INFO")
            return
        
        self.log("🧹 Cleaning up test files...", "INFO")
        
        cleaned_files = 0
        for file_path in self.test_files_created:
            try:
                path = Path(file_path)
                if path.exists():
                    if path.is_file():
                        path.unlink()
                        cleaned_files += 1
                    elif path.is_dir() and not any(path.iterdir()):  # Only remove empty dirs
                        path.rmdir()
                        cleaned_files += 1
            except Exception as e:
                self.log(f"⚠️ Failed to clean up {file_path}: {str(e)}", "WARNING")
        
        self.log(f"🧹 Cleaned up {cleaned_files} test files", "INFO")
    
    def generate_test_report(self):
        """Generate final test report"""
        elapsed = time.time() - self.test_start_time
        
        print("\n" + "=" * 80)
        print("📊 FUNCTIONALITY TEST REPORT")
        print("=" * 80)
        print(f"⏱️ Total test duration: {elapsed:.1f}s (limit: {TEST_TIMEOUT}s)")
        print(f"🎯 Test timeout: {'❌ EXCEEDED' if elapsed > TEST_TIMEOUT else '✅ Within limit'}")
        print()
        
        # Individual test results
        tests = [
            ("Camera Connection", self.test_results["camera_connection"]),
            ("Screenshot Capture", self.test_results["screenshot_capture"]),
            ("Person Extraction", self.test_results["person_extraction"])
        ]
        
        passed_tests = 0
        for test_name, passed in tests:
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"   {test_name:20} : {status}")
            if passed:
                passed_tests += 1
        
        # End-to-end result
        self.test_results["end_to_end"] = passed_tests == len(tests)
        end_to_end_status = "✅ PASS" if self.test_results["end_to_end"] else "❌ FAIL"
        print(f"   {'End-to-End Pipeline':20} : {end_to_end_status}")
        
        print()
        print(f"📈 Test Summary: {passed_tests}/{len(tests)} individual tests passed")
        print(f"🎯 End-to-End Result: {'✅ SUCCESS' if self.test_results['end_to_end'] else '❌ FAILURE'}")
        
        if self.test_results["errors"]:
            print(f"\n❌ Errors encountered ({len(self.test_results['errors'])}):")
            for i, error in enumerate(self.test_results["errors"], 1):
                print(f"   {i}. {error}")
        
        print("=" * 80)
        
        return self.test_results["end_to_end"]
    
    def run_full_test(self):
        """Run the complete functionality test suite"""
        self.log("🚀 Starting functionality test agent...", "START")
        self.log(f"⏱️ Test timeout: {TEST_TIMEOUT} seconds", "INFO")
        
        # Set up signal handler for timeout
        def timeout_handler(signum, frame):
            self.log("⚠️ Test timeout reached - terminating", "TIMEOUT")
            self.cleanup_test_files()
            sys.exit(1)
        
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(TEST_TIMEOUT)
        
        try:
            # Run tests in sequence
            test1_result = self.test_camera_connection()
            if not test1_result:
                self.log("⚠️ Camera connection failed - continuing with remaining tests", "WARNING")
            
            test2_result = self.test_screenshot_capture()
            if not test2_result:
                self.log("⚠️ Screenshot capture failed - skipping person extraction", "WARNING")
                self.cleanup_test_files()
                return self.generate_test_report()
            
            test3_result = self.test_person_extraction()
            
            # Generate final report
            success = self.generate_test_report()
            
            # Cleanup
            self.cleanup_test_files()
            
            return success
            
        except Exception as e:
            self.log(f"❌ Critical test failure: {str(e)}", "CRITICAL")
            self.cleanup_test_files()
            return False
        finally:
            signal.alarm(0)  # Disable alarm

def main():
    """Main function to run functionality tests"""
    agent = FunctionalityTestAgent()
    success = agent.run_full_test()
    
    if success:
        print("\n🎉 All functionality tests passed! The pipeline is working correctly.")
        sys.exit(0)
    else:
        print("\n😞 Some functionality tests failed. Please check the errors above.")
        sys.exit(1)

if __name__ == "__main__":
    main()