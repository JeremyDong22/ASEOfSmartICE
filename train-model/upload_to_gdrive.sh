#!/bin/bash
# Google Drive Upload Helper for Train-Model Data
# Version: 1.0.0
# Last Updated: 2025-11-11
#
# Purpose: Upload training data, models, and results to Google Drive
#
# Usage:
#   ./upload_to_gdrive.sh <local_path> [remote_path]
#
# Examples:
#   ./upload_to_gdrive.sh model_v3/raw_images/
#   ./upload_to_gdrive.sh model_v3/models/ SmartICE/models/v3
#   ./upload_to_gdrive.sh model_v3/dataset/train/ SmartICE/datasets/v3/train

set -e  # Exit on error

# Configuration
GDRIVE_REMOTE="gdrive"  # Name of your rclone remote (change if different)
DEFAULT_REMOTE_BASE="SmartICE"  # Default base folder in Google Drive

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
    print_error "Usage: $0 <local_path> [remote_path]"
    echo ""
    echo "Examples:"
    echo "  $0 model_v3/raw_images/"
    echo "  $0 model_v3/models/ SmartICE/models/v3"
    echo "  $0 extracted-persons/ SmartICE/extracted/camera_35"
    exit 1
fi

LOCAL_PATH="$1"
REMOTE_PATH="${2:-${DEFAULT_REMOTE_BASE}/$(basename "$LOCAL_PATH")}"

# Validate local path exists
if [ ! -e "$LOCAL_PATH" ]; then
    print_error "Local path does not exist: $LOCAL_PATH"
    exit 1
fi

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Convert to absolute path if relative
if [[ "$LOCAL_PATH" != /* ]]; then
    LOCAL_PATH="${SCRIPT_DIR}/${LOCAL_PATH}"
fi

# Display upload plan
echo "=========================================="
print_info "Google Drive Upload Plan"
echo "=========================================="
echo "Local:  $LOCAL_PATH"
echo "Remote: ${GDRIVE_REMOTE}:/${REMOTE_PATH}"
echo ""

# Check size
if [ -d "$LOCAL_PATH" ]; then
    SIZE=$(du -sh "$LOCAL_PATH" | cut -f1)
    print_info "Directory size: $SIZE"

    # Count files
    FILE_COUNT=$(find "$LOCAL_PATH" -type f | wc -l | tr -d ' ')
    print_info "Total files: $FILE_COUNT"
elif [ -f "$LOCAL_PATH" ]; then
    SIZE=$(du -sh "$LOCAL_PATH" | cut -f1)
    print_info "File size: $SIZE"
fi

echo ""
read -p "Proceed with upload? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_warning "Upload cancelled"
    exit 0
fi

# Perform upload
print_info "Starting upload..."
echo ""

# Use rclone copy (doesn't delete files in destination)
rclone copy "$LOCAL_PATH" "${GDRIVE_REMOTE}:/${REMOTE_PATH}" \
    --progress \
    --transfers 4 \
    --stats 5s \
    --exclude ".DS_Store" \
    --exclude "*.tmp" \
    --exclude "__pycache__/" \
    --exclude "*.pyc"

if [ $? -eq 0 ]; then
    echo ""
    print_info "Upload completed successfully!"
    print_info "Remote location: ${GDRIVE_REMOTE}:/${REMOTE_PATH}"
else
    echo ""
    print_error "Upload failed!"
    exit 1
fi
