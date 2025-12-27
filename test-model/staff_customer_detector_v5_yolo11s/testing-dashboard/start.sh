#!/bin/bash

# Quick Start Script for V5 Testing Dashboard
# Sets up and starts both backend and frontend

set -e

echo "========================================"
echo "V5 Testing Dashboard - Quick Start"
echo "========================================"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo -e "${RED}Error: Node.js is not installed${NC}"
    echo "Please install Node.js 18+ from https://nodejs.org/"
    exit 1
fi

echo -e "${GREEN}✓ Node.js found:${NC} $(node --version)"
echo ""

# Check if Python server is running
echo "Checking Python V5 server..."
if curl -s http://localhost:8001/api/active_cameras > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Python server is running${NC}"
else
    echo -e "${YELLOW}⚠ Python server not detected${NC}"
    echo "Make sure to start it first:"
    echo "  cd ../test-model/staff_customer_detector_v5_yolo11s"
    echo "  python3 manual_camera_tester_pyav.py"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo ""

# Backend setup
echo "========================================"
echo "Backend Setup"
echo "========================================"

cd backend

if [ ! -d "node_modules" ]; then
    echo "Installing backend dependencies..."
    npm install
else
    echo "✓ Backend dependencies already installed"
fi

echo "Building backend..."
npm run build

echo -e "${GREEN}✓ Backend ready${NC}"
echo ""

# Frontend setup
cd ../frontend

echo "========================================"
echo "Frontend Setup"
echo "========================================"

if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
else
    echo "✓ Frontend dependencies already installed"
fi

echo "Building frontend..."
npm run build

echo -e "${GREEN}✓ Frontend ready${NC}"
echo ""

# Return to root
cd ..

echo "========================================"
echo "Starting Dashboard"
echo "========================================"
echo ""
echo "Backend will start on: http://localhost:3000"
echo "Dashboard will be at: http://localhost:3000/"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Start backend
cd backend
npm start
