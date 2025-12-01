/**
 * WebSocket Hook for Real-time Process Monitoring
 */

import { useEffect, useRef, useState } from 'react';
import type { ProcessEvent } from '../types';

export interface UseWebSocketOptions {
  onEvent?: (event: ProcessEvent) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
}

export function useWebSocket(
  url: string | null,
  options: UseWebSocketOptions = {}
) {
  const [isConnected, setIsConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState<ProcessEvent | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!url) return;

    // Create WebSocket connection
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('[WebSocket] Connected:', url);
      setIsConnected(true);
      options.onConnect?.();
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as ProcessEvent;
        setLastEvent(data);
        options.onEvent?.(data);
      } catch (error) {
        console.error('[WebSocket] Failed to parse message:', error);
      }
    };

    ws.onerror = (error) => {
      console.error('[WebSocket] Error:', error);
      options.onError?.(error);
    };

    ws.onclose = () => {
      console.log('[WebSocket] Disconnected');
      setIsConnected(false);
      options.onDisconnect?.();
    };

    // Cleanup on unmount
    return () => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.close();
      }
    };
  }, [url]);

  return {
    isConnected,
    lastEvent,
    ws: wsRef.current,
  };
}
