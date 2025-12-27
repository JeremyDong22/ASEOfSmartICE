/**
 * Real-time Stats Service using Server-Sent Events (SSE)
 */

import { StatsResponse } from '../types';

type StatsCallback = (stats: StatsResponse) => void;
type ErrorCallback = (error: Error) => void;

class RealtimeService {
  private eventSource: EventSource | null = null;
  private baseUrl: string;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000; // Start with 1 second

  constructor(baseUrl: string = 'http://localhost:3000') {
    this.baseUrl = baseUrl;
  }

  /**
   * Connect to the real-time stats stream
   */
  connect(onStats: StatsCallback, onError?: ErrorCallback): void {
    if (this.eventSource) {
      console.warn('Already connected to real-time stream');
      return;
    }

    const url = `${this.baseUrl}/api/stats/realtime`;
    console.log('Connecting to real-time stats stream:', url);

    this.eventSource = new EventSource(url);

    this.eventSource.onmessage = (event) => {
      try {
        const stats: StatsResponse = JSON.parse(event.data);
        onStats(stats);
        this.reconnectAttempts = 0; // Reset on successful message
      } catch (error) {
        console.error('Failed to parse stats:', error);
        if (onError) {
          onError(error instanceof Error ? error : new Error('Failed to parse stats'));
        }
      }
    };

    this.eventSource.onerror = (error) => {
      console.error('EventSource error:', error);

      // Close the connection
      this.disconnect();

      // Attempt to reconnect with exponential backoff
      if (this.reconnectAttempts < this.maxReconnectAttempts) {
        this.reconnectAttempts++;
        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);

        console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);

        setTimeout(() => {
          this.connect(onStats, onError);
        }, delay);
      } else {
        console.error('Max reconnect attempts reached');
        if (onError) {
          onError(new Error('Failed to connect to real-time stream after multiple attempts'));
        }
      }
    };

    this.eventSource.onopen = () => {
      console.log('Connected to real-time stats stream');
      this.reconnectAttempts = 0;
    };
  }

  /**
   * Disconnect from the real-time stream
   */
  disconnect(): void {
    if (this.eventSource) {
      console.log('Disconnecting from real-time stats stream');
      this.eventSource.close();
      this.eventSource = null;
    }
  }

  /**
   * Check if connected
   */
  isConnected(): boolean {
    return this.eventSource !== null && this.eventSource.readyState === EventSource.OPEN;
  }

  /**
   * Get connection state
   */
  getState(): number {
    return this.eventSource?.readyState ?? EventSource.CLOSED;
  }
}

export default RealtimeService;
