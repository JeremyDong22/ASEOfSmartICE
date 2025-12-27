/**
 * Python Server Proxy
 * Proxies requests to the Python Flask server running on port 8001
 */

import axios, { AxiosInstance, AxiosError } from 'axios';
import Logger from '../utils/logger';
import {
  StartCameraRequest,
  StartCameraResponse,
  StopCameraRequest,
  StopCameraResponse,
  ActiveCamerasResponse,
  StatsResponse,
} from '../types';

const logger = new Logger('PythonProxy');

class PythonProxyService {
  private client: AxiosInstance;
  private baseUrl: string;

  constructor(pythonServerUrl: string = 'http://localhost:8001') {
    this.baseUrl = pythonServerUrl;
    this.client = axios.create({
      baseURL: this.baseUrl,
      timeout: 10000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    logger.info(`Initialized proxy to Python server: ${this.baseUrl}`);
  }

  /**
   * Start a camera by channel number
   */
  async startCamera(channel: number): Promise<StartCameraResponse> {
    try {
      logger.info(`Starting camera ${channel}`);
      const response = await this.client.post<StartCameraResponse>(
        '/api/start_camera',
        { channel } as StartCameraRequest
      );
      logger.info(`Camera ${channel} started successfully`);
      return response.data;
    } catch (error) {
      logger.error(`Failed to start camera ${channel}`, this.getErrorDetails(error));
      throw this.handleError(error);
    }
  }

  /**
   * Stop a camera by channel number
   */
  async stopCamera(channel: number): Promise<StopCameraResponse> {
    try {
      logger.info(`Stopping camera ${channel}`);
      const response = await this.client.post<StopCameraResponse>(
        '/api/stop_camera',
        { channel } as StopCameraRequest
      );
      logger.info(`Camera ${channel} stopped successfully`);
      return response.data;
    } catch (error) {
      logger.error(`Failed to stop camera ${channel}`, this.getErrorDetails(error));
      throw this.handleError(error);
    }
  }

  /**
   * Get list of active cameras
   */
  async getActiveCameras(): Promise<ActiveCamerasResponse> {
    try {
      const response = await this.client.get<ActiveCamerasResponse>('/api/active_cameras');
      return response.data;
    } catch (error) {
      logger.error('Failed to get active cameras', this.getErrorDetails(error));
      throw this.handleError(error);
    }
  }

  /**
   * Get comprehensive stats from Python server
   */
  async getStats(): Promise<StatsResponse> {
    try {
      const response = await this.client.get<StatsResponse>('/api/stats');
      return response.data;
    } catch (error) {
      logger.error('Failed to get stats', this.getErrorDetails(error));
      throw this.handleError(error);
    }
  }

  /**
   * Health check - verify Python server is accessible
   */
  async healthCheck(): Promise<boolean> {
    try {
      await this.client.get('/api/active_cameras', { timeout: 3000 });
      return true;
    } catch (error) {
      logger.warn('Python server health check failed');
      return false;
    }
  }

  /**
   * Handle axios errors and convert to standard error format
   */
  private handleError(error: unknown): Error {
    if (axios.isAxiosError(error)) {
      const axiosError = error as AxiosError;
      if (axiosError.response) {
        // Server responded with error status
        const message = (axiosError.response.data as { error?: string })?.error || axiosError.message;
        return new Error(`Python server error: ${message}`);
      } else if (axiosError.request) {
        // Request made but no response
        return new Error('Python server not responding. Is it running on port 8001?');
      }
    }
    return error instanceof Error ? error : new Error('Unknown error occurred');
  }

  /**
   * Extract error details for logging
   */
  private getErrorDetails(error: unknown): Record<string, unknown> {
    if (axios.isAxiosError(error)) {
      return {
        message: error.message,
        code: error.code,
        status: error.response?.status,
        data: error.response?.data,
      };
    }
    return { error: String(error) };
  }

  /**
   * Get base URL of Python server
   */
  getBaseUrl(): string {
    return this.baseUrl;
  }
}

export default PythonProxyService;
