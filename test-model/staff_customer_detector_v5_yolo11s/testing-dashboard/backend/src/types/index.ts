/**
 * Type definitions for V5 Testing Dashboard
 */

// ============================================================================
// System Monitoring Types
// ============================================================================

export interface GPUStats {
  utilization: number; // 0-100
  memory_used: number; // MB
  memory_total: number; // MB
  temperature: number; // Celsius
  power_draw?: number; // Watts
}

export interface CPUStats {
  overall: number; // 0-100
  per_core: number[]; // Array of per-core usage 0-100
  temperature?: number; // Celsius (if available)
}

export interface MemoryStats {
  used: number; // GB
  total: number; // GB
  percent: number; // 0-100
  used_mb: number; // MB
  total_mb: number; // MB
}

export interface InferenceStats {
  avg_time_ms: number;
  min_time_ms: number;
  max_time_ms: number;
  queue_depth: number;
  queue_max: number;
}

export interface SystemStats {
  gpu: GPUStats | null;
  cpu: CPUStats;
  memory: MemoryStats;
  inference: InferenceStats;
  timestamp: string; // ISO 8601
}

// ============================================================================
// Camera Types
// ============================================================================

export type CameraStatus = 'active' | 'stopped' | 'error' | 'starting' | 'connecting' | 'connected' | 'failed';

export interface DetectionCounts {
  staff: number;
  customer: number;
  total: number;
}

export interface ConfidenceStats {
  avg: number;
  min: number;
  max: number;
}

export interface CameraStats {
  channel: number;
  status: CameraStatus;
  fps: number;
  target_fps: number;
  decode_time_ms: number;
  inference_time_ms: number;
  avg_decode_ms: number;
  avg_inference_ms: number;
  lag_ms: number; // Time from capture to display
  frame_drops: number;
  total_frames: number;
  processed_frames: number;
  skipped_frames: number;
  detections: DetectionCounts;
  confidence: ConfidenceStats;
  stream_width: number;
  stream_height: number;
  connection_status: string;
  decode_method: string;
  hw_accel_verified: boolean;
}

// ============================================================================
// API Request/Response Types
// ============================================================================

export interface StartCameraRequest {
  channel: number;
}

export interface StartCameraResponse {
  success: boolean;
  channel: number;
  status: CameraStatus;
  active_cameras: number;
  thread_count?: number;
  error?: string;
}

export interface StopCameraRequest {
  channel: number;
}

export interface StopCameraResponse {
  success: boolean;
  channel: number;
  error?: string;
}

export interface ActiveCamerasResponse {
  cameras: number[];
}

export interface AdjustFPSRequest {
  channel?: number; // If not provided, apply to all cameras
  fps: number; // 1-30
}

export interface AdjustFPSResponse {
  success: boolean;
  fps: number;
  affected_cameras: number[];
  error?: string;
}

// ============================================================================
// Stats API Response Types
// ============================================================================

export interface StatsSummary {
  active_cameras: number;
  total_fps: number;
  target_fps: number;
  avg_decode_ms: number;
  avg_inference_ms: number;
  hw_accel_cameras: number;
  hw_accel_percentage: number;
  inference_queue_size: number;
  batch_size: number;
}

export interface StatsResponse {
  system: SystemStats;
  cameras: CameraStats[];
  summary: StatsSummary;
}

export interface CameraDetailResponse {
  camera: CameraStats;
  system: SystemStats;
}

// ============================================================================
// Real-time Update Types (WebSocket)
// ============================================================================

export type WSMessageType =
  | 'stats_update'
  | 'camera_started'
  | 'camera_stopped'
  | 'camera_error'
  | 'system_alert';

export interface WSMessage<T = unknown> {
  type: WSMessageType;
  timestamp: string;
  data: T;
}

export interface StatsUpdateData {
  stats: StatsResponse;
}

export interface CameraEventData {
  channel: number;
  status: CameraStatus;
  message?: string;
}

export interface SystemAlertData {
  level: 'info' | 'warning' | 'error' | 'critical';
  message: string;
  metric?: string;
  value?: number;
}

// ============================================================================
// Configuration Types
// ============================================================================

export interface ServerConfig {
  port: number;
  pythonServerUrl: string;
  pythonServerPort: number;
  corsOrigins: string[];
  wsHeartbeatInterval: number; // ms
  statsUpdateInterval: number; // ms
}

// ============================================================================
// Error Types
// ============================================================================

export interface APIError {
  error: string;
  code?: string;
  details?: string;
}

// ============================================================================
// Logger Types
// ============================================================================

export type LogLevel = 'debug' | 'info' | 'warn' | 'error';

export interface LogEntry {
  timestamp: string;
  level: LogLevel;
  message: string;
  context?: Record<string, unknown>;
}
