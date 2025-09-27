# Camera Credentials and Access Information

## Working Camera Credentials (8/9 cameras tested successfully)

### High Resolution Cameras (2592x1944)
- **202.168.40.27**: admin/a12345678 @ 20 FPS
  - RTSP: `rtsp://admin:a12345678@202.168.40.27:554/Streaming/Channels/102`
- **202.168.40.28**: admin/123456 @ 20 FPS  
  - RTSP: `rtsp://admin:123456@202.168.40.28:554/Streaming/Channels/102`

### Medium Resolution Cameras (1920x1080)
- **202.168.40.36**: admin/123456 @ 20 FPS
  - RTSP: `rtsp://admin:123456@202.168.40.36:554/Streaming/Channels/102`
- **202.168.40.35**: admin/123456 @ 20 FPS
  - RTSP: `rtsp://admin:123456@202.168.40.35:554/Streaming/Channels/102`
- **202.168.40.22**: admin/123456 @ 20 FPS
  - RTSP: `rtsp://admin:123456@202.168.40.22:554/Streaming/Channels/102`

### Low Resolution Cameras (640x360)
- **202.168.40.24**: admin/a12345678 @ 25 FPS
  - RTSP: `rtsp://admin:a12345678@202.168.40.24:554/Streaming/Channels/102`
- **202.168.40.26**: admin/a12345678 @ 25 FPS
  - RTSP: `rtsp://admin:a12345678@202.168.40.26:554/Streaming/Channels/102`
- **202.168.40.29**: admin/a12345678 @ 25 FPS
  - RTSP: `rtsp://admin:a12345678@202.168.40.29:554/Streaming/Channels/102`

### Failed Cameras
- **202.168.40.34**: Both passwords failed - camera not reachable

## Connection Pattern Analysis
- **Password 123456**: Works for IPs ending in 28, 36, 35, 22
- **Password a12345678**: Works for IPs ending in 27, 24, 26, 29
- **Failed**: IP ending in 34 (no response to either password)

## Technical Notes
- All cameras use sub-stream endpoint: `/Streaming/Channels/102`
- RTSP port: 554
- Username: admin
- Stream stability: All working cameras show >90% frame stability
- H.265 encoding detected in most streams

## Usage for Model Training
- Recommended cameras for training: High/Medium resolution cameras
- For batch processing: Use all 8 working cameras
- Timeout settings: 5s connection, 3s frame capture