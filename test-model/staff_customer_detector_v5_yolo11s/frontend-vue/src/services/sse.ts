import type { SSEMessage, DetectionData } from '@/types'

type MessageHandler = (data: DetectionData) => void
type ErrorHandler = (error: Error) => void

class SSEService {
  private eventSource: EventSource | null = null
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 2000

  /**
   * Connect to SSE endpoint for real-time updates
   */
  connect(onMessage: MessageHandler, onError?: ErrorHandler): void {
    if (this.eventSource) {
      console.warn('SSE already connected')
      return
    }

    const url = '/api/stream/events'
    console.log('Connecting to SSE:', url)

    this.eventSource = new EventSource(url)

    this.eventSource.onmessage = (event) => {
      try {
        const message: SSEMessage = JSON.parse(event.data)

        if (message.type === 'detection') {
          onMessage(message.data as DetectionData)
        } else if (message.type === 'heartbeat') {
          console.debug('SSE heartbeat received')
        }
      } catch (error) {
        console.error('Failed to parse SSE message:', error)
        onError?.(error as Error)
      }
    }

    this.eventSource.onerror = (error) => {
      console.error('SSE connection error:', error)

      if (this.eventSource?.readyState === EventSource.CLOSED) {
        console.log('SSE connection closed, attempting reconnect...')
        this.handleReconnect(onMessage, onError)
      }

      onError?.(new Error('SSE connection error'))
    }

    this.eventSource.onopen = () => {
      console.log('SSE connection established')
      this.reconnectAttempts = 0
    }
  }

  /**
   * Disconnect from SSE
   */
  disconnect(): void {
    if (this.eventSource) {
      console.log('Disconnecting SSE')
      this.eventSource.close()
      this.eventSource = null
      this.reconnectAttempts = 0
    }
  }

  /**
   * Handle reconnection logic
   */
  private handleReconnect(onMessage: MessageHandler, onError?: ErrorHandler): void {
    this.disconnect()

    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max SSE reconnect attempts reached')
      onError?.(new Error('Max reconnect attempts reached'))
      return
    }

    this.reconnectAttempts++
    const delay = this.reconnectDelay * this.reconnectAttempts

    console.log(`Reconnecting SSE in ${delay}ms (attempt ${this.reconnectAttempts})`)

    setTimeout(() => {
      this.connect(onMessage, onError)
    }, delay)
  }

  /**
   * Check if SSE is connected
   */
  isConnected(): boolean {
    return this.eventSource !== null && this.eventSource.readyState === EventSource.OPEN
  }
}

export const sseService = new SSEService()
export default sseService
