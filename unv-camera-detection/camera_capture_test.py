#!/usr/bin/env python3
"""
Camera Capture Test v1.0
- Captures 5 screenshots from each of 30 cameras within 5 seconds
- Generates HTML gallery for visual inspection
- Uses SAME method as production (OpenCV cv2.VideoCapture)
- Created: 2025-12-23
"""

import cv2
import os
import time
import json
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# NVR Configuration
NVR_CONFIG = {
    "ip": "192.168.1.3",
    "username": "admin",
    "password": "ybl123456789",
    "port": 554,
    "total_cameras": 30
}

# Output directory
OUTPUT_DIR = Path(__file__).parent / "camera_test_results"
SCREENSHOTS_PER_CAMERA = 5
CAPTURE_INTERVAL = 1.0  # 1 second between captures (5 captures in 5 seconds)


def get_rtsp_url(channel, stream_type="s0"):
    """Generate RTSP URL for a camera channel"""
    return (f"rtsp://{NVR_CONFIG['username']}:{NVR_CONFIG['password']}@"
            f"{NVR_CONFIG['ip']}:{NVR_CONFIG['port']}/unicast/c{channel}/{stream_type}/live")


def capture_camera_screenshots(channel):
    """
    Capture multiple screenshots from a single camera
    Returns: dict with results
    """
    result = {
        "channel": channel,
        "status": "unknown",
        "screenshots": [],
        "codec": None,
        "resolution": None,
        "errors": []
    }

    rtsp_url = get_rtsp_url(channel, "s0")
    camera_dir = OUTPUT_DIR / f"channel_{channel}"
    camera_dir.mkdir(exist_ok=True)

    print(f"[CH {channel:02d}] Connecting...")

    try:
        # Connect using same method as production
        cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        # Wait for connection (max 5 seconds)
        start_time = time.time()
        while not cap.isOpened() and (time.time() - start_time) < 5:
            time.sleep(0.1)

        if not cap.isOpened():
            result["status"] = "connection_failed"
            result["errors"].append("Connection timeout")
            print(f"[CH {channel:02d}] ❌ Connection failed")
            return result

        # Get codec info
        fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
        codec = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)])
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        result["codec"] = codec
        result["resolution"] = f"{width}x{height}"

        # Capture 5 screenshots
        successful_captures = 0
        for i in range(SCREENSHOTS_PER_CAMERA):
            ret, frame = cap.read()

            if ret and frame is not None:
                # Check if frame is valid
                mean_val = frame.mean()

                timestamp = datetime.now().strftime("%H%M%S_%f")[:-3]
                filename = f"shot_{i+1}_{timestamp}.jpg"
                filepath = camera_dir / filename

                # Save screenshot
                success, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
                if success:
                    with open(filepath, 'wb') as f:
                        f.write(buffer.tobytes())

                    file_size = len(buffer.tobytes()) / 1024

                    result["screenshots"].append({
                        "filename": filename,
                        "path": str(filepath),
                        "size_kb": round(file_size, 1),
                        "mean_brightness": round(float(mean_val), 1),
                        "is_black": bool(mean_val < 10),
                        "is_corrupted": bool(file_size < 5)  # Very small files are likely corrupted
                    })
                    successful_captures += 1
            else:
                result["errors"].append(f"Frame {i+1} failed")

            # Wait between captures
            if i < SCREENSHOTS_PER_CAMERA - 1:
                time.sleep(CAPTURE_INTERVAL)

        cap.release()

        # Determine status
        if successful_captures == SCREENSHOTS_PER_CAMERA:
            # Check if any screenshots look corrupted
            corrupted_count = sum(1 for s in result["screenshots"] if s["is_corrupted"] or s["is_black"])
            if corrupted_count == 0:
                result["status"] = "success"
                print(f"[CH {channel:02d}] ✅ {successful_captures} screenshots OK | {codec} | {width}x{height}")
            elif corrupted_count < SCREENSHOTS_PER_CAMERA:
                result["status"] = "partial"
                print(f"[CH {channel:02d}] ⚠️ {corrupted_count}/{SCREENSHOTS_PER_CAMERA} corrupted | {codec}")
            else:
                result["status"] = "corrupted"
                print(f"[CH {channel:02d}] ❌ All corrupted | {codec}")
        elif successful_captures > 0:
            result["status"] = "partial"
            print(f"[CH {channel:02d}] ⚠️ Only {successful_captures}/{SCREENSHOTS_PER_CAMERA} captured")
        else:
            result["status"] = "failed"
            print(f"[CH {channel:02d}] ❌ No frames captured")

    except Exception as e:
        result["status"] = "error"
        result["errors"].append(str(e))
        print(f"[CH {channel:02d}] ❌ Error: {str(e)[:50]}")

    return result


