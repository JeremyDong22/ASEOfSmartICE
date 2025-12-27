/**
 * Camera Control Routes
 * Handles camera start/stop operations
 */

import { Router, Request, Response } from 'express';
import Logger from '../utils/logger';
import PythonProxyService from '../services/pythonProxy';
import {
  StartCameraRequest,
  StopCameraRequest,
  AdjustFPSRequest,
  APIError,
} from '../types';

const logger = new Logger('CameraRoutes');

function createCameraRoutes(pythonProxy: PythonProxyService): Router {
  const router = Router();

  /**
   * POST /api/camera/start
   * Start a specific camera by channel number
   */
  router.post('/start', async (req: Request, res: Response): Promise<void> => {
    try {
      const { channel } = req.body as StartCameraRequest;

      if (!channel || typeof channel !== 'number') {
        const error: APIError = { error: 'Invalid channel number' };
        res.status(400).json(error);
        return;
      }

      if (channel < 1 || channel > 30) {
        const error: APIError = { error: 'Channel must be between 1 and 30' };
        res.status(400).json(error);
        return;
      }

      logger.info(`Starting camera ${channel}`);
      const result = await pythonProxy.startCamera(channel);

      res.json(result);
    } catch (error) {
      logger.error('Failed to start camera', { error: String(error) });
      const apiError: APIError = {
        error: error instanceof Error ? error.message : 'Failed to start camera',
      };
      res.status(500).json(apiError);
    }
  });

  /**
   * POST /api/camera/stop
   * Stop a specific camera by channel number
   */
  router.post('/stop', async (req: Request, res: Response): Promise<void> => {
    try {
      const { channel } = req.body as StopCameraRequest;

      if (!channel || typeof channel !== 'number') {
        const error: APIError = { error: 'Invalid channel number' };
        res.status(400).json(error); return;
      }

      logger.info(`Stopping camera ${channel}`);
      const result = await pythonProxy.stopCamera(channel);

      res.json(result);
    } catch (error) {
      logger.error('Failed to stop camera', { error: String(error) });
      const apiError: APIError = {
        error: error instanceof Error ? error.message : 'Failed to stop camera',
      };
      res.status(500).json(apiError);
    }
  });

  /**
   * GET /api/camera/status
   * Get status of all active cameras
   */
  router.get('/status', async (_req: Request, res: Response): Promise<void> => {
    try {
      const result = await pythonProxy.getActiveCameras();
      res.json(result);
    } catch (error) {
      logger.error('Failed to get camera status', { error: String(error) });
      const apiError: APIError = {
        error: error instanceof Error ? error.message : 'Failed to get camera status',
      };
      res.status(500).json(apiError);
    }
  });

  /**
   * POST /api/camera/fps
   * Adjust FPS for specific camera or all cameras
   * Note: This feature requires Python server support
   */
  router.post('/fps', async (req: Request, res: Response): Promise<void> => {
    try {
      const { channel, fps } = req.body as AdjustFPSRequest;

      if (!fps || typeof fps !== 'number' || fps < 1 || fps > 30) {
        const error: APIError = { error: 'FPS must be between 1 and 30' };
        res.status(400).json(error); return;
      }

      // Note: Python server doesn't currently support dynamic FPS adjustment
      // This would require modifying the Python server to accept FPS updates
      logger.warn('FPS adjustment not yet implemented in Python server');

      const response = {
        success: false,
        error: 'FPS adjustment not yet implemented. Python server restart required to change FPS.',
        fps,
        affected_cameras: channel ? [channel] : [],
      };

      res.status(501).json(response);
    } catch (error) {
      logger.error('Failed to adjust FPS', { error: String(error) });
      const apiError: APIError = {
        error: error instanceof Error ? error.message : 'Failed to adjust FPS',
      };
      res.status(500).json(apiError);
    }
  });

  return router;
}

export default createCameraRoutes;
