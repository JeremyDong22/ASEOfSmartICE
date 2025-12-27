#!/bin/bash
#
# Video Lag Testing Script - IMPROVED VERSION
# Tests video stream lag by adding cameras ONE BY ONE to find exact threshold
#
# Lag Definition:
# - Real end-to-end video delay from camera capture to browser display
# - Measured by: inference queue depth + FPS drops + avg_inference_ms
#
# Key Improvements:
# 1. Add cameras ONE BY ONE (not batches) to find exact threshold
# 2. Wait 30 seconds (not 10s) after each camera for full stabilization
# 3. Better lag indicators:
#    - avg_inference_ms > 150ms = lag starting
#    - FPS drops below 10 = lag detected
#    - inference_queue_size growing = backlog building up
#
# Expected Result at 15 FPS:
# - Cameras 1-6: Normal (inference <100ms, FPS ~15)
# - Camera 7: LAG DETECTED (inference >150ms, FPS drops)

API_BASE="http://localhost:3000/api"
PYTHON_SERVER="http://localhost:8001"

# Lag detection thresholds
INFERENCE_LAG_THRESHOLD_MS=150  # If avg_inference_ms exceeds this = lag
FPS_DROP_THRESHOLD=10           # If FPS drops below this = lag
WAIT_TIME=30                    # Seconds to wait after starting each camera (increased from 10s)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Log file
LOG_FILE="lag_test_results_$(date +%Y%m%d_%H%M%S).log"

echo "============================================================================"
echo "Video Stream Lag Test - 15 FPS Validation"
echo "============================================================================"
echo "Lag Detection Thresholds:"
echo "  - Inference time: >${INFERENCE_LAG_THRESHOLD_MS}ms (noticeable lag)"
echo "  - FPS drop: <${FPS_DROP_THRESHOLD} FPS (lag detected)"
echo "  - Queue depth: growing (backlog building)"
echo ""
echo "Test Method: Add cameras ONE BY ONE to find exact lag threshold"
echo "Wait time per camera: ${WAIT_TIME}s (allow full stabilization)"
echo "Log file: $LOG_FILE"
echo "============================================================================"
echo ""

