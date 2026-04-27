import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, RefreshCw, ShieldAlert } from "lucide-react";
import { useState } from "react";
import { apiClient } from "@/shared/api/client";

interface QuotaEntry {
  workspace_id: string;
  scanner_name: string;
  monthly_limit: number;
  requests_used: number;
  period_start: string;
  alerts_enabled: boolean;
}

interface QuotaResponse {
  quotas: QuotaEntry[];
  total_scanners: number;
  over_limit: number;
  near_limit: number;
}

interface UpsertQuotaPayload {
  scanner_name: string;
  monthly_limit: number;
  alerts_enabled: boolean;
}

function usagePercent(entry: QuotaEntry): number {
  if (entry.monthly_limit <= 0) return 0;
  return Math.min(100, Math.round((entry.requests_used / entry.monthly_limit) * 100));
}

function barColor(pct: number): string {
  if (pct >= 100) return "var(--danger-500)";
  if (pct >= 80) return "var(--warning-500)";
  return "var(--success-500)";
}

function labelFromPct(pct: number): string {
  if (pct >= 100) return "Over limit";
  if (pct >= 80) return "Near limit";
  return "OK";
}

interface EditModalProps {
  entry: QuotaEntry;
  onClose: () => void;
}

function EditModal({ entry, onClose }: EditModalProps) {
  const queryClient = useQueryClient();
  const [limit, setLimit] = useState(String(entry.monthly_limit));
  const [alerts, setAlerts] = useState(entry.alerts_enabled);
  const [validationError, setValidationError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: async (payload: UpsertQuotaPayload) => {
      const resp = await apiClient.post("/scanner-quota", payload);
      return resp.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["scanner-quota"] });
      onClose();
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const parsedLimit = parseInt(limit, 10);
    if (isNaN(parsedLimit) || parsedLimit < 1) {
      setValidationError("Limit must be a positive number.");
      return;
    }
    setValidationError(null);
    mutation.mutate({
      scanner_name: entry.scanner_name,
      monthly_limit: parsedLimit,
      alerts_enabled: alerts,
    });
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: "rgba(0,0,0,0.6)" }}
      role="dialog"
      aria-modal="true"
      aria-label={`Edit quota for ${entry.scanner_name}`}
    >
      <div
        className="w-full max-w-sm rounded-xl border p-6 shadow-2xl"
        style={{ background: "var(--bg-elevated)", borderColor: "var(--border-default)" }}
      >
        <h2 className="mb-4 text-base font-semibold" style={{ color: "var(--text-primary)" }}>
          Edit quota — <code className="text-sm" style={{ color: "var(--brand-400)" }}>{entry.scanner_name}</code>
        </h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1 block text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
              Monthly limit (requests)
            </label>
            <input
              type="number"
              min={1}
              value={limit}
              onChange={(e) => setLimit(e.target.value)}
              autoFocus
              className="w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2"
              style={{
                background: "var(--bg-surface)",
                borderColor: validationError ? "var(--danger-500)" : "var(--border-default)",
                color: "var(--text-primary)",
              }}
            />
            {validationError && (
              <p className="mt-1 text-xs" style={{ color: "var(--danger-400)" }}>{validationError}</p>
            )}
          </div>
          <div className="flex items-center gap-2">
            <input
              id="alerts-toggle"
              type="checkbox"
              checked={alerts}
              onChange={(e) => setAlerts(e.target.checked)}
              className="h-4 w-4 cursor-pointer rounded"
            />
            <label htmlFor="alerts-toggle" className="cursor-pointer text-sm" style={{ color: "var(--text-secondary)" }}>
              Alert when ≥80% consumed
            </label>
          </div>
          <div className="flex gap-2 pt-2">
            <button
              type="submit"
              disabled={mutation.isPending}
              className="flex-1 rounded-md px-4 py-2 text-sm font-semibold transition-colors disabled:opacity-50"
              style={{ background: "var(--brand-500)", color: "#fff" }}
            >
              {mutation.isPending ? "Saving…" : "Save"}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="rounded-md px-4 py-2 text-sm transition-colors hover:bg-bg-overlay"
              style={{ color: "var(--text-secondary)", border: "1px solid var(--border-subtle)" }}
            >
              Cancel
            </button>
          </div>
          {mutation.isError && (
            <p className="text-xs" style={{ color: "var(--danger-400)" }}>
              Failed to save quota. Please try again.
            </p>
          )}
        </form>
      </div>
    </div>
  );
}

