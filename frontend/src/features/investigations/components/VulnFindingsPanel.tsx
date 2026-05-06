import { useState, useMemo } from "react";
import { Shield, ShieldAlert, ShieldCheck, ShieldX, ExternalLink, ChevronDown, ChevronRight, BookOpen, Tag } from "lucide-react";
import { Badge } from "@/shared/components/Badge";
import { Card, CardBody, CardHeader } from "@/shared/components/Card";
import { EmptyState } from "@/shared/components/EmptyState";

// ── Types ─────────────────────────────────────────────────────────────────────

interface VulnFinding {
  template_id: string;
  name: string;
  severity: "critical" | "high" | "medium" | "low" | "info";
  category: string;
  description: string;
  matched_at: string;
  evidence: string;
  extracted: Record<string, string>;
  request_ms: number;
  remediation: string;
  references: string[];
  cvss_score: number | null;
  tags: string[];
}

interface VulnScanData {
  target_url: string;
  scan_mode: string;
  findings: VulnFinding[];
  summary: Record<string, number>;
  templates_run: number;
  elapsed_ms: number;
}

interface VulnFindingsPanelProps {
  /** All scan results from the investigation */
  scanResults: Array<{ scanner_name: string; raw_data: Record<string, unknown>; status: string }>;
}

// ── Severity config ───────────────────────────────────────────────────────────

type SeverityKey = "critical" | "high" | "medium" | "low" | "info";

const SEVERITY_CONFIG: Record<SeverityKey, {
  label: string;
  color: string;
  bg: string;
  icon: typeof ShieldAlert;
  variant: "danger" | "warning" | "info" | "neutral";
}> = {
  critical: { label: "Critical", color: "var(--danger-500, #ef4444)", bg: "var(--danger-500, #ef4444)14", icon: ShieldX, variant: "danger" },
  high:     { label: "High",     color: "var(--warning-600, #d97706)", bg: "var(--warning-500, #f59e0b)14", icon: ShieldAlert, variant: "warning" },
  medium:   { label: "Medium",   color: "var(--warning-400, #fbbf24)", bg: "var(--warning-400, #fbbf24)14", icon: Shield, variant: "warning" },
  low:      { label: "Low",      color: "var(--info-400, #38bdf8)", bg: "var(--info-400, #38bdf8)14", icon: ShieldCheck, variant: "info" },
  info:     { label: "Info",     color: "var(--text-tertiary)", bg: "var(--bg-elevated)", icon: Shield, variant: "neutral" },
};

const SEVERITY_ORDER: SeverityKey[] = ["critical", "high", "medium", "low", "info"];

// ── Sub-components ────────────────────────────────────────────────────────────

function SeveritySummaryBar({ summary }: { summary: Record<string, number> }) {
  return (
    <div className="flex items-center gap-3 flex-wrap">
      {SEVERITY_ORDER.map((sev) => {
        const count = summary[sev] ?? 0;
        if (count === 0) return null;
        const cfg = SEVERITY_CONFIG[sev];
        return (
          <div key={sev} className="flex items-center gap-1.5 rounded-md px-2 py-1" style={{ background: cfg.bg }}>
            <cfg.icon className="h-3.5 w-3.5" style={{ color: cfg.color }} />
            <span className="text-xs font-semibold tabular-nums" style={{ color: cfg.color }}>{count}</span>
            <span className="text-xs" style={{ color: cfg.color }}>{cfg.label}</span>
          </div>
        );
      })}
    </div>
  );
}

