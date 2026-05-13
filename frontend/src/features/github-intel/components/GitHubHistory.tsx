import { Trash2 } from "lucide-react";
import { useState } from "react";
import type { GitHubIntelScan } from "../types";
import { useGitHubIntelHistory, useDeleteGitHubIntelScan } from "../hooks";

interface Props {
  onSelect: (scan: GitHubIntelScan) => void;
}

export function GitHubHistory({ onSelect }: Props) {
  const [page, setPage] = useState(1);
  const { data, isLoading } = useGitHubIntelHistory(page);
  const deleteMutation = useDeleteGitHubIntelScan();

  if (isLoading) {
    return <div className="text-sm" style={{ color: "var(--text-tertiary)" }}>Loading history...</div>;
  }

  if (!data?.items.length) {
    return <div className="text-sm" style={{ color: "var(--text-tertiary)" }}>No previous scans.</div>;
  }

  return (
    <div className="space-y-2">
      {data.items.map((scan) => (
        <div
          key={scan.id}
          className="flex items-center justify-between rounded-md border px-3 py-2 text-sm cursor-pointer hover:border-brand-500/50 transition-colors"
          style={{ borderColor: "var(--border-subtle)", background: "var(--bg-surface)" }}
          onClick={() => onSelect(scan)}
        >
          <div className="min-w-0">
            <span className="font-medium truncate block" style={{ color: "var(--text-primary)" }}>
              {scan.query}
            </span>
            <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>
              {scan.query_type} · {scan.total_results} result{scan.total_results !== 1 ? "s" : ""} ·{" "}
              {new Date(scan.created_at).toLocaleString()}
            </span>
          </div>
          <button
            onClick={(e) => { e.stopPropagation(); deleteMutation.mutate(scan.id); }}
            className="ml-2 shrink-0 rounded p-1 text-text-tertiary hover:text-danger-500 transition-colors"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      ))}
      {data.total_pages > 1 && (
        <div className="flex justify-center gap-2 pt-2">
          <button disabled={page === 1} onClick={() => setPage((p) => p - 1)} className="px-3 py-1 text-xs rounded border disabled:opacity-40" style={{ borderColor: "var(--border-subtle)" }}>Prev</button>
          <span className="px-3 py-1 text-xs" style={{ color: "var(--text-tertiary)" }}>{page} / {data.total_pages}</span>
          <button disabled={page === data.total_pages} onClick={() => setPage((p) => p + 1)} className="px-3 py-1 text-xs rounded border disabled:opacity-40" style={{ borderColor: "var(--border-subtle)" }}>Next</button>
        </div>
      )}
    </div>
  );
}
