#!/bin/bash
# Install dependencies for SmartICE Backend

echo "===================================================="
echo "SmartICE Backend - Dependency Installation"
echo "===================================================="
echo ""
echo "This script will install required dependencies."
echo "Sudo password will be required."
echo ""

# Update package list
echo "Updating package list..."
sudo apt-get update

# Install required dependencies
echo ""
echo "Installing required dependencies..."
echo "  - cmake (build system)"
echo "  - build-essential (g++, make, etc.)"
echo ""
sudo apt-get install -y cmake build-essential

# Check if user wants optional dependencies
echo ""
echo "===================================================="
echo "Optional Dependencies"
echo "===================================================="
echo ""
echo "The following are optional but enable advanced features:"
echo "  - libnghttp2-dev (HTTP/2 support)"
echo "  - libevent-dev (async I/O)"
echo "  - FFmpeg dev libraries (video decoding)"
echo ""
read -p "Install optional dependencies? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "Installing optional dependencies..."
    sudo apt-get install -y libnghttp2-dev libevent-dev
    sudo apt-get install -y libavcodec-dev libavformat-dev libavutil-dev || true
    echo "Optional dependencies installed (some may have failed - this is OK)"
fi

echo ""
echo "===================================================="
echo "Installation Complete!"
echo "===================================================="
echo ""
echo "Verify installation:"
echo "  cmake --version"
echo "  g++ --version"
echo ""
echo "Build the project with:"
echo "  cd backend-c"
echo "  ./build.sh"
echo ""
