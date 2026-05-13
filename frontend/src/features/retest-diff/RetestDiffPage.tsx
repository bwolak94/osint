import { useState, useCallback } from "react";
import { Upload, RefreshCw, CheckCircle, XCircle, Minus, AlertTriangle } from "lucide-react";
import { Card, CardBody, CardHeader } from "@/shared/components/Card";
import { Badge } from "@/shared/components/Badge";
import { Button } from "@/shared/components/Button";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ScanFinding {
  title: string;
  severity?: string | null;
  tool?: string;
  host?: string | null;
  url?: string | null;
  cve?: string[];
}

interface DiffEntry {
  key: string;
  finding: ScanFinding;
  status: "fixed" | "new" | "persists";
}

function fingerprintFinding(f: ScanFinding): string {
  return `${f.title}|${f.host ?? ""}|${f.url ?? ""}`.toLowerCase();
}

function computeDiff(baseline: ScanFinding[], retest: ScanFinding[]): DiffEntry[] {
  const baselineKeys = new Map<string, ScanFinding>(baseline.map((f) => [fingerprintFinding(f), f]));
  const retestKeys = new Map<string, ScanFinding>(retest.map((f) => [fingerprintFinding(f), f]));

  const result: DiffEntry[] = [];

  for (const [key, f] of baselineKeys) {
    result.push({ key, finding: f, status: retestKeys.has(key) ? "persists" : "fixed" });
  }
  for (const [key, f] of retestKeys) {
    if (!baselineKeys.has(key)) {
      result.push({ key, finding: f, status: "new" });
    }
  }
  return result.sort((a, b) => {
    const order = { new: 0, persists: 1, fixed: 2 };
    return (order[a.status] ?? 3) - (order[b.status] ?? 3);
  });
}

function parseJson(raw: string): ScanFinding[] | null {
  try {
    const parsed = JSON.parse(raw);
    // Accept array of findings or ToolRunResult shape
    if (Array.isArray(parsed)) return parsed as ScanFinding[];
    if (Array.isArray(parsed.findings)) return parsed.findings as ScanFinding[];
    // Session export shape
    if (Array.isArray(parsed.findings) || Array.isArray(parsed)) {
      return (parsed.findings ?? parsed) as ScanFinding[];
    }
    return null;
  } catch {
    return null;
  }
}

const SEV_VARIANTS: Record<string, "danger" | "warning" | "neutral" | "success"> = {
  critical: "danger",
  high: "danger",
  medium: "warning",
  low: "neutral",
  info: "neutral",
};

// ---------------------------------------------------------------------------
// File drop zone
// ---------------------------------------------------------------------------

