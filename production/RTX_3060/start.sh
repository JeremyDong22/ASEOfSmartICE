#!/bin/bash
# Modified: 2025-11-16 - Created robust startup wrapper script with daemon protection

# ASE Restaurant Surveillance System - Robust Startup Script
# Version: 2.0.0
# Created: 2025-11-16
#
# Purpose:
# - Robust startup wrapper for surveillance system
# - Automatic crash recovery and restart
# - Logging and monitoring
# - Can run in background or foreground
#
# Usage:
#   ./start.sh                # Start service (recommended)
#   ./start.sh --foreground   # Run in foreground (debug mode)
#   ./start.sh --status       # Check service status
#   ./start.sh --stop         # Stop service
#   ./start.sh --restart      # Restart service
#   ./start.sh --logs         # View logs
#
# Features:
# - Auto-restart on crash
# - Logging to file and console
# - PID file management
# - Graceful shutdown handling
# - Network/system check before start

set -euo pipefail  # Exit on error, undefined variable, pipe failure

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
PID_FILE="$PROJECT_ROOT/surveillance_wrapper.pid"  # Wrapper uses separate PID file
SERVICE_PID_FILE="$PROJECT_ROOT/surveillance_service.pid"  # Python service PID
LOG_FILE="$PROJECT_ROOT/logs/startup.log"
PYTHON_SCRIPT="$PROJECT_ROOT/scripts/orchestration/surveillance_service.py"

# Ensure logs directory exists
mkdir -p "$PROJECT_ROOT/logs"

# Logging function
log() {
    local level=$1
    shift
    local message="$@"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${timestamp} [${level}] ${message}" | tee -a "$LOG_FILE"
}

log_info() {
    log "INFO" "${GREEN}$@${NC}"
}

log_warn() {
    log "WARN" "${YELLOW}$@${NC}"
}

log_error() {
    log "ERROR" "${RED}$@${NC}"
}

# Banner
print_banner() {
    echo ""
    echo "========================================================================"
    echo "🎥 ASE Restaurant Surveillance System v2.0.0"
    echo "========================================================================"
    echo "Project: $PROJECT_ROOT"
    echo "PID File: $PID_FILE"
    echo "Log File: $LOG_FILE"
    echo "========================================================================"
    echo ""
}

# Check if service is running
is_running() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0  # Running
        else
            # Stale PID file
            rm -f "$PID_FILE"
            return 1  # Not running
        fi
    fi
    return 1  # Not running
}

# Get service status
get_status() {
    if is_running; then
        local pid=$(cat "$PID_FILE")
        log_info "✅ Service is RUNNING (PID: $pid)"

        # Show process info
        ps -p "$pid" -o pid,ppid,%cpu,%mem,etime,cmd --no-headers

        return 0
    else
        log_warn "⚠️  Service is NOT running"
        return 1
    fi
}

# Pre-flight checks
preflight_checks() {
    log_info "🔍 Running pre-flight checks..."

    # Check Python
    if ! command -v python3 &> /dev/null; then
        log_error "❌ Python3 not found!"
        exit 1
    fi
    log_info "✅ Python3: $(python3 --version)"

    # Check database
    if [ ! -f "$PROJECT_ROOT/db/detection_data.db" ]; then
        log_warn "⚠️  Database not initialized"
        log_info "Run: python3 scripts/deployment/initialize_restaurant.py"
        read -p "Continue anyway? (y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    else
        log_info "✅ Database exists"
    fi

    # Check models
    if [ ! -f "$PROJECT_ROOT/models/yolov8m.pt" ]; then
        log_error "❌ YOLO model not found!"
        exit 1
    fi
    log_info "✅ Models present"

    # Check disk space
    local free_space=$(df "$PROJECT_ROOT" | awk 'NR==2 {print $4}')
    local free_gb=$((free_space / 1024 / 1024))
    log_info "💾 Free disk space: ${free_gb}GB"

    if [ $free_gb -lt 50 ]; then
        log_warn "⚠️  Low disk space! (< 50GB)"
    fi

    # Check network
    if ping -c 1 -W 2 8.8.8.8 &> /dev/null; then
        log_info "✅ Network connectivity OK"
    else
        log_warn "⚠️  No internet connectivity"
    fi

    log_info "✅ Pre-flight checks complete"
}

