import SimplePeer from 'simple-peer'
import type { WebRTCConfig } from '@/types'

interface PeerConnection {
  peer: SimplePeer.Instance
  stream: MediaStream | null
}

class WebRTCService {
  private connections = new Map<number, PeerConnection>()
  private config: WebRTCConfig = {
    iceServers: [
      { urls: 'stun:stun.l.google.com:19302' },
      { urls: 'stun:stun1.l.google.com:19302' }
    ]
  }

  /**
   * Create WebRTC connection for a camera channel
   */
  async createConnection(channel: number): Promise<MediaStream> {
    if (this.connections.has(channel)) {
      console.warn(`WebRTC connection already exists for channel ${channel}`)
      const existing = this.connections.get(channel)
      if (existing?.stream) {
        return existing.stream
      }
    }

    return new Promise((resolve, reject) => {
      const peer = new SimplePeer({
        initiator: true,
        config: this.config,
        trickle: true
      })

      const connection: PeerConnection = {
        peer,
        stream: null
      }

      this.connections.set(channel, connection)

      peer.on('signal', (signal) => {
        console.log('WebRTC signal generated for channel', channel, signal)
        // Send signal to backend via HTTP
        this.sendSignalToBackend(channel, signal)
      })

      peer.on('stream', (stream) => {
        console.log('WebRTC stream received for channel', channel)
        connection.stream = stream
        resolve(stream)
      })

      peer.on('error', (err) => {
        console.error('WebRTC error for channel', channel, err)
        this.close(channel)
        reject(err)
      })

      peer.on('close', () => {
        console.log('WebRTC connection closed for channel', channel)
        this.close(channel)
      })
    })
  }

  /**
   * Handle signal from backend
   */
  handleSignal(channel: number, signal: any): void {
    const connection = this.connections.get(channel)
    if (!connection) {
      console.error(`No WebRTC connection found for channel ${channel}`)
      return
    }

    try {
      connection.peer.signal(signal)
    } catch (error) {
      console.error('Failed to handle WebRTC signal:', error)
    }
  }

  /**
   * Close WebRTC connection for a channel
   */
  close(channel: number): void {
    const connection = this.connections.get(channel)
    if (!connection) return

    try {
      if (connection.stream) {
        connection.stream.getTracks().forEach(track => track.stop())
      }
      connection.peer.destroy()
    } catch (error) {
      console.error('Error closing WebRTC connection:', error)
    }

    this.connections.delete(channel)
  }

  /**
   * Close all WebRTC connections
   */
  closeAll(): void {
    this.connections.forEach((_, channel) => {
      this.close(channel)
    })
  }

  /**
   * Send signal to backend (to be implemented with actual API)
   */
  private async sendSignalToBackend(channel: number, signal: any): Promise<void> {
    try {
      // This would send the signal to the backend
      // Backend would respond with its own signal
      console.log('Sending signal to backend for channel', channel, signal)

      // For now, this is a placeholder
      // In production, this would be an HTTP request to /api/webrtc/signal
    } catch (error) {
      console.error('Failed to send signal to backend:', error)
    }
  }
}

export const webrtcService = new WebRTCService()
export default webrtcService
