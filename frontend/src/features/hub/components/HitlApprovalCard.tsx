/**
 * HitlApprovalCard — shown when the agent pauses for Human-in-the-Loop approval.
 *
 * Displays the pending action summary and approve/reject buttons.
 */

import { useId } from "react";
import { ShieldAlert, CheckCircle, XCircle } from "lucide-react";

interface HitlApprovalCardProps {
  query: string;
  onApprove: () => void;
  onReject: () => void;
  isPending?: boolean;
}

export function HitlApprovalCard({
  query,
  onApprove,
  onReject,
  isPending = false,
}: HitlApprovalCardProps) {
  const descId = useId();

  return (
    <div
      role="alertdialog"
      aria-labelledby="hitl-title"
      aria-describedby={descId}
      className="rounded-xl border p-5 shadow-sm"
      style={{
        background: "var(--bg-surface)",
        borderColor: "var(--warning-500)",
      }}
    >
      <div className="flex items-start gap-3">
        <ShieldAlert
          className="mt-0.5 h-5 w-5 shrink-0"
          style={{ color: "var(--warning-500)" }}
          aria-hidden="true"
        />
        <div className="flex-1 space-y-1">
          <h3
            id="hitl-title"
            className="font-semibold"
            style={{ color: "var(--text-primary)" }}
          >
            Human approval required
          </h3>
          <p
            id={descId}
            className="text-sm"
            style={{ color: "var(--text-secondary)" }}
          >
            The agent detected a potentially destructive operation in your
            request:
          </p>
          <blockquote
            className="mt-1 rounded-md px-3 py-2 text-sm italic"
            style={{
              background: "var(--bg-overlay)",
              borderLeft: "3px solid var(--warning-500)",
              color: "var(--text-primary)",
            }}
          >
            {query}
          </blockquote>
          <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
            Approve to let the agent proceed, or reject to cancel.
          </p>
        </div>
      </div>

      <div className="mt-4 flex gap-3">
        <button
          type="button"
          onClick={onApprove}
          disabled={isPending}
          className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-all
            ${isPending ? "cursor-not-allowed opacity-50" : "hover:scale-105 active:scale-95"}`}
          style={{ background: "var(--success-500)", color: "white" }}
        >
          <CheckCircle className="h-4 w-4" aria-hidden="true" />
          Approve
        </button>
        <button
          type="button"
          onClick={onReject}
          disabled={isPending}
          className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-all
            ${isPending ? "cursor-not-allowed opacity-50" : "hover:scale-105 active:scale-95"}`}
          style={{
            background: "var(--bg-overlay)",
            color: "var(--danger-500)",
            border: "1px solid var(--danger-500)",
          }}
        >
          <XCircle className="h-4 w-4" aria-hidden="true" />
          Reject
        </button>
      </div>
    </div>
  );
}
