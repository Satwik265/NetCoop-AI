import { useEffect, useRef, useState, useCallback } from "react";
import { EnvelopeLogItem } from "../types/protocol";

export type WebSocketStatus = "connected" | "connecting" | "offline";

export interface UseWebSocketReturn {
  status: WebSocketStatus;
  lastEventTime: string | null;
  envelopes: EnvelopeLogItem[];
  addEnvelope: (env: EnvelopeLogItem) => void;
  clearEnvelopes: () => void;
  isPaused: boolean;
  setIsPaused: (paused: boolean) => void;
}

export function useWebSocket(initialEnvelopes: EnvelopeLogItem[] = []): UseWebSocketReturn {
  const [status, setStatus] = useState<WebSocketStatus>("connecting");
  const [lastEventTime, setLastEventTime] = useState<string | null>(null);
  const [envelopes, setEnvelopes] = useState<EnvelopeLogItem[]>(initialEnvelopes);
  const [isPaused, setIsPaused] = useState<boolean>(false);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const reconnectAttemptsRef = useRef<number>(0);
  const seenIdsRef = useRef<Set<string>>(new Set(initialEnvelopes.map((e) => e.message_id)));

  const addEnvelope = useCallback(
    (env: EnvelopeLogItem) => {
      if (!env.message_id || seenIdsRef.current.has(env.message_id)) {
        return;
      }
      seenIdsRef.current.add(env.message_id);
      setLastEventTime(env.timestamp_utc || new Date().toISOString());
      if (!isPaused) {
        setEnvelopes((prev) => [...prev, env]);
      }
    },
    [isPaused]
  );

  const clearEnvelopes = useCallback(() => {
    seenIdsRef.current.clear();
    setEnvelopes([]);
  }, []);

  const connect = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      return;
    }

    setStatus("connecting");
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/ws/events`;

    try {
      const socket = new WebSocket(wsUrl);
      wsRef.current = socket;

      socket.onopen = () => {
        setStatus("connected");
        reconnectAttemptsRef.current = 0;
      };

      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.event_type === "envelope_logged" && data.envelope) {
            const env = data.envelope;
            const logItem: EnvelopeLogItem = {
              id: Date.now(),
              message_id: env.header?.message_id || `msg-${Date.now()}`,
              correlation_id: env.header?.correlation_id || "corr-default",
              timestamp_utc: env.header?.timestamp_utc || new Date().toISOString(),
              sender: env.header?.sender || "unknown",
              recipient: env.header?.recipient || "unknown",
              message_type: env.header?.message_type || "UNKNOWN",
              priority: env.header?.priority || "normal",
              payload: env.payload || {},
              context: env.context || {},
            };
            addEnvelope(logItem);
          } else if (data.event_type === "connected") {
            setLastEventTime(new Date().toISOString());
          }
        } catch {
          // ignore non-json
        }
      };

      socket.onclose = () => {
        setStatus("offline");
        wsRef.current = null;
        // Exponential backoff reconnect: 1s, 2s, 4s, up to 10s
        const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 10000);
        reconnectAttemptsRef.current += 1;
        reconnectTimeoutRef.current = window.setTimeout(connect, delay);
      };

      socket.onerror = () => {
        setStatus("offline");
        socket.close();
      };
    } catch {
      setStatus("offline");
      reconnectTimeoutRef.current = window.setTimeout(connect, 3000);
    }
  }, [addEnvelope]);

  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  return {
    status,
    lastEventTime,
    envelopes,
    addEnvelope,
    clearEnvelopes,
    isPaused,
    setIsPaused,
  };
}

