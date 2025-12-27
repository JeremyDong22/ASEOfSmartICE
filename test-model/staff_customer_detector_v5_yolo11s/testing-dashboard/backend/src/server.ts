/**
 * Main Express Server
 * TypeScript backend for V5 YOLO11s Testing Dashboard
 */

import express, { Application, Request, Response, NextFunction } from 'express';
import cors from 'cors';
import path from 'path';
import Logger from './utils/logger';
import PythonProxyService from './services/pythonProxy';
import SystemMonitorService from './services/systemMonitor';
import StatsAggregatorService from './services/statsAggregator';
import createCameraRoutes from './routes/camera';
import createStatsRoutes from './routes/stats';
import createSystemRoutes from './routes/system';
import { ServerConfig, APIError } from './types';

const logger = new Logger('Server');

// ============================================================================
// Configuration
// ============================================================================

const config: ServerConfig = {
  port: parseInt(process.env.PORT || '3000'),
  pythonServerUrl: process.env.PYTHON_SERVER_URL || 'http://localhost:8001',
  pythonServerPort: parseInt(process.env.PYTHON_SERVER_PORT || '8001'),
  corsOrigins: process.env.CORS_ORIGINS?.split(',') || ['http://localhost:3000'],
  wsHeartbeatInterval: 30000, // 30 seconds
  statsUpdateInterval: 1000, // 1 second
};

// ============================================================================
// Initialize Services
// ============================================================================

const pythonProxy = new PythonProxyService(config.pythonServerUrl);
const systemMonitor = new SystemMonitorService();
const statsAggregator = new StatsAggregatorService(pythonProxy, systemMonitor);

// ============================================================================
// Express App Setup
// ============================================================================

const app: Application = express();

// Middleware
app.use(cors({
  origin: '*', // Allow all origins for development
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization'],
}));

app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Request logging middleware
app.use((req: Request, _res: Response, next: NextFunction) => {
  logger.info(`${req.method} ${req.path}`);
  next();
});

// ============================================================================
// API Routes
// ============================================================================

app.use('/api/camera', createCameraRoutes(pythonProxy));
app.use('/api/stats', createStatsRoutes(statsAggregator));
app.use('/api/system', createSystemRoutes(pythonProxy, systemMonitor));

// Root endpoint
app.get('/api', (_req: Request, res: Response) => {
  res.json({
    name: 'V5 Testing Dashboard API',
    version: '1.0.0',
    status: 'running',
    python_server: config.pythonServerUrl,
    endpoints: {
      camera: {
        start: 'POST /api/camera/start',
        stop: 'POST /api/camera/stop',
        status: 'GET /api/camera/status',
        fps: 'POST /api/camera/fps',
      },
      stats: {
        all: 'GET /api/stats',
        summary: 'GET /api/stats/summary',
        camera: 'GET /api/stats/camera/:channel',
        realtime: 'GET /api/stats/realtime (SSE)',
      },
      system: {
        health: 'GET /api/system/health',
        gpu: 'GET /api/system/gpu',
        cpu: 'GET /api/system/cpu',
        memory: 'GET /api/system/memory',
        info: 'GET /api/system/info',
      },
    },
  });
});

// ============================================================================
// Static Files (Frontend)
// ============================================================================

const frontendPath = path.join(__dirname, '../../frontend/public');
app.use(express.static(frontendPath));

// Serve index.html for root path
app.get('/', (_req: Request, res: Response) => {
  res.sendFile(path.join(frontendPath, 'index.html'));
});

// ============================================================================
// Error Handling
// ============================================================================

// 404 handler
app.use((_req: Request, res: Response) => {
  const error: APIError = {
    error: 'Not Found',
    code: '404',
  };
  res.status(404).json(error);
});

// Global error handler
app.use((err: Error, _req: Request, res: Response, _next: NextFunction) => {
  logger.error('Unhandled error:', { error: err.message, stack: err.stack });

  const error: APIError = {
    error: err.message || 'Internal Server Error',
    code: '500',
  };
  res.status(500).json(error);
});

// ============================================================================
// Server Startup
// ============================================================================

async function startServer() {
  try {
    logger.info('='.repeat(70));
    logger.info('V5 YOLO11s Testing Dashboard - TypeScript Backend');
    logger.info('='.repeat(70));
    logger.info(`Port: ${config.port}`);
    logger.info(`Python Server: ${config.pythonServerUrl}`);
    logger.info(`CORS Origins: ${config.corsOrigins.join(', ')}`);
    logger.info('='.repeat(70));

    // Check Python server health
    logger.info('Checking Python server connection...');
    const pythonHealthy = await pythonProxy.healthCheck();

    if (pythonHealthy) {
      logger.info('Python server is accessible');
    } else {
      logger.warn('Python server is NOT accessible. Some features may not work.');
      logger.warn('Make sure the Python server is running on port 8001');
    }

    // Check GPU availability
    const gpuStats = await systemMonitor.getGPUStats();
    if (gpuStats) {
      logger.info(`GPU detected: ${gpuStats.memory_total}MB VRAM, ${gpuStats.temperature}°C`);
    } else {
      logger.warn('GPU not detected or nvidia-smi not available');
    }

    // Start Express server
    app.listen(config.port, () => {
      logger.info('='.repeat(70));
      logger.info(`Server running at http://localhost:${config.port}`);
      logger.info(`API documentation: http://localhost:${config.port}/api`);
      logger.info(`Dashboard: http://localhost:${config.port}/`);
      logger.info('='.repeat(70));
    });

  } catch (error) {
    logger.error('Failed to start server', { error: String(error) });
    process.exit(1);
  }
}

// Handle graceful shutdown
process.on('SIGINT', () => {
  logger.info('Received SIGINT, shutting down gracefully...');
  process.exit(0);
});

process.on('SIGTERM', () => {
  logger.info('Received SIGTERM, shutting down gracefully...');
  process.exit(0);
});

// Start the server
if (require.main === module) {
  startServer();
}

export default app;
