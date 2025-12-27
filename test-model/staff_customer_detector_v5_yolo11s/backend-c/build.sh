#!/bin/bash
# Build script for SmartICE Backend

set -e

echo "===================================================="
echo "SmartICE Backend Build Script"
echo "===================================================="
echo ""

# Check for CMake
if ! command -v cmake &> /dev/null; then
    echo "ERROR: CMake is not installed!"
    echo ""
    echo "Please install CMake first:"
    echo "  sudo apt-get update"
    echo "  sudo apt-get install -y cmake build-essential"
    echo ""
    exit 1
fi

# Check CMake version
CMAKE_VERSION=$(cmake --version | head -1 | awk '{print $3}')
echo "Found CMake version: $CMAKE_VERSION"

# Check for g++
if ! command -v g++ &> /dev/null; then
    echo "ERROR: g++ is not installed!"
    echo ""
    echo "Please install build tools:"
    echo "  sudo apt-get install -y build-essential"
    echo ""
    exit 1
fi

G++_VERSION=$(g++ --version | head -1)
echo "Found compiler: $G++_VERSION"
echo ""

# Create build directory
BUILD_DIR="build"
if [ ! -d "$BUILD_DIR" ]; then
    echo "Creating build directory..."
    mkdir -p "$BUILD_DIR"
fi

cd "$BUILD_DIR"

# Configure
echo "===================================================="
echo "Configuring project..."
echo "===================================================="
cmake .. -DCMAKE_BUILD_TYPE=Release

# Build
echo ""
echo "===================================================="
echo "Building project..."
echo "===================================================="
make -j$(nproc)

# Test
echo ""
echo "===================================================="
echo "Running tests..."
echo "===================================================="
ctest --verbose

echo ""
echo "===================================================="
echo "Build complete!"
echo "===================================================="
echo ""
echo "Run the server with:"
echo "  ./smartice_server"
echo ""
echo "Test endpoints:"
echo "  curl http://localhost:8001/"
echo "  curl http://localhost:8001/api/health"
echo "  curl http://localhost:8001/api/stats"
echo ""
