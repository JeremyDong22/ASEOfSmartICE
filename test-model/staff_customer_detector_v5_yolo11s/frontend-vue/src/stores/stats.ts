import { defineStore } from 'pinia'

export const useStatsStore = defineStore('stats', {
  state: () => ({
    globalStats: {
      totalCameras: 0,
      activeCameras: 0,
      totalDetections: 0,
      totalStaff: 0,
      totalCustomers: 0,
      averageFps: 0
    },
    lastUpdate: 0,
    isLoading: false
  }),

  getters: {
    /**
     * Check if stats are stale (older than 5 seconds)
     */
    isStale: (state): boolean => {
      return Date.now() - state.lastUpdate > 5000
    },

    /**
     * Get formatted average FPS
     */
    formattedAverageFps: (state): string => {
      return state.globalStats.averageFps.toFixed(1)
    }
  },

  actions: {
    /**
     * Update global statistics
     */
    updateGlobalStats(stats: {
      totalCameras?: number
      activeCameras?: number
      totalDetections?: number
      totalStaff?: number
      totalCustomers?: number
      averageFps?: number
    }): void {
      Object.assign(this.globalStats, stats)
      this.lastUpdate = Date.now()
    },

    /**
     * Reset all statistics
     */
    reset(): void {
      this.globalStats = {
        totalCameras: 0,
        activeCameras: 0,
        totalDetections: 0,
        totalStaff: 0,
        totalCustomers: 0,
        averageFps: 0
      }
      this.lastUpdate = 0
    }
  }
})
