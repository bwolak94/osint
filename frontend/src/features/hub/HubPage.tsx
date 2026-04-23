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
 *   │  Query input                                │
 *   └─────────────────────────────────────────────┘
 */

import { useState } from "react";
import { Brain } from "lucide-react";

import { useHubStore } from "./store";
import { useAgentStream } from "./hooks/useAgentStream";
import { useRunAgent, useTaskStatus, useApproveHitl, buildRunRequest } from "./hooks/useHubAgent";

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

export function HubPage() {
  const [module, setModule] = useState<HubModule>("chat");
  const [query, setQuery] = useState("");

  // Store selectors
  const taskId = useHubStore((s) => s.taskId);
  const status = useHubStore((s) => s.status);
  const thoughts = useHubStore((s) => s.thoughts);
  const result = useHubStore((s) => s.result);
  const error = useHubStore((s) => s.error);

  // Derived
  const isActive = ACTIVE_STATUSES.has(status);
  const isAwaitingHitl = status === "awaiting_hitl";

  // Hooks
  useAgentStream(taskId);
  useTaskStatus(); // fallback polling

  const runAgent = useRunAgent();
  const approveHitl = useApproveHitl();

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

  return (
    <div className="flex h-full flex-col gap-6">
      {/* Page header */}
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

      {/* Query input — hidden on news module (RAG chat is inline in NewsFeedPanel) */}
      {module !== "news" && (
        <HubQueryInput
          value={query}
          onChange={setQuery}
          onSubmit={handleSubmit}
          disabled={isActive}
          placeholder={`Ask the ${module} agent anything…`}
        />
      )}
    </div>
  );
}