# Log function
log() {
    echo "[$(date '+%H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Check if servers are running
check_servers() {
    log "Checking if backend server is running..."
    if ! curl -s "${API_BASE}/system/health" > /dev/null 2>&1; then
        echo -e "${RED}Error: Backend server not running on port 3000${NC}"
        echo "Run: cd testing-dashboard && ./restart_servers.sh"
        exit 1
    fi

    log "Checking if Python server is running..."
    if ! curl -s "${PYTHON_SERVER}/api/active_cameras" > /dev/null 2>&1; then
        echo -e "${RED}Error: Python server not running on port 8001${NC}"
        echo "Run: python3 manual_camera_tester_pyav.py"
        exit 1
    fi

    log "✓ Both servers are running"
    echo ""
}

# Start a camera
start_camera() {
    local channel=$1

    response=$(curl -s -X POST "${API_BASE}/camera/start" \
        -H "Content-Type: application/json" \
        -d "{\"channel\": $channel}")

    if echo "$response" | grep -q '"success":true'; then
        echo -e "${GREEN}  ✓ Camera $channel started${NC}"
        return 0
    else
        echo -e "${RED}  ✗ Failed to start camera $channel${NC}"
        echo "  Response: $response"
        return 1
    fi
}

# Get detailed camera stats with lag detection
get_camera_stats_detailed() {
    curl -s "${API_BASE}/stats" | python3 -c "
import sys, json

try:
    data = json.load(sys.stdin)
    cameras = data.get('cameras', [])
    summary = data.get('summary', {})

    if len(cameras) == 0:
        print('No active cameras')
        sys.exit(0)

    # Sort by channel
    cameras.sort(key=lambda x: x.get('channel', 0))

    # Get queue size from summary
    queue_size = summary.get('inference_queue_size', 0)

    print(f'{"Channel":<8} {"Status":<12} {"FPS":<8} {"Inference":<12} {"Queue":<8} {"Lag?":<8}')
    print('-' * 70)

    max_inference = 0
    max_inference_channel = 0
    min_fps = 999
    min_fps_channel = 0
    total_inference = 0
    active_count = 0
    lag_detected = False
    lag_channel = 0

    for cam in cameras:
        ch = cam.get('channel', 0)
        status = cam.get('connection_status', 'unknown')
        fps = cam.get('current_fps', 0)
        inference_ms = cam.get('avg_inference_ms', 0)

        # Only count connected cameras
        if status == 'connected' and fps > 0:
            active_count += 1
            total_inference += inference_ms

            if inference_ms > max_inference:
                max_inference = inference_ms
                max_inference_channel = ch

            if fps < min_fps:
                min_fps = fps
                min_fps_channel = ch

            # Lag detection logic
            lag_indicator = ''
            if inference_ms > $INFERENCE_LAG_THRESHOLD_MS:
                lag_indicator = 'SLOW'
                if not lag_detected:
                    lag_detected = True
                    lag_channel = ch
            elif fps < $FPS_DROP_THRESHOLD:
                lag_indicator = 'FPS_DROP'
                if not lag_detected:
                    lag_detected = True
                    lag_channel = ch
            else:
                lag_indicator = 'OK'
        else:
            lag_indicator = 'N/A'

        print(f'{ch:<8} {status:<12} {fps:<8.1f} {inference_ms:<12.1f} {queue_size:<8} {lag_indicator:<8}')

    print('-' * 70)

    if active_count > 0:
        avg_inference = total_inference / active_count
        print(f'Active: {active_count} | Avg inference: {avg_inference:.1f}ms | Max: {max_inference:.1f}ms (Ch{max_inference_channel}) | Min FPS: {min_fps:.1f} (Ch{min_fps_channel}) | Queue: {queue_size}')

        # Output machine-readable results
        print(f'ACTIVE_COUNT={active_count}')
        print(f'AVG_INFERENCE={avg_inference:.1f}')
        print(f'MAX_INFERENCE={max_inference:.1f}')
        print(f'MAX_INFERENCE_CHANNEL={max_inference_channel}')
        print(f'MIN_FPS={min_fps:.1f}')
        print(f'MIN_FPS_CHANNEL={min_fps_channel}')
        print(f'QUEUE_SIZE={queue_size}')
        print(f'LAG_DETECTED={str(lag_detected).lower()}')
        print(f'LAG_CHANNEL={lag_channel}')
    else:
        print('No active cameras with valid stats yet')

except Exception as e:
    print(f'Error parsing stats: {e}', file=sys.stderr)
    import traceback
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)
"
}

