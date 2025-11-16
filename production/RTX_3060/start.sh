#!/bin/bash
# Modified: 2025-11-16 - Ultimate entry point with crash protection and interactive wizard
# Feature: Auto-restart protection, interactive configuration, systemd integration

# ASE Restaurant Surveillance System - Ultimate Startup Script
# Version: 3.0.0
# Created: 2025-11-16
#
# Purpose:
# - Ultimate entry point for all surveillance operations
# - Interactive wizard for configuration and testing
# - Auto-restart protection for production reliability
# - Systemd service integration
#
# Usage:
#   ./start.sh                    # Interactive mode (wizard + protection)
#   ./start.sh --daemon           # Daemon mode (skip wizard, auto-restart)
#   ./start.sh --status           # Check service status
#   ./start.sh --stop             # Stop service
#   ./start.sh --restart          # Restart service
#   ./start.sh --logs             # View logs
#   ./start.sh --install-systemd  # Install systemd service
#
# Features:
# - Interactive configuration wizard
# - Auto-restart on crash
# - PID file management
# - Graceful shutdown handling
# - Comprehensive logging

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Project paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
PID_FILE="$PROJECT_ROOT/surveillance_service.pid"
LOG_DIR="$PROJECT_ROOT/logs"
LOG_FILE="$LOG_DIR/startup.log"
SERVICE_LOG="$LOG_DIR/surveillance_service.log"
INTERACTIVE_SCRIPT="$PROJECT_ROOT/interactive_start.py"
SERVICE_SCRIPT="$PROJECT_ROOT/scripts/orchestration/surveillance_service.py"

# Ensure logs directory exists
mkdir -p "$LOG_DIR"

# Logging functions
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
    echo "🎥 ASE Restaurant Surveillance System v3.0.0"
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
        ps -p "$pid" -o pid,ppid,%cpu,%mem,etime,cmd --no-headers 2>/dev/null || true

        return 0
    else
        log_warn "⚠️  Service is NOT running"
        return 1
    fi
}

# Check if systemd service is installed
is_systemd_installed() {
    systemctl list-unit-files | grep -q "ase_surveillance.service"
}

# Auto-install systemd if not present
ensure_systemd_installed() {
    if is_systemd_installed; then
        log_info "✅ Systemd service already installed"
        return 0
    fi

    log_warn "⚠️  Systemd service not installed"
    log_info ""
    log_info "For production reliability, this service should be managed by systemd."
    log_info "This provides:"
    log_info "  • Auto-restart on crash"
    log_info "  • Auto-start on system boot"
    log_info "  • OS-level process management"
    log_info "  • Integrated logging (journalctl)"
    log_info ""

    if [ "${DAEMON_MODE:-false}" = "true" ]; then
        # In daemon mode, install automatically without asking
        log_info "Installing systemd service automatically..."
    else
        # In interactive mode, ask for confirmation
        read -p "Install systemd service now? (y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_warn "Systemd not installed. Using shell-based protection instead."
            return 1
        fi
    fi

    # Install systemd
    local systemd_installer="$PROJECT_ROOT/scripts/deployment/install_service.sh"

    if [ ! -f "$systemd_installer" ]; then
        log_error "❌ Systemd installer not found: $systemd_installer"
        return 1
    fi

    log_info ""
    log_info "Installing systemd service (requires sudo)..."
    sudo bash "$systemd_installer"

    if is_systemd_installed; then
        log_info "✅ Systemd service installed successfully!"
        return 0
    else
        log_error "❌ Systemd installation failed"
        return 1
    fi
}

