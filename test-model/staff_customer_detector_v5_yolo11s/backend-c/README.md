# SmartICE Backend - C++ High-Performance Server

Production-ready C++ backend for SmartICE video surveillance and inference system.

## Features

- **HTTP Server**: Simple HTTP/1.1 server with route handling (HTTP/2 ready with nghttp2)
- **Thread Pool**: Lock-free task queue with configurable worker threads
- **Lock-Free Queue**: High-performance concurrent queue for frame processing
- **Logging**: Structured logging with spdlog (console + rotating file)
- **Video Decoding**: FFmpeg + NVDEC integration (stub, ready for implementation)
- **Inference**: TensorRT integration (stub, ready for implementation)

## Project Structure

```
backend-c/
├── CMakeLists.txt              # Main build configuration
├── src/
│   ├── main.cpp                # Server entry point
│   ├── http_server.cpp         # HTTP server implementation
│   ├── video_decoder.cpp       # FFmpeg wrapper (stub)
│   ├── inference_engine.cpp    # TensorRT wrapper (stub)
│   ├── thread_pool.cpp         # Thread pool implementation
│   └── utils.cpp               # Logging and utilities
├── include/
│   ├── http_server.h
│   ├── video_decoder.h
│   ├── inference_engine.h
│   ├── thread_pool.h
│   ├── lockfree_queue.hpp      # Header-only lock-free queue
│   └── utils.h
├── tests/
│   ├── CMakeLists.txt
│   ├── test_http_server.cpp
│   ├── test_thread_pool.cpp
│   └── test_lockfree_queue.cpp
└── third_party/                # FetchContent dependencies
```

## Dependencies

### Required (Auto-Downloaded via FetchContent)
- **spdlog** (v1.12.0) - Logging library
- **nlohmann/json** (v3.11.3) - JSON parsing

### Optional (System Packages)
- **nghttp2** - HTTP/2 support (not required for basic HTTP/1.1)
- **libevent** - Event-driven I/O (not required for basic server)
- **FFmpeg** - Video decoding (libavcodec, libavformat, libavutil)
- **CUDA** - GPU acceleration for NVDEC
- **TensorRT** - Inference engine

## Installation

### Install CMake (if not installed)

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y cmake build-essential

# Verify installation
cmake --version  # Should be 3.18 or higher
```

### Install Optional Dependencies (Ubuntu/Debian)

```bash
# HTTP/2 support (optional)
sudo apt-get install -y libnghttp2-dev libevent-dev

# FFmpeg (optional, for video decoding)
sudo apt-get install -y libavcodec-dev libavformat-dev libavutil-dev

# CUDA (optional, for GPU acceleration)
# Follow NVIDIA CUDA installation guide

# TensorRT (optional, for inference)
# Follow NVIDIA TensorRT installation guide
```

## Build Instructions

### Quick Start (Basic Build)

```bash
cd /home/smartice001/smartice/ASEOfSmartICE/test-model/staff_customer_detector_v5_yolo11s/backend-c

# Create build directory
mkdir build && cd build

# Configure and build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j$(nproc)

# Run tests
ctest --verbose

# Run server
./smartice_server
```

### Build with Specific Options

```bash
# Debug build with verbose output
cmake .. -DCMAKE_BUILD_TYPE=Debug
make -j$(nproc) VERBOSE=1

# Release build with optimizations
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j$(nproc)
```

### Install (Optional)

```bash
sudo make install
```

This installs:
- Binary: `/usr/local/bin/smartice_server`
- Library: `/usr/local/lib/libsmartice_backend.a`
- Headers: `/usr/local/include/smartice/`

## Running the Server

### Basic Usage

```bash
# Default port 8001
./smartice_server

# Custom port
./smartice_server 9000
```

### Test Endpoints

```bash
# Hello message
curl http://localhost:8001/

# Health check (JSON)
curl http://localhost:8001/api/health

# Server statistics (JSON)
curl http://localhost:8001/api/stats
```

### Expected Output

```bash
$ curl http://localhost:8001/
Hello from C++ Backend

$ curl http://localhost:8001/api/health
{
  "service": "SmartICE Backend",
  "status": "ok",
  "timestamp": "2025-12-27 19:55:00",
  "version": "1.0.0"
}

$ curl http://localhost:8001/api/stats
{
  "thread_pool": {
    "num_threads": 8,
    "pending_tasks": 0
  },
  "timestamp": "2025-12-27 19:55:30"
}
```

## Testing

### Run All Tests

```bash
cd build
ctest --verbose
```

### Run Individual Tests

```bash
# HTTP server test
./tests/test_http_server

# Thread pool test
./tests/test_thread_pool

# Lock-free queue test
./tests/test_lockfree_queue
```

### Expected Test Output

```
Test 1: PASSED - Got expected response
Test 2: PASSED - Got 404 as expected

All HTTP server tests passed!
```

## Performance

### Thread Pool
- Configurable worker threads (defaults to CPU core count)
- Lock-free task queue
- Future-based task results
- Exception handling per task

### Lock-Free Queue
- Michael-Scott algorithm
- Atomic operations only (no mutexes)
- Supports concurrent producers and consumers
- Tested with 4 producers × 4 consumers × 1000 items

### HTTP Server
- Simple HTTP/1.1 implementation
- Blocking I/O (can upgrade to libevent for async)
- Route-based request handling
- JSON response support

## Development Status

### Implemented ✅
- [x] HTTP/1.1 server with routing
- [x] Thread pool with futures
- [x] Lock-free queue
- [x] Logging system (console + file)
- [x] Build system (CMake)
- [x] Unit tests (CTest)
- [x] JSON serialization

### Stub/TODO 🚧
- [ ] FFmpeg video decoding (header-only stub)
- [ ] NVDEC GPU acceleration
- [ ] TensorRT inference engine
- [ ] HTTP/2 upgrade (requires nghttp2)
- [ ] WebSocket support
- [ ] Async I/O with libevent

## Troubleshooting

### CMake Not Found

```bash
sudo apt-get install cmake
```

### Missing Dependencies

Check CMake output for missing dependencies. The project will build with basic features even without optional dependencies.

```bash
cmake .. | grep "found"
```

### Port Already in Use

```bash
# Check what's using the port
sudo lsof -i :8001

# Use a different port
./smartice_server 8002
```

### Build Errors

```bash
# Clean build
cd build
rm -rf *
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j$(nproc)
```

## License

Internal SmartICE project. All rights reserved.

## Contact

For issues or questions, contact the SmartICE development team.
