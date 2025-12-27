#!/bin/bash
# Test V5 with 30 cameras and measure FPS performance

echo "=========================================="
echo "V5 Multi-Camera Performance Test"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Test configurations
CAMERAS_15=(1 2 3 4 5 6 7 8 9 10 11 12 13 14 15)
CAMERAS_30=(1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30)

BASE_URL="http://localhost:8001"

# Function to start a camera
start_camera() {
    local channel=$1
    curl -s -X POST "${BASE_URL}/api/start_camera" \
        -H "Content-Type: application/json" \
        -d "{\"channel\": ${channel}}" > /dev/null
    echo -e "${GREEN}✓${NC} Started camera ${channel}"
}

# Function to stop all cameras
stop_all_cameras() {
    echo "Stopping all cameras..."
    for i in {1..30}; do
        curl -s -X POST "${BASE_URL}/api/stop_camera" \
            -H "Content-Type: application/json" \
            -d "{\"channel\": ${i}}" > /dev/null 2>&1
    done
    sleep 2
}

# Function to get stats
get_stats() {
    curl -s "${BASE_URL}/api/stats" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"Active Cameras: {data['summary']['active_cameras']}\")
print(f\"Total FPS: {data['summary']['total_fps']:.1f}\")
print(f\"Avg FPS/Camera: {data['summary']['avg_fps_per_camera']:.1f}\")
print(f\"Avg Inference: {data['summary']['avg_inference_ms']:.1f}ms\")
print(f\"CPU Usage: {data['system']['cpu']['overall']:.1f}%\")
if 'gpu' in data['system']:
    print(f\"GPU Usage: {data['system']['gpu']['utilization']:.1f}%\")
    print(f\"GPU Memory: {data['system']['gpu']['memory_used_mb']:.0f}MB / {data['system']['gpu']['memory_total_mb']:.0f}MB\")
" 2>/dev/null
}

# Function to check batch stats from logs
get_batch_stats() {
    echo ""
    echo "Batch Collection Statistics (last 30 seconds):"
    tail -200 /tmp/manual_camera_tester_8001.log 2>/dev/null | grep "Collected" | tail -20 | python3 -c "
import sys, re
batch_sizes = []
for line in sys.stdin:
    match = re.search(r'Collected (\d+) frames', line)
    if match:
        batch_sizes.append(int(match.group(1)))
if batch_sizes:
    print(f'  Batches analyzed: {len(batch_sizes)}')
    print(f'  Min batch size: {min(batch_sizes)}')
    print(f'  Max batch size: {max(batch_sizes)}')
    print(f'  Avg batch size: {sum(batch_sizes)/len(batch_sizes):.1f}')
    print(f'  Batch efficiency: {sum(batch_sizes)/len(batch_sizes)/32*100:.1f}% (target: 32 frames/batch)')
else:
    print('  No batch data found in logs')
" 2>/dev/null
}

# Test 1: 15 Cameras
echo ""
echo -e "${YELLOW}=== Test 1: 15 Cameras ===${NC}"
stop_all_cameras

echo "Starting 15 cameras..."
for ch in "${CAMERAS_15[@]}"; do
    start_camera $ch
    sleep 0.5
done

echo ""
echo "Waiting 10 seconds for warmup..."
sleep 10

echo ""
echo "Performance Metrics (15 cameras):"
get_stats
get_batch_stats

# Test 2: 30 Cameras
echo ""
echo ""
echo -e "${YELLOW}=== Test 2: 30 Cameras ===${NC}"

echo "Starting additional 15 cameras (16-30)..."
for ch in {16..30}; do
    start_camera $ch
    sleep 0.5
done

echo ""
echo "Waiting 10 seconds for stabilization..."
sleep 10

echo ""
echo "Performance Metrics (30 cameras):"
get_stats
get_batch_stats

# Summary
echo ""
echo "=========================================="
echo -e "${GREEN}Test Complete!${NC}"
echo "=========================================="
echo ""
echo "Expected improvements from optimization:"
echo "  - Batch size increased: 16 → 32"
echo "  - Collection window: 20ms → 100ms"
echo "  - Get timeout: 5ms → 20ms"
echo ""
echo "Target Performance:"
echo "  - Baseline: 80-113 FPS"
echo "  - Optimized: 200+ FPS (2-2.5x improvement)"
echo ""
echo "Dashboard: http://localhost:3000"
echo ""