# Start service with crash protection
start_service() {
    print_banner

    # Check if already running
    if is_running; then
        log_error "❌ Service is already running!"
        get_status
        exit 1
    fi

    log_info "🚀 Starting ASE Surveillance System..."
    log_info ""

    # Determine mode
    local skip_wizard=false
    if [ "${DAEMON_MODE:-false}" = "true" ]; then
        skip_wizard=true
        log_info "🤖 Daemon mode: Skipping interactive wizard"
    else
        log_info "🎨 Interactive mode: Running configuration wizard"
    fi

    # Run interactive wizard (unless daemon mode)
    if [ "$skip_wizard" = "false" ]; then
        log_info ""
        log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        log_info "📋 INTERACTIVE CONFIGURATION WIZARD"
        log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        log_info ""

        # Run wizard
        if python3 "$INTERACTIVE_SCRIPT"; then
            log_info ""
            log_info "✅ Interactive wizard completed successfully"
            log_info ""
        else
            local exit_code=$?
            if [ $exit_code -ne 0 ]; then
                log_error "❌ Interactive wizard failed or was cancelled"
                exit $exit_code
            fi
        fi
    fi

    # Ensure systemd is installed (auto-install if needed)
    # Skip if already running under systemd (daemon mode)
    log_info ""
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_info "🛡️  CRASH PROTECTION SETUP"
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_info ""

    local use_systemd=true
    if [ "${DAEMON_MODE:-false}" = "true" ]; then
        # Already running under systemd, skip installation check
        log_info "✅ Running under systemd supervision"
        use_systemd=false  # Use direct mode since systemd already manages us
    elif ! ensure_systemd_installed; then
        use_systemd=false
    fi

    # Start service
    log_info ""
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_info "🚀 STARTING SERVICE"
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_info ""

    if [ "$use_systemd" = true ]; then
        # Start via systemd (best protection)
        log_info "Using systemd for maximum reliability..."
        log_info ""

        sudo systemctl start ase_surveillance

        # Wait for service to start
        sleep 2

        # Check status
        if sudo systemctl is-active --quiet ase_surveillance; then
            log_info ""
            log_info "✅ Service started successfully via systemd!"
            log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            log_info ""
            log_info "Management commands:"
            log_info "  sudo systemctl status ase_surveillance    # Check status"
            log_info "  sudo systemctl stop ase_surveillance      # Stop service"
            log_info "  sudo systemctl restart ase_surveillance   # Restart service"
            log_info ""
            log_info "Enable auto-start on boot:"
            log_info "  sudo systemctl enable ase_surveillance"
            log_info ""
            log_info "View logs:"
            log_info "  sudo journalctl -u ase_surveillance -f"
            log_info "  tail -f $SERVICE_LOG"
            log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            log_info ""
        else
            log_error "❌ Failed to start via systemd"
            log_info "Falling back to shell-based protection..."
            use_systemd=false
        fi
    fi

    # Fallback: Shell-based protection (if systemd not available)
    if [ "$use_systemd" = false ]; then
        start_with_shell_protection
    fi
}

# Shell-based crash protection (fallback)
start_with_shell_protection() {
    log_warn "⚠️  Using shell-based protection (systemd not available)"
    log_info ""

    if [ "${FOREGROUND:-false}" = "true" ]; then
        # Foreground mode (for debugging)
        log_info "Running in foreground mode (Ctrl+C to stop)"
        log_info ""

        # Direct execution with auto-restart
        while true; do
            log_info "Starting surveillance service..."
            python3 "$SERVICE_SCRIPT" start --foreground
            exit_code=$?

            if [ $exit_code -eq 0 ]; then
                log_info "Clean exit (exit code 0), stopping auto-restart"
                break
            fi

            log_warn "⚠️  Service crashed (exit code $exit_code), restarting in 10 seconds..."
            sleep 10
        done
    else
        # Background mode with auto-restart protection
        log_info "Starting in background mode with auto-restart..."
        log_info ""

        # Launch auto-restart daemon
        nohup bash -c '
            PID_FILE="'"$PID_FILE"'"
            LOG_FILE="'"$LOG_FILE"'"
            SERVICE_SCRIPT="'"$SERVICE_SCRIPT"'"

            # Write our own PID
            echo $$ > "$PID_FILE"

            while true; do
                echo "[$(date "+%Y-%m-%d %H:%M:%S")] Starting surveillance service..." >> "$LOG_FILE"

                python3 "$SERVICE_SCRIPT" start
                exit_code=$?

                echo "[$(date "+%Y-%m-%d %H:%M:%S")] Service exited with code: $exit_code" >> "$LOG_FILE"

                # Check if clean exit
                if [ $exit_code -eq 0 ]; then
                    echo "[$(date "+%Y-%m-%d %H:%M:%S")] Clean exit, stopping auto-restart" >> "$LOG_FILE"
                    rm -f "$PID_FILE"
                    break
                fi

                # Check if manually stopped
                if [ ! -f "$PID_FILE" ]; then
                    echo "[$(date "+%Y-%m-%d %H:%M:%S")] PID file removed, stopping auto-restart" >> "$LOG_FILE"
                    break
                fi

                echo "[$(date "+%Y-%m-%d %H:%M:%S")] ⚠️  Crash detected! Restarting in 10 seconds..." >> "$LOG_FILE"
                sleep 10
            done
        ' >> "$LOG_FILE" 2>&1 &

        local wrapper_pid=$!

        # Wait for service to start
        sleep 3

        # Verify it started
        if is_running; then
            local pid=$(cat "$PID_FILE")
            log_info ""
            log_info "✅ Service started successfully!"
            log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            log_info "PID: $pid (auto-restart wrapper)"
            log_info ""
            log_info "Management commands:"
            log_info "  ./start.sh --status     # Check service status"
            log_info "  ./start.sh --stop       # Stop service"
            log_info "  ./start.sh --restart    # Restart service"
            log_info "  ./start.sh --logs       # View logs"
            log_info ""
            log_info "Log files:"
            log_info "  Startup:    $LOG_FILE"
            log_info "  Service:    $SERVICE_LOG"
            log_info ""
            log_info "Real-time monitoring:"
            log_info "  tail -f $SERVICE_LOG"
            log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            log_info ""
        else
            log_error "❌ Failed to start service!"
            log_error "Check logs: $LOG_FILE"
            exit 1
        fi
    fi
}

