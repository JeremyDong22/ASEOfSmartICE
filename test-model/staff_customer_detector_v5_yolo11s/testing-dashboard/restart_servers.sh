#!/bin/bash

echo "Restarting V5 Dashboard Servers..."

# Kill existing processes
pkill -f "python3.*manual_camera" 2>/dev/null
pkill -f "node.*server.js" 2>/dev/null
sleep 2

# Start Python server
cd /home/smartice001/smartice/ASEOfSmartICE/test-model/staff_customer_detector_v5_yolo11s
python3 manual_camera_tester_pyav.py > /tmp/v5_python.log 2>&1 &
PYTHON_PID=$!
echo "Python server started (PID: $PYTHON_PID)"

# Wait for Python server
echo "Waiting for Python server to be ready..."
for i in {1..20}; do
  sleep 2
  if curl -s http://localhost:8001/api/active_cameras -m 1 >/dev/null 2>&1; then
    echo "✓ Python server is UP!"
    break
  fi
  echo "  Attempt $i/20..."
done

# Verify Python server
if ! curl -s http://localhost:8001/api/active_cameras -m 1 >/dev/null 2>&1; then
  echo "❌ Python server failed to start"
  exit 1
fi

# Start TypeScript backend
cd testing-dashboard/backend
npm start > /tmp/dashboard_backend.log 2>&1 &
BACKEND_PID=$!
echo "TypeScript backend started (PID: $BACKEND_PID)"

# Wait for backend
echo "Waiting for backend to be ready..."
for i in {1..10}; do
  sleep 2
  if curl -s http://localhost:3000/api/system/health -m 1 >/dev/null 2>&1; then
    echo "✓ Backend is UP!"
    break
  fi
  echo "  Attempt $i/10..."
done

# Verify backend
if curl -s http://localhost:3000/api/system/health -m 1 >/dev/null 2>&1; then
  echo ""
  echo "========================================="
  echo "✅ All servers are running!"
  echo "========================================="
  echo "Python server: http://localhost:8001"
  echo "Dashboard: http://localhost:3000"
  echo ""
  curl -s http://localhost:3000/api/system/health | python3 -m json.tool
else
  echo "❌ Backend failed to start"
  tail -30 /tmp/dashboard_backend.log
  exit 1
fi
