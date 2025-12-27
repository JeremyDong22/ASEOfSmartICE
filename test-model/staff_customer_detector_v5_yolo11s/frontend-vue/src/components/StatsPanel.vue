<template>
  <div class="stats-panel">
    <el-card shadow="hover" class="stat-card">
      <div class="stat-content">
        <el-icon class="stat-icon" color="#409eff">
          <VideoCamera />
        </el-icon>
        <div class="stat-info">
          <div class="stat-value">{{ activeCameras }}</div>
          <div class="stat-label">Active Cameras</div>
        </div>
      </div>
    </el-card>

    <el-card shadow="hover" class="stat-card">
      <div class="stat-content">
        <el-icon class="stat-icon" color="#67c23a">
          <User />
        </el-icon>
        <div class="stat-info">
          <div class="stat-value">{{ totalStaff }}</div>
          <div class="stat-label">Staff Detected</div>
        </div>
      </div>
    </el-card>

    <el-card shadow="hover" class="stat-card">
      <div class="stat-content">
        <el-icon class="stat-icon" color="#f56c6c">
          <UserFilled />
        </el-icon>
        <div class="stat-info">
          <div class="stat-value">{{ totalCustomers }}</div>
          <div class="stat-label">Customers Detected</div>
        </div>
      </div>
    </el-card>

    <el-card shadow="hover" class="stat-card">
      <div class="stat-content">
        <el-icon class="stat-icon" color="#e6a23c">
          <Odometer />
        </el-icon>
        <div class="stat-info">
          <div class="stat-value">{{ averageFps }}</div>
          <div class="stat-label">Average FPS</div>
        </div>
      </div>
    </el-card>

    <el-card shadow="hover" class="stat-card">
      <div class="stat-content">
        <el-icon class="stat-icon" color="#909399">
          <Connection />
        </el-icon>
        <div class="stat-info">
          <div class="stat-value">{{ totalDetections }}</div>
          <div class="stat-label">Total Detections</div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useCameraStore } from '@/stores/camera'
import {
  VideoCamera,
  User,
  UserFilled,
  Odometer,
  Connection
} from '@element-plus/icons-vue'

const cameraStore = useCameraStore()

const activeCameras = computed(() => cameraStore.getActiveCameras.length)
const totalStaff = computed(() => cameraStore.getTotalStaff)
const totalCustomers = computed(() => cameraStore.getTotalCustomers)
const totalDetections = computed(() => cameraStore.getTotalDetections)
const averageFps = computed(() => cameraStore.getAverageFps.toFixed(1))
</script>

<style scoped>
.stats-panel {
  display: flex;
  gap: 16px;
  padding: 16px 0;
  flex-wrap: wrap;
}

.stat-card {
  flex: 1;
  min-width: 200px;
  cursor: default;
}

.stat-content {
  display: flex;
  align-items: center;
  gap: 16px;
}

.stat-icon {
  font-size: 40px;
  flex-shrink: 0;
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 28px;
  font-weight: bold;
  color: #303133;
  line-height: 1.2;
}

.stat-label {
  font-size: 14px;
  color: #909399;
  margin-top: 4px;
}
</style>
