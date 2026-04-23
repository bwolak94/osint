/**
 * useHubAgent — TanStack Query mutations for Hub agent operations.
 *
 * Exposes:
 *   runAgent(request)        → POST /hub/agent/run, seeds Zustand store
 *   approveHitl(approved)    → POST /hub/tasks/{taskId}/approve
 *   taskStatus               → GET /hub/tasks/{taskId} (polls while active)
 */

import { useMutation, useQuery } from "@tanstack/react-query";
import { runHubAgent, getTaskStatus, approveHitl } from "../api";
import { useHubStore } from "../store";
import type { AgentRunRequest, HubModule } from "../types";

const ACTIVE_STATUSES = new Set(["queued", "running", "awaiting_hitl"]);
// Poll every 2 s while the task is active (WebSocket is the primary channel;
// this is a fallback for environments where WS is unavailable).
const POLL_INTERVAL_MS = 2_000;

/** Submit a new agent query. */
export function useRunAgent() {
  const startTask = useHubStore((s) => s.startTask);
  const reset = useHubStore((s) => s.reset);

  return useMutation({
    mutationFn: (req: AgentRunRequest) => runHubAgent(req),
    onMutate: () => {
      reset();
    },
    onSuccess: (data) => {
      startTask(data.task_id, data.stream_url);
    },
  });
}

/** Poll task status — disabled once the task reaches a terminal state. */
export function useTaskStatus() {
  const taskId = useHubStore((s) => s.taskId);
  const status = useHubStore((s) => s.status);
  const setStatus = useHubStore((s) => s.setStatus);
  const setResult = useHubStore((s) => s.setResult);
  const appendThought = useHubStore((s) => s.appendThought);

  const isActive = taskId !== null && ACTIVE_STATUSES.has(status);

  return useQuery({
    queryKey: ["hub", "task", taskId],
    queryFn: async () => {
      const res = await getTaskStatus(taskId!);

      // Sync thoughts that arrived while WS was disconnected
      if (res.thoughts.length > 0) {
        const currentStore = useHubStore.getState();
        const newThoughts = res.thoughts.slice(currentStore.thoughts.length);
        newThoughts.forEach((t) => appendThought(t));
      }

      if (!ACTIVE_STATUSES.has(res.status)) {
        setStatus(res.status);
        setResult(res.result, res.error, res.result_metadata);
      }
      return res;
    },
    enabled: isActive,
    refetchInterval: isActive ? POLL_INTERVAL_MS : false,
    staleTime: 0,
  });
}

/** Resolve a HITL gate (approve or reject). */
export function useApproveHitl() {
  const taskId = useHubStore((s) => s.taskId);
  const setStatus = useHubStore((s) => s.setStatus);

  return useMutation({
    mutationFn: (approved: boolean) =>
      approveHitl(taskId!, { approved }),
    onSuccess: (data) => {
      setStatus(data.status);
    },
  });
}

/** Convenience builder for AgentRunRequest. */
export function buildRunRequest(
  query: string,
  module: HubModule,
  userPreferences?: Record<string, unknown>,
): AgentRunRequest {
  return { query, module, user_preferences: userPreferences };
}
