/**
 * Logger utility for consistent logging across the application
 */

import { LogLevel, LogEntry } from '../types';

class Logger {
  private context: string;

  constructor(context: string = 'App') {
    this.context = context;
  }

  private formatMessage(level: LogLevel, message: string, meta?: Record<string, unknown>): LogEntry {
    const entry: LogEntry = {
      timestamp: new Date().toISOString(),
      level,
      message: `[${this.context}] ${message}`,
    };

    if (meta) {
      entry.context = meta;
    }

    return entry;
  }

  private log(level: LogLevel, message: string, meta?: Record<string, unknown>): void {
    const entry = this.formatMessage(level, message, meta);
    const timestamp = new Date().toLocaleTimeString();
    const emoji = this.getEmoji(level);

    const logMessage = `${emoji} [${timestamp}] [${level.toUpperCase()}] ${entry.message}`;

    switch (level) {
      case 'error':
        console.error(logMessage, meta ? meta : '');
        break;
      case 'warn':
        console.warn(logMessage, meta ? meta : '');
        break;
      case 'info':
        console.info(logMessage, meta ? meta : '');
        break;
      case 'debug':
        console.debug(logMessage, meta ? meta : '');
        break;
    }
  }

  private getEmoji(level: LogLevel): string {
    switch (level) {
      case 'error':
        return '❌';
      case 'warn':
        return '⚠️';
      case 'info':
        return 'ℹ️';
      case 'debug':
        return '🔍';
      default:
        return '📝';
    }
  }

  debug(message: string, meta?: Record<string, unknown>): void {
    this.log('debug', message, meta);
  }

  info(message: string, meta?: Record<string, unknown>): void {
    this.log('info', message, meta);
  }

  warn(message: string, meta?: Record<string, unknown>): void {
    this.log('warn', message, meta);
  }

  error(message: string, meta?: Record<string, unknown>): void {
    this.log('error', message, meta);
  }

  setContext(context: string): void {
    this.context = context;
  }
}

export default Logger;