def generate_html_report(results):
    """Generate HTML gallery for viewing test results"""

    # Count statistics
    stats = {
        "success": len([r for r in results if r["status"] == "success"]),
        "partial": len([r for r in results if r["status"] == "partial"]),
        "corrupted": len([r for r in results if r["status"] == "corrupted"]),
        "failed": len([r for r in results if r["status"] in ["failed", "connection_failed", "error"]])
    }

    html = f'''<!DOCTYPE html>
<html>
<head>
    <title>SmartICE Camera Test Results - {datetime.now().strftime("%Y-%m-%d %H:%M")}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            background: #1a1a2e;
            color: #eee;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            padding: 20px;
        }}
        h1 {{
            text-align: center;
            padding: 20px;
            background: linear-gradient(135deg, #16213e, #0f3460);
            border-radius: 10px;
            margin-bottom: 20px;
        }}
        .stats {{
            display: flex;
            justify-content: center;
            gap: 30px;
            padding: 20px;
            background: #16213e;
            border-radius: 10px;
            margin-bottom: 20px;
        }}
        .stat {{
            text-align: center;
            padding: 15px 30px;
            border-radius: 8px;
        }}
        .stat.success {{ background: #1b4332; }}
        .stat.partial {{ background: #5c4d1a; }}
        .stat.corrupted {{ background: #5c1a1a; }}
        .stat.failed {{ background: #3d1a1a; }}
        .stat-num {{ font-size: 36px; font-weight: bold; }}
        .stat-label {{ font-size: 14px; opacity: 0.8; }}

        .camera-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
            gap: 20px;
        }}
        .camera-card {{
            background: #16213e;
            border-radius: 10px;
            overflow: hidden;
            border: 3px solid transparent;
        }}
        .camera-card.success {{ border-color: #2d6a4f; }}
        .camera-card.partial {{ border-color: #f4a261; }}
        .camera-card.corrupted {{ border-color: #e63946; }}
        .camera-card.failed {{ border-color: #6c757d; }}

        .camera-header {{
            padding: 15px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: #0f3460;
        }}
        .camera-title {{
            font-size: 18px;
            font-weight: bold;
        }}
        .camera-status {{
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
        }}
        .camera-status.success {{ background: #2d6a4f; }}
        .camera-status.partial {{ background: #f4a261; color: #000; }}
        .camera-status.corrupted {{ background: #e63946; }}
        .camera-status.failed {{ background: #6c757d; }}

        .camera-info {{
            padding: 10px 15px;
            font-size: 13px;
            color: #aaa;
        }}
        .camera-info span {{
            margin-right: 15px;
        }}

        .screenshots {{
            display: flex;
            overflow-x: auto;
            padding: 10px;
            gap: 10px;
            background: #0a0a15;
        }}
        .screenshot {{
            flex-shrink: 0;
            width: 200px;
            text-align: center;
        }}
        .screenshot img {{
            width: 100%;
            height: 120px;
            object-fit: cover;
            border-radius: 5px;
            cursor: pointer;
            transition: transform 0.2s;
        }}
        .screenshot img:hover {{
            transform: scale(1.05);
        }}
        .screenshot-info {{
            font-size: 11px;
            color: #888;
            margin-top: 5px;
        }}
        .screenshot.corrupted img {{
            border: 2px solid #e63946;
        }}
        .screenshot.black img {{
            border: 2px solid #f4a261;
        }}

        .no-screenshots {{
            padding: 40px;
            text-align: center;
            color: #666;
        }}

        .errors {{
            padding: 10px 15px;
            background: #2d1a1a;
            font-size: 12px;
            color: #e63946;
        }}

        /* Modal for full-size image */
        .modal {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.9);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }}
        .modal img {{
            max-width: 95%;
            max-height: 95%;
        }}
        .modal.active {{
            display: flex;
        }}
    </style>
</head>
<body>
    <h1>SmartICE Camera Test Results</h1>

    <div class="stats">
        <div class="stat success">
            <div class="stat-num">{stats["success"]}</div>
            <div class="stat-label">Success</div>
        </div>
        <div class="stat partial">
            <div class="stat-num">{stats["partial"]}</div>
            <div class="stat-label">Partial</div>
        </div>
        <div class="stat corrupted">
            <div class="stat-num">{stats["corrupted"]}</div>
            <div class="stat-label">Corrupted</div>
        </div>
        <div class="stat failed">
            <div class="stat-num">{stats["failed"]}</div>
            <div class="stat-label">Failed</div>
        </div>
    </div>

    <div class="camera-grid">
'''

    # Sort by channel number
    results.sort(key=lambda x: x["channel"])

    for r in results:
        status_class = r["status"] if r["status"] in ["success", "partial", "corrupted"] else "failed"
        status_text = {
            "success": "OK",
            "partial": "PARTIAL",
            "corrupted": "CORRUPTED",
            "failed": "FAILED",
            "connection_failed": "NO CONNECTION",
            "error": "ERROR"
        }.get(r["status"], r["status"].upper())

        html += f'''
        <div class="camera-card {status_class}">
            <div class="camera-header">
                <span class="camera-title">Channel {r["channel"]}</span>
                <span class="camera-status {status_class}">{status_text}</span>
            </div>
            <div class="camera-info">
                <span>Codec: <b>{r["codec"] or "N/A"}</b></span>
                <span>Resolution: <b>{r["resolution"] or "N/A"}</b></span>
            </div>
'''

        if r["screenshots"]:
            html += '<div class="screenshots">'
            for shot in r["screenshots"]:
                shot_class = ""
                if shot.get("is_corrupted"):
                    shot_class = "corrupted"
                elif shot.get("is_black"):
                    shot_class = "black"

                # Use relative path for HTML
                rel_path = f"channel_{r['channel']}/{shot['filename']}"
                html += f'''
                <div class="screenshot {shot_class}">
                    <img src="{rel_path}" onclick="showModal(this.src)" alt="Shot">
                    <div class="screenshot-info">{shot["size_kb"]} KB</div>
                </div>
'''
            html += '</div>'
        else:
            html += '<div class="no-screenshots">No screenshots captured</div>'

        if r["errors"]:
            html += f'<div class="errors">Errors: {", ".join(r["errors"])}</div>'

        html += '</div>'

    html += '''
    </div>

    <div class="modal" id="modal" onclick="hideModal()">
        <img id="modalImg" src="">
    </div>

    <script>
        function showModal(src) {
            document.getElementById('modalImg').src = src;
            document.getElementById('modal').classList.add('active');
        }
        function hideModal() {
            document.getElementById('modal').classList.remove('active');
        }
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') hideModal();
        });
    </script>
</body>
</html>
'''

    # Save HTML
    html_path = OUTPUT_DIR / "test_results.html"
    with open(html_path, 'w') as f:
        f.write(html)

    return html_path


