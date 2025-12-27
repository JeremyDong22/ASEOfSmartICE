import { defineStore } from 'pinia'
import type { Camera, CameraStatus, DetectionData } from '@/types'
import { apiService } from '@/services/api'

export const useCameraStore = defineStore('camera', {
  state: () => ({
    cameras: new Map<number, Camera>() as Map<number, Camera>,
    activeCameras: new Set<number>() as Set<number>,
    availableChannels: Array.from({ length: 30 }, (_, i) => i + 1) as number[], // All 30 channels
    isLoading: false,
    error: null as string | null
  }),

  getters: {
    /**
     * Get camera by channel number
     */
    getCameraByChannel: (state) => (channel: number): Camera | undefined => {
      return state.cameras.get(channel)
    },

    /**
     * Get all active cameras
     */
    getActiveCameras: (state): Camera[] => {
      return Array.from(state.cameras.values()).filter(
        (camera) => camera.status === 'connected'
      )
    },

    /**
     * Get total detection count across all cameras
     */
    getTotalDetections: (state): number => {
      return Array.from(state.cameras.values()).reduce(
        (total, camera) => total + camera.detections,
        0
      )
    },

    /**
     * Get total staff count
     */
    getTotalStaff: (state): number => {
      return Array.from(state.cameras.values()).reduce(
        (total, camera) => total + camera.staffCount,
        0
      )
    },

    /**
     * Get total customer count
     */
    getTotalCustomers: (state): number => {
      return Array.from(state.cameras.values()).reduce(
        (total, camera) => total + camera.customerCount,
        0
      )
    },

    /**
     * Get average FPS across all active cameras
     */
    getAverageFps: (state): number => {
      const activeCameras = Array.from(state.cameras.values()).filter(
        (camera) => camera.status === 'connected'
      )
      if (activeCameras.length === 0) return 0

      const totalFps = activeCameras.reduce((sum, camera) => sum + camera.fps, 0)
      return totalFps / activeCameras.length
    }
  },

  actions: {
    /**
     * Initialize camera in the store
     */
    initializeCamera(channel: number): void {
      if (!this.cameras.has(channel)) {
        this.cameras.set(channel, {
          channel,
          status: 'stopped',
          fps: 0,
          detections: 0,
          staffCount: 0,
          customerCount: 0,
          lastUpdate: Date.now()
        })
      }
    },

    /**
     * Start camera detection
     */
    async startCamera(channel: number): Promise<void> {
      this.initializeCamera(channel)
      this.updateCameraStatus(channel, 'connecting')

      try {
        const response = await apiService.startCamera(channel)

        if (response.success) {
          this.updateCameraStatus(channel, 'connected')
          this.activeCameras.add(channel)
        } else {
          this.updateCameraStatus(channel, 'error', response.message)
        }
      } catch (error) {
        console.error('Failed to start camera:', error)
        this.updateCameraStatus(channel, 'error', 'Failed to start camera')
        throw error
      }
    },

    /**
     * Stop camera detection
     */
    async stopCamera(channel: number): Promise<void> {
      try {
        const response = await apiService.stopCamera(channel)

        if (response.success) {
          this.updateCameraStatus(channel, 'stopped')
          this.activeCameras.delete(channel)
        } else {
          this.error = response.message || 'Failed to stop camera'
        }
      } catch (error) {
        console.error('Failed to stop camera:', error)
        this.error = 'Failed to stop camera'
        throw error
      }
    },

    /**
     * Update camera status
     */
    updateCameraStatus(
      channel: number,
      status: CameraStatus,
      errorMessage?: string
    ): void {
      const camera = this.cameras.get(channel)
      if (camera) {
        camera.status = status
        camera.errorMessage = errorMessage
        camera.lastUpdate = Date.now()
      }
    },

    /**
     * Update camera statistics from SSE data
     */
    updateStats(channel: number, data: DetectionData): void {
      this.initializeCamera(channel)
      const camera = this.cameras.get(channel)

      if (camera) {
        camera.fps = data.fps
        camera.detections = data.detections
        camera.staffCount = data.staffCount
        camera.customerCount = data.customerCount
        camera.lastUpdate = Date.now()
        camera.status = 'connected'
      }
    },

    /**
     * Reset all camera data
     */
    reset(): void {
      this.cameras.clear()
      this.activeCameras.clear()
      this.error = null
    }
  }
})