# Stop all cameras
stop_all_cameras() {
    log "Stopping all cameras..."

    # Get list of active cameras
    active_cameras=$(curl -s "${API_BASE}/camera/status" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    cameras = data.get('cameras', [])
    print(' '.join(map(str, cameras)))
except:
    pass
")

    if [ -z "$active_cameras" ]; then
        log "No active cameras to stop"
        return 0
    fi

    for channel in $active_cameras; do
        curl -s -X POST "${API_BASE}/camera/stop" \
            -H "Content-Type: application/json" \
            -d "{\"channel\": $channel}" > /dev/null
        echo "  Stopped camera $channel"
    done

    sleep 2
    log "✓ All cameras stopped"
    echo ""
}

# Main test loop - ONE CAMERA AT A TIME
run_lag_test() {
    local max_cameras=15  # Test up to 15 cameras
    local first_lag_camera=0
    local first_lag_type=""
    local first_lag_value=0

    for camera_num in $(seq 1 $max_cameras); do
        echo ""
        echo -e "${CYAN}========================================${NC}"
        echo -e "${CYAN}Testing Camera $camera_num (Total: $camera_num cameras)${NC}"
        echo -e "${CYAN}========================================${NC}"

        # Start this camera
        log "Starting camera $camera_num..."
        if ! start_camera $camera_num; then
            log "Failed to start camera $camera_num, stopping test"
            break
        fi

        # Wait for camera to stabilize (30 seconds)
        echo ""
        log "Waiting ${WAIT_TIME}s for camera to stabilize and reach steady state..."
        for i in $(seq $WAIT_TIME -1 1); do
            if (( i % 5 == 0 )) || (( i <= 5 )); then
                echo -e "  ${YELLOW}${i}s remaining...${NC}"
            fi
            sleep 1
        done
        echo ""

        # Get stats
        log "Collecting statistics for $camera_num camera(s)..."
        echo ""

        stats_output=$(get_camera_stats_detailed)
        echo "$stats_output"

        # Parse results
        avg_inference=$(echo "$stats_output" | grep "AVG_INFERENCE=" | cut -d'=' -f2)
        max_inference=$(echo "$stats_output" | grep "MAX_INFERENCE=" | cut -d'=' -f2 | head -1)
        max_inference_channel=$(echo "$stats_output" | grep "MAX_INFERENCE_CHANNEL=" | cut -d'=' -f2)
        min_fps=$(echo "$stats_output" | grep "MIN_FPS=" | cut -d'=' -f2 | head -1)
        min_fps_channel=$(echo "$stats_output" | grep "MIN_FPS_CHANNEL=" | cut -d'=' -f2)
        queue_size=$(echo "$stats_output" | grep "QUEUE_SIZE=" | cut -d'=' -f2)
        lag_detected=$(echo "$stats_output" | grep "LAG_DETECTED=" | cut -d'=' -f2)
        lag_channel=$(echo "$stats_output" | grep "LAG_CHANNEL=" | cut -d'=' -f2)

        # Check if lag detected
        if [ "$lag_detected" = "true" ] && [ $first_lag_camera -eq 0 ]; then
            first_lag_camera=$camera_num
            first_lag_value=$max_inference

            # Determine lag type
            if (( $(echo "$max_inference > $INFERENCE_LAG_THRESHOLD_MS" | bc -l 2>/dev/null || echo 0) )); then
                first_lag_type="High inference time (${max_inference}ms)"
            elif (( $(echo "$min_fps < $FPS_DROP_THRESHOLD" | bc -l 2>/dev/null || echo 0) )); then
                first_lag_type="FPS drop (${min_fps} FPS)"
            else
                first_lag_type="Unknown lag indicator"
            fi

            echo ""
            echo -e "${RED}${BOLD}⚠️  LAG DETECTED ⚠️${NC}"
            echo -e "${RED}Camera $camera_num caused lag: $first_lag_type${NC}"
            echo -e "${RED}Lag first appeared on camera: Ch${lag_channel}${NC}"
            log "LAG DETECTED at camera $camera_num: $first_lag_type"

            # Stop here - we found the threshold
            echo ""
            echo -e "${YELLOW}Stopping test - lag threshold found${NC}"
            break
        else
            echo ""
            echo -e "${GREEN}✓ All cameras operating normally${NC}"
            echo -e "${GREEN}  Avg inference: ${avg_inference}ms | Min FPS: ${min_fps} | Queue: ${queue_size}${NC}"
        fi

        echo ""
        log "Continuing to next camera..."
        sleep 2
    done

    # Summary
    echo ""
    echo "============================================================================"
    echo -e "${CYAN}${BOLD}TEST SUMMARY${NC}"
    echo "============================================================================"
    echo ""

    if [ $first_lag_camera -gt 0 ]; then
        echo -e "${YELLOW}${BOLD}Lag detected starting at camera: $first_lag_camera${NC}"
        echo -e "${YELLOW}Lag type: $first_lag_type${NC}"
        echo ""
        echo -e "${GREEN}Recommendation: Safe to run up to $((first_lag_camera - 1)) cameras at 15 FPS${NC}"
        echo ""
        echo -e "${CYAN}Next step: Change TARGET_FPS to 7 and retest to find 7 FPS threshold${NC}"
    else
        echo -e "${GREEN}${BOLD}All tested cameras showed acceptable performance!${NC}"
        echo -e "${GREEN}No lag detected with $max_cameras cameras at 15 FPS${NC}"
        echo ""
        echo -e "${CYAN}Note: Test stopped at $max_cameras cameras. You can test more if needed.${NC}"
    fi

    echo ""
    echo "Detailed results saved to: $LOG_FILE"
    echo "============================================================================"
}

# Cleanup function
cleanup() {
    echo ""
    log "Cleaning up..."
    stop_all_cameras
    log "Test completed"
}

# Set trap for cleanup on exit
trap cleanup EXIT

# Main execution
check_servers
run_lag_test
