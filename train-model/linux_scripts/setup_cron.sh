#!/bin/bash
# Version: 1.0
# Setup script for camera capture cron job

echo "====================================="
echo "Camera Capture Cron Setup"
echo "====================================="

# Get the absolute path to the wrapper script
SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/camera_capture_wrapper.sh"

if [ ! -f "$SCRIPT_PATH" ]; then
    echo "ERROR: Wrapper script not found at $SCRIPT_PATH"
    exit 1
fi

# Create the cron entry
# Runs every hour from 11 AM to 9 PM (to ensure coverage until 10 PM with 2-hour runtime)
CRON_ENTRY="0 11,13,15,17,19,21 * * * $SCRIPT_PATH"

echo ""
echo "This will add the following cron job:"
echo "$CRON_ENTRY"
echo ""
echo "Schedule explanation:"
echo "- Runs at: 11:00 AM, 1:00 PM, 3:00 PM, 5:00 PM, 7:00 PM, 9:00 PM"
echo "- Each run captures for up to 2 hours"
echo "- Ensures continuous coverage from 11 AM to 10 PM"
echo ""

read -p "Do you want to add this cron job? (y/n): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Check if cron entry already exists
    if crontab -l 2>/dev/null | grep -q "$SCRIPT_PATH"; then
        echo "WARNING: Cron job already exists for this script!"
        echo "Current entry:"
        crontab -l | grep "$SCRIPT_PATH"
        echo ""
        read -p "Do you want to replace it? (y/n): " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            # Remove old entry and add new one
            (crontab -l 2>/dev/null | grep -v "$SCRIPT_PATH"; echo "$CRON_ENTRY") | crontab -
            echo "✅ Cron job updated successfully!"
        else
            echo "❌ Cron job not modified."
            exit 0
        fi
    else
        # Add new cron entry
        (crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -
        echo "✅ Cron job added successfully!"
    fi

    echo ""
    echo "Current crontab:"
    echo "----------------"
    crontab -l | grep "$SCRIPT_PATH"
    echo ""
    echo "To remove this cron job later, run:"
    echo "crontab -e"
    echo "And delete the line containing: $SCRIPT_PATH"
    echo ""
    echo "To monitor the capture logs:"
    echo "tail -f /var/log/camera_capture/capture_$(date +%Y%m%d).log"
    echo "Or if using local logs:"
    echo "tail -f $(dirname "$SCRIPT_PATH")/logs/capture_$(date +%Y%m%d).log"
else
    echo "❌ Cron job not added."
    echo ""
    echo "To manually add the cron job later, run:"
    echo "crontab -e"
    echo "And add this line:"
    echo "$CRON_ENTRY"
fi

echo ""
echo "====================================="
echo "Setup complete!"
echo "====================================="