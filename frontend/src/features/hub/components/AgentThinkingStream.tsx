/**
 * AgentThinkingStream — renders the agent's Chain-of-Thought in real time.
 *
 * Memoised with React.memo: only re-renders when `thoughts` or `status` changes.
 * Each thought line animates in via a simple CSS fade-in so the stream feels live.
 */

import { memo, useId } from "react";
import type { AgentStatus } from "../types";

interface AgentThinkingStreamProps {
  thoughts: string[];
  status: AgentStatus | "idle";
}

const STATUS_LABELS: Record<AgentStatus | "idle", string> = {
  idle: "Idle",
  queued: "Queued…",
  running: "Thinking…",
  completed: "Done",
  failed: "Failed",
  awaiting_hitl: "Awaiting your approval",
};

const STATUS_COLORS: Record<AgentStatus | "idle", string> = {
  idle: "var(--text-tertiary)",
  queued: "var(--brand-400)",
  running: "var(--brand-500)",
  completed: "var(--success-500)",
  failed: "var(--danger-500)",
  awaiting_hitl: "var(--warning-500)",
};

export const AgentThinkingStream = memo(function AgentThinkingStream({
  thoughts,
  status,
}: AgentThinkingStreamProps) {
  const labelId = useId();

  return (
    <section aria-labelledby={labelId} className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        {/* Pulse indicator while running */}
        {status === "running" && (
          <span
            className="inline-block h-2 w-2 animate-pulse rounded-full"
            style={{ background: "var(--brand-500)" }}
            aria-hidden="true"
          />
        )}
        <h3
          id={labelId}
          className="text-xs font-semibold uppercase tracking-wide"
          style={{ color: STATUS_COLORS[status] }}
        >
          {STATUS_LABELS[status]}
        </h3>
      </div>

      {thoughts.length === 0 && status !== "idle" && (
        <p className="text-sm italic" style={{ color: "var(--text-tertiary)" }}>
          Starting agent pipeline…
        </p>
      )}

      <ol className="space-y-1.5" aria-label="Agent thoughts">
        {thoughts.map((thought, idx) => (
          <li
            key={idx}
            className="text-sm leading-relaxed"
            style={{
              color: "var(--text-secondary)",
              // Fade in each new line
              animation: "hub-thought-in 0.25s ease-out both",
            }}
          >
            <span className="mr-1.5 text-xs" style={{ color: "var(--text-tertiary)" }}>
              {idx + 1}.
            </span>
            {thought}
          </li>
        ))}
      </ol>

      <style>{`
        @keyframes hub-thought-in {
          from { opacity: 0; transform: translateY(4px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </section>
  );
});