function DropZone({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  const handleFile = useCallback((file: File) => {
    const reader = new FileReader();
    reader.onload = (e) => onChange(e.target?.result as string ?? "");
    reader.readAsText(file);
  }, [onChange]);

  return (
    <div className="space-y-2">
      <label className="text-xs font-semibold block" style={{ color: "var(--text-secondary)" }}>{label}</label>
      <label
        className="flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed px-4 py-6 cursor-pointer transition-colors"
        style={{ borderColor: "var(--border-default)", background: "var(--bg-base)" }}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          const file = e.dataTransfer.files[0];
          if (file) handleFile(file);
        }}
      >
        <Upload className="h-5 w-5" style={{ color: "var(--text-tertiary)" }} />
        <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>Drop JSON or click to upload</span>
        <input type="file" accept=".json" className="hidden" onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handleFile(file);
        }} />
      </label>
      {value && (
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          rows={4}
          placeholder="Or paste JSON findings array here..."
          className="w-full rounded-md border px-3 py-2 text-xs font-mono resize-none"
          style={{ background: "var(--bg-elevated)", borderColor: "var(--border-default)", color: "var(--text-primary)" }}
        />
      )}
      {!value && (
        <textarea
          placeholder="Or paste JSON findings array here..."
          rows={3}
          onChange={(e) => onChange(e.target.value)}
          className="w-full rounded-md border px-3 py-2 text-xs font-mono resize-none"
          style={{ background: "var(--bg-elevated)", borderColor: "var(--border-default)", color: "var(--text-primary)" }}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function RetestDiffPage() {
  const [baselineRaw, setBaselineRaw] = useState("");
  const [retestRaw, setRetestRaw] = useState("");
  const [diff, setDiff] = useState<DiffEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleCompare = useCallback(() => {
    setError(null);
    const baseline = parseJson(baselineRaw);
    const retest = parseJson(retestRaw);
    if (!baseline) { setError("Baseline JSON is invalid or not a findings array."); return; }
    if (!retest) { setError("Retest JSON is invalid or not a findings array."); return; }
    setDiff(computeDiff(baseline, retest));
  }, [baselineRaw, retestRaw]);

  const fixed = diff?.filter((d) => d.status === "fixed") ?? [];
  const newFindings = diff?.filter((d) => d.status === "new") ?? [];
  const persists = diff?.filter((d) => d.status === "persists") ?? [];

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
          Retest Diff
        </h1>
        <p className="text-sm mt-1" style={{ color: "var(--text-secondary)" }}>
          Compare two scan exports to identify fixed, new, and persisting findings.
        </p>
      </div>

      <div className="grid sm:grid-cols-2 gap-4">
        <DropZone label="Baseline scan (before)" value={baselineRaw} onChange={setBaselineRaw} />
        <DropZone label="Retest scan (after)" value={retestRaw} onChange={setRetestRaw} />
      </div>

      {error && (
        <div className="flex items-center gap-2 text-sm" style={{ color: "var(--danger-400)" }}>
          <AlertTriangle className="h-4 w-4 shrink-0" />
          {error}
        </div>
      )}

      <div className="flex gap-3">
        <Button
          leftIcon={<RefreshCw className="h-3.5 w-3.5" />}
          onClick={handleCompare}
          disabled={!baselineRaw || !retestRaw}
        >
          Compare
        </Button>
        {diff && (
          <Button variant="ghost" size="sm" onClick={() => { setDiff(null); setBaselineRaw(""); setRetestRaw(""); }}>
            Reset
          </Button>
        )}
      </div>

      {diff && (
        <>
          {/* Summary cards */}
          <div className="grid grid-cols-3 gap-3">
            <div className="rounded-lg p-4 text-center" style={{ background: "rgba(34,197,94,0.1)", border: "1px solid rgba(34,197,94,0.3)" }}>
              <CheckCircle className="h-5 w-5 mx-auto mb-1" style={{ color: "var(--success-400)" }} />
              <p className="text-2xl font-bold" style={{ color: "var(--success-400)" }}>{fixed.length}</p>
              <p className="text-xs" style={{ color: "var(--text-secondary)" }}>Fixed</p>
            </div>
            <div className="rounded-lg p-4 text-center" style={{ background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)" }}>
              <XCircle className="h-5 w-5 mx-auto mb-1" style={{ color: "var(--danger-400)" }} />
              <p className="text-2xl font-bold" style={{ color: "var(--danger-400)" }}>{newFindings.length}</p>
              <p className="text-xs" style={{ color: "var(--text-secondary)" }}>New</p>
            </div>
            <div className="rounded-lg p-4 text-center" style={{ background: "rgba(245,158,11,0.1)", border: "1px solid rgba(245,158,11,0.3)" }}>
              <Minus className="h-5 w-5 mx-auto mb-1" style={{ color: "var(--warning-400)" }} />
              <p className="text-2xl font-bold" style={{ color: "var(--warning-400)" }}>{persists.length}</p>
              <p className="text-xs" style={{ color: "var(--text-secondary)" }}>Persists</p>
            </div>
          </div>

          {/* Diff table */}
          {[
            { label: "New Findings", items: newFindings, color: "var(--danger-400)", bg: "rgba(239,68,68,0.05)" },
            { label: "Persisting Findings", items: persists, color: "var(--warning-400)", bg: "rgba(245,158,11,0.05)" },
            { label: "Fixed Findings", items: fixed, color: "var(--success-400)", bg: "rgba(34,197,94,0.05)" },
          ].map(({ label, items, color, bg }) => items.length > 0 && (
            <Card key={label}>
              <CardHeader>
                <p className="text-sm font-semibold" style={{ color }}>{label} ({items.length})</p>
              </CardHeader>
              <CardBody className="p-0">
                {items.map((entry) => (
                  <div key={entry.key} className="flex items-center gap-3 px-4 py-2.5 border-b text-xs"
                    style={{ borderColor: "var(--border-default)", background: bg }}>
                    <Badge variant={SEV_VARIANTS[(entry.finding.severity ?? "info").toLowerCase()] ?? "neutral"} size="sm">
                      {(entry.finding.severity ?? "info").toUpperCase()}
                    </Badge>
                    <span className="flex-1 font-medium" style={{ color: "var(--text-primary)" }}>{entry.finding.title}</span>
                    {entry.finding.tool && (
                      <span className="font-mono" style={{ color: "var(--text-tertiary)" }}>{entry.finding.tool}</span>
                    )}
                    {(entry.finding.host || entry.finding.url) && (
                      <span className="font-mono truncate max-w-xs" style={{ color: "var(--text-tertiary)" }}>
                        {entry.finding.host || entry.finding.url}
                      </span>
                    )}
                  </div>
                ))}
              </CardBody>
            </Card>
          ))}
        </>
      )}
    </div>
  );
}
