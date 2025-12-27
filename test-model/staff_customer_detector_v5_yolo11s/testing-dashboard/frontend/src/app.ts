/**
 * Main Application
 * V5 YOLO11s Testing Dashboard
 */

import APIService from './services/api';
import RealtimeService from './services/realtime';
import { StatsResponse, CameraStats } from './types';

class Dashboard {
  private api: APIService;
  private realtime: RealtimeService;
  private activeCameras: Set<number> = new Set();
  private logEntries: Array<{ timestamp: string; level: string; message: string }> = [];
  private maxLogEntries = 100;
  private videoPage = 0;
  private videosPerPage = 6; // Browser HTTP/1.1 connection limit
  private activeVideoStreams: Map<number, HTMLImageElement> = new Map(); // Track active streams

  constructor() {
    // Initialize services
    this.api = new APIService('http://localhost:3000');
    this.realtime = new RealtimeService('http://localhost:3000');

    // Initialize UI
    this.initializeUI();

    // Connect to real-time updates
    this.connectRealtime();

    // Load initial data
    this.loadActiveCameras();
  }

  /**
   * Initialize UI components and event listeners
   */
  private initializeUI(): void {
    // Camera control buttons
    document.getElementById('startCameraBtn')?.addEventListener('click', () => this.startCamera());
    document.getElementById('stopCameraBtn')?.addEventListener('click', () => this.stopCamera());
    document.getElementById('stopAllBtn')?.addEventListener('click', () => this.stopAllCameras());

    // Video pagination buttons
    document.getElementById('prevPageBtn')?.addEventListener('click', () => this.previousPage());
    document.getElementById('nextPageBtn')?.addEventListener('click', () => this.nextPage());

    // Generate camera grid buttons (1-30)
    this.generateCameraButtons();

    // Enter key on input
    document.getElementById('channelInput')?.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') {
        this.startCamera();
      }
    });
  }

  /**
   * Generate 30 camera quick-select buttons
   */
  private generateCameraButtons(): void {
    const container = document.getElementById('cameraButtons');
    if (!container) return;

    for (let i = 1; i <= 30; i++) {
      const btn = document.createElement('button');
      btn.className = 'camera-btn';
      btn.textContent = String(i);
      btn.dataset.channel = String(i);
      btn.addEventListener('click', () => this.toggleCamera(i));
      container.appendChild(btn);
    }
  }

  /**
   * Connect to real-time stats stream
   */
  private connectRealtime(): void {
    this.updateConnectionStatus('connecting');

    this.realtime.connect(
      (stats) => {
        this.updateConnectionStatus('connected');
        this.updateUI(stats);
      },
      (error) => {
        this.updateConnectionStatus('disconnected');
        this.addLog('error', `Connection error: ${error.message}`);
      }
    );
  }

  /**
   * Update connection status indicator
   */
  private updateConnectionStatus(status: 'connecting' | 'connected' | 'disconnected'): void {
    const indicator = document.getElementById('connectionStatus');
    if (!indicator) return;

    indicator.className = `status-indicator ${status}`;

    const statusText = indicator.querySelector('.status-text');
    if (statusText) {
      const messages = {
        connecting: 'Connecting...',
        connected: 'Connected',
        disconnected: 'Disconnected',
      };
      statusText.textContent = messages[status];
    }
  }

  /**
   * Load active cameras from API
   */
  private async loadActiveCameras(): Promise<void> {
    try {
      const cameras = await this.api.getActiveCameras();
      this.activeCameras = new Set(cameras);
      this.updateCameraButtons();
      this.updateActiveCamerasList();
      this.updateVideoGrid();
    } catch (error) {
      this.addLog('error', `Failed to load active cameras: ${error}`);
    }
  }

  /**
   * Start a camera
   */
  private async startCamera(): Promise<void> {
    const input = document.getElementById('channelInput') as HTMLInputElement;
    const channel = parseInt(input.value);

    console.log(`🎬 [FRONTEND] START_CAMERA: User clicked start for channel ${channel}`);

    if (isNaN(channel) || channel < 1 || channel > 30) {
      console.error(`🎬 [FRONTEND] START_CAMERA: Invalid channel number: ${channel}`);
      this.addLog('error', 'Invalid channel number (1-30)');
      return;
    }

    if (this.activeCameras.has(channel)) {
      console.warn(`🎬 [FRONTEND] START_CAMERA: Channel ${channel} already active`);
      this.addLog('warning', `Camera ${channel} is already active`);
      return;
    }

    console.log(`🎬 [FRONTEND] START_CAMERA: Sending API request to start channel ${channel}...`);
    this.addLog('info', `Starting camera ${channel}...`);
    this.updateCameraButtonState(channel, 'starting');

    const result = await this.api.startCamera(channel);
    console.log(`🎬 [FRONTEND] START_CAMERA: API response for channel ${channel}:`, result);

    if (result.success) {
      console.log(`🎬 [FRONTEND] START_CAMERA: ✅ Channel ${channel} started successfully`);
      this.activeCameras.add(channel);
      this.updateCameraButtons();
      this.updateActiveCamerasList();
      this.updateVideoGrid();
      this.addLog('info', `Camera ${channel} started successfully`);

      // Auto-increment channel number
      input.value = String(channel + 1);
    } else {
      console.error(`🎬 [FRONTEND] START_CAMERA: ❌ Failed to start channel ${channel}:`, result.error);
      this.updateCameraButtonState(channel, 'error');
      this.addLog('error', `Failed to start camera ${channel}: ${result.error}`);
    }
  }

  /**
   * Stop a camera
   */
  private async stopCamera(channel?: number): Promise<void> {
    if (!channel) {
      const input = document.getElementById('channelInput') as HTMLInputElement;
      channel = parseInt(input.value);
    }

    if (isNaN(channel) || channel < 1 || channel > 30) {
      this.addLog('error', 'Invalid channel number (1-30)');
      return;
    }

    if (!this.activeCameras.has(channel)) {
      this.addLog('warning', `Camera ${channel} is not active`);
      return;
    }

    this.addLog('info', `Stopping camera ${channel}...`);

    const result = await this.api.stopCamera(channel);

    if (result.success) {
      this.activeCameras.delete(channel);
      this.updateCameraButtons();
      this.updateActiveCamerasList();
      this.updateVideoGrid();
      this.addLog('info', `Camera ${channel} stopped successfully`);
    } else {
      this.addLog('error', `Failed to stop camera ${channel}: ${result.error}`);
    }
  }

  /**
   * Stop all cameras
   */
  private async stopAllCameras(): Promise<void> {
    if (this.activeCameras.size === 0) {
      this.addLog('warning', 'No active cameras to stop');
      return;
    }

    this.addLog('info', `Stopping all ${this.activeCameras.size} cameras...`);

    const cameras = Array.from(this.activeCameras);
    for (const channel of cameras) {
      await this.stopCamera(channel);
    }
  }

  /**
   * Toggle camera on/off
   */
  private async toggleCamera(channel: number): Promise<void> {
    if (this.activeCameras.has(channel)) {
      await this.stopCamera(channel);
    } else {
      const input = document.getElementById('channelInput') as HTMLInputElement;
      input.value = String(channel);
      await this.startCamera();
    }
  }

  /**
   * Update camera button states
   */
  private updateCameraButtons(): void {
    const buttons = document.querySelectorAll('.camera-btn');
    buttons.forEach((btn) => {
      const channel = parseInt((btn as HTMLElement).dataset.channel || '0');
      btn.className = 'camera-btn';

      if (this.activeCameras.has(channel)) {
        btn.classList.add('active');
      }
    });
  }

  /**
   * Update camera button state
   */
  private updateCameraButtonState(channel: number, state: 'active' | 'starting' | 'error'): void {
    const btn = document.querySelector(`.camera-btn[data-channel="${channel}"]`);
    if (btn) {
      btn.className = `camera-btn ${state}`;
    }
  }

  /**
   * Update active cameras list
   */
  private updateActiveCamerasList(): void {
    const container = document.getElementById('activeCamerasList');
    const count = document.getElementById('activeCameraCount');

    if (!container || !count) return;

    count.textContent = String(this.activeCameras.size);

    if (this.activeCameras.size === 0) {
      container.innerHTML = '<p style="color: #808080;">No active cameras</p>';
      return;
    }

    const cameras = Array.from(this.activeCameras).sort((a, b) => a - b);
    container.innerHTML = cameras
      .map(
        (channel) => `
        <div class="active-camera-tag">
          Camera ${channel}
          <button onclick="dashboard.stopCamera(${channel})" title="Stop camera ${channel}">×</button>
        </div>
      `
      )
      .join('');
  }

  /**
   * Update video grid with active camera feeds
   */
  private updateVideoGrid(): void {
    const container = document.getElementById('videoGrid');
    if (!container) return;

    // ✅ FIX: Cleanup old video streams before rendering new page
    console.log(`🎥 [FRONTEND] Cleaning up ${this.activeVideoStreams.size} old video streams...`);
    this.activeVideoStreams.forEach((img, channel) => {
      console.log(`🎥 [FRONTEND] CH${channel}: Stopping old stream - clearing src and handlers`);
      // Stop the stream by clearing src
      img.src = '';
      // Remove all event handlers
      img.onload = null;
      img.onerror = null;
      img.onloadstart = null;
      img.onprogress = null;
    });
    this.activeVideoStreams.clear();
    console.log(`🎥 [FRONTEND] ✓ All old streams cleaned up`);

    if (this.activeCameras.size === 0) {
      container.innerHTML = `
        <div class="no-videos">
          <p>No active camera feeds</p>
          <p class="hint">Start cameras above to see live detection streams</p>
        </div>
      `;
      this.updatePaginationControls();
      return;
    }

    const cameras = Array.from(this.activeCameras).sort((a, b) => a - b);
    const totalPages = Math.ceil(cameras.length / this.videosPerPage);

    // Adjust current page if out of bounds
    if (this.videoPage >= totalPages) {
      this.videoPage = Math.max(0, totalPages - 1);
    }

    const startIdx = this.videoPage * this.videosPerPage;
    const endIdx = Math.min(startIdx + this.videosPerPage, cameras.length);
    const visibleCameras = cameras.slice(startIdx, endIdx);
    console.log(`🎥 [FRONTEND] Rendering page ${this.videoPage + 1}/${totalPages} with cameras:`, visibleCameras);

    container.innerHTML = `
      <div class="pagination-controls">
        <button id="prevPageBtn" class="btn btn-nav" ${this.videoPage === 0 ? 'disabled' : ''}>
          ← Previous
        </button>
        <span class="page-info">
          Page ${this.videoPage + 1} of ${totalPages} |
          Showing cameras ${startIdx + 1}-${endIdx} of ${cameras.length}
        </span>
        <button id="nextPageBtn" class="btn btn-nav" ${this.videoPage >= totalPages - 1 ? 'disabled' : ''}>
          Next →
        </button>
      </div>
      <div class="video-grid-content">
        ${visibleCameras
          .map(
            (channel) => `
          <div class="video-item" data-channel="${channel}">
            <div class="video-header">
              <div class="video-title">Camera ${channel}</div>
              <div class="video-status">
                <span class="video-status-dot"></span>
                <span>Live</span>
              </div>
            </div>
            <div class="video-container">
              <img
                src="http://localhost:8001/video_feed/${channel}?t=${Date.now()}"
                alt="Camera ${channel} feed"
                class="video-stream"
                id="video-stream-${channel}"
                onerror="setTimeout(() => { const img = document.getElementById('video-stream-${channel}'); if(img) img.src = 'http://localhost:8001/video_feed/${channel}?t=' + Date.now(); }, 2000)"
              />
              <div class="video-loading" id="loading-${channel}">Loading...</div>
            </div>
          </div>
        `
          )
          .join('')}
      </div>
    `;

    // Re-attach event listeners after updating DOM
    document.getElementById('prevPageBtn')?.addEventListener('click', () => this.previousPage());
    document.getElementById('nextPageBtn')?.addEventListener('click', () => this.nextPage());

    // Setup staggered loading and event handlers for video streams
    this.setupVideoStreamHandlers(visibleCameras);
  }

  /**
   * Setup video stream event handlers with staggered loading
   */
  private setupVideoStreamHandlers(channels: number[]): void {
    console.log(`🎥 [FRONTEND] Setting up video stream handlers for ${channels.length} cameras:`, channels);

    channels.forEach((channel, index) => {
      const img = document.getElementById(`video-stream-${channel}`) as HTMLImageElement;
      const loadingDiv = document.getElementById(`loading-${channel}`);

      if (!img) {
        console.error(`🎥 [FRONTEND] CH${channel}: Image element not found!`);
        return;
      }

      // ✅ FIX: Store image element in activeVideoStreams Map for cleanup tracking
      this.activeVideoStreams.set(channel, img);
      console.log(`🎥 [FRONTEND] CH${channel}: Registered in activeVideoStreams Map (total: ${this.activeVideoStreams.size})`);

      const staggerDelay = index * 200;
      console.log(`🎥 [FRONTEND] CH${channel}: Will start loading in ${staggerDelay}ms (position ${index + 1}/${channels.length})`);

      // Stagger initial load by 200ms per camera to avoid overwhelming browser
      setTimeout(() => {
        console.log(`🎥 [FRONTEND] CH${channel}: ⏰ Stagger timer fired, setting up handlers...`);

        // Track load start time
        const loadStartTime = Date.now();

        // Add load handler
        img.onload = () => {
          const loadTime = Date.now() - loadStartTime;
          console.log(`🎥 [FRONTEND] CH${channel}: ✅ onload fired! Load time: ${loadTime}ms`);
          if (loadingDiv) loadingDiv.style.display = 'none';
          this.addLog('info', `Camera ${channel} stream loaded (${loadTime}ms)`);
        };

        // Track if image starts loading
        img.onloadstart = () => {
          console.log(`🎥 [FRONTEND] CH${channel}: 🔄 onloadstart - browser started fetching`);
        };

        // Track progress
        img.onprogress = () => {
          const elapsed = Date.now() - loadStartTime;
          console.log(`🎥 [FRONTEND] CH${channel}: 📊 onprogress - data receiving... (${elapsed}ms elapsed)`);
        };

        // ✅ FIX: MJPEG streams don't always fire onload event reliably
        // Fallback: Check if image has valid dimensions after 2 seconds
        const checkLoadedInterval = setInterval(() => {
          if (img.naturalWidth > 0 && img.naturalHeight > 0) {
            const loadTime = Date.now() - loadStartTime;
            console.log(`🎥 [FRONTEND] CH${channel}: ✅ Image has valid dimensions (${img.naturalWidth}x${img.naturalHeight}), hiding loading overlay (${loadTime}ms)`);
            if (loadingDiv) loadingDiv.style.display = 'none';
            clearInterval(checkLoadedInterval);
          }
        }, 500); // Check every 500ms

        // Clear interval after 10 seconds to avoid memory leak
        setTimeout(() => clearInterval(checkLoadedInterval), 10000);

        // Enhanced error handler with exponential backoff
        let retryCount = 0;
        const maxRetries = 10;
        img.onerror = (event) => {
          const elapsed = Date.now() - loadStartTime;
          console.error(`🎥 [FRONTEND] CH${channel}: ❌ onerror fired! Elapsed: ${elapsed}ms, Retry: ${retryCount}/${maxRetries}`);
          console.error(`🎥 [FRONTEND] CH${channel}: Error event:`, event);
          console.error(`🎥 [FRONTEND] CH${channel}: Current src: ${img.src}`);
          console.error(`🎥 [FRONTEND] CH${channel}: naturalWidth: ${img.naturalWidth}, naturalHeight: ${img.naturalHeight}`);

          if (retryCount < maxRetries) {
            const backoff = Math.min(1000 * Math.pow(1.5, retryCount), 10000);
            retryCount++;
            console.warn(`🎥 [FRONTEND] CH${channel}: 🔄 Scheduling retry #${retryCount} in ${backoff}ms...`);
            this.addLog('warning', `Camera ${channel} error, retrying in ${(backoff/1000).toFixed(1)}s (attempt ${retryCount})`);

            setTimeout(() => {
              const newSrc = `http://localhost:8001/video_feed/${channel}?t=${Date.now()}&retry=${retryCount}`;
              console.log(`🎥 [FRONTEND] CH${channel}: 🔄 Retry #${retryCount} - setting new src: ${newSrc}`);
              img.src = newSrc;
            }, backoff);
          } else {
            console.error(`🎥 [FRONTEND] CH${channel}: ❌❌❌ Max retries (${maxRetries}) reached, giving up`);
            if (loadingDiv) {
              loadingDiv.innerHTML = `Camera ${channel}<br>Stream Error<br><small>Max retries reached</small>`;
              loadingDiv.style.color = '#ff0000';
            }
            this.addLog('error', `Camera ${channel} stream failed after ${maxRetries} retries`);
          }
        };

        // Trigger initial load
        const initialSrc = `http://localhost:8001/video_feed/${channel}?t=${Date.now()}`;
        console.log(`🎥 [FRONTEND] CH${channel}: 🚀 Setting initial src: ${initialSrc}`);
        // Don't actually set src here - it's already set in the HTML template
        // But log that we're ready
        console.log(`🎥 [FRONTEND] CH${channel}: 👀 Handlers ready, waiting for browser to load...`);
      }, staggerDelay);
    });
  }

  /**
   * Update pagination controls
   */
  private updatePaginationControls(): void {
    const prevBtn = document.getElementById('prevPageBtn') as HTMLButtonElement;
    const nextBtn = document.getElementById('nextPageBtn') as HTMLButtonElement;

    if (prevBtn) prevBtn.disabled = this.videoPage === 0;
    if (nextBtn) {
      const totalPages = Math.ceil(this.activeCameras.size / this.videosPerPage);
      nextBtn.disabled = this.videoPage >= totalPages - 1;
    }
  }

  /**
   * Navigate to previous page
   */
  private previousPage(): void {
    if (this.videoPage > 0) {
      this.videoPage--;
      this.updateVideoGrid();
      this.addLog('info', `Video page: ${this.videoPage + 1}`);
    }
  }

  /**
   * Navigate to next page
   */
  private nextPage(): void {
    const totalPages = Math.ceil(this.activeCameras.size / this.videosPerPage);
    if (this.videoPage < totalPages - 1) {
      this.videoPage++;
      this.updateVideoGrid();
      this.addLog('info', `Video page: ${this.videoPage + 1}`);
    }
  }

  /**
   * Update UI with stats
   */
  private updateUI(stats: StatsResponse): void {
    this.updateSystemStats(stats);
    this.updateCameraTable(stats.cameras);
    this.updateCPUCores(stats.system.cpu.per_core);
  }

  /**
   * Update system stats cards
   */
  private updateSystemStats(stats: StatsResponse): void {
    const { system, summary } = stats;

    // GPU Stats
    if (system.gpu) {
      this.updateStat('gpuUsage', `${system.gpu.utilization.toFixed(1)}%`, system.gpu.utilization);
      this.updateElement('gpuDetail', `${system.gpu.temperature}°C | ${system.gpu.memory_used.toFixed(0)}MB / ${system.gpu.memory_total.toFixed(0)}MB`);
      this.updateProgress('gpuProgress', system.gpu.utilization);
    } else {
      this.updateElement('gpuUsage', 'N/A');
      this.updateElement('gpuDetail', 'GPU not available');
    }

    // CPU Stats
    this.updateStat('cpuUsage', `${system.cpu.overall.toFixed(1)}%`, system.cpu.overall);
    this.updateElement('cpuDetail', system.cpu.temperature ? `${system.cpu.temperature.toFixed(1)}°C` : 'Temp N/A');
    this.updateProgress('cpuProgress', system.cpu.overall);

    // Memory Stats
    this.updateStat('memoryUsage', `${system.memory.percent.toFixed(1)}%`, system.memory.percent);
    this.updateElement('memoryDetail', `${system.memory.used.toFixed(1)} / ${system.memory.total.toFixed(1)} GB`);
    this.updateProgress('memoryProgress', system.memory.percent);

    // FPS Stats
    this.updateElement('totalFps', summary.total_fps.toFixed(1));

    // Inference Stats
    this.updateElement('inferenceTime', `${system.inference.avg_time_ms.toFixed(1)}ms`);
    this.updateElement(
      'inferenceDetail',
      `Min: ${system.inference.min_time_ms.toFixed(1)}ms | Max: ${system.inference.max_time_ms.toFixed(1)}ms`
    );

    // Queue Stats
    this.updateElement('queueDepth', `${system.inference.queue_depth}`);
    this.updateElement('queueDetail', `Batch size: ${summary.batch_size} | Max: ${system.inference.queue_max}`);
  }

  /**
   * Update stat with threshold-based coloring
   */
  private updateStat(id: string, value: string, percentage: number): void {
    const element = document.getElementById(id);
    if (!element) return;

    element.textContent = value;
    element.className = 'stat-value';

    if (percentage > 90) {
      element.classList.add('danger');
    } else if (percentage > 75) {
      element.classList.add('warning');
    }
  }

  /**
   * Update element text content
   */
  private updateElement(id: string, value: string): void {
    const element = document.getElementById(id);
    if (element) {
      element.textContent = value;
    }
  }

  /**
   * Update progress bar
   */
  private updateProgress(id: string, percentage: number): void {
    const element = document.getElementById(id);
    if (!element) return;

    element.style.width = `${Math.min(100, Math.max(0, percentage))}%`;
    element.className = 'progress-fill';

    if (percentage > 90) {
      element.classList.add('danger');
    } else if (percentage > 75) {
      element.classList.add('warning');
    }
  }

  /**
   * Update CPU cores visualization
   */
  private updateCPUCores(cores: number[]): void {
    const container = document.getElementById('cpuCores');
    if (!container) return;

    // Create core bars if needed
    if (container.children.length === 0) {
      cores.forEach((_, index) => {
        const bar = document.createElement('div');
        bar.className = 'core-bar';
        bar.innerHTML = `
          <div class="core-fill" data-core="${index}"></div>
          <div class="core-label">Core ${index + 1}</div>
          <div class="core-value" data-core="${index}">0%</div>
        `;
        container.appendChild(bar);
      });
    }

    // Update core usage
    cores.forEach((usage, index) => {
      const fill = container.querySelector(`.core-fill[data-core="${index}"]`) as HTMLElement;
      const value = container.querySelector(`.core-value[data-core="${index}"]`) as HTMLElement;

      if (fill) {
        fill.style.height = `${usage}%`;
      }

      if (value) {
        value.textContent = `${usage.toFixed(0)}%`;
      }
    });
  }

  /**
   * Update camera table
   */
  private updateCameraTable(cameras: CameraStats[]): void {
    const tbody = document.getElementById('cameraTableBody');
    if (!tbody) return;

    if (cameras.length === 0) {
      tbody.innerHTML = '<tr><td colspan="9" class="no-data">No active cameras</td></tr>';
      return;
    }

    tbody.innerHTML = cameras
      .sort((a, b) => a.channel - b.channel)
      .map((cam) => this.createCameraRow(cam))
      .join('');
  }

  /**
   * Create camera table row
   */
  private createCameraRow(cam: CameraStats): string {
    const statusClass = cam.status === 'active' || cam.status === 'connected' ? 'active' : cam.status === 'starting' || cam.status === 'connecting' ? 'starting' : 'error';

    return `
      <tr>
        <td><strong>${cam.channel}</strong></td>
        <td><span class="status-badge ${statusClass}">${cam.connection_status}</span></td>
        <td>${cam.fps.toFixed(1)} / ${cam.target_fps}</td>
        <td>${cam.avg_decode_ms.toFixed(1)}ms</td>
        <td>${cam.avg_inference_ms.toFixed(1)}ms</td>
        <td>${cam.lag_ms.toFixed(0)}ms</td>
        <td>${cam.detections?.total || 0}</td>
        <td>${cam.stream_width}×${cam.stream_height}</td>
        <td>${cam.hw_accel_verified ? '✓ GPU' : '✗ CPU'}</td>
      </tr>
    `;
  }

  /**
   * Add log entry
   */
  private addLog(level: 'info' | 'warning' | 'error', message: string): void {
    const timestamp = new Date().toLocaleTimeString();

    this.logEntries.push({ timestamp, level, message });

    // Limit log entries
    if (this.logEntries.length > this.maxLogEntries) {
      this.logEntries.shift();
    }

    this.updateConsoleLog();
  }

  /**
   * Update console log
   */
  private updateConsoleLog(): void {
    const container = document.getElementById('consoleLog');
    if (!container) return;

    container.innerHTML = this.logEntries
      .slice()
      .reverse()
      .map(
        (entry) => `
        <div class="log-entry ${entry.level}">
          <span class="log-timestamp">[${entry.timestamp}]</span>
          <span class="log-message">${entry.message}</span>
        </div>
      `
      )
      .join('');
  }

  /**
   * Public method to stop camera (called from HTML)
   */
  public async stopCameraPublic(channel: number): Promise<void> {
    await this.stopCamera(channel);
  }
}

// Initialize dashboard when DOM is loaded
let dashboard: Dashboard;

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    dashboard = new Dashboard();
    // Make dashboard globally accessible for HTML onclick handlers
    (window as any).dashboard = dashboard;
  });
} else {
  dashboard = new Dashboard();
  (window as any).dashboard = dashboard;
}

export default Dashboard;
