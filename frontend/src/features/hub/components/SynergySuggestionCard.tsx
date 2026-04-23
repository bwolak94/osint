/**
 * SynergySuggestionCard — Phase 3 cross-module proposal card.
 *
 * Shows the full news → task → calendar chain in a single reviewable card.
 * One-click approve or dismiss. Dismissed suggestions are logged to episodic
 * memory via the /hub/synergy/{event_id}/dismiss endpoint.
 *
 * Never auto-applies changes — every action requires explicit user intent.
 */

import { useId, useState, useCallback } from "react";
import { useTransition } from "react";
import {
  Sparkles,
  CheckCircle,
  XCircle,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  ClipboardEdit,
  Calendar,
} from "lucide-react";
import type {
  SynergyChain,
  TaskModificationProposal,
  CalendarAdjustmentProposal,
} from "../types";

interface SynergySuggestionCardProps {
  chain: SynergyChain;
  taskId: string;
  onApprove: (chainId: string) => Promise<void>;
  onDismiss: (chainId: string, eventId: string) => Promise<void>;
}

function RelevanceBadge({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color =
    score >= 0.85
      ? "var(--success-500)"
      : score >= 0.7
        ? "var(--warning-500)"
        : "var(--text-tertiary)";
  return (
    <span
      className="rounded-full px-2 py-0.5 text-xs font-medium"
      style={{ background: "var(--bg-overlay)", color }}
    >
      {pct}% relevant
    </span>
  );
}

function TaskProposalRow({ proposal }: { proposal: TaskModificationProposal }) {
  return (
    <div
      className="rounded-lg border px-3 py-2.5"
      style={{
        background: "var(--bg-overlay)",
        borderColor: "var(--border-default)",
      }}
    >
      <div className="flex items-start gap-2">
        <ClipboardEdit
          className="mt-0.5 h-4 w-4 shrink-0"
          style={{ color: "var(--text-tertiary)" }}
          aria-hidden="true"
        />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
            {proposal.task_title}
          </p>
          <p className="mt-0.5 text-xs" style={{ color: "var(--text-tertiary)" }}>
            Change <code className="font-mono">{proposal.field}</code>
            {proposal.current_value !== null && proposal.current_value !== undefined && (
              <> from <span className="line-through opacity-60">{String(proposal.current_value)}</span></>
            )}
            {" → "}
            <span style={{ color: "var(--text-primary)" }}>
              {typeof proposal.proposed_value === "string" && proposal.proposed_value.length > 80
                ? `${proposal.proposed_value.slice(0, 80)}…`
                : String(proposal.proposed_value)}
            </span>
          </p>
          <p className="mt-1 text-xs italic" style={{ color: "var(--text-tertiary)" }}>
            {proposal.reason}
          </p>
        </div>
      </div>
    </div>
  );
}

function CalendarProposalRow({ proposal }: { proposal: CalendarAdjustmentProposal }) {
  return (
    <div
      className="rounded-lg border px-3 py-2.5"
      style={{
        background: "var(--bg-overlay)",
        borderColor: "var(--border-default)",
      }}
    >
      <div className="flex items-start gap-2">
        <Calendar
          className="mt-0.5 h-4 w-4 shrink-0"
          style={{ color: "var(--text-tertiary)" }}
          aria-hidden="true"
        />
        <div className="min-w-0 flex-1">
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            {proposal.summary}
          </p>
          {proposal.proposed_reschedule && (
            <p className="mt-0.5 text-xs" style={{ color: "var(--text-tertiary)" }}>
              Proposed slot:{" "}
              <span style={{ color: "var(--text-primary)" }}>
                {new Date(proposal.proposed_reschedule).toLocaleString()}
              </span>
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

export function SynergySuggestionCard({
  chain,
  taskId,
  onApprove,
  onDismiss,
}: SynergySuggestionCardProps) {
  const titleId = useId();
  const [isExpanded, setIsExpanded] = useState(false);
  const [isActing, startTransition] = useTransition();

  const handleApprove = useCallback(() => {
    startTransition(async () => {
      await onApprove(chain.chain_id);
    });
  }, [chain.chain_id, onApprove, startTransition]);

  const handleDismiss = useCallback(() => {
    startTransition(async () => {
      await onDismiss(chain.chain_id, chain.event.event_id);
    });
  }, [chain.chain_id, chain.event.event_id, onDismiss, startTransition]);

  const toggleExpand = useCallback(() => setIsExpanded((v) => !v), []);

  const hasProposals =
    chain.task_proposals.length > 0 || chain.calendar_proposals.length > 0;

  return (
    <article
      aria-labelledby={titleId}
      className="rounded-xl border shadow-sm overflow-hidden"
      style={{
        background: "var(--bg-surface)",
        borderColor: "var(--warning-500)",
      }}
    >
      {/* Header */}
      <div className="px-4 py-3">
        <div className="flex items-start gap-3">
          <Sparkles
            className="mt-0.5 h-5 w-5 shrink-0"
            style={{ color: "var(--warning-500)" }}
            aria-hidden="true"
          />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h4
                id={titleId}
                className="text-sm font-semibold"
                style={{ color: "var(--text-primary)" }}
              >
                Synergy Suggestion
              </h4>
              <RelevanceBadge score={chain.event.action_relevance_score} />
            </div>
            <p className="mt-0.5 text-sm leading-snug" style={{ color: "var(--text-secondary)" }}>
              {chain.news_headline}
              {chain.news_url && (
                <a
                  href={chain.news_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="ml-1 inline-flex items-center gap-0.5 underline-offset-2 hover:underline"
                  aria-label="Open source article"
                  style={{ color: "var(--text-tertiary)" }}
                >
                  <ExternalLink className="h-3 w-3" aria-hidden="true" />
                </a>
              )}
            </p>
          </div>
        </div>

        {/* Proposal count summary */}
        {hasProposals && (
          <button
            type="button"
            onClick={toggleExpand}
            aria-expanded={isExpanded}
            className="mt-2 flex items-center gap-1 text-xs transition-opacity hover:opacity-80"
            style={{ color: "var(--text-tertiary)" }}
          >
            {isExpanded ? (
              <ChevronUp className="h-3.5 w-3.5" aria-hidden="true" />
            ) : (
              <ChevronDown className="h-3.5 w-3.5" aria-hidden="true" />
            )}
            {chain.task_proposals.length} task change
            {chain.task_proposals.length !== 1 ? "s" : ""}
            {chain.calendar_proposals.length > 0 &&
              `, ${chain.calendar_proposals.length} calendar adjustment`}
          </button>
        )}
      </div>

      {/* Expandable proposal detail */}
      {isExpanded && hasProposals && (
        <div
          className="border-t px-4 py-3 space-y-2"
          style={{ borderColor: "var(--border-default)" }}
        >
          {chain.task_proposals.map((p) => (
            <TaskProposalRow key={p.proposal_id} proposal={p} />
          ))}
          {chain.calendar_proposals.map((p) => (
            <CalendarProposalRow key={p.proposal_id} proposal={p} />
          ))}
        </div>
      )}

      {/* Actions */}
      <div
        className="border-t px-4 py-3 flex gap-3"
        style={{ borderColor: "var(--border-default)" }}
      >
        <button
          type="button"
          onClick={handleApprove}
          disabled={isActing}
          className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-all
            ${isActing ? "cursor-not-allowed opacity-50" : "hover:scale-105 active:scale-95"}`}
          style={{ background: "var(--success-500)", color: "white" }}
          aria-busy={isActing}
        >
          <CheckCircle className="h-4 w-4" aria-hidden="true" />
          Apply changes
        </button>
        <button
          type="button"
          onClick={handleDismiss}
          disabled={isActing}
          className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-all
            ${isActing ? "cursor-not-allowed opacity-50" : "hover:scale-105 active:scale-95"}`}
          style={{
            background: "var(--bg-overlay)",
            color: "var(--text-secondary)",
            border: "1px solid var(--border-default)",
          }}
        >
          <XCircle className="h-4 w-4" aria-hidden="true" />
          Dismiss
        </button>
      </div>
    </article>
  );
}
