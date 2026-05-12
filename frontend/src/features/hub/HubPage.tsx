/**
 * HubPage — AI Productivity Hub command center.
 *
 * Layout:
 *   ┌─────────────────────────────────────────────┐
 *   │  Module selector (tabs)                     │
 *   ├─────────────────────────────────┬───────────┤
 *   │  Result / HITL approval         │  Thinking │
 *   │  (main panel)                   │  stream   │
 *   ├─────────────────────────────────┴───────────┤
 *   │  Query input + cancel button                │
 *   └─────────────────────────────────────────────┘
 */

import { useState, useCallback } from "react";
import { useShallow } from "zustand/shallow";
import { Brain, X, History, ChevronDown, ChevronUp } from "lucide-react";
import { useQuery, useMutation } from "@tanstack/react-query";

import { useHubStore } from "./store";
import { useAgentStream } from "./hooks/useAgentStream";
import { useRunAgent, useTaskStatus, useApproveHitl, buildRunRequest } from "./hooks/useHubAgent";
import { cancelTask, getConversations } from "./api";

import { ModuleSelector } from "./components/ModuleSelector";
import { HubQueryInput } from "./components/HubQueryInput";
import { AgentThinkingStream } from "./components/AgentThinkingStream";
import { AgentResultPanel } from "./components/AgentResultPanel";
import { HitlApprovalCard } from "./components/HitlApprovalCard";
import { NewsFeedPanel } from "./components/NewsFeedPanel";
import { TaskList } from "./components/TaskList";
import { KnowledgePanel } from "./components/KnowledgePanel";

import type { HubModule } from "./types";

const ACTIVE_STATUSES = new Set(["queued", "running", "awaiting_hitl"]);

// ── Conversation history sidebar ─────────────────────────────────────────────

