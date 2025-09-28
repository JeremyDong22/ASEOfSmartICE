#!/bin/bash
# Created: 2025-09-28 - Camera surveillance master controller with hourly health checks
# All-in-one script that manages cron, wrapper, and continuous monitoring
# Hourly cron checks with time-based control and self-healing capabilities

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WRAPPER_SCRIPT="$SCRIPT_DIR/camera_capture_wrapper.sh"
MASTER_PID_FILE="/tmp/camera_master.pid"
LOG_DIR="$SCRIPT_DIR/logs"
MASTER_LOG="$LOG_DIR/master_$(date +%Y%m%d).log"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Function to log messages
log_master() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] MASTER: $1" | tee -a "$MASTER_LOG"
}

# Function to check if we're already running
check_master_running() {
    if [ -f "$MASTER_PID_FILE" ]; then
        OLD_PID=$(cat "$MASTER_PID_FILE")
        if ps -p "$OLD_PID" > /dev/null 2>&1; then
            echo "Camera surveillance master is already running (PID: $OLD_PID)"
            exit 1
        else
            rm -f "$MASTER_PID_FILE"
        fi
    fi
}

# Function to cleanup on exit
cleanup_master() {
    log_master "Master controller shutting down..."

    # Kill any running camera processes
    pkill -f "linux_capture_screenshots_to_supabase_resilient.py" 2>/dev/null

    # Remove PID file
    rm -f "$MASTER_PID_FILE"

    log_master "Master controller stopped"
    exit 0
}

# Function to kill existing processes
kill_existing_processes() {
    log_master "Cleaning up existing camera processes..."

    # Kill Python capture script
    pkill -f "linux_capture_screenshots_to_supabase_resilient.py" && \
        log_master "Killed existing Python capture process"

    # Kill wrapper processes
    pkill -f "camera_capture_wrapper.sh" && \
        log_master "Killed existing wrapper processes"

    # Remove old PID files
    rm -f /tmp/camera_capture.pid /tmp/camera_master.pid

    # Remove cron job
    (crontab -l | grep -v "camera_capture_wrapper.sh") | crontab - 2>/dev/null && \
        log_master "Removed existing cron job"

    sleep 3
    log_master "Cleanup completed"
}

# Function to install cron job
install_cron() {
    log_master "Installing smart cron job (every hour: 11-21)..."

    # Add our cron job - runs every hour from 11 AM to 9 PM
    (crontab -l 2>/dev/null | grep -v "camera_capture_wrapper.sh"; \
     echo "0 11-21 * * * $WRAPPER_SCRIPT") | crontab -

    log_master "Cron job installed successfully"
}

# Function to monitor and maintain the system
monitor_system() {
    log_master "Starting continuous monitoring system..."

    while true; do
        CURRENT_HOUR=$(date +%H | sed 's/^0//')

        # Check if we're in operating hours (11 AM - 10 PM)
        if [ "$CURRENT_HOUR" -ge 11 ] && [ "$CURRENT_HOUR" -lt 22 ]; then

            # Check if capture process is running
            if ! pgrep -f "linux_capture_screenshots_to_supabase_resilient.py" > /dev/null; then
                log_master "No capture process detected during operating hours. Starting recovery..."

                # Run wrapper script to start capture
                "$WRAPPER_SCRIPT" >> "$MASTER_LOG" 2>&1

                # Wait and verify
                sleep 5
                if pgrep -f "linux_capture_screenshots_to_supabase_resilient.py" > /dev/null; then
                    log_master "Recovery successful - capture process restarted"
                else
                    log_master "WARNING: Recovery failed - capture process not started"
                fi
            fi

            # Check every 5 minutes during operating hours
            sleep 300
        else
            # Outside operating hours - check every 30 minutes
            sleep 1800
        fi
    done
}

# Function to start the master system
start_master() {
    check_master_running

    # Save our PID
    echo $$ > "$MASTER_PID_FILE"

    log_master "==========================================="
    log_master "Camera Surveillance Master Controller"
    log_master "Hourly health checks with time-based control"
    log_master "Starting comprehensive surveillance system..."
    log_master "==========================================="

    # Setup signal handlers
    trap cleanup_master INT TERM EXIT

    # Phase 1: Clean existing processes
    kill_existing_processes

    # Phase 2: Install smart cron job
    install_cron

    # Phase 3: Start initial capture if in operating hours
    CURRENT_HOUR=$(date +%H | sed 's/^0//')
    if [ "$CURRENT_HOUR" -ge 11 ] && [ "$CURRENT_HOUR" -lt 22 ]; then
        log_master "In operating hours - starting initial capture session..."
        "$WRAPPER_SCRIPT" >> "$MASTER_LOG" 2>&1
        sleep 3
    else
        log_master "Outside operating hours - system ready for next session"
    fi

    # Phase 4: Start monitoring system
    log_master "System initialization complete. Beginning monitoring..."
    monitor_system
}

# Main execution
case "${1:-start}" in
    start)
        start_master
        ;;
    stop)
        if [ -f "$MASTER_PID_FILE" ]; then
            MASTER_PID=$(cat "$MASTER_PID_FILE")
            log_master "Stopping master controller (PID: $MASTER_PID)..."
            kill -TERM "$MASTER_PID" 2>/dev/null
            sleep 2
            if ps -p "$MASTER_PID" > /dev/null 2>&1; then
                kill -9 "$MASTER_PID" 2>/dev/null
            fi
            rm -f "$MASTER_PID_FILE"
            log_master "Master controller stopped"
        else
            echo "Master controller is not running"
        fi
        ;;
    status)
        if [ -f "$MASTER_PID_FILE" ]; then
            MASTER_PID=$(cat "$MASTER_PID_FILE")
            if ps -p "$MASTER_PID" > /dev/null 2>&1; then
                echo "Master controller is running (PID: $MASTER_PID)"

                # Check capture process
                if pgrep -f "linux_capture_screenshots_to_supabase_resilient.py" > /dev/null; then
                    CAPTURE_PID=$(pgrep -f "linux_capture_screenshots_to_supabase_resilient.py")
                    echo "Capture process is running (PID: $CAPTURE_PID)"
                else
                    echo "Capture process is not running"
                fi
            else
                echo "Master controller PID file exists but process is not running"
                rm -f "$MASTER_PID_FILE"
            fi
        else
            echo "Master controller is not running"
        fi
        ;;
    restart)
        $0 stop
        sleep 3
        $0 start
        ;;
    *)
        echo "Usage: $0 {start|stop|status|restart}"
        echo "  start   - Start the master surveillance system"
        echo "  stop    - Stop all camera surveillance processes"
        echo "  status  - Check system status"
        echo "  restart - Restart the entire system"
        exit 1
        ;;
esac