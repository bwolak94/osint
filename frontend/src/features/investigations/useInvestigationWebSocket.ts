import { useEffect, useRef, useState, useCallback } from "react";
import { useAuthStore } from "@/features/auth/store";

export interface WSMessage {
  type: "progress" | "node_discovered" | "edge_discovered" | "scan_complete" | "investigation_complete" | "error" | "heartbeat" | "pong";
  timestamp?: string;
  [key: string]: unknown;
}

interface ProgressState {
  completed: number;
  total: number;
  percentage: number;
  currentScanner: string | null;
  nodesDiscovered: number;
  edgesDiscovered: number;
  events: WSMessage[];
}

const initialState: ProgressState = {
  completed: 0, total: 0, percentage: 0,
  currentScanner: null, nodesDiscovered: 0, edgesDiscovered: 0, events: [],
};

export function useInvestigationWebSocket(investigationId: string | undefined, enabled: boolean) {
  const [progress, setProgress] = useState<ProgressState>(initialState);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeout = useRef<ReturnType<typeof setTimeout>>();
  const reconnectAttempts = useRef(0);
  const token = useAuthStore((s) => s.accessToken);

  const connect = useCallback(() => {
    if (!investigationId || !enabled || !token) return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${protocol}//${window.location.host}/api/v1/investigations/${investigationId}/live?token=${token}`;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      reconnectAttempts.current = 0;
    };

    ws.onmessage = (event) => {
      try {
        const msg: WSMessage = JSON.parse(event.data);
        setProgress((prev) => {
          const events = [msg, ...prev.events].slice(0, 50);
          switch (msg.type) {
            case "progress":
              return {
                ...prev,
                completed: (msg.completed as number) ?? prev.completed,
                total: (msg.total as number) ?? prev.total,
                percentage: (msg.percentage as number) ?? prev.percentage,
                currentScanner: (msg.current_scanner as string) ?? prev.currentScanner,
                events,
              };
            case "node_discovered":
              return { ...prev, nodesDiscovered: prev.nodesDiscovered + 1, events };
            case "edge_discovered":
              return { ...prev, edgesDiscovered: prev.edgesDiscovered + 1, events };
            case "scan_complete":
              return { ...prev, events };
            case "investigation_complete":
              return { ...prev, percentage: 100, events };
            case "error":
              return { ...prev, events };
            default:
              return prev;
          }
        });
      } catch {
        // Ignore parse errors
      }
    };

    ws.onclose = () => {
      setConnected(false);
      // Exponential backoff reconnect
      if (enabled) {
        const delay = Math.min(1000 * 2 ** reconnectAttempts.current, 30000);
        reconnectAttempts.current++;
        reconnectTimeout.current = setTimeout(connect, delay);
      }
    };

    ws.onerror = () => { ws.close(); };
  }, [investigationId, enabled, token]);

  useEffect(() => {
    connect();
    return () => {
      if (wsRef.current) wsRef.current.close();
      if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current);
    };
  }, [connect]);

  return { progress, connected };
}
