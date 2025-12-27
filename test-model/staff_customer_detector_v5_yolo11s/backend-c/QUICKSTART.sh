#!/bin/bash
# Quick Start Guide - SmartICE Backend

cat << 'EOF'
╔══════════════════════════════════════════════════════════════╗
║         SmartICE Backend - Quick Start Guide                 ║
╚══════════════════════════════════════════════════════════════╝

📁 Project Location:
   /home/smartice001/smartice/ASEOfSmartICE/test-model/staff_customer_detector_v5_yolo11s/backend-c/

═══════════════════════════════════════════════════════════════

🚀 STEP 1: Install Dependencies

   cd backend-c
   ./install_deps.sh

   This will install:
   ✓ CMake (build system)
   ✓ build-essential (g++, make)
   ✓ Optional: nghttp2, FFmpeg (if you choose)

═══════════════════════════════════════════════════════════════

🔨 STEP 2: Build Project

   ./build.sh

   This will:
   ✓ Configure with CMake
   ✓ Download dependencies (spdlog, nlohmann/json)
   ✓ Compile all source files
   ✓ Run unit tests

═══════════════════════════════════════════════════════════════

▶️  STEP 3: Run Server

   cd build
   ./smartice_server

   Server will start on: http://localhost:8001

═══════════════════════════════════════════════════════════════

🧪 STEP 4: Test Endpoints

   Open a new terminal:

   # Hello message
   curl http://localhost:8001/

   # Health check (JSON)
   curl http://localhost:8001/api/health

   # Server stats (JSON)
   curl http://localhost:8001/api/stats

═══════════════════════════════════════════════════════════════

📊 Expected Output:

   $ curl http://localhost:8001/
   Hello from C++ Backend

   $ curl http://localhost:8001/api/health
   {
     "service": "SmartICE Backend",
     "status": "ok",
     "timestamp": "2025-12-27 20:00:00",
     "version": "1.0.0"
   }

═══════════════════════════════════════════════════════════════

✅ What's Implemented:

   ✓ HTTP/1.1 server with route handling
   ✓ Thread pool (8 threads)
   ✓ Lock-free queue (Michael-Scott algorithm)
   ✓ Logging (console + rotating files)
   ✓ JSON response support
   ✓ Unit tests (CTest)

🚧 What's Stubbed (Ready for Implementation):

   ⏩ FFmpeg video decoding
   ⏩ NVDEC GPU acceleration
   ⏩ TensorRT inference

═══════════════════════════════════════════════════════════════

📚 Documentation:

   README.md          - Complete build/usage guide
   PROJECT_STATUS.md  - Implementation status
   src/main.cpp       - Server entry point
   tests/*            - Unit test examples

═══════════════════════════════════════════════════════════════

🛠️  Troubleshooting:

   Q: Build fails with "cmake: command not found"
   A: Run ./install_deps.sh first

   Q: Port 8001 already in use
   A: ./smartice_server 8002 (use different port)

   Q: Tests fail
   A: Check logs in build/test_*.log

═══════════════════════════════════════════════════════════════

🎯 Ready to Start!

   1. ./install_deps.sh    (install CMake)
   2. ./build.sh           (build project)
   3. cd build && ./smartice_server
   4. curl http://localhost:8001/

═══════════════════════════════════════════════════════════════
EOF
