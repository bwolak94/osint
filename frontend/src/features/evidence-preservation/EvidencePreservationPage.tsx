import { useState } from "react";
import { Archive, Camera, CheckCircle2, AlertTriangle, Clock, Link2, Hash } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import axios from "axios";

interface PreserveResponse {
  evidence_id: string;
  url: string;
  label: string | null;
  mode: string;
  content_hash: string | null;
  storage_path: string | null;
  wayback_url: string | null;
  captured_at: string;
  investigation_id: string | null;
  status: "ok" | "partial" | "failed";
  error: string | null;
}

type Mode = "archive" | "screenshot" | "both";

export function EvidencePreservationPage() {
  const [url, setUrl] = useState("");
  const [label, setLabel] = useState("");
  const [investigationId, setInvestigationId] = useState("");
  const [mode, setMode] = useState<Mode>("both");

  const mutation = useMutation({
    mutationFn: () =>
      axios
        .post<PreserveResponse>("/api/v1/preservation", {
          url,
          label: label || undefined,
          investigation_id: investigationId || undefined,
          mode,
          full_page: true,
        })
        .then((r) => r.data),
  });

  const modes: { value: Mode; label: string; icon: React.ElementType }[] = [
    { value: "archive", label: "HTML Archive", icon: Archive },
    { value: "screenshot", label: "Screenshot", icon: Camera },
    { value: "both", label: "Both", icon: Link2 },
  ];

  const statusColor = (s: string) => {
    if (s === "ok") return { bg: "#052e16", border: "#14532d", text: "#86efac" };
    if (s === "partial") return { bg: "#422006", border: "#713f12", text: "#fde68a" };
    return { bg: "#450a0a", border: "#7f1d1d", text: "#fca5a5" };
  };

  return (
    <div className="min-h-screen p-6" style={{ background: "var(--bg-base)" }}>
      <div className="mx-auto max-w-2xl">
        {/* Header */}
        <div className="mb-8 flex items-center gap-3">
          <div
            className="flex h-10 w-10 items-center justify-center rounded-lg"
            style={{ background: "var(--brand-subtle)", border: "1px solid var(--brand-border)" }}
          >
            <Archive className="h-5 w-5" style={{ color: "var(--brand-400)" }} />
          </div>
          <div>
            <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
              Evidence Preservation
            </h1>
            <p className="text-sm" style={{ color: "var(--text-tertiary)" }}>
              Capture screenshots and archive web pages with tamper-evident hashing
            </p>
          </div>
        </div>

        {/* Form */}
        <div
          className="mb-6 rounded-xl border p-5"
          style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}
        >
          <div className="mb-4">
            <label className="mb-1.5 block text-sm font-medium" style={{ color: "var(--text-secondary)" }}>
              URL to preserve *
            </label>
            <input
              type="url"
              placeholder="https://example.com/page"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              className="w-full rounded-lg border px-3 py-2.5 text-sm outline-none font-mono"
              style={{
                background: "var(--bg-base)",
                borderColor: "var(--border-default)",
                color: "var(--text-primary)",
              }}
            />
          </div>

          <div className="mb-4 grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1.5 block text-sm font-medium" style={{ color: "var(--text-secondary)" }}>
                Label
              </label>
              <input
                type="text"
                placeholder="e.g. Main evidence page"
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                className="w-full rounded-lg border px-3 py-2 text-sm outline-none"
                style={{
                  background: "var(--bg-base)",
                  borderColor: "var(--border-default)",
                  color: "var(--text-primary)",
                }}
              />
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium" style={{ color: "var(--text-secondary)" }}>
                Investigation ID
              </label>
              <input
                type="text"
                placeholder="Optional UUID"
                value={investigationId}
                onChange={(e) => setInvestigationId(e.target.value)}
                className="w-full rounded-lg border px-3 py-2 text-sm outline-none font-mono"
                style={{
                  background: "var(--bg-base)",
                  borderColor: "var(--border-default)",
                  color: "var(--text-primary)",
                }}
              />
            </div>
          </div>

          {/* Mode selector */}
          <div className="mb-5">
            <label className="mb-2 block text-sm font-medium" style={{ color: "var(--text-secondary)" }}>
              Preservation mode
            </label>
            <div className="flex gap-2">
              {modes.map((m) => {
                const Icon = m.icon;
                const active = mode === m.value;
                return (
                  <button
                    key={m.value}
                    onClick={() => setMode(m.value)}
                    className="flex items-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium transition-all"
                    style={{
                      background: active ? "var(--brand-subtle)" : "var(--bg-base)",
                      borderColor: active ? "var(--brand-border)" : "var(--border-default)",
                      color: active ? "var(--brand-400)" : "var(--text-secondary)",
                    }}
                  >
                    <Icon className="h-3.5 w-3.5" />
                    {m.label}
                  </button>
                );
              })}
            </div>
          </div>

          <button
            onClick={() => url && mutation.mutate()}
            disabled={!url || mutation.isPending}
            className="flex w-full items-center justify-center gap-2 rounded-xl py-3 text-sm font-semibold transition-all disabled:opacity-40"
            style={{ background: "var(--brand-500)", color: "#fff" }}
          >
            {mutation.isPending ? (
              <>
                <Clock className="h-4 w-4 animate-spin" />
                Preserving evidence...
              </>
            ) : (
              <>
                <Archive className="h-4 w-4" />
                Preserve Evidence
              </>
            )}
          </button>
        </div>

        {/* Result */}
        {mutation.data && (() => {
          const d = mutation.data;
          const colors = statusColor(d.status);
          return (
            <div
              className="rounded-xl border p-5"
              style={{ background: colors.bg, borderColor: colors.border }}
            >
              <div className="mb-3 flex items-center gap-2">
                {d.status === "ok" ? (
                  <CheckCircle2 className="h-5 w-5" style={{ color: colors.text }} />
                ) : (
                  <AlertTriangle className="h-5 w-5" style={{ color: colors.text }} />
                )}
                <span className="text-sm font-semibold capitalize" style={{ color: colors.text }}>
                  {d.status === "ok" ? "Preserved successfully" : d.status === "partial" ? "Partially preserved" : "Preservation failed"}
                </span>
              </div>

              <div className="space-y-2">
                <div className="flex items-start gap-2">
                  <Hash className="mt-0.5 h-4 w-4 shrink-0" style={{ color: colors.text }} />
                  <div>
                    <p className="text-xs font-medium" style={{ color: colors.text }}>Evidence ID</p>
                    <p className="font-mono text-xs" style={{ color: "var(--text-tertiary)" }}>{d.evidence_id}</p>
                  </div>
                </div>

                {d.content_hash && (
                  <div className="flex items-start gap-2">
                    <Hash className="mt-0.5 h-4 w-4 shrink-0" style={{ color: colors.text }} />
                    <div>
                      <p className="text-xs font-medium" style={{ color: colors.text }}>SHA-256 Content Hash</p>
                      <p className="font-mono text-xs break-all" style={{ color: "var(--text-tertiary)" }}>{d.content_hash}</p>
                    </div>
                  </div>
                )}

                {d.storage_path && (
                  <div className="flex items-start gap-2">
                    <Archive className="mt-0.5 h-4 w-4 shrink-0" style={{ color: colors.text }} />
                    <div>
                      <p className="text-xs font-medium" style={{ color: colors.text }}>Stored at</p>
                      <p className="font-mono text-xs" style={{ color: "var(--text-tertiary)" }}>{d.storage_path}</p>
                    </div>
                  </div>
                )}

                {d.wayback_url && (
                  <div className="flex items-start gap-2">
                    <Link2 className="mt-0.5 h-4 w-4 shrink-0" style={{ color: colors.text }} />
                    <div>
                      <p className="text-xs font-medium" style={{ color: colors.text }}>Wayback Machine</p>
                      <a
                        href={d.wayback_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs hover:underline"
                        style={{ color: "var(--brand-400)" }}
                      >
                        {d.wayback_url}
                      </a>
                    </div>
                  </div>
                )}

                <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                  Captured: {d.captured_at.slice(0, 19).replace("T", " ")} UTC
                </p>

                {d.error && (
                  <p className="text-xs" style={{ color: "#f87171" }}>{d.error}</p>
                )}
              </div>
            </div>
          );
        })()}
      </div>
    </div>
  );
}