function FindingCard({ finding }: { finding: VulnFinding }) {
  const [expanded, setExpanded] = useState(false);
  const cfg = SEVERITY_CONFIG[finding.severity] ?? SEVERITY_CONFIG.info;
  const Icon = cfg.icon;

  return (
    <div
      className="rounded-lg border transition-colors"
      style={{ borderColor: expanded ? cfg.color + "60" : "var(--border-subtle)", background: "var(--bg-surface)" }}
    >
      {/* Header row */}
      <button
        className="flex w-full items-start gap-3 px-4 py-3 text-left"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
      >
        <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md" style={{ background: cfg.bg }}>
          <Icon className="h-3.5 w-3.5" style={{ color: cfg.color }} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
              {finding.name}
            </span>
            <Badge variant={cfg.variant} size="sm">{cfg.label}</Badge>
            {finding.cvss_score != null && (
              <span className="font-mono text-xs" style={{ color: "var(--text-tertiary)" }}>
                CVSS {finding.cvss_score.toFixed(1)}
              </span>
            )}
            <span className="text-xs font-mono" style={{ color: "var(--text-tertiary)" }}>
              {finding.template_id}
            </span>
          </div>
          <p className="mt-0.5 truncate text-xs" style={{ color: "var(--text-secondary)" }}>
            {finding.matched_at}
          </p>
        </div>
        <div className="shrink-0 mt-1">
          {expanded
            ? <ChevronDown className="h-4 w-4" style={{ color: "var(--text-tertiary)" }} />
            : <ChevronRight className="h-4 w-4" style={{ color: "var(--text-tertiary)" }} />}
        </div>
      </button>

      {/* Expanded detail */}
      {expanded && (
        <div className="border-t px-4 py-4 space-y-4" style={{ borderColor: "var(--border-subtle)" }}>
          {/* Description */}
          <div>
            <p className="text-xs font-medium uppercase tracking-wide mb-1" style={{ color: "var(--text-tertiary)" }}>Description</p>
            <p className="text-sm" style={{ color: "var(--text-secondary)" }}>{finding.description}</p>
          </div>

          {/* Evidence */}
          {finding.evidence && (
            <div>
              <p className="text-xs font-medium uppercase tracking-wide mb-1" style={{ color: "var(--text-tertiary)" }}>Evidence</p>
              <pre
                className="overflow-x-auto rounded-md p-2 text-xs font-mono"
                style={{ background: "var(--bg-elevated)", color: "var(--text-primary)" }}
              >
                {finding.evidence}
              </pre>
            </div>
          )}

          {/* Extracted values */}
          {Object.keys(finding.extracted).length > 0 && (
            <div>
              <p className="text-xs font-medium uppercase tracking-wide mb-1" style={{ color: "var(--text-tertiary)" }}>Extracted</p>
              <div className="space-y-1">
                {Object.entries(finding.extracted).map(([k, v]) => (
                  <div key={k} className="flex items-center gap-2">
                    <span className="text-xs font-mono" style={{ color: "var(--text-tertiary)" }}>{k}:</span>
                    <span className="text-xs font-mono truncate" style={{ color: "var(--text-primary)" }}>{v}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Remediation */}
          {finding.remediation && (
            <div className="rounded-md p-3" style={{ background: "var(--success-500)0d", border: "1px solid var(--success-500)30" }}>
              <div className="flex items-start gap-2">
                <ShieldCheck className="h-4 w-4 mt-0.5 shrink-0" style={{ color: "var(--success-500)" }} />
                <div>
                  <p className="text-xs font-medium mb-1" style={{ color: "var(--success-500)" }}>Remediation</p>
                  <p className="text-xs" style={{ color: "var(--text-secondary)" }}>{finding.remediation}</p>
                </div>
              </div>
            </div>
          )}

          {/* Tags + References */}
          <div className="flex items-start justify-between gap-4 flex-wrap">
            {finding.tags.length > 0 && (
              <div className="flex items-center gap-1.5 flex-wrap">
                <Tag className="h-3 w-3" style={{ color: "var(--text-tertiary)" }} />
                {finding.tags.map((tag) => (
                  <Badge key={tag} variant="neutral" size="sm">{tag}</Badge>
                ))}
              </div>
            )}
            {finding.references.length > 0 && (
              <div className="flex items-center gap-2">
                <BookOpen className="h-3 w-3" style={{ color: "var(--text-tertiary)" }} />
                {finding.references.map((ref, i) => (
                  <a
                    key={i}
                    href={ref}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-0.5 text-xs underline hover:no-underline"
                    style={{ color: "var(--brand-400)" }}
                  >
                    Ref {i + 1}
                    <ExternalLink className="h-3 w-3" />
                  </a>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function VulnFindingsPanel({ scanResults }: VulnFindingsPanelProps) {
  const [activeFilter, setActiveFilter] = useState<SeverityKey | "all">("all");

  // Collect all vuln_probe scan results
  const vulnScans: VulnScanData[] = useMemo(() =>
    scanResults
      .filter((r) => r.scanner_name === "vuln_probe" && r.status === "success")
      .map((r) => r.raw_data as unknown as VulnScanData),
    [scanResults],
  );

  // Flatten all findings across all vuln_probe scans
  const allFindings: VulnFinding[] = useMemo(() =>
    vulnScans.flatMap((s) => s.findings ?? []),
    [vulnScans],
  );

  const aggregateSummary = useMemo(() => {
    const totals: Record<string, number> = {};
    for (const s of vulnScans) {
      for (const [sev, count] of Object.entries(s.summary ?? {})) {
        totals[sev] = (totals[sev] ?? 0) + count;
      }
    }
    return totals;
  }, [vulnScans]);

  const visibleFindings = useMemo(() =>
    activeFilter === "all"
      ? allFindings
      : allFindings.filter((f) => f.severity === activeFilter),
    [allFindings, activeFilter],
  );

  if (vulnScans.length === 0) {
    return (
      <EmptyState
        title="No Vulnerability Scan Results"
        description="Run the investigation with the vuln_probe scanner enabled to detect web security issues."
      />
    );
  }

  return (
    <div className="space-y-4">
      {/* Aggregate stats bar */}
      {vulnScans.map((scan, idx) => (
        <Card key={idx}>
          <CardHeader className="flex items-center justify-between py-3">
            <div className="flex items-center gap-2">
              <Shield className="h-4 w-4" style={{ color: "var(--brand-400)" }} />
              <span className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                {scan.target_url}
              </span>
              <Badge variant="neutral" size="sm">{scan.templates_run} templates</Badge>
              <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                {(scan.elapsed_ms / 1000).toFixed(1)}s
              </span>
            </div>
            <SeveritySummaryBar summary={scan.summary} />
          </CardHeader>
        </Card>
      ))}

      {/* Severity filter tabs */}
      <div className="flex gap-1 border-b" style={{ borderColor: "var(--border-subtle)" }}>
        {(["all", ...SEVERITY_ORDER] as const).map((sev) => {
          const count = sev === "all" ? allFindings.length : (aggregateSummary[sev] ?? 0);
          const cfg = sev !== "all" ? SEVERITY_CONFIG[sev] : null;
          return (
            <button
              key={sev}
              onClick={() => setActiveFilter(sev)}
              className={`flex items-center gap-1.5 border-b-2 px-3 py-2 text-xs font-medium transition-colors ${
                activeFilter === sev
                  ? "border-brand-500 text-brand-400"
                  : "border-transparent text-text-secondary hover:text-text-primary"
              }`}
            >
              {cfg && <cfg.icon className="h-3 w-3" style={{ color: activeFilter === sev ? cfg.color : undefined }} />}
              <span className="capitalize">{sev}</span>
              {count > 0 && (
                <span
                  className="rounded-full px-1.5 py-0.5 text-[10px] font-bold"
                  style={{
                    background: cfg ? cfg.bg : "var(--bg-elevated)",
                    color: cfg ? cfg.color : "var(--text-secondary)",
                  }}
                >
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Findings list */}
      {visibleFindings.length === 0 ? (
        <EmptyState
          title={activeFilter === "all" ? "No Findings" : `No ${activeFilter} Findings`}
          description={activeFilter === "all"
            ? "The scanner ran but found no issues. The target may be well-configured."
            : `No ${activeFilter}-severity issues were detected.`}
        />
      ) : (
        <div className="space-y-2">
          {visibleFindings.map((f, idx) => (
            <FindingCard key={`${f.template_id}-${idx}`} finding={f} />
          ))}
        </div>
      )}
    </div>
  );
}
