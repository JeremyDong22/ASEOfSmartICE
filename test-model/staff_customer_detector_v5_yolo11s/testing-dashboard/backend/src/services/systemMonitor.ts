/**
 * System Monitoring Service
 * Monitors GPU, CPU, and memory usage using system utilities
 */

import { exec } from 'child_process';
import { promisify } from 'util';
import Logger from '../utils/logger';
import { GPUStats, CPUStats, MemoryStats } from '../types';

const execAsync = promisify(exec);
const logger = new Logger('SystemMonitor');

class SystemMonitorService {
  /**
   * Get GPU statistics using nvidia-smi
   */
  async getGPUStats(): Promise<GPUStats | null> {
    try {
      const { stdout } = await execAsync(
        'nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw --format=csv,noheader,nounits',
        { timeout: 2000 }
      );

      const parts = stdout.trim().split(',').map(p => parseFloat(p.trim()));

      if (parts.length >= 4) {
        return {
          utilization: parts[0],
          memory_used: parts[1],
          memory_total: parts[2],
          temperature: parts[3],
          power_draw: parts[4] || undefined,
        };
      }

      return null;
    } catch (error) {
      // GPU not available or nvidia-smi not installed
      return null;
    }
  }

  /**
   * Get CPU statistics
   */
  async getCPUStats(): Promise<CPUStats> {
    try {
      // Get overall CPU usage
      const overall = await this.getCPUUsage();

      // Get per-core CPU usage
      const perCore = await this.getCPUPerCore();

      // Get CPU temperature (if available)
      const temperature = await this.getCPUTemperature();

      return {
        overall,
        per_core: perCore,
        temperature,
      };
    } catch (error) {
      logger.error('Failed to get CPU stats', { error: String(error) });
      return {
        overall: 0,
        per_core: [],
        temperature: undefined,
      };
    }
  }

  /**
   * Get overall CPU usage percentage
   */
  private async getCPUUsage(): Promise<number> {
    try {
      // Use /proc/stat to calculate CPU usage
      const stat1 = await this.readProcStat();
      await this.sleep(100); // Wait 100ms
      const stat2 = await this.readProcStat();

      const idle1 = stat1.idle + stat1.iowait;
      const idle2 = stat2.idle + stat2.iowait;

      const total1 = stat1.total;
      const total2 = stat2.total;

      const idleDelta = idle2 - idle1;
      const totalDelta = total2 - total1;

      const usage = 100 * (1 - idleDelta / totalDelta);
      return Math.max(0, Math.min(100, usage));
    } catch (error) {
      return 0;
    }
  }

  /**
   * Get per-core CPU usage
   */
  private async getCPUPerCore(): Promise<number[]> {
    try {
      const { stdout } = await execAsync('mpstat -P ALL 1 1 | grep -E "Average.*[0-9]"', {
        timeout: 2000,
      });

      const lines = stdout.trim().split('\n').filter(l => l.includes('Average'));
      const coreUsage: number[] = [];

      for (const line of lines) {
        const parts = line.trim().split(/\s+/);
        if (parts.length >= 12) {
          const idle = parseFloat(parts[11]);
          const usage = 100 - idle;
          coreUsage.push(Math.max(0, Math.min(100, usage)));
        }
      }

      return coreUsage;
    } catch (error) {
      // Fallback: return empty array if mpstat not available
      return [];
    }
  }

  /**
   * Read /proc/stat for CPU statistics
   */
  private async readProcStat(): Promise<{
    user: number;
    nice: number;
    system: number;
    idle: number;
    iowait: number;
    irq: number;
    softirq: number;
    total: number;
  }> {
    const { stdout } = await execAsync('cat /proc/stat | head -1');
    const parts = stdout.trim().split(/\s+/).slice(1).map(Number);

    const [user, nice, system, idle, iowait, irq, softirq] = parts;
    const total = user + nice + system + idle + iowait + irq + softirq;

    return { user, nice, system, idle, iowait, irq, softirq, total };
  }

  /**
   * Get CPU temperature (if available)
   */
  private async getCPUTemperature(): Promise<number | undefined> {
    try {
      // Try reading from sensors
      const { stdout } = await execAsync(
        'sensors | grep -E "Package id 0|Tctl" | head -1 | grep -oP "\\+\\d+\\.\\d+" | head -1',
        { timeout: 1000 }
      );

      const temp = parseFloat(stdout.trim().replace('+', ''));
      return isNaN(temp) ? undefined : temp;
    } catch (error) {
      // Temperature not available
      return undefined;
    }
  }

  /**
   * Get memory statistics
   */
  async getMemoryStats(): Promise<MemoryStats> {
    try {
      const { stdout } = await execAsync('cat /proc/meminfo', { timeout: 1000 });

      const lines = stdout.split('\n');
      let total = 0;
      let available = 0;

      for (const line of lines) {
        if (line.startsWith('MemTotal:')) {
          total = parseInt(line.split(/\s+/)[1]);
        } else if (line.startsWith('MemAvailable:')) {
          available = parseInt(line.split(/\s+/)[1]);
        }
      }

      const used = total - available;
      const percent = (used / total) * 100;

      return {
        used: used / (1024 * 1024), // Convert KB to GB
        total: total / (1024 * 1024),
        percent: Math.max(0, Math.min(100, percent)),
        used_mb: used / 1024, // Convert KB to MB
        total_mb: total / 1024,
      };
    } catch (error) {
      logger.error('Failed to get memory stats', { error: String(error) });
      return {
        used: 0,
        total: 0,
        percent: 0,
        used_mb: 0,
        total_mb: 0,
      };
    }
  }

  /**
   * Sleep utility
   */
  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Get all system stats at once
   */
  async getAllStats() {
    const [gpu, cpu, memory] = await Promise.all([
      this.getGPUStats(),
      this.getCPUStats(),
      this.getMemoryStats(),
    ]);

    return { gpu, cpu, memory };
  }
}

export default SystemMonitorService;
