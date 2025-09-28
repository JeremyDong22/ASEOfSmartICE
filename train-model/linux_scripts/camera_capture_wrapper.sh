#!/bin/bash
# Version: 1.1
# Camera capture automation wrapper for Linux cron execution
# Manages Python script execution from 11am to 10pm with 2-hour segments
# Now supports resilient version with local backup queue

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Use resilient version by default (change to non-resilient if needed)
PYTHON_SCRIPT="$SCRIPT_DIR/linux_capture_screenshots_to_supabase_resilient.py"
PID_FILE="/tmp/camera_capture.pid"
LOG_DIR="/var/log/camera_capture"
LOG_FILE="$LOG_DIR/capture_$(date +%Y%m%d).log"
ERROR_LOG="$LOG_DIR/errors_$(date +%Y%m%d).log"
PYTHON_CMD="python3"

# Time configuration
START_HOUR=11  # 11 AM
STOP_HOUR=22   # 10 PM

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR" 2>/dev/null || {
    # If /var/log is not writable, use local directory
    LOG_DIR="$SCRIPT_DIR/logs"
    mkdir -p "$LOG_DIR"
    LOG_FILE="$LOG_DIR/capture_$(date +%Y%m%d).log"
    ERROR_LOG="$LOG_DIR/errors_$(date +%Y%m%d).log"
}

# Function to log messages
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Function to check if process is running
is_running() {
    if [ -f "$PID_FILE" ]; then
        OLD_PID=$(cat "$PID_FILE")
        if ps -p "$OLD_PID" > /dev/null 2>&1; then
            return 0  # Process is running
        else
            # Stale PID file
            rm -f "$PID_FILE"
            return 1
        fi
    fi
    return 1  # No PID file or process not running
}

# Function to check current time
should_run() {
    # Temporarily bypass time check for testing
    return 0  # Always should run for testing

    CURRENT_HOUR=$(date +%H | sed 's/^0//')  # Remove leading zero

    if [ "$CURRENT_HOUR" -ge "$START_HOUR" ] && [ "$CURRENT_HOUR" -lt "$STOP_HOUR" ]; then
        return 0  # Should run
    else
        return 1  # Should not run
    fi
}

# Function to start the capture process
start_capture() {
    log_message "Starting camera capture process..."

    # Check Python installation
    if ! command -v $PYTHON_CMD &> /dev/null; then
        log_message "ERROR: Python3 not found!"
        exit 1
    fi

    # Check if script exists
    if [ ! -f "$PYTHON_SCRIPT" ]; then
        log_message "ERROR: Python script not found at $PYTHON_SCRIPT"
        exit 1
    fi

    # Check disk space (require at least 1GB free)
    AVAILABLE_SPACE=$(df "$SCRIPT_DIR" | awk 'NR==2 {print $4}')
    if [ "$AVAILABLE_SPACE" -lt 1048576 ]; then  # 1GB in KB
        log_message "WARNING: Low disk space! Available: ${AVAILABLE_SPACE}KB"
    fi

    # Start the Python script in background
    cd "$SCRIPT_DIR"
    nohup $PYTHON_CMD "$PYTHON_SCRIPT" >> "$LOG_FILE" 2>> "$ERROR_LOG" &

    # Save PID
    PYTHON_PID=$!
    echo $PYTHON_PID > "$PID_FILE"

    log_message "Camera capture started with PID: $PYTHON_PID"

    # Verify process started successfully
    sleep 2
    if ps -p $PYTHON_PID > /dev/null; then
        log_message "Process verified running successfully"
    else
        log_message "ERROR: Process failed to start!"
        rm -f "$PID_FILE"
        exit 1
    fi
}

# Function to stop the capture process
stop_capture() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        log_message "Stopping camera capture process (PID: $PID)..."

        # Send SIGTERM for graceful shutdown
        kill -TERM "$PID" 2>/dev/null

        # Wait for process to terminate (max 10 seconds)
        for i in {1..10}; do
            if ! ps -p "$PID" > /dev/null 2>&1; then
                break
            fi
            sleep 1
        done

        # Force kill if still running
        if ps -p "$PID" > /dev/null 2>&1; then
            log_message "Force killing process..."
            kill -9 "$PID" 2>/dev/null
        fi

        rm -f "$PID_FILE"
        log_message "Camera capture stopped"
    fi
}

# Main execution
main() {
    log_message "========================================="
    log_message "Camera capture wrapper started"
    log_message "Current time: $(date)"

    # Check if we should be running at this time
    if ! should_run; then
        log_message "Outside operating hours (11 AM - 10 PM). Exiting."

        # Stop any running process if it's after hours
        if is_running; then
            log_message "Found running process outside hours. Stopping..."
            stop_capture
        fi
        exit 0
    fi

    # Check if already running
    if is_running; then
        log_message "Camera capture is already running. Checking health..."

        # The Python script will auto-exit after 2 hours
        # This allows cron to restart it for continuous operation
        log_message "Process is healthy. Exiting wrapper."
    else
        log_message "No running process found. Starting new capture session..."
        start_capture
    fi

    log_message "Camera capture wrapper completed"
    log_message "========================================="
}

# Handle script termination
trap 'log_message "Wrapper script interrupted"; exit 1' INT TERM

# Run main function
main

# Exit successfully
exit 0