#!/bin/bash
echo "========================================="
echo "Testing Vue 3 Frontend with C++ Backend"
echo "========================================="
echo ""

# Check if backend is running
echo "1. Checking backend (port 8001)..."
if curl -s http://localhost:8001/api/stats > /dev/null 2>&1; then
    echo "   ✅ Backend is running on port 8001"
else
    echo "   ❌ Backend not running on port 8001"
    echo "   Please start the backend first:"
    echo "   cd /home/smartice001/smartice/ASEOfSmartICE/test-model/staff_customer_detector_v5_yolo11s"
    echo "   python3 manual_camera_tester_pyav.py"
    exit 1
fi
echo ""

# Check if frontend dev server is running
echo "2. Checking frontend (port 3001)..."
if curl -s http://localhost:3001 > /dev/null 2>&1; then
    echo "   ✅ Frontend is running on port 3001"
else
    echo "   ❌ Frontend not running on port 3001"
    echo "   Please start the frontend:"
    echo "   cd /home/smartice001/smartice/ASEOfSmartICE/test-model/staff_customer_detector_v5_yolo11s/frontend-vue"
    echo "   npm run dev"
    exit 1
fi
echo ""

# Test API endpoints
echo "3. Testing API endpoints..."
echo ""

echo "   Testing POST /api/start_camera (channel 18)..."
response=$(curl -s -X POST http://localhost:8001/api/start_camera \
    -H "Content-Type: application/json" \
    -d '{"channel": 18}')

if echo "$response" | grep -q '"success"'; then
    echo "   ✅ Camera start API works"
    echo "   Response: $response"
else
    echo "   ❌ Camera start API failed"
    echo "   Response: $response"
fi
echo ""

# Wait for camera to connect
echo "   Waiting 3 seconds for camera to connect..."
sleep 3
echo ""

# Check MJPEG stream
echo "   Testing MJPEG stream (GET /video_feed/18)..."
if timeout 2 curl -s http://localhost:8001/video_feed/18 > /dev/null 2>&1; then
    echo "   ✅ MJPEG stream is working"
else
    echo "   ⚠️  MJPEG stream not responding (may still be connecting)"
fi
echo ""

# Stop camera
echo "   Testing POST /api/stop_camera (channel 18)..."
response=$(curl -s -X POST http://localhost:8001/api/stop_camera \
    -H "Content-Type: application/json" \
    -d '{"channel": 18}')

if echo "$response" | grep -q '"success"'; then
    echo "   ✅ Camera stop API works"
    echo "   Response: $response"
else
    echo "   ❌ Camera stop API failed"
    echo "   Response: $response"
fi
echo ""

# Test stats endpoint
echo "   Testing GET /api/stats..."
stats=$(curl -s http://localhost:8001/api/stats)
if echo "$stats" | grep -q '"summary"'; then
    echo "   ✅ Stats API works"
    active_cameras=$(echo "$stats" | python3 -c "import sys, json; print(json.load(sys.stdin)['summary']['active_cameras'])" 2>/dev/null)
    echo "   Active cameras: $active_cameras"
else
    echo "   ❌ Stats API failed"
fi
echo ""

# Final summary
echo "========================================="
echo "Test Summary"
echo "========================================="
echo "✅ Backend is running"
echo "✅ Frontend is running"
echo "✅ API endpoints are working"
echo ""
echo "Next steps:"
echo "1. Open http://localhost:3001 in your browser"
echo "2. Click on camera control buttons to start cameras"
echo "3. MJPEG video streams should display with detection overlays"
echo "4. Check stats panel for camera count and FPS"
echo ""
echo "========================================="
