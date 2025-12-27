<template>
  <div class="video-grid">
    <RecycleScroller
      v-if="cameras.length > 0"
      :items="cameras"
      :item-size="itemSize"
      :grid-items="gridColumns"
      key-field="channel"
      class="scroller"
    >
      <template #default="{ item }">
        <div class="grid-item">
          <VideoPlayer :channel="item.channel" :use-web-r-t-c="useWebRTC" />
        </div>
      </template>
    </RecycleScroller>

    <el-empty
      v-else
      description="No cameras available"
      :image-size="200"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { RecycleScroller } from 'vue-virtual-scroller'
import 'vue-virtual-scroller/dist/vue-virtual-scroller.css'
import VideoPlayer from './VideoPlayer.vue'
import { useCameraStore } from '@/stores/camera'

interface Props {
  useWebRTC?: boolean
  gridColumns?: number
}

const props = withDefaults(defineProps<Props>(), {
  useWebRTC: false,
  gridColumns: 2
})

const cameraStore = useCameraStore()

const cameras = computed(() => {
  // Return all initialized cameras
  return Array.from(cameraStore.cameras.values()).sort(
    (a, b) => a.channel - b.channel
  )
})

// Calculate item size based on grid columns
// Each item needs height for video (16:9 ratio) + padding
const itemSize = computed(() => {
  const viewportWidth = window.innerWidth
  const itemWidth = viewportWidth / props.gridColumns
  const videoHeight = (itemWidth * 9) / 16 // 16:9 aspect ratio
  return Math.floor(videoHeight + 32) // Add padding
})
</script>

<style scoped>
.video-grid {
  width: 100%;
  height: 100%;
  overflow: hidden;
}

.scroller {
  height: 100%;
}

.grid-item {
  padding: 8px;
  height: 100%;
}

:deep(.vue-recycle-scroller__item-wrapper) {
  display: grid;
  grid-template-columns: repeat(v-bind(gridColumns), 1fr);
  gap: 16px;
  padding: 16px;
}
</style>
