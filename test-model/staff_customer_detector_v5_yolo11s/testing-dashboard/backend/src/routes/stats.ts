/**
 * Stats Routes
 * Handles statistics and monitoring data
 */

import { Router, Request, Response } from 'express';
import Logger from '../utils/logger';
import StatsAggregatorService from '../services/statsAggregator';
import { APIError } from '../types';

const logger = new Logger('StatsRoutes');

function createStatsRoutes(statsAggregator: StatsAggregatorService): Router {
  const router = Router();

  /**
   * GET /api/stats/summary
   * Get overall system stats summary (FPS, GPU, CPU, RAM, inference time)
   */
  router.get('/summary', async (_req: Request, res: Response) => {
    try {
      const stats = await statsAggregator.getAggregatedStats();

      const summary = {
        system: stats.system,
        summary: stats.summary,
        timestamp: stats.system.timestamp,
      };

      res.json(summary);
    } catch (error) {
      logger.error('Failed to get stats summary', { error: String(error) });
      const apiError: APIError = {
        error: error instanceof Error ? error.message : 'Failed to get stats summary',
      };
      res.status(500).json(apiError);
    }
  });

  /**
   * GET /api/stats/camera/:channel
   * Get detailed stats for a specific camera
   */
  router.get('/camera/:channel', async (req: Request, res: Response): Promise<void> => {
    try {
      const channel = parseInt(req.params.channel);

      if (isNaN(channel) || channel < 1 || channel > 30) {
        const error: APIError = { error: 'Invalid channel number (1-30)' };
        res.status(400).json(error); return;
      }

      const stats = await statsAggregator.getAggregatedStats();
      const cameraStats = stats.cameras.find(c => c.channel === channel);

      if (!cameraStats) {
        const error: APIError = { error: `Camera ${channel} not active` };
        res.status(404).json(error); return;
      }

      res.json({
        camera: cameraStats,
        system: stats.system,
      });
    } catch (error) {
      logger.error('Failed to get camera stats', { error: String(error) });
      const apiError: APIError = {
        error: error instanceof Error ? error.message : 'Failed to get camera stats',
      };
      res.status(500).json(apiError);
    }
  });

  /**
   * GET /api/stats/realtime
   * Server-Sent Events endpoint for real-time stats streaming
   */
  router.get('/realtime', (req: Request, res: Response): void => {
    // Set headers for SSE
    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Connection', 'keep-alive');
    res.setHeader('Access-Control-Allow-Origin', '*');

    logger.info('Client connected to real-time stats stream');

    // Send initial stats immediately
    statsAggregator.getAggregatedStats().then(stats => {
      res.write(`data: ${JSON.stringify(stats)}\n\n`);
    }).catch(err => {
      logger.error('Failed to send initial stats', { error: String(err) });
    });

    // Send stats every 1 second
    const intervalId = setInterval(async () => {
      try {
        const stats = await statsAggregator.getAggregatedStats();
        res.write(`data: ${JSON.stringify(stats)}\n\n`);
      } catch (error) {
        logger.error('Failed to send real-time stats', { error: String(error) });
      }
    }, 1000);

    // Cleanup on client disconnect
    req.on('close', () => {
      clearInterval(intervalId);
      logger.info('Client disconnected from real-time stats stream');
      res.end();
    });
  });

  /**
   * GET /api/stats
   * Get all stats (system + all cameras)
   */
  router.get('/', async (_req: Request, res: Response) => {
    try {
      const stats = await statsAggregator.getAggregatedStats();
      res.json(stats);
    } catch (error) {
      logger.error('Failed to get stats', { error: String(error) });
      const apiError: APIError = {
        error: error instanceof Error ? error.message : 'Failed to get stats',
      };
      res.status(500).json(apiError);
    }
  });

  return router;
}

export default createStatsRoutes;
