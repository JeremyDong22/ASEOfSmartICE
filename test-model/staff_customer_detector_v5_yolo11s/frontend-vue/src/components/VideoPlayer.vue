<template>
  <div class="video-player" :class="{ error: camera?.status === 'error' }">
    <!-- MJPEG stream (no WebRTC for now) -->
    <img
      v-if="camera?.status === 'connected'"
      :src="mjpegUrl"
      alt="Camera stream"
      class="video-stream"
      @load="handleImageLoad"
      @error="handleImageError"
    />

    <!-- Loading state -->
    <div v-if="camera?.status === 'connecting'" class="status-overlay">
      <el-icon class="is-loading">
        <Loading />
      </el-icon>
      <p>Connecting...</p>
    </div>

    <!-- Error state -->
    <div v-if="camera?.status === 'error'" class="status-overlay error">
      <el-icon>
        <CircleClose />
      </el-icon>
      <p>{{ camera.errorMessage || 'Connection error' }}</p>
    </div>

    <!-- Stopped state -->
    <div v-if="camera?.status === 'stopped'" class="status-overlay">
      <el-icon>
        <VideoPause />
      </el-icon>
      <p>Camera Stopped</p>
    </div>

    <!-- Stats overlay -->
    <div v-if="camera?.status === 'connected'" class="stats-overlay">
      <div class="channel-label">Channel {{ channel }}</div>
      <div class="stats-row">
        <span class="stat-item">
          <el-icon><VideoPlay /></el-icon>
          {{ camera.fps.toFixed(1) }} FPS
        </span>
      </div>
      <div class="stats-row">
        <span class="stat-item staff">
          <el-icon><User /></el-icon>
          Staff: {{ camera.staffCount }}
        </span>
        <span class="stat-item customer">
          <el-icon><UserFilled /></el-icon>
          Customer: {{ camera.customerCount }}
        </span>
      </div>
      <div class="stats-row">
        <span class="stat-item total">
          Total: {{ camera.detections }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useCameraStore } from '@/stores/camera'
import {
  Loading,
  CircleClose,
  VideoPause,
  VideoPlay,
  User,
  UserFilled
} from '@element-plus/icons-vue'

interface Props {
  channel: number
}

const props = defineProps<Props>()

const cameraStore = useCameraStore()

const camera = computed(() => cameraStore.getCameraByChannel(props.channel))

const mjpegUrl = computed(() => {
  return `http://localhost:8001/video_feed/${props.channel}`
})

const handleImageLoad = () => {
  console.log(`Stream loaded for channel ${props.channel}`)
}

const handleImageError = () => {
  console.error(`Failed to load MJPEG stream for channel ${props.channel}`)
  cameraStore.updateCameraStatus(props.channel, 'error', 'Failed to load stream')
}
</script>

<style scoped>
.video-player {
  position: relative;
  width: 100%;
  height: 100%;
  background: #000;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.video-player.error {
  border: 2px solid #f56c6c;
}

.video-stream {
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
}

.status-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.7);
  color: #fff;
  font-size: 16px;
}

.status-overlay.error {
  color: #f56c6c;
}

.status-overlay .el-icon {
  font-size: 48px;
  margin-bottom: 12px;
}

.stats-overlay {
  position: absolute;
  top: 8px;
  left: 8px;
  background: rgba(0, 0, 0, 0.75);
  color: #fff;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 13px;
  line-height: 1.6;
}

.channel-label {
  font-weight: bold;
  font-size: 14px;
  margin-bottom: 6px;
  color: #67c23a;
}

.stats-row {
  display: flex;
  gap: 12px;
  margin-top: 4px;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.stat-item.staff {
  color: #67c23a;
}

.stat-item.customer {
  color: #f56c6c;
}

.stat-item.total {
  color: #909399;
}

.stat-item .el-icon {
  font-size: 14px;
}
</style>
