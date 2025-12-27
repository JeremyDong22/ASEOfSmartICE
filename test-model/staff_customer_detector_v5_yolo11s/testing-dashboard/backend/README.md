# Backend - TypeScript Express Server

TypeScript backend for V5 YOLO11s Testing Dashboard.

## Features

- RESTful API for camera control
- System monitoring (GPU, CPU, memory)
- Python server proxy
- Server-Sent Events for real-time stats
- Comprehensive error handling
- Structured logging

## Directory Structure

```
backend/
├── src/
│   ├── server.ts              # Main Express server
│   ├── routes/
│   │   ├── camera.ts          # Camera control endpoints
│   │   ├── stats.ts           # Statistics endpoints
│   │   └── system.ts          # System monitoring endpoints
│   ├── services/
│   │   ├── pythonProxy.ts     # Proxy to Python server (port 8001)
│   │   ├── systemMonitor.ts   # GPU/CPU/memory monitoring
│   │   └── statsAggregator.ts # Aggregate stats from multiple sources
│   ├── types/
│   │   └── index.ts           # TypeScript type definitions
│   └── utils/
│       └── logger.ts          # Logging utility
├── dist/                      # Compiled JavaScript (generated)
├── tests/
│   ├── api_test.sh            # Bash test script
│   └── api_tests.http         # HTTP test file
├── package.json
├── tsconfig.json
└── README.md                  # This file
```

## Installation

```bash
npm install
```

## Development

```bash
# Development mode with auto-restart
npm run dev

# Build TypeScript
npm run build

# Production mode
npm start

# Lint code
npm run lint
```

## Configuration

Edit `src/server.ts`:

```typescript
const config: ServerConfig = {
  port: 3000,
  pythonServerUrl: 'http://localhost:8001',
  pythonServerPort: 8001,
  corsOrigins: ['*'],
  wsHeartbeatInterval: 30000,
  statsUpdateInterval: 1000,
};
```

## Environment Variables

```bash
PORT=3000
PYTHON_SERVER_URL=http://localhost:8001
PYTHON_SERVER_PORT=8001
CORS_ORIGINS=http://localhost:3000
```

## API Endpoints

See `/api` endpoint for complete documentation or refer to `../API.md`.

### Camera Control
- `POST /api/camera/start` - Start camera
- `POST /api/camera/stop` - Stop camera
- `GET /api/camera/status` - Get active cameras
- `POST /api/camera/fps` - Adjust FPS (not yet implemented)

### Statistics
- `GET /api/stats` - Get all stats
- `GET /api/stats/summary` - Get summary
- `GET /api/stats/camera/:channel` - Get camera stats
- `GET /api/stats/realtime` - Real-time SSE stream

### System
- `GET /api/system/health` - Health check
- `GET /api/system/gpu` - GPU stats
- `GET /api/system/cpu` - CPU stats
- `GET /api/system/memory` - Memory stats
- `GET /api/system/info` - System info

## Services

### PythonProxyService
Proxies requests to the Python Flask server running on port 8001.

**Methods:**
- `startCamera(channel)` - Start camera
- `stopCamera(channel)` - Stop camera
- `getActiveCameras()` - Get active cameras
- `getStats()` - Get comprehensive stats
- `healthCheck()` - Check Python server health

### SystemMonitorService
Monitors GPU, CPU, and memory using system utilities.

**Methods:**
- `getGPUStats()` - Uses nvidia-smi
- `getCPUStats()` - Uses /proc/stat and mpstat
- `getMemoryStats()` - Uses /proc/meminfo
- `getAllStats()` - Get all system stats

**Requirements:**
- nvidia-smi (for GPU monitoring)
- mpstat (for per-core CPU monitoring)
- /proc/stat (for overall CPU usage)
- /proc/meminfo (for memory stats)

### StatsAggregatorService
Combines stats from Python server and system monitoring.

**Methods:**
- `getAggregatedStats()` - Merge Python stats with enhanced system monitoring
- `getSystemStatsOnly()` - Get system stats without camera data

## Testing

### Run Bash Test Script
```bash
cd tests
./api_test.sh
```

### Use HTTP File
Open `tests/api_tests.http` in VS Code with REST Client extension.

### Manual Testing
```bash
# Health check
curl http://localhost:3000/api/system/health

# Start camera
curl -X POST http://localhost:3000/api/camera/start \
  -H "Content-Type: application/json" \
  -d '{"channel":1}'

# Get stats
curl http://localhost:3000/api/stats | jq '.'

# Real-time stream
curl -N http://localhost:3000/api/stats/realtime
```

## Error Handling

All errors follow this format:

```json
{
  "error": "Error message",
  "code": "404",
  "details": "Additional details"
}
```

## Logging

Uses custom Logger utility with context and levels:

```typescript
const logger = new Logger('ServiceName');

logger.info('Message', { metadata });
logger.warn('Warning', { metadata });
logger.error('Error', { metadata });
logger.debug('Debug', { metadata });
```

## TypeScript

### Strict Mode
TypeScript strict mode is enabled for maximum type safety.

### Type Definitions
All types are defined in `src/types/index.ts` and exported for use across the application.

## Dependencies

**Production:**
- express - Web server framework
- cors - CORS middleware
- axios - HTTP client
- ws - WebSocket support

**Development:**
- typescript - TypeScript compiler
- ts-node-dev - Development server with auto-restart
- @types/* - Type definitions
- eslint - Code linting

## Building

```bash
npm run build
```

Output: `dist/` directory

## Running in Production

```bash
npm start
```

Or with PM2:

```bash
pm2 start dist/server.js --name v5-dashboard-backend
```

## Troubleshooting

### Port 3000 already in use
```bash
# Find process using port
lsof -i :3000

# Kill process
kill -9 <PID>
```

### TypeScript errors
```bash
# Clean build
rm -rf dist/
npm run build
```

### Python server not responding
- Check if Python server is running: `curl http://localhost:8001/api/active_cameras`
- Check Python server logs
- Verify network connectivity

### GPU stats not working
- Check nvidia-smi: `nvidia-smi`
- Ensure CUDA drivers installed
- Verify nvidia-smi in PATH