def main():
    """Main test function"""
    print("=" * 60)
    print("SmartICE Camera Capture Test")
    print(f"Testing {NVR_CONFIG['total_cameras']} cameras")
    print(f"Capturing {SCREENSHOTS_PER_CAMERA} screenshots per camera")
    print("=" * 60)

    # Create output directory
    OUTPUT_DIR.mkdir(exist_ok=True)
    print(f"Output: {OUTPUT_DIR}\n")

    results = []
    start_time = time.time()

    # Test cameras sequentially (to avoid overwhelming NVR)
    for channel in range(1, NVR_CONFIG['total_cameras'] + 1):
        result = capture_camera_screenshots(channel)
        results.append(result)

    elapsed = time.time() - start_time

    print("\n" + "=" * 60)
    print(f"Test completed in {elapsed:.1f} seconds")
    print("=" * 60)

    # Generate HTML report
    html_path = generate_html_report(results)
    print(f"\n📊 HTML Report: {html_path}")

    # Save JSON results
    json_path = OUTPUT_DIR / "test_results.json"
    with open(json_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"📋 JSON Data: {json_path}")

    # Open HTML in browser
    print("\n🌐 Opening results in browser...")
    os.system(f'open "{html_path}"')

    # Print summary
    success = len([r for r in results if r["status"] == "success"])
    partial = len([r for r in results if r["status"] == "partial"])
    corrupted = len([r for r in results if r["status"] == "corrupted"])
    failed = len([r for r in results if r["status"] in ["failed", "connection_failed", "error"]])

    print(f"\n📈 Summary:")
    print(f"   ✅ Success: {success}")
    print(f"   ⚠️ Partial: {partial}")
    print(f"   ❌ Corrupted: {corrupted}")
    print(f"   🚫 Failed: {failed}")


if __name__ == "__main__":
    main()
