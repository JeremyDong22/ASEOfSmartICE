# Staff/Customer Detector Dashboard - Vue 3 Frontend

Production-ready Vue 3 + TypeScript dashboard for the Staff/Customer Detector V5 (YOLO11s) real-time detection system.

## Features

- Real-time video streaming (MJPEG + WebRTC support)
- Virtual scrolling for efficient rendering of multiple camera feeds
- Live detection statistics (Staff/Customer counts, FPS)
- Individual and bulk camera control
- Server-Sent Events (SSE) for real-time updates
- TypeScript strict mode for type safety
- Element Plus UI components
- Pinia state management
- Responsive grid layout

## Tech Stack

- **Vue 3.4** - Composition API with `<script setup>`
- **TypeScript 5.3** - Strict type checking
- **Vite 5** - Fast build tool and dev server
- **Pinia** - State management
- **Element Plus** - UI component library
- **Vue Virtual Scroller** - Efficient rendering of large lists
- **Simple Peer** - WebRTC wrapper
- **Axios** - HTTP client

## Prerequisites

- Node.js 18+ (LTS recommended)
- npm or yarn
- Backend API running on http://localhost:8001

## Installation

```bash
# Install dependencies
npm install

# Or using yarn
yarn install
```

## Development

```bash
# Start dev server (http://localhost:3000)
npm run dev

# Type check
npm run type-check

# Build for production
npm run build

# Preview production build
npm run preview
```

## Project Structure

```
frontend-vue/
├── src/
│   ├── main.ts                # Entry point
│   ├── App.vue                # Root component
│   ├── router/
│   │   └── index.ts           # Vue Router config
│   ├── stores/
│   │   ├── camera.ts          # Camera state (Pinia)
│   │   └── stats.ts           # Stats state (Pinia)
│   ├── components/
│   │   ├── VideoGrid.vue      # Virtual scroll grid
│   │   ├── VideoPlayer.vue    # WebRTC + MJPEG player
│   │   ├── StatsPanel.vue     # Real-time statistics
│   │   └── CameraControl.vue  # Camera start/stop controls
│   ├── services/
│   │   ├── api.ts             # HTTP API client
│   │   ├── sse.ts             # Server-Sent Events client
│   │   └── webrtc.ts          # WebRTC client
│   ├── types/
│   │   └── index.ts           # TypeScript type definitions
│   └── assets/
│       └── styles/
│           └── main.css       # Global styles
├── package.json
├── vite.config.ts
├── tsconfig.json
└── index.html
```

## API Integration

The frontend connects to the backend API at `http://localhost:8001` via Vite proxy.

### API Endpoints

- `POST /api/cameras/start` - Start camera detection
- `POST /api/cameras/stop` - Stop camera detection
- `GET /api/cameras` - Get available cameras
- `GET /api/stats` - Get global statistics
- `GET /api/stream/events` - SSE endpoint for real-time updates
- `GET /stream/mjpeg/{channel}` - MJPEG video stream

## Environment Variables

Create `.env` file for custom configuration:

```bash
VITE_API_URL=http://localhost:8001
VITE_ENABLE_WEBRTC=false
```

## State Management

### Camera Store (`stores/camera.ts`)

Manages camera states, detection counts, and control actions.

```typescript
const cameraStore = useCameraStore()

// Actions
await cameraStore.startCamera(18)
await cameraStore.stopCamera(18)
await cameraStore.loadAvailableCameras()

// Getters
const camera = cameraStore.getCameraByChannel(18)
const activeCameras = cameraStore.getActiveCameras
const totalStaff = cameraStore.getTotalStaff
```

### Stats Store (`stores/stats.ts`)

Manages global statistics across all cameras.

```typescript
const statsStore = useStatsStore()

// Update stats
statsStore.updateGlobalStats({
  totalCameras: 4,
  activeCameras: 2,
  totalDetections: 15,
  totalStaff: 8,
  totalCustomers: 7,
  averageFps: 45.3
})
```

## Components

### VideoPlayer

Displays individual camera feed with detection overlay.

```vue
<VideoPlayer :channel="18" :use-web-r-t-c="false" />
```

### VideoGrid

Renders multiple camera feeds with virtual scrolling.

```vue
<VideoGrid :use-web-r-t-c="false" :grid-columns="2" />
```

### StatsPanel

Displays real-time statistics across all cameras.

```vue
<StatsPanel />
```

### CameraControl

Individual and bulk camera start/stop controls.

```vue
<CameraControl />
```

## Real-Time Updates

The dashboard uses Server-Sent Events (SSE) for real-time detection updates:

```typescript
import { sseService } from '@/services/sse'

sseService.connect(
  (data) => {
    console.log('Detection update:', data)
  },
  (error) => {
    console.error('SSE error:', error)
  }
)
```

## WebRTC Support

WebRTC is prepared but disabled by default (uses MJPEG fallback):

```typescript
import { webrtcService } from '@/services/webrtc'

// Create WebRTC connection
const stream = await webrtcService.createConnection(18)
videoElement.srcObject = stream

// Close connection
webrtcService.close(18)
```

## Type Safety

All API responses and component props are fully typed:

```typescript
interface Camera {
  channel: number
  status: 'stopped' | 'connecting' | 'connected' | 'error'
  fps: number
  detections: number
  staffCount: number
  customerCount: number
}
```

## Building for Production

```bash
# Build
npm run build

# Output: dist/
# Serve with any static file server (nginx, Apache, etc.)
```

## Troubleshooting

### Port 3000 already in use

Change port in `vite.config.ts`:

```typescript
server: {
  port: 3001
}
```

### Backend API not responding

Check backend is running on http://localhost:8001 and proxy configuration in `vite.config.ts`.

### TypeScript errors

```bash
# Check types
npm run type-check

# Clean install
rm -rf node_modules package-lock.json
npm install
```

## License

MIT

## Author

SmartICE Detection System Team