# Start service
start_service() {
    print_banner

    # Check if already running
    if is_running; then
        log_error "❌ Service is already running!"
        get_status
        exit 1
    fi

    log_info "🚀 Launching interactive startup wizard..."
    log_info ""

    # Run interactive startup wizard
    if [ "$FOREGROUND" = true ]; then
        # Foreground mode - run wizard interactively
        python3 "$PROJECT_ROOT/interactive_start.py"
    else
        # Background mode - run wizard with auto-accept
        python3 "$PROJECT_ROOT/interactive_start.py"
    fi

    # Check if service started successfully
    sleep 2

    if [ -f "$SERVICE_PID_FILE" ]; then
        local service_pid=$(cat "$SERVICE_PID_FILE")
        log_info ""
        log_info "✅ Service started successfully!"
        log_info "PID: $service_pid"
        log_info ""
        log_info "Management commands:"
        log_info "  ./start.sh --status    # Check status"
        log_info "  ./start.sh --stop      # Stop service"
        log_info "  ./start.sh --logs      # View logs"
    else
        log_warn "⚠️  Wizard exited. Service may not have started."
        log_info "Run './start.sh --status' to check service status"
    fi
}

# Stop service
stop_service() {
    print_banner

    if ! is_running; then
        log_warn "⚠️  Service is not running"
        return 0
    fi

    # First, stop the Python service using its stop command
    if [ -f "$SERVICE_PID_FILE" ]; then
        local service_pid=$(cat "$SERVICE_PID_FILE")
        log_info "🛑 Stopping Python service (PID: $service_pid)..."

        # Send SIGTERM to Python service
        kill -TERM "$service_pid" 2>/dev/null || true

        # Wait up to 15 seconds for Python service to stop
        local count=0
        while [ $count -lt 15 ]; do
            if ! ps -p "$service_pid" > /dev/null 2>&1; then
                break
            fi
            sleep 1
            count=$((count + 1))
        done

        # Force kill if still running
        if ps -p "$service_pid" > /dev/null 2>&1; then
            log_warn "⚠️  Python service didn't stop gracefully, force killing..."
            kill -9 "$service_pid" 2>/dev/null || true
        fi
    fi

    # Now stop the wrapper
    local wrapper_pid=$(cat "$PID_FILE")
    log_info "🛑 Stopping wrapper (PID: $wrapper_pid)..."

    # Try graceful shutdown first
    kill -TERM "$wrapper_pid" 2>/dev/null || true

    # Wait up to 15 seconds for graceful shutdown
    local count=0
    while [ $count -lt 15 ]; do
        if ! ps -p "$wrapper_pid" > /dev/null 2>&1; then
            break
        fi
        sleep 1
        count=$((count + 1))
    done

    # Force kill if still running
    if ps -p "$wrapper_pid" > /dev/null 2>&1; then
        log_warn "⚠️  Wrapper didn't stop gracefully, force killing..."
        kill -9 "$wrapper_pid" 2>/dev/null || true
        sleep 1
    fi

    # Clean up PID files
    rm -f "$PID_FILE"
    rm -f "$SERVICE_PID_FILE"

    # Kill any remaining child processes
    pkill -f "surveillance_service.py" 2>/dev/null || true
    pkill -f "capture_rtsp_streams.py" 2>/dev/null || true

    log_info "✅ Service stopped"
}

# Restart service
restart_service() {
    log_info "🔄 Restarting service..."
    stop_service
    sleep 2
    start_service
}

# View logs
view_logs() {
    if [ -f "$LOG_FILE" ]; then
        echo "========================================"
        echo "📋 Recent Logs (last 50 lines)"
        echo "========================================"
        tail -n 50 "$LOG_FILE"
        echo ""
        echo "========================================"
        echo "Follow logs in real-time:"
        echo "  tail -f $LOG_FILE"
        echo "========================================"
    else
        log_warn "No logs found at $LOG_FILE"
    fi
}

# Main script logic
COMMAND="${1:-start}"
FOREGROUND=false

case "$COMMAND" in
    start|--start)
        start_service
        ;;
    --foreground|-f)
        FOREGROUND=true
        start_service
        ;;
    stop|--stop)
        stop_service
        ;;
    restart|--restart)
        restart_service
        ;;
    status|--status)
        print_banner
        get_status
        ;;
    logs|--logs)
        view_logs
        ;;
    *)
        echo "Usage: $0 {start|--foreground|stop|restart|status|logs}"
        echo ""
        echo "Commands:"
        echo "  start, --start      Start service in background"
        echo "  --foreground, -f    Run in foreground (debug mode)"
        echo "  stop, --stop        Stop service"
        echo "  restart, --restart  Restart service"
        echo "  status, --status    Check service status"
        echo "  logs, --logs        View recent logs"
        exit 1
        ;;
esac
