/**
 * Hub Zustand store — single source of truth for the active agent task.
 *
 * Not persisted to localStorage: task state is server-authoritative (Redis).
 * Re-hydrate via GET /hub/tasks/{task_id} on page reload if needed.
 */

import { create } from "zustand";
import type { AgentStatus, HubAgentState } from "./types";

const initialState = {
  taskId: null,
  status: "idle" as AgentStatus | "idle",
  thoughts: [] as string[],
  result: null,
  resultMetadata: {} as Record<string, unknown>,
  error: null,
  streamUrl: null,
};

export const useHubStore = create<HubAgentState>()((set) => ({
  ...initialState,

  startTask: (taskId: string, streamUrl: string) =>
    set({
      taskId,
      streamUrl,
      status: "queued",
      thoughts: [],
      result: null,
      resultMetadata: {},
      error: null,
    }),

  appendThought: (thought: string) =>
    set((s) => ({ thoughts: [...s.thoughts, thought] })),

  setStatus: (status: AgentStatus | "idle") => set({ status }),

  setResult: (result: string | null, error: string | null, resultMetadata?: Record<string, unknown>) =>
    set({
      result,
      resultMetadata: resultMetadata ?? {},
      error,
      status: error ? "failed" : "completed",
    }),

  reset: () => set(initialState),
}));
