import { useState } from "react";
import { Globe, Search, Shield, CheckCircle, XCircle, Trash2 } from "lucide-react";
import { useHttpFingerprint, useHttpFingerprintHistory, useDeleteHttpFingerprintScan } from "./hooks";
import type { HttpFingerprintResult } from "./types";
import { Button } from "@/shared/components/Button";
import { Input } from "@/shared/components/Input";
import { Card, CardBody } from "@/shared/components/Card";
import { Badge } from "@/shared/components/Badge";

function ScoreBar({ score }: { score: number }) {
  const color = score >= 80 ? "var(--success-400, #4ade80)" : score >= 50 ? "var(--warning-400)" : "var(--danger-400)";
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 h-2 rounded-full overflow-hidden" style={{ background: "var(--bg-overlay)" }}>
        <div className="h-full rounded-full transition-all" style={{ width: `${score}%`, background: color }} />
      </div>
      <span className="text-sm font-bold w-10 text-right" style={{ color }}>{score}/100</span>
    </div>
  );
}

function FingerprintResults({ data }: { data: HttpFingerprintResult }) {
  if (data.error) {
    return (
      <div className="rounded-xl border px-5 py-4" style={{ borderColor: "var(--danger-500)", background: "var(--bg-surface)" }}>
        <p className="text-sm font-medium" style={{ color: "var(--danger-400)" }}>Scan Error</p>
        <p className="text-xs mt-1 font-mono" style={{ color: "var(--text-secondary)" }}>{data.error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Summary row */}
      <div className="grid gap-3 sm:grid-cols-4">
        {[
          { label: "Status", value: data.status_code ?? "—" },
          { label: "CDN", value: data.cdn ?? "None" },
          { label: "Technologies", value: data.technologies.length },
          { label: "Security Score", value: `${data.security.score}%` },
        ].map(({ label, value }) => (
          <div key={label} className="rounded-xl border p-4 text-center" style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}>
            <p className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>{value}</p>
            <p className="text-xs mt-1" style={{ color: "var(--text-tertiary)" }}>{label}</p>
          </div>
        ))}
      </div>

      {/* Technologies */}
      {data.technologies.length > 0 && (
        <div className="rounded-xl border p-4 space-y-2" style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}>
          <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--text-tertiary)" }}>Detected Technologies</p>
          <div className="flex flex-wrap gap-2">
            {data.technologies.map((t) => <Badge key={t} variant="brand" size="sm">{t}</Badge>)}
          </div>
        </div>
      )}

      {/* Security headers */}
      <div className="rounded-xl border p-4 space-y-3" style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}>
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: "var(--text-tertiary)" }}>Security Header Score</p>
          <ScoreBar score={data.security.score} />
        </div>
        <div className="grid gap-1 sm:grid-cols-2">
          {data.security.present.map((h) => (
            <div key={h} className="flex items-center gap-2 text-xs">
              <CheckCircle className="h-3 w-3 shrink-0" style={{ color: "var(--success-400, #4ade80)" }} />
              <span className="font-mono" style={{ color: "var(--text-secondary)" }}>{h}</span>
            </div>
          ))}
          {data.security.missing.map((h) => (
            <div key={h} className="flex items-center gap-2 text-xs">
              <XCircle className="h-3 w-3 shrink-0" style={{ color: "var(--danger-400)" }} />
              <span className="font-mono" style={{ color: "var(--text-tertiary)" }}>{h}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Response headers (collapsed list) */}
      <details className="rounded-xl border" style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}>
        <summary className="px-4 py-3 text-xs font-semibold uppercase tracking-wide cursor-pointer" style={{ color: "var(--text-tertiary)" }}>
          Response Headers ({Object.keys(data.headers).length})
        </summary>
        <div className="px-4 pb-4 space-y-1">
          {Object.entries(data.headers).map(([k, v]) => (
            <div key={k} className="flex gap-3 text-xs">
              <span className="font-mono font-medium w-48 shrink-0 truncate" style={{ color: "var(--brand-400)" }}>{k}</span>
              <span className="font-mono truncate" style={{ color: "var(--text-secondary)" }}>{v}</span>
            </div>
          ))}
        </div>
      </details>
    </div>
  );
}

function HttpFingerprintHistory({ onSelect }: { onSelect: (item: HttpFingerprintResult) => void }) {
  const { data, isLoading } = useHttpFingerprintHistory();
  const deleteScan = useDeleteHttpFingerprintScan();

  if (isLoading) return <p className="text-xs py-4 text-center" style={{ color: "var(--text-tertiary)" }}>Loading history...</p>;
  if (!data?.items.length) return <p className="text-xs py-4 text-center" style={{ color: "var(--text-tertiary)" }}>No previous scans yet.</p>;

  return (
    <div className="space-y-1">
      {data.items.map((item) => (
        <div
          key={item.id}
          className="flex items-center justify-between rounded-lg px-3 py-2 cursor-pointer"
          style={{ background: "var(--bg-overlay)" }}
          onClick={() => onSelect(item)}
        >
          <div className="flex-1 min-w-0">
            <p className="text-sm font-mono truncate" style={{ color: "var(--text-primary)" }}>{item.url}</p>
            <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
              Score: {item.security.score}/100 · {item.technologies.length} tech · {item.created_at ? new Date(item.created_at).toLocaleString() : ""}
            </p>
          </div>
          <button
            className="ml-2 p-1 rounded opacity-60 hover:opacity-100"
            onClick={(e) => { e.stopPropagation(); if (item.id) deleteScan.mutate(item.id); }}
          >
            <Trash2 className="h-3.5 w-3.5" style={{ color: "var(--danger-400)" }} />
          </button>
        </div>
      ))}
    </div>
  );
}

export function HttpFingerprintPage() {
  const [url, setUrl] = useState("");
  const fingerprint = useHttpFingerprint();
  const [currentResult, setCurrentResult] = useState<HttpFingerprintResult | null>(null);

  const handleScan = () => {
    if (url.trim()) fingerprint.mutate(url.trim(), { onSuccess: (d) => setCurrentResult(d) });
  };

  const result = fingerprint.data ?? currentResult;

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <Globe className="h-6 w-6" style={{ color: "var(--brand-400)" }} />
        <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>HTTP Fingerprint</h1>
      </div>

      <Card>
        <CardBody>
          <div className="flex gap-3">
            <div className="flex-1">
              <Input
                placeholder="https://example.com"
                prefixIcon={<Search className="h-4 w-4" />}
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleScan()}
              />
            </div>
            <Button onClick={handleScan} disabled={!url.trim() || fingerprint.isPending} leftIcon={<Shield className="h-4 w-4" />}>
              {fingerprint.isPending ? "Scanning..." : "Fingerprint"}
            </Button>
          </div>
          <p className="mt-2 text-xs" style={{ color: "var(--text-tertiary)" }}>
            Detects tech stack, CDN, and security headers without installing anything.
          </p>
        </CardBody>
      </Card>

      {result && <FingerprintResults data={result} />}

      {!result && !fingerprint.isPending && (
        <div className="rounded-xl border py-16 text-center" style={{ borderColor: "var(--border-subtle)" }}>
          <Globe className="mx-auto h-10 w-10 mb-3" style={{ color: "var(--text-tertiary)" }} />
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Enter a URL to fingerprint its tech stack and security posture</p>
        </div>
      )}

      <div className="rounded-xl border p-5" style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}>
        <h2 className="mb-3 text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Scan History</h2>
        <HttpFingerprintHistory onSelect={setCurrentResult} />
      </div>
    </div>
  );
}
