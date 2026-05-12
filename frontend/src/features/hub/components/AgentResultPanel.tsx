/**
 * AgentResultPanel — displays the final agent result with markdown rendering.
 *
 * Memoised with React.memo since result text doesn't change after completion.
 */

import { memo, useId } from "react";
import { CheckCircle, AlertCircle } from "lucide-react";
import { MarkdownContent } from "./MarkdownContent";

interface AgentResultPanelProps {
  result: string | null;
  error: string | null;
}

export const AgentResultPanel = memo(function AgentResultPanel({
  result,
  error,
}: AgentResultPanelProps) {
  const labelId = useId();

  if (!result && !error) return null;

  const isError = Boolean(error);

  return (
    <section
      aria-labelledby={labelId}
      className="rounded-xl border p-5 shadow-sm"
      style={{
        background: "var(--bg-surface)",
        borderColor: isError ? "var(--danger-500)" : "var(--border-default)",
      }}
    >
      <div className="flex items-center gap-2 mb-3">
        {isError ? (
          <AlertCircle
            className="h-4 w-4 shrink-0"
            style={{ color: "var(--danger-500)" }}
            aria-hidden="true"
          />
        ) : (
          <CheckCircle
            className="h-4 w-4 shrink-0"
            style={{ color: "var(--success-500)" }}
            aria-hidden="true"
          />
        )}
        <h3
          id={labelId}
          className="text-sm font-semibold"
          style={{
            color: isError ? "var(--danger-500)" : "var(--text-primary)",
          }}
        >
          {isError ? "Error" : "Result"}
        </h3>
      </div>

      {isError ? (
        <p
          className="text-sm leading-relaxed whitespace-pre-wrap"
          style={{ color: "var(--danger-400)" }}
        >
          {error}
        </p>
      ) : (
        <MarkdownContent content={result ?? ""} />
      )}
    </section>
  );
});