function ConversationHistory({ onSelect }: { onSelect: (query: string) => void }) {
  const [open, setOpen] = useState(false);

  const { data } = useQuery({
    queryKey: ["hub", "conversations"],
    queryFn: () => getConversations({ limit: 20 }),
    staleTime: 30_000,
    enabled: open,
  });

  const conversations = data?.conversations ?? [];

  return (
    <div className="flex-shrink-0">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 text-xs rounded-lg px-2 py-1 transition-opacity hover:opacity-70"
        style={{ color: "var(--text-secondary)" }}
        aria-expanded={open}
        aria-controls="conv-history"
      >
        <History className="h-3.5 w-3.5" aria-hidden="true" />
        History
        {open ? (
          <ChevronUp className="h-3 w-3" aria-hidden="true" />
        ) : (
          <ChevronDown className="h-3 w-3" aria-hidden="true" />
        )}
      </button>

      {open && (
        <div
          id="conv-history"
          className="absolute right-0 z-20 mt-1 w-80 rounded-xl border shadow-lg overflow-hidden"
          style={{ background: "var(--bg-surface)", borderColor: "var(--border-default)" }}
        >
          <div
            className="px-3 py-2 border-b text-xs font-semibold"
            style={{ borderColor: "var(--border-subtle)", color: "var(--text-secondary)" }}
          >
            Recent conversations
          </div>
          {conversations.length === 0 ? (
            <p
              className="px-3 py-4 text-xs text-center"
              style={{ color: "var(--text-tertiary)" }}
            >
              No history yet.
            </p>
          ) : (
            <ul className="max-h-72 overflow-y-auto divide-y" style={{ borderColor: "var(--border-subtle)" }}>
              {conversations.map((c) => (
                <li key={c.task_id}>
                  <button
                    onClick={() => {
                      onSelect(c.query);
                      setOpen(false);
                    }}
                    className="w-full text-left px-3 py-2.5 hover:opacity-80 transition-opacity"
                  >
                    <p
                      className="text-xs font-medium line-clamp-1"
                      style={{ color: "var(--text-primary)" }}
                    >
                      {c.query}
                    </p>
                    <p className="text-xs mt-0.5" style={{ color: "var(--text-tertiary)" }}>
                      {c.module} · {c.completed_at ? new Date(c.completed_at).toLocaleDateString() : "—"}
                      {c.error && (
                        <span style={{ color: "var(--danger-500)" }}> · failed</span>
                      )}
                    </p>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function HubPage() {
  const [module, setModule] = useState<HubModule>("chat");
  const [query, setQuery] = useState("");

  // Batch store selectors with useShallow to avoid unnecessary re-renders
  const { taskId, status, thoughts, result, error } = useHubStore(
    useShallow((s) => ({
      taskId: s.taskId,
      status: s.status,
      thoughts: s.thoughts,
      result: s.result,
      error: s.error,
    })),
  );

  const setStatus = useHubStore((s) => s.setStatus);

  // Derived
  const isActive = ACTIVE_STATUSES.has(status);
  const isAwaitingHitl = status === "awaiting_hitl";

  // Hooks
  useAgentStream(taskId);
  useTaskStatus(); // fallback polling

  const runAgent = useRunAgent();
  const approveHitl = useApproveHitl();

  const cancelMutation = useMutation({
    mutationFn: () => cancelTask(taskId!),
    onSuccess: () => {
      setStatus("cancelled");
    },
  });

  function handleSubmit() {
    if (!query.trim() || isActive) return;
    runAgent.mutate(buildRunRequest(query.trim(), module));
  }

  function handleApprove() {
    approveHitl.mutate(true);
  }

  function handleReject() {
    approveHitl.mutate(false);
  }

  const handleHistorySelect = useCallback((q: string) => {
    setQuery(q);
  }, []);

  return (
    <div className="flex h-full flex-col gap-6">
      {/* Page header */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Brain
            className="h-6 w-6 shrink-0"
            style={{ color: "var(--brand-500)" }}
            aria-hidden="true"
          />
          <div>
            <h1
              className="text-xl font-bold"
              style={{ color: "var(--text-primary)" }}
            >
              AI Productivity Hub
            </h1>
            <p className="text-sm" style={{ color: "var(--text-tertiary)" }}>
              Search, plan, and act — powered by AI agents
            </p>
          </div>
        </div>

        {/* Conversation history button */}
        <div className="relative">
          <ConversationHistory onSelect={handleHistorySelect} />
        </div>
      </div>

      {/* Module selector */}
      <ModuleSelector
        value={module}
        onChange={setModule}
        disabled={isActive}
      />

      {/* Main content area */}
      {module === "news" ? (
        /* News module — standalone live feed + RAG chat, no agent run needed */
        <NewsFeedPanel />
      ) : (
        /* All other modules — agent result + thinking stream side-by-side */
        <div className="flex flex-1 gap-4 overflow-hidden">
          {/* Left: result or HITL card */}
          <div className="flex flex-1 flex-col gap-4 overflow-y-auto">
            {isAwaitingHitl && (
              <HitlApprovalCard
                query={query}
                onApprove={handleApprove}
                onReject={handleReject}
                isPending={approveHitl.isPending}
              />
            )}

            {/* Module-specific panels */}
            {module === "tasks" && <TaskList />}
            {module === "knowledge" && <KnowledgePanel />}

            {/* Generic result for chat / calendar */}
            {module !== "tasks" && module !== "knowledge" && (
              <AgentResultPanel result={result} error={error} />
            )}

            {/* Empty state — only for non-persistent modules */}
            {status === "idle" && module !== "tasks" && module !== "knowledge" && (
              <div
                className="flex flex-1 flex-col items-center justify-center gap-3 rounded-xl border border-dashed py-16"
                style={{ borderColor: "var(--border-subtle)" }}
              >
                <Brain
                  className="h-10 w-10"
                  style={{ color: "var(--text-tertiary)" }}
                  aria-hidden="true"
                />
                <p
                  className="text-sm text-center max-w-xs"
                  style={{ color: "var(--text-tertiary)" }}
                >
                  Type a question below and the agent will search, plan, or
                  retrieve knowledge for you.
                </p>
              </div>
            )}
          </div>

          {/* Right: Chain-of-Thought stream */}
          {(thoughts.length > 0 || isActive) && (
            <aside
              className="w-72 shrink-0 overflow-y-auto rounded-xl border p-4"
              style={{
                background: "var(--bg-surface)",
                borderColor: "var(--border-subtle)",
              }}
              aria-label="Agent thinking stream"
            >
              <AgentThinkingStream thoughts={thoughts} status={status} />
            </aside>
          )}
        </div>
      )}

      {/* Query input + cancel — hidden on news module */}
      {module !== "news" && (
        <div className="flex items-end gap-2">
          <div className="flex-1">
            <HubQueryInput
              value={query}
              onChange={setQuery}
              onSubmit={handleSubmit}
              disabled={isActive}
              placeholder={`Ask the ${module} agent anything…`}
            />
          </div>

          {/* Cancel button — only shown while a task is active */}
          {isActive && taskId && (
            <button
              onClick={() => cancelMutation.mutate()}
              disabled={cancelMutation.isPending}
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg transition-all hover:scale-105 active:scale-95 disabled:opacity-40"
              style={{ background: "var(--danger-500)", color: "white" }}
              aria-label="Cancel running task"
              title="Cancel task"
            >
              {cancelMutation.isPending ? (
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
              ) : (
                <X className="h-4 w-4" aria-hidden="true" />
              )}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