# Stop service
stop_service() {
    print_banner

    if ! is_running; then
        log_warn "⚠️  Service is not running"
        return 0
    fi

    local pid=$(cat "$PID_FILE")
    log_info "🛑 Stopping service (PID: $pid)..."

    # Remove PID file first (stops auto-restart loop)
    rm -f "$PID_FILE"

    # Try graceful shutdown
    kill -TERM "$pid" 2>/dev/null || true

    # Wait up to 30 seconds for graceful shutdown
    local count=0
    while [ $count -lt 30 ]; do
        if ! ps -p "$pid" > /dev/null 2>&1; then
            break
        fi
        sleep 1
        count=$((count + 1))
    done

    # Force kill if still running
    if ps -p "$pid" > /dev/null 2>&1; then
        log_warn "⚠️  Graceful shutdown failed, force killing..."
        kill -9 "$pid" 2>/dev/null || true
        sleep 1
    fi

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
    if [ -f "$SERVICE_LOG" ]; then
        echo "========================================"
        echo "📋 Service Logs (last 50 lines)"
        echo "========================================"
        tail -n 50 "$SERVICE_LOG"
        echo ""
        echo "========================================"
        echo "Follow logs in real-time:"
        echo "  tail -f $SERVICE_LOG"
        echo "========================================"
    else
        log_warn "No service logs found at $SERVICE_LOG"
    fi
}

# Install systemd service
install_systemd() {
    print_banner

    log_info "📦 Installing systemd service..."
    log_info ""

    local systemd_installer="$PROJECT_ROOT/scripts/deployment/install_service.sh"

    if [ ! -f "$systemd_installer" ]; then
        log_error "❌ Systemd installer not found: $systemd_installer"
        exit 1
    fi

    # Run installer
    sudo bash "$systemd_installer"

    log_info ""
    log_info "✅ Systemd service installed successfully!"
    log_info ""
    log_info "Service management commands:"
    log_info "  sudo systemctl start ase_surveillance      # Start service"
    log_info "  sudo systemctl stop ase_surveillance       # Stop service"
    log_info "  sudo systemctl restart ase_surveillance    # Restart service"
    log_info "  sudo systemctl status ase_surveillance     # Check status"
    log_info "  sudo systemctl enable ase_surveillance     # Auto-start on boot"
    log_info "  sudo systemctl disable ase_surveillance    # Disable auto-start"
    log_info ""
    log_info "View logs:"
    log_info "  sudo journalctl -u ase_surveillance -f"
    log_info ""
}

# Main script logic
COMMAND="${1:-start}"
DAEMON_MODE=false
FOREGROUND=false

# Parse arguments
case "$COMMAND" in
    start|--start)
        start_service
        ;;
    --daemon|-d)
        DAEMON_MODE=true
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
        echo "ASE Restaurant Surveillance System v3.0.0"
        echo ""
        echo "Usage: $0 {COMMAND} [OPTIONS]"
        echo ""
        echo "Commands:"
        echo "  start, --start           Start service (auto-installs systemd if needed)"
        echo "  --daemon, -d             Start in daemon mode (skip wizard)"
        echo "  --foreground, -f         Run in foreground (debug mode)"
        echo "  stop, --stop             Stop service"
        echo "  restart, --restart       Restart service"
        echo "  status, --status         Check service status"
        echo "  logs, --logs             View recent logs"
        echo ""
        echo "Examples:"
        echo "  $0                       # Interactive start (auto-protection)"
        echo "  $0 --daemon              # Daemon start (no wizard)"
        echo "  $0 --status              # Check if running"
        echo ""
        echo "Note: Systemd protection is installed automatically on first run"
        echo ""
        exit 1
        ;;
esac
