#!/bin/bash
# Test 2: Backend Processing Capacity Test
# Tests how many cameras the backend can handle at 15 FPS without queue buildup

echo "=========================================================================="
echo "Backend Processing Capacity Test (15 FPS)"
echo "=========================================================================="
echo "This test monitors the inference queue depth to detect backend overload"
echo "Queue buildup = Backend can't keep up with camera input"
echo "=========================================================================="
echo ""

BASE_URL="http://localhost:8001"

# Stop all cameras first
echo "Stopping all cameras..."
for ch in $(seq 1 30); do
    curl -s -X POST "$BASE_URL/api/stop_camera" \
        -H "Content-Type: application/json" \
        -d "{\"channel\": $ch}" > /dev/null 2>&1
done
sleep 3
echo "✓ All cameras stopped"
echo ""

# Header
printf "%-10s %-12s %-15s %-15s %-20s\n" "Cameras" "Queue Depth" "Avg Inference" "Total FPS" "Status"
printf "%-10s %-12s %-15s %-15s %-20s\n" "-------" "-----------" "-------------" "---------" "------"

MAX_CAMERAS=20
QUEUE_THRESHOLD=10  # If queue > 10, backend is overloaded

for num_cams in $(seq 1 $MAX_CAMERAS); do
    # Start camera
    curl -s -X POST "$BASE_URL/api/start_camera" \
        -H "Content-Type: application/json" \
        -d "{\"channel\": $num_cams}" > /dev/null 2>&1

    # Wait for stabilization
    sleep 8

    # Get stats
    stats=$(curl -s "$BASE_URL/api/stats" | python3 -c "
import sys, json
data = json.load(sys.stdin)
summary = data.get('summary', {})
queue = summary.get('inference_queue_size', 0)
avg_inf = summary.get('avg_inference_ms', 0)
total_fps = summary.get('total_fps', 0)
active = summary.get('active_cameras', 0)
print(f'{active},{queue},{avg_inf:.1f},{total_fps:.1f}')
" 2>/dev/null)

    if [ -n "$stats" ]; then
        IFS=',' read -r active queue avg_inf total_fps <<< "$stats"

        # Check if queue is building up
        if (( $(echo "$queue > $QUEUE_THRESHOLD" | bc -l) )); then
            status="⚠️ OVERLOAD"
            printf "%-10s %-12s %-15s %-15s %-20s\n" \
                "$active" "$queue" "${avg_inf}ms" "${total_fps} FPS" "$status"
            echo ""
            echo "=========================================================================="
            echo "Backend Capacity Reached!"
            echo "=========================================================================="
            echo "Maximum cameras at 15 FPS: $(($active - 1))"
            echo "Queue started building at: $active cameras"
            echo "Avg inference time: ${avg_inf}ms"
            echo ""
            echo "Conclusion: Backend can handle $(($active - 1)) cameras in real-time"
            echo "            Adding more cameras causes queue buildup (lag)"
            break
        else
            status="✓ OK"
            printf "%-10s %-12s %-15s %-15s %-20s\n" \
                "$active" "$queue" "${avg_inf}ms" "${total_fps} FPS" "$status"
        fi
    fi
done

echo ""
echo "Test complete. Backend capacity determined."
echo ""

# Cleanup
echo "Stopping all cameras..."
for ch in $(seq 1 $MAX_CAMERAS); do
    curl -s -X POST "$BASE_URL/api/stop_camera" \
        -H "Content-Type: application/json" \
        -d "{\"channel\": $ch}" > /dev/null 2>&1
done
echo "✓ Cleanup complete"
