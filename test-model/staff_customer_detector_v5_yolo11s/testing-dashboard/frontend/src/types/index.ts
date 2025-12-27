/**
 * Frontend Type Definitions
 * Mirrors backend types for type safety
 */

export interface GPUStats {
  utilization: number;
  memory_used: number;
  memory_total: number;
  temperature: number;
  power_draw?: number;
}

export interface CPUStats {
  overall: number;
  per_core: number[];
  temperature?: number;
}

export interface MemoryStats {
  used: number;
  total: number;
  percent: number;
  used_mb: number;
  total_mb: number;
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
  timestamp: string;
}

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
  lag_ms: number;
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

export interface APIError {
  error: string;
  code?: string;
  details?: string;
}
