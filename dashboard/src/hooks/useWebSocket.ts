import { useEffect, useRef, useCallback, useState } from "react";

type EventHandler = (data: unknown) => void;

export function useWebSocket(url: string) {
  const wsRef = useRef<WebSocket | null>(null);
  const handlersRef = useRef<Map<string, EventHandler[]>>(new Map());
  const [connected, setConnected] = useState(false);

  const on = useCallback((event: string, handler: EventHandler) => {
    const handlers = handlersRef.current.get(event) || [];
    handlers.push(handler);
    handlersRef.current.set(event, handlers);
    return () => {
      const h = handlersRef.current.get(event) || [];
      handlersRef.current.set(
        event,
        h.filter((fn) => fn !== handler)
      );
    };
  }, []);

  useEffect(() => {
    let reconnectTimer: ReturnType<typeof setTimeout>;
    let ws: WebSocket;

    function connect() {
      ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => setConnected(true);

      ws.onclose = () => {
        setConnected(false);
        reconnectTimer = setTimeout(connect, 3000);
      };

      ws.onerror = () => ws.close();

      ws.onmessage = (evt) => {
        try {
          const msg = JSON.parse(evt.data);
          const handlers = handlersRef.current.get(msg.event) || [];
          for (const h of handlers) h(msg.data);
        } catch {
          // ignore malformed messages
        }
      };
    }

    connect();

    return () => {
      clearTimeout(reconnectTimer);
      ws?.close();
    };
  }, [url]);

  return { connected, on };
}
