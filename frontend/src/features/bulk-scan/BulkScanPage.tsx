import { useState } from "react";
import { Layers, Plus, Trash2, Play, AlertCircle, CheckCircle2, Clock } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import axios from "axios";

interface BulkTarget {
  id: string;
  value: string;
  label: string;
}

interface BulkScanResponse {
  bulk_id: string;
  total_targets: number;
  task_ids: string[];
  status: string;
  message: string;
}

function useBulkScan() {
  return useMutation({
    mutationFn: (targets: BulkTarget[]) =>
      axios
        .post<BulkScanResponse>("/api/v1/scans/bulk", {
          targets: targets.map((t) => ({ value: t.value, label: t.label || undefined })),
          priority: "low",
        })
        .then((r) => r.data),
  });
}

export function BulkScanPage() {
  const [targets, setTargets] = useState<BulkTarget[]>([
    { id: crypto.randomUUID(), value: "", label: "" },
  ]);

  const mutation = useBulkScan();

  const addTarget = () =>
    setTargets((prev) => [...prev, { id: crypto.randomUUID(), value: "", label: "" }]);

  const removeTarget = (id: string) =>
    setTargets((prev) => prev.filter((t) => t.id !== id));

  const updateTarget = (id: string, field: keyof BulkTarget, value: string) =>
    setTargets((prev) => prev.map((t) => (t.id === id ? { ...t, [field]: value } : t)));

  const validTargets = targets.filter((t) => t.value.trim().length > 0);

  const handleSubmit = () => {
    if (validTargets.length === 0) return;
    mutation.mutate(validTargets);
  };

  return (
    <div className="min-h-screen p-6" style={{ background: "var(--bg-base)" }}>
      <div className="mx-auto max-w-3xl">
        {/* Header */}
        <div className="mb-8 flex items-center gap-3">
          <div
            className="flex h-10 w-10 items-center justify-center rounded-lg"
            style={{ background: "var(--brand-subtle)", border: "1px solid var(--brand-border)" }}
          >
            <Layers className="h-5 w-5" style={{ color: "var(--brand-400)" }} />
          </div>
          <div>
            <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
              Bulk Scanner
            </h1>
            <p className="text-sm" style={{ color: "var(--text-tertiary)" }}>
              Queue multiple targets for parallel OSINT scanning
            </p>
          </div>
        </div>

        {/* Target list */}
        <div
          className="mb-4 rounded-xl border"
          style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}
        >
          <div className="border-b px-5 py-4" style={{ borderColor: "var(--border-subtle)" }}>
            <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
              Targets ({validTargets.length} valid)
            </h2>
          </div>
          <div className="divide-y" style={{ borderColor: "var(--border-subtle)" }}>
            {targets.map((target, i) => (
              <div key={target.id} className="flex items-center gap-3 px-5 py-3">
                <span
                  className="w-6 shrink-0 text-center text-xs font-mono"
                  style={{ color: "var(--text-tertiary)" }}
                >
                  {i + 1}
                </span>
                <input
                  type="text"
                  placeholder="domain.com, email@, IP, username..."
                  value={target.value}
                  onChange={(e) => updateTarget(target.id, "value", e.target.value)}
                  className="flex-1 rounded-lg border px-3 py-2 text-sm font-mono outline-none transition-colors"
                  style={{
                    background: "var(--bg-base)",
                    borderColor: "var(--border-default)",
                    color: "var(--text-primary)",
                  }}
                />
                <input
                  type="text"
                  placeholder="Label (optional)"
                  value={target.label}
                  onChange={(e) => updateTarget(target.id, "label", e.target.value)}
                  className="w-36 rounded-lg border px-3 py-2 text-sm outline-none"
                  style={{
                    background: "var(--bg-base)",
                    borderColor: "var(--border-default)",
                    color: "var(--text-secondary)",
                  }}
                />
                <button
                  onClick={() => removeTarget(target.id)}
                  disabled={targets.length === 1}
                  className="shrink-0 rounded-lg p-1.5 transition-colors hover:opacity-80 disabled:opacity-30"
                  style={{ color: "var(--danger-400, #f87171)" }}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
          <div className="border-t px-5 py-3" style={{ borderColor: "var(--border-subtle)" }}>
            <button
              onClick={addTarget}
              className="flex items-center gap-2 text-sm transition-opacity hover:opacity-70"
              style={{ color: "var(--brand-400)" }}
            >
              <Plus className="h-4 w-4" />
              Add target
            </button>
          </div>
        </div>

        {/* Info */}
        <div
          className="mb-6 flex items-start gap-3 rounded-lg border px-4 py-3"
          style={{ borderColor: "var(--warning-border, #713f12)", background: "var(--warning-subtle, #422006)" }}
        >
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" style={{ color: "var(--warning-400, #fbbf24)" }} />
          <p className="text-xs" style={{ color: "var(--warning-300, #fde68a)" }}>
            Up to 50 targets per bulk scan. Scans are queued with low priority and may take several minutes.
            Results are stored per investigation and accessible via the Investigations page.
          </p>
        </div>

        {/* Submit */}
        <button
          onClick={handleSubmit}
          disabled={validTargets.length === 0 || mutation.isPending}
          className="flex w-full items-center justify-center gap-2 rounded-xl py-3 text-sm font-semibold transition-all disabled:opacity-40"
          style={{ background: "var(--brand-500)", color: "#fff" }}
        >
          {mutation.isPending ? (
            <>
              <Clock className="h-4 w-4 animate-spin" />
              Queuing {validTargets.length} target{validTargets.length !== 1 ? "s" : ""}...
            </>
          ) : (
            <>
              <Play className="h-4 w-4" />
              Start Bulk Scan ({validTargets.length} target{validTargets.length !== 1 ? "s" : ""})
            </>
          )}
        </button>

        {/* Result */}
        {mutation.isSuccess && (
          <div
            className="mt-6 flex items-start gap-3 rounded-xl border px-5 py-4"
            style={{ borderColor: "var(--success-border, #14532d)", background: "var(--success-subtle, #052e16)" }}
          >
            <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0" style={{ color: "var(--success-400, #4ade80)" }} />
            <div>
              <p className="text-sm font-medium" style={{ color: "var(--success-300, #86efac)" }}>
                Bulk scan queued successfully
              </p>
              <p className="mt-1 text-xs font-mono" style={{ color: "var(--text-tertiary)" }}>
                Bulk ID: {mutation.data.bulk_id}
              </p>
              <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                {mutation.data.total_targets} targets dispatched across {mutation.data.task_ids.length} tasks
              </p>
            </div>
          </div>
        )}

        {mutation.isError && (
          <div
            className="mt-6 rounded-xl border px-5 py-4"
            style={{ borderColor: "var(--danger-border, #7f1d1d)", background: "var(--danger-subtle, #450a0a)" }}
          >
            <p className="text-sm" style={{ color: "var(--danger-300, #fca5a5)" }}>
              Failed to queue bulk scan. Please try again.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
