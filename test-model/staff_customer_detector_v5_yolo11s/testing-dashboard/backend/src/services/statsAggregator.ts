/**
 * Stats Aggregator Service
 * Combines stats from Python server and system monitoring
 */

import Logger from '../utils/logger';
import PythonProxyService from './pythonProxy';
import SystemMonitorService from './systemMonitor';
import { StatsResponse, SystemStats, InferenceStats } from '../types';

const logger = new Logger('StatsAggregator');

class StatsAggregatorService {
  private pythonProxy: PythonProxyService;
  private systemMonitor: SystemMonitorService;

  constructor(pythonProxy: PythonProxyService, systemMonitor: SystemMonitorService) {
    this.pythonProxy = pythonProxy;
    this.systemMonitor = systemMonitor;
  }

  /**
   * Get comprehensive stats from both Python server and system monitoring
   */
  async getAggregatedStats(): Promise<StatsResponse> {
    try {
      // Fetch stats from Python server (includes camera stats and basic system info)
      const pythonStats = await this.pythonProxy.getStats();

      // Fetch enhanced system stats from our monitoring
      const systemStats = await this.systemMonitor.getAllStats();

      // Transform camera stats to match frontend expectations
      const transformedCameras = pythonStats.cameras.map(cam => this.transformCameraStats(cam));

      // Merge system stats - prioritize our monitoring for GPU/CPU/Memory
      const enhancedStats: StatsResponse = {
        ...pythonStats,
        cameras: transformedCameras,
        system: {
          gpu: systemStats.gpu,
          cpu: systemStats.cpu,
          memory: {
            used: systemStats.memory.used,
            total: systemStats.memory.total,
            percent: systemStats.memory.percent,
            used_mb: systemStats.memory.used_mb,
            total_mb: systemStats.memory.total_mb,
          },
          inference: this.extractInferenceStats(pythonStats),
          timestamp: new Date().toISOString(),
        },
      };

      return enhancedStats;
    } catch (error) {
      logger.error('Failed to aggregate stats', { error: String(error) });

      // Return minimal stats if Python server is down
      const systemStats = await this.systemMonitor.getAllStats();

      return {
        system: {
          gpu: systemStats.gpu,
          cpu: systemStats.cpu,
          memory: {
            used: systemStats.memory.used,
            total: systemStats.memory.total,
            percent: systemStats.memory.percent,
            used_mb: systemStats.memory.used_mb,
            total_mb: systemStats.memory.total_mb,
          },
          inference: {
            avg_time_ms: 0,
            min_time_ms: 0,
            max_time_ms: 0,
            queue_depth: 0,
            queue_max: 100,
          },
          timestamp: new Date().toISOString(),
        },
        cameras: [],
        summary: {
          active_cameras: 0,
          total_fps: 0,
          target_fps: 15,
          avg_decode_ms: 0,
          avg_inference_ms: 0,
          hw_accel_cameras: 0,
          hw_accel_percentage: 0,
          inference_queue_size: 0,
          batch_size: 16,
        },
      };
    }
  }

  /**
   * Transform Python camera stats to match frontend interface
   * Maps field names and adds missing fields with defaults
   */
  private transformCameraStats(cam: any): any {
    return {
      ...cam,
      // Map current_fps to fps (frontend expects 'fps')
      fps: cam.current_fps || 0,
      // Add target_fps if missing (default 15 FPS)
      target_fps: 15,
      // Add lag_ms if missing (calculate as decode + inference time)
      lag_ms: (cam.current_decode_ms || 0) + (cam.current_inference_ms || 0),
      // Ensure all numeric fields have defaults
      decode_time_ms: cam.current_decode_ms || 0,
      inference_time_ms: cam.current_inference_ms || 0,
      // Add detection counts if missing
      detections: cam.detections || { total: 0, staff: 0, customer: 0 },
      // Add confidence stats if missing
      confidence: {
        avg: cam.avg_confidence || 0,
        min: 0,
        max: 0,
      },
    };
  }

  /**
   * Extract inference stats from Python stats response
   */
  private extractInferenceStats(pythonStats: StatsResponse): InferenceStats {
    const cameras = pythonStats.cameras;

    if (cameras.length === 0) {
      return {
        avg_time_ms: 0,
        min_time_ms: 0,
        max_time_ms: 0,
        queue_depth: pythonStats.summary.inference_queue_size,
        queue_max: 100,
      };
    }

    const inferenceTimes = cameras
      .map(c => c.avg_inference_ms)
      .filter(t => t > 0);

    return {
      avg_time_ms: inferenceTimes.length > 0
        ? inferenceTimes.reduce((a, b) => a + b, 0) / inferenceTimes.length
        : 0,
      min_time_ms: inferenceTimes.length > 0
        ? Math.min(...inferenceTimes)
        : 0,
      max_time_ms: inferenceTimes.length > 0
        ? Math.max(...inferenceTimes)
        : 0,
      queue_depth: pythonStats.summary.inference_queue_size,
      queue_max: 100,
    };
  }

  /**
   * Get system stats only (without camera data)
   */
  async getSystemStatsOnly(): Promise<SystemStats> {
    const systemStats = await this.systemMonitor.getAllStats();

    return {
      gpu: systemStats.gpu,
      cpu: systemStats.cpu,
      memory: {
        used: systemStats.memory.used,
        total: systemStats.memory.total,
        percent: systemStats.memory.percent,
        used_mb: systemStats.memory.used_mb,
        total_mb: systemStats.memory.total_mb,
      },
      inference: {
        avg_time_ms: 0,
        min_time_ms: 0,
        max_time_ms: 0,
        queue_depth: 0,
        queue_max: 100,
      },
      timestamp: new Date().toISOString(),
    };
  }
}

export default StatsAggregatorService;
