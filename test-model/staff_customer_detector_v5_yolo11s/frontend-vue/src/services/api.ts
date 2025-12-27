import axios, { AxiosInstance } from 'axios'
import type {
  StatsResponse,
  CameraListResponse,
  CameraStartResponse,
  CameraStopResponse
} from '@/types'

class APIService {
  private client: AxiosInstance

  constructor() {
    this.client = axios.create({
      baseURL: 'http://localhost:8001',
      timeout: 10000,
      headers: {
        'Content-Type': 'application/json'
      }
    })
  }

  /**
   * Start camera detection on a specific channel
   */
  async startCamera(channel: number): Promise<CameraStartResponse> {
    const response = await this.client.post<CameraStartResponse>('/api/start_camera', {
      channel
    })
    return response.data
  }

  /**
   * Stop camera detection on a specific channel
   */
  async stopCamera(channel: number): Promise<CameraStopResponse> {
    const response = await this.client.post<CameraStopResponse>('/api/stop_camera', {
      channel
    })
    return response.data
  }

  /**
   * Get global statistics across all cameras
   */
  async getStats(): Promise<StatsResponse> {
    const response = await this.client.get<StatsResponse>('/api/stats')
    return response.data
  }

  /**
   * Get list of active cameras
   */
  async getActiveCameras(): Promise<number[]> {
    const response = await this.client.get<{ cameras: number[] }>('/api/active_cameras')
    return response.data.cameras
  }

  /**
   * Health check endpoint (using stats endpoint for now)
   */
  async healthCheck(): Promise<boolean> {
    try {
      await this.client.get('/api/stats')
      return true
    } catch {
      return false
    }
  }
}

export const apiService = new APIService()
export default apiService
