#!/usr/bin/env python3
import cv2
import time

cameras = [
    {"name": "camera_27", "url": "rtsp://admin:a12345678@202.168.40.27:554/Streaming/Channels/102"},
    {"name": "camera_28", "url": "rtsp://admin:123456@202.168.40.28:554/Streaming/Channels/102"},
    {"name": "camera_22", "url": "rtsp://admin:123456@202.168.40.22:554/Streaming/Channels/102"},
    {"name": "camera_35", "url": "rtsp://admin:123456@202.168.40.35:554/Streaming/Channels/102"},
    {"name": "camera_36", "url": "rtsp://admin:123456@202.168.40.36:554/Streaming/Channels/102"}
]

for camera in cameras:
    print(f"\n🎥 Testing {camera['name']} with OpenCV...")
    print(f"URL: {camera['url']}")
    
    start_time = time.time()
    
    try:
        # Test connection
        cap = cv2.VideoCapture(camera['url'], cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        connection_time = time.time()
        print(f"  Connection attempt: {connection_time - start_time:.3f}s")
        
        # Wait for opening
        timeout = 10
        while not cap.isOpened() and (time.time() - start_time) < timeout:
            time.sleep(0.1)
        
        open_time = time.time()
        print(f"  Open time: {open_time - start_time:.3f}s")
        
        if not cap.isOpened():
            print(f"  ❌ Failed to open (timeout after {timeout}s)")
            cap.release()
            continue
            
        # Try to read frame
        ret, frame = cap.read()
        frame_time = time.time()
        print(f"  First frame: {frame_time - start_time:.3f}s")
        
        if ret and frame is not None:
            print(f"  ✅ Success! Frame shape: {frame.shape}")
            print(f"  📊 Total time: {frame_time - start_time:.3f}s")
        else:
            print(f"  ❌ No frame received")
            
        cap.release()
        
    except Exception as e:
        end_time = time.time()
        print(f"  ❌ Exception after {end_time - start_time:.3f}s: {e}")

print("\n🏁 OpenCV camera test completed!")
