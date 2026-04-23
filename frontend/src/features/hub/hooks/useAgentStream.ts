/**
 * useAgentStream — WebSocket hook that bridges Redis pub/sub events into Zustand.
 *
 * Connects to /api/v1/hub/tasks/{taskId}/stream and dispatches:
 *   thought        → appendThought (wrapped in startTransition for non-urgent update)
 *   status_update  → setStatus
 *   graph_done     → poll GET /hub/tasks/{taskId} for final result
 *
 * The socket is closed automatically on unmount or when taskId changes.
 */

import { useEffect, useRef, useTransition } from "react";
import { useHubStore } from "../store";
import { getTaskStatus } from "../api";
import type { WsEvent } from "../types";

export function useAgentStream(taskId: string | null): void {
  const appendThought = useHubStore((s) => s.appendThought);
  const setStatus = useHubStore((s) => s.setStatus);
  const setResult = useHubStore((s) => s.setResult);
  const [, startTransition] = useTransition();

  // Keep a stable ref so the cleanup in useEffect doesn't close a new socket
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!taskId) return;

    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const url = `${protocol}://${window.location.host}/api/v1/hub/tasks/${taskId}/stream`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onmessage = (evt: MessageEvent<string>) => {
      let event: WsEvent;
      try {
        event = JSON.parse(evt.data) as WsEvent;
      } catch {
        return; // Malformed frame — ignore
      }

      switch (event.type) {
        case "graph_start":
          setStatus("running");
          break;

        case "thought": {
          const thought = event.thought ?? event.chunk ?? "";
          if (thought) {
            // Non-urgent — won't block user interaction
            startTransition(() => appendThought(thought));
          }
          break;
        }

        case "status_update":
          if (event.status) setStatus(event.status);
          break;

        case "graph_done":
          // Fetch the authoritative final state from the API.
          // graph_done is published AFTER Redis writes so result is always present.
          void getTaskStatus(taskId).then((res) => {
            setResult(res.result, res.error, res.result_metadata);
          });
          break;

        case "graph_error":
          // Emitted by cancel_task endpoint — treat as a terminal cancellation signal
          setStatus("cancelled");
          setResult(null, event.message ?? null);
          break;

        case "error":
          setResult(null, event.message ?? "Unknown streaming error");
          break;

        default:
          break;
      }
    };

    ws.onerror = () => {
      setResult(null, "WebSocket connection failed");
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [taskId, appendThought, setStatus, setResult, startTransition]);
}
