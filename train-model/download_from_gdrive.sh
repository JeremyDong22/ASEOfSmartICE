#!/bin/bash
# Google Drive Download Helper for Train-Model Data
# Version: 1.0.0
# Last Updated: 2025-11-11
#
# Purpose: Download training data from Google Drive to local machine
#
# Usage:
#   ./download_from_gdrive.sh <remote_path> [local_path]
#
# Examples:
#   ./download_from_gdrive.sh SmartICE/raw_images/ model_v3/raw_images/
#   ./download_from_gdrive.sh SmartICE/models/v3 model_v3/models/
#   ./download_from_gdrive.sh SmartICE/datasets/v3/train model_v3/dataset/train/

set -e  # Exit on error

# Configuration
GDRIVE_REMOTE="gdrive"  # Name of your rclone remote (change if different)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored messages
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check if rclone is installed
if ! command -v rclone &> /dev/null; then
    print_error "rclone is not installed!"
    echo "Please install it first:"
    echo "  macOS: brew install rclone"
    echo "  Linux: curl https://rclone.org/install.sh | sudo bash"
    exit 1
fi

# Check if rclone is configured
if ! rclone listremotes | grep -q "^${GDRIVE_REMOTE}:$"; then
    print_error "Google Drive remote '${GDRIVE_REMOTE}' is not configured!"
    echo "Please run: rclone config"
    echo "See google-drive-setup.md for detailed instructions"
    exit 1
fi

# Check arguments
if [ $# -lt 1 ]; then
    print_error "Usage: $0 <remote_path> [local_path]"
    echo ""
    echo "Examples:"
    echo "  $0 SmartICE/raw_images/ model_v3/raw_images/"
    echo "  $0 SmartICE/models/v3 model_v3/models/"
    echo "  $0 SmartICE/datasets/v3/train model_v3/dataset/train/"
    exit 1
fi

REMOTE_PATH="$1"
LOCAL_PATH="${2:-$(basename "$REMOTE_PATH")}"

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Convert to absolute path if relative
if [[ "$LOCAL_PATH" != /* ]]; then
    LOCAL_PATH="${SCRIPT_DIR}/${LOCAL_PATH}"
fi

# Display download plan
echo "=========================================="
print_info "Google Drive Download Plan"
echo "=========================================="
echo "Remote: ${GDRIVE_REMOTE}:/${REMOTE_PATH}"
echo "Local:  $LOCAL_PATH"
echo ""

# Check if remote path exists
print_info "Checking remote path..."
if ! rclone lsf "${GDRIVE_REMOTE}:/${REMOTE_PATH}" &>/dev/null; then
    print_error "Remote path does not exist: ${GDRIVE_REMOTE}:/${REMOTE_PATH}"
    echo ""
    print_info "Available paths in ${GDRIVE_REMOTE}:/"
    rclone lsd "${GDRIVE_REMOTE}:/" | head -20
    exit 1
fi

# Get remote size
print_info "Calculating remote size..."
SIZE_INFO=$(rclone size "${GDRIVE_REMOTE}:/${REMOTE_PATH}" 2>/dev/null || echo "Size calculation failed")
echo "$SIZE_INFO"
echo ""

# Create local directory if it doesn't exist
mkdir -p "$LOCAL_PATH"

echo ""
read -p "Proceed with download? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_warning "Download cancelled"
    exit 0
fi

# Perform download
print_info "Starting download..."
echo ""

# Use rclone copy (doesn't delete files in destination)
rclone copy "${GDRIVE_REMOTE}:/${REMOTE_PATH}" "$LOCAL_PATH" \
    --progress \
    --transfers 4 \
    --stats 5s \
    --exclude ".DS_Store" \
    --exclude "*.tmp" \
    --exclude "__pycache__/" \
    --exclude "*.pyc"

if [ $? -eq 0 ]; then
    echo ""
    print_info "Download completed successfully!"
    print_info "Local location: $LOCAL_PATH"

    # Show what was downloaded
    if [ -d "$LOCAL_PATH" ]; then
        FILE_COUNT=$(find "$LOCAL_PATH" -type f | wc -l | tr -d ' ')
        LOCAL_SIZE=$(du -sh "$LOCAL_PATH" | cut -f1)
        print_info "Downloaded: $FILE_COUNT files ($LOCAL_SIZE)"
    fi
else
    echo ""
    print_error "Download failed!"
    exit 1
fi