export function ScannerQuotaPage() {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<QuotaEntry | null>(null);

  const { data, isLoading, error, isFetching } = useQuery<QuotaResponse>({
    queryKey: ["scanner-quota"],
    queryFn: async () => {
      const resp = await apiClient.get("/scanner-quota");
      return resp.data as QuotaResponse;
    },
    staleTime: 60 * 1000,
  });

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      {editing && <EditModal entry={editing} onClose={() => setEditing(null)} />}

      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
            Scanner Quota
          </h1>
          <p className="mt-0.5 text-sm" style={{ color: "var(--text-tertiary)" }}>
            Monthly API request limits per scanner
          </p>
        </div>
        <button
          onClick={() => queryClient.invalidateQueries({ queryKey: ["scanner-quota"] })}
          disabled={isFetching}
          className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors hover:bg-bg-overlay disabled:opacity-50"
          style={{ color: "var(--text-secondary)", border: "1px solid var(--border-subtle)" }}
          aria-label="Refresh quota data"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {/* Summary cards */}
      {data && (
        <div className="mb-6 grid grid-cols-3 gap-4">
          {[
            { label: "Total scanners", value: data.total_scanners, color: "var(--text-primary)" },
            { label: "Near limit (≥80%)", value: data.near_limit, color: "var(--warning-500)" },
            { label: "Over limit", value: data.over_limit, color: "var(--danger-500)" },
          ].map(({ label, value, color }) => (
            <div
              key={label}
              className="rounded-lg border px-4 py-3"
              style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}
            >
              <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>{label}</p>
              <p className="mt-1 text-2xl font-bold" style={{ color }}>{value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Over-limit alert banner */}
      {data && data.over_limit > 0 && (
        <div
          className="mb-4 flex items-center gap-2 rounded-lg border px-4 py-3 text-sm"
          style={{
            background: "var(--danger-950)",
            borderColor: "var(--danger-500)",
            color: "var(--danger-400)",
          }}
          role="alert"
        >
          <ShieldAlert className="h-4 w-4 shrink-0" />
          {data.over_limit} scanner{data.over_limit > 1 ? "s are" : " is"} over the monthly limit. Requests may be throttled.
        </div>
      )}

      {/* Loading / error */}
      {isLoading && (
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <div
              key={i}
              className="h-16 animate-pulse rounded-lg"
              style={{ background: "var(--bg-surface)" }}
            />
          ))}
        </div>
      )}

      {error && (
        <div
          className="flex items-center gap-2 rounded-lg border px-4 py-3 text-sm"
          style={{ background: "var(--danger-950)", borderColor: "var(--danger-500)", color: "var(--danger-400)" }}
          role="alert"
        >
          <AlertTriangle className="h-4 w-4 shrink-0" />
          Failed to load quota data. Check your connection and try again.
        </div>
      )}

      {/* Quota table */}
      {data && data.quotas.length === 0 && (
        <p className="py-12 text-center text-sm" style={{ color: "var(--text-tertiary)" }}>
          No quota records found. Quotas are created automatically when scanners run.
        </p>
      )}

      {data && data.quotas.length > 0 && (
        <div
          className="overflow-hidden rounded-lg border"
          style={{ borderColor: "var(--border-subtle)" }}
        >
          <table className="w-full text-sm">
            <thead>
              <tr style={{ background: "var(--bg-overlay)", borderBottom: "1px solid var(--border-subtle)" }}>
                {["Scanner", "Used / Limit", "Usage", "Status", "Period start", ""].map((h) => (
                  <th
                    key={h}
                    className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide"
                    style={{ color: "var(--text-tertiary)" }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.quotas.map((entry, i) => {
                const pct = usagePercent(entry);
                const color = barColor(pct);
                return (
                  <tr
                    key={`${entry.workspace_id}-${entry.scanner_name}`}
                    style={{
                      borderTop: i > 0 ? "1px solid var(--border-subtle)" : undefined,
                      background: "var(--bg-surface)",
                    }}
                  >
                    <td className="px-4 py-3">
                      <code className="rounded px-1.5 py-0.5 text-xs" style={{ background: "var(--bg-elevated)", color: "var(--brand-400)" }}>
                        {entry.scanner_name}
                      </code>
                    </td>
                    <td className="px-4 py-3 tabular-nums" style={{ color: "var(--text-secondary)" }}>
                      {entry.requests_used.toLocaleString()} / {entry.monthly_limit.toLocaleString()}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div
                          className="h-1.5 w-28 overflow-hidden rounded-full"
                          style={{ background: "var(--bg-overlay)" }}
                          role="progressbar"
                          aria-valuenow={pct}
                          aria-valuemin={0}
                          aria-valuemax={100}
                          aria-label={`${pct}% of quota used`}
                        >
                          <div
                            className="h-full rounded-full transition-all"
                            style={{ width: `${pct}%`, background: color }}
                          />
                        </div>
                        <span className="text-xs tabular-nums" style={{ color: "var(--text-tertiary)" }}>
                          {pct}%
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className="rounded-full px-2 py-0.5 text-xs font-medium"
                        style={{ background: `${color}22`, color }}
                      >
                        {labelFromPct(pct)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs" style={{ color: "var(--text-tertiary)" }}>
                      {new Date(entry.period_start).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => setEditing(entry)}
                        className="rounded-md px-2.5 py-1 text-xs font-medium transition-colors hover:bg-bg-overlay"
                        style={{ color: "var(--text-secondary)", border: "1px solid var(--border-subtle)" }}
                        aria-label={`Edit quota for ${entry.scanner_name}`}
                      >
                        Edit
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <p className="mt-4 text-xs" style={{ color: "var(--text-tertiary)" }}>
        Quotas reset on the 1st of each month. Alerts fire at ≥80% usage when enabled.
      </p>
    </div>
  );
}
