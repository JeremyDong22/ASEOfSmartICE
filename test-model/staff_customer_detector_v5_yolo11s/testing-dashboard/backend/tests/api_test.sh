#!/bin/bash

# API Test Script for V5 Testing Dashboard
# Tests all API endpoints with example requests

BASE_URL="http://localhost:3000/api"

echo "========================================"
echo "V5 Testing Dashboard - API Test Script"
echo "========================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test function
test_endpoint() {
    local method=$1
    local endpoint=$2
    local data=$3
    local description=$4

    echo -e "${YELLOW}Testing:${NC} $description"
    echo "  → $method $endpoint"

    if [ -n "$data" ]; then
        response=$(curl -s -X $method "$BASE_URL$endpoint" \
            -H "Content-Type: application/json" \
            -d "$data" \
            -w "\n%{http_code}")
    else
        response=$(curl -s -X $method "$BASE_URL$endpoint" \
            -w "\n%{http_code}")
    fi

    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n-1)

    if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ]; then
        echo -e "  ${GREEN}✓ Success${NC} (HTTP $http_code)"
    elif [ "$http_code" -ge 400 ] && [ "$http_code" -lt 500 ]; then
        echo -e "  ${YELLOW}⚠ Client Error${NC} (HTTP $http_code)"
    else
        echo -e "  ${RED}✗ Error${NC} (HTTP $http_code)"
    fi

    echo "  Response:"
    echo "$body" | jq '.' 2>/dev/null || echo "$body"
    echo ""
}

# 1. Health Check
test_endpoint "GET" "/system/health" "" "System Health Check"

# 2. System Info
test_endpoint "GET" "/system/info" "" "System Information"

# 3. GPU Stats
test_endpoint "GET" "/system/gpu" "" "GPU Statistics"

# 4. CPU Stats
test_endpoint "GET" "/system/cpu" "" "CPU Statistics"

# 5. Memory Stats
test_endpoint "GET" "/system/memory" "" "Memory Statistics"

# 6. Get Active Cameras (before starting any)
test_endpoint "GET" "/camera/status" "" "Get Active Cameras (initial)"

# 7. Start Camera 1
test_endpoint "POST" "/camera/start" '{"channel":1}' "Start Camera 1"

# Wait for camera to connect
echo "Waiting 3 seconds for camera to connect..."
sleep 3

# 8. Get Active Cameras (after starting)
test_endpoint "GET" "/camera/status" "" "Get Active Cameras (after start)"

# 9. Get All Stats
test_endpoint "GET" "/stats" "" "Get All Statistics"

# 10. Get Stats Summary
test_endpoint "GET" "/stats/summary" "" "Get Stats Summary"

# 11. Get Camera 1 Stats
test_endpoint "GET" "/stats/camera/1" "" "Get Camera 1 Statistics"

# 12. Try to start camera 1 again (should fail)
test_endpoint "POST" "/camera/start" '{"channel":1}' "Start Camera 1 Again (should fail)"

# 13. Try invalid channel
test_endpoint "POST" "/camera/start" '{"channel":99}' "Start Invalid Channel (should fail)"

# 14. Stop Camera 1
test_endpoint "POST" "/camera/stop" '{"channel":1}' "Stop Camera 1"

# Wait for camera to stop
echo "Waiting 2 seconds for camera to stop..."
sleep 2

# 15. Get Active Cameras (after stopping)
test_endpoint "GET" "/camera/status" "" "Get Active Cameras (after stop)"

# 16. Try to stop camera 1 again (should fail)
test_endpoint "POST" "/camera/stop" '{"channel":1}' "Stop Camera 1 Again (should fail)"

echo "========================================"
echo "API Tests Complete"
echo "========================================"
echo ""
echo "Note: Real-time SSE endpoint (/api/stats/realtime) requires EventSource client."
echo "Test it with: curl -N http://localhost:3000/api/stats/realtime"
