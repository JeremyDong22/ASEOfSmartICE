// Camera status types
export type CameraStatus = 'stopped' | 'connecting' | 'connected' | 'error'

// Camera interface
export interface Camera {
  channel: number
  status: CameraStatus
  fps: number
  detections: number
  staffCount: number
  customerCount: number
  lastUpdate: number
  errorMessage?: string
}

// Detection data from SSE
export interface DetectionData {
  channel: number
  fps: number
  detections: number
  staffCount: number
  customerCount: number
  timestamp: number
}

// API response types
export interface StatsResponse {
  totalCameras: number
  activeCameras: number
  totalDetections: number
  totalStaff: number
  totalCustomers: number
  averageFps: number
}

export interface CameraListResponse {
  cameras: number[]
}

export interface CameraStartResponse {
  success: boolean
  channel: number
  message?: string
}

export interface CameraStopResponse {
  success: boolean
  channel: number
  message?: string
}

// WebRTC types
export interface WebRTCConfig {
  iceServers: Array<{
    urls: string | string[]
    username?: string
    credential?: string
  }>
}

export interface WebRTCSignal {
  type: 'offer' | 'answer'
  sdp: string
}

// SSE message types
export interface SSEMessage {
  type: 'detection' | 'stats' | 'error' | 'heartbeat'
  data: DetectionData | StatsResponse | { message: string }
}
