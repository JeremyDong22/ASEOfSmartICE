<template>
  <el-container class="app-container">
    <el-header class="app-header">
      <div class="header-content">
        <h1 class="app-title">
          <el-icon class="title-icon"><VideoCamera /></el-icon>
          Staff/Customer Detector Dashboard
        </h1>
        <div class="header-actions">
          <el-tag type="success">V5 - YOLO11s</el-tag>
        </div>
      </div>
    </el-header>

    <el-main class="app-main">
      <StatsPanel />
      <CameraControl />
      <VideoGrid :use-web-r-t-c="false" :grid-columns="2" />
    </el-main>

    <el-footer class="app-footer">
      <p>SmartICE Detection System - Powered by YOLO11s</p>
    </el-footer>
  </el-container>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { useCameraStore } from '@/stores/camera'
import { sseService } from '@/services/sse'
import StatsPanel from '@/components/StatsPanel.vue'
import CameraControl from '@/components/CameraControl.vue'
import VideoGrid from '@/components/VideoGrid.vue'
import { VideoCamera } from '@element-plus/icons-vue'
import type { DetectionData } from '@/types'

const cameraStore = useCameraStore()

const handleSSEMessage = (data: DetectionData) => {
  cameraStore.updateStats(data.channel, data)
}

const handleSSEError = (error: Error) => {
  console.error('SSE error:', error)
}

onMounted(async () => {
  // Load available cameras
  await cameraStore.loadAvailableCameras()

  // Connect to SSE for real-time updates
  sseService.connect(handleSSEMessage, handleSSEError)
})

onUnmounted(() => {
  // Cleanup SSE connection
  sseService.disconnect()
})
</script>

<style scoped>
.app-container {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.app-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 20px 32px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  max-width: 1800px;
  margin: 0 auto;
}

.app-title {
  margin: 0;
  font-size: 28px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 12px;
}

.title-icon {
  font-size: 32px;
}

.header-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

.app-main {
  flex: 1;
  padding: 24px 32px;
  overflow-y: auto;
  background: #f5f7fa;
}

.app-footer {
  background: #ffffff;
  border-top: 1px solid #e4e7ed;
  text-align: center;
  color: #909399;
  padding: 16px;
}

.app-footer p {
  margin: 0;
  font-size: 14px;
}
</style>
