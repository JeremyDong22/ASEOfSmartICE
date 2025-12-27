/**
 * System Routes
 * Handles system-level operations and health checks
 */

import { Router, Request, Response } from 'express';
import Logger from '../utils/logger';
import PythonProxyService from '../services/pythonProxy';
import SystemMonitorService from '../services/systemMonitor';

const logger = new Logger('SystemRoutes');

function createSystemRoutes(
  pythonProxy: PythonProxyService,
  systemMonitor: SystemMonitorService
): Router {
  const router = Router();

  /**
   * GET /api/system/health
   * Health check endpoint
   */
  router.get('/health', async (_req: Request, res: Response) => {
    const pythonServerHealthy = await pythonProxy.healthCheck();

    const health = {
      status: pythonServerHealthy ? 'healthy' : 'degraded',
      typescript_server: 'healthy',
      python_server: pythonServerHealthy ? 'healthy' : 'down',
      python_server_url: pythonProxy.getBaseUrl(),
      timestamp: new Date().toISOString(),
    };

    const statusCode = pythonServerHealthy ? 200 : 503;
    res.status(statusCode).json(health);
  });

  /**
   * GET /api/system/gpu
   * Get GPU stats only
   */
  router.get('/gpu', async (_req: Request, res: Response): Promise<void> => {
    try {
      const gpuStats = await systemMonitor.getGPUStats();

      if (!gpuStats) {
        res.status(404).json({
          error: 'GPU not available or nvidia-smi not found',
        });
        return;
      }

      res.json(gpuStats);
    } catch (error) {
      logger.error('Failed to get GPU stats', { error: String(error) });
      res.status(500).json({
        error: error instanceof Error ? error.message : 'Failed to get GPU stats',
      });
    }
  });

  /**
   * GET /api/system/cpu
   * Get CPU stats only
   */
  router.get('/cpu', async (_req: Request, res: Response) => {
    try {
      const cpuStats = await systemMonitor.getCPUStats();
      res.json(cpuStats);
    } catch (error) {
      logger.error('Failed to get CPU stats', { error: String(error) });
      res.status(500).json({
        error: error instanceof Error ? error.message : 'Failed to get CPU stats',
      });
    }
  });

  /**
   * GET /api/system/memory
   * Get memory stats only
   */
  router.get('/memory', async (_req: Request, res: Response) => {
    try {
      const memoryStats = await systemMonitor.getMemoryStats();
      res.json(memoryStats);
    } catch (error) {
      logger.error('Failed to get memory stats', { error: String(error) });
      res.status(500).json({
        error: error instanceof Error ? error.message : 'Failed to get memory stats',
      });
    }
  });

  /**
   * GET /api/system/info
   * Get system information
   */
  router.get('/info', async (_req: Request, res: Response) => {
    try {
      const systemStats = await systemMonitor.getAllStats();

      const info = {
        gpu_available: systemStats.gpu !== null,
        cpu_cores: systemStats.cpu.per_core.length,
        memory_total_gb: systemStats.memory.total,
        timestamp: new Date().toISOString(),
      };

      res.json(info);
    } catch (error) {
      logger.error('Failed to get system info', { error: String(error) });
      res.status(500).json({
        error: error instanceof Error ? error.message : 'Failed to get system info',
      });
    }
  });

  return router;
}

export default createSystemRoutes;
