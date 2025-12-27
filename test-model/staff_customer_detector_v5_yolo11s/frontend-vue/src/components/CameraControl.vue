<template>
  <div class="camera-control">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>Camera Control</span>
          <el-tag :type="sseConnected ? 'success' : 'danger'">
            {{ sseConnected ? 'Connected' : 'Disconnected' }}
          </el-tag>
        </div>
      </template>

      <div class="control-grid">
        <div
          v-for="channel in availableChannels"
          :key="channel"
          class="control-item"
        >
          <div class="channel-info">
            <span class="channel-number">Channel {{ channel }}</span>
            <el-tag
              :type="getCameraStatusType(channel)"
              size="small"
            >
              {{ getCameraStatus(channel) }}
            </el-tag>
          </div>

          <div class="control-buttons">
            <el-button
              type="success"
              size="small"
              :loading="isStarting[channel]"
              :disabled="isActive(channel)"
              @click="handleStart(channel)"
            >
              <el-icon><VideoPlay /></el-icon>
              Start
            </el-button>

            <el-button
              type="danger"
              size="small"
              :loading="isStopping[channel]"
              :disabled="!isActive(channel)"
              @click="handleStop(channel)"
            >
              <el-icon><VideoPause /></el-icon>
              Stop
            </el-button>
          </div>
        </div>
      </div>

      <el-divider />

      <div class="bulk-actions">
        <el-button
          type="primary"
          :loading="isStartingAll"
          @click="handleStartAll"
        >
          <el-icon><VideoPlay /></el-icon>
          Start All Cameras
        </el-button>

        <el-button
          type="warning"
          :loading="isStoppingAll"
          @click="handleStopAll"
        >
          <el-icon><VideoPause /></el-icon>
          Stop All Cameras
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useCameraStore } from '@/stores/camera'
import { ElMessage } from 'element-plus'
import { VideoPlay, VideoPause } from '@element-plus/icons-vue'
import type { CameraStatus } from '@/types'

const cameraStore = useCameraStore()

const isStarting = ref<Record<number, boolean>>({})
const isStopping = ref<Record<number, boolean>>({})
const isStartingAll = ref(false)
const isStoppingAll = ref(false)
const sseConnected = ref(true) // TODO: Connect to SSE service

// All 30 camera channels
const availableChannels = computed(() => Array.from({ length: 30 }, (_, i) => i + 1))

const isActive = (channel: number): boolean => {
  const camera = cameraStore.getCameraByChannel(channel)
  return camera?.status === 'connected' || camera?.status === 'connecting'
}

const getCameraStatus = (channel: number): string => {
  const camera = cameraStore.getCameraByChannel(channel)
  return camera?.status || 'stopped'
}

const getCameraStatusType = (channel: number): string => {
  const status = getCameraStatus(channel) as CameraStatus
  const typeMap: Record<CameraStatus, string> = {
    connected: 'success',
    connecting: 'warning',
    stopped: 'info',
    error: 'danger'
  }
  return typeMap[status] || 'info'
}

const handleStart = async (channel: number): Promise<void> => {
  isStarting.value[channel] = true

  try {
    await cameraStore.startCamera(channel)
    ElMessage.success(`Camera ${channel} started successfully`)
  } catch (error) {
    console.error('Failed to start camera:', error)
    ElMessage.error(`Failed to start camera ${channel}`)
  } finally {
    isStarting.value[channel] = false
  }
}

const handleStop = async (channel: number): Promise<void> => {
  isStopping.value[channel] = true

  try {
    await cameraStore.stopCamera(channel)
    ElMessage.success(`Camera ${channel} stopped`)
  } catch (error) {
    console.error('Failed to stop camera:', error)
    ElMessage.error(`Failed to stop camera ${channel}`)
  } finally {
    isStopping.value[channel] = false
  }
}

const handleStartAll = async (): Promise<void> => {
  isStartingAll.value = true

  try {
    await Promise.all(
      availableChannels.value.map(channel => cameraStore.startCamera(channel))
    )
    ElMessage.success('All cameras started')
  } catch (error) {
    console.error('Failed to start all cameras:', error)
    ElMessage.error('Failed to start some cameras')
  } finally {
    isStartingAll.value = false
  }
}

const handleStopAll = async (): Promise<void> => {
  isStoppingAll.value = true

  try {
    await Promise.all(
      cameraStore.activeCameras.map(channel => cameraStore.stopCamera(channel))
    )
    ElMessage.success('All cameras stopped')
  } catch (error) {
    console.error('Failed to stop all cameras:', error)
    ElMessage.error('Failed to stop some cameras')
  } finally {
    isStoppingAll.value = false
  }
}
</script>

<style scoped>
.camera-control {
  margin-bottom: 24px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.control-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}

.control-item {
  padding: 12px;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  background: #fafafa;
}

.channel-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.channel-number {
  font-weight: 600;
  font-size: 15px;
  color: #303133;
}

.control-buttons {
  display: flex;
  gap: 8px;
}

.control-buttons .el-button {
  flex: 1;
}

.bulk-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
}

.el-divider {
  margin: 20px 0;
}
</style>
