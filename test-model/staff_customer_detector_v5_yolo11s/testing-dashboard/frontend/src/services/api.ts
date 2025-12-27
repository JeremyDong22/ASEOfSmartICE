/**
 * API Service
 * Handles all communication with the TypeScript backend
 */

import { StatsResponse, CameraStats, APIError } from '../types';

class APIService {
  private baseUrl: string;

  constructor(baseUrl: string = 'http://localhost:3000') {
    this.baseUrl = baseUrl;
  }

  /**
   * Start a camera by channel number
   */
  async startCamera(channel: number): Promise<{ success: boolean; error?: string }> {
    try {
      const response = await fetch(`${this.baseUrl}/api/camera/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ channel }),
      });

      if (!response.ok) {
        const error: APIError = await response.json();
        throw new Error(error.error);
      }

      return await response.json();
    } catch (error) {
      console.error('Failed to start camera:', error);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to start camera',
      };
    }
  }

  /**
   * Stop a camera by channel number
   */
  async stopCamera(channel: number): Promise<{ success: boolean; error?: string }> {
    try {
      const response = await fetch(`${this.baseUrl}/api/camera/stop`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ channel }),
      });

      if (!response.ok) {
        const error: APIError = await response.json();
        throw new Error(error.error);
      }

      return await response.json();
    } catch (error) {
      console.error('Failed to stop camera:', error);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to stop camera',
      };
    }
  }

  /**
   * Get list of active cameras
   */
  async getActiveCameras(): Promise<number[]> {
    try {
      const response = await fetch(`${this.baseUrl}/api/camera/status`);
      if (!response.ok) {
        throw new Error('Failed to get active cameras');
      }
      const data = await response.json();
      return data.cameras || [];
    } catch (error) {
      console.error('Failed to get active cameras:', error);
      return [];
    }
  }

  /**
   * Get all stats
   */
  async getStats(): Promise<StatsResponse | null> {
    try {
      const response = await fetch(`${this.baseUrl}/api/stats`);
      if (!response.ok) {
        throw new Error('Failed to get stats');
      }
      return await response.json();
    } catch (error) {
      console.error('Failed to get stats:', error);
      return null;
    }
  }

  /**
   * Get stats for a specific camera
   */
  async getCameraStats(channel: number): Promise<CameraStats | null> {
    try {
      const response = await fetch(`${this.baseUrl}/api/stats/camera/${channel}`);
      if (!response.ok) {
        return null;
      }
      const data = await response.json();
      return data.camera;
    } catch (error) {
      console.error(`Failed to get camera ${channel} stats:`, error);
      return null;
    }
  }

  /**
   * Check backend health
   */
  async healthCheck(): Promise<boolean> {
    try {
      const response = await fetch(`${this.baseUrl}/api/system/health`, {
        timeout: 3000,
      } as RequestInit);
      return response.ok;
    } catch (error) {
      return false;
    }
  }
}

export default APIService;
