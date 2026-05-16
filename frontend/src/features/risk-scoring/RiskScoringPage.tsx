import { useState } from "react";
import { ShieldAlert, TrendingUp, AlertTriangle, Info, CheckCircle2 } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import axios from "axios";

interface RiskScoreResponse {
  score: number;
  risk_level: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  breakdown: {
    total_findings: number;
    severity_counts: Record<string, number>;
    raw_score: number;
  };
  top_threats: Array<{ type: string; severity: string; source: string; description: string }>;
  recommendations: string[];
}

const RISK_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  CRITICAL: { bg: "#7f1d1d", text: "#fca5a5", border: "#991b1b" },
  HIGH: { bg: "#7c2d12", text: "#fdba74", border: "#9a3412" },
  MEDIUM: { bg: "#713f12", text: "#fde68a", border: "#92400e" },
  LOW: { bg: "#14532d", text: "#86efac", border: "#166534" },
  UNKNOWN: { bg: "#1e293b", text: "#94a3b8", border: "#334155" },
};

function ScoreGauge({ score, level }: { score: number; level: string }) {
  const colors = RISK_COLORS[level] || RISK_COLORS.UNKNOWN;
  const circumference = 2 * Math.PI * 40;
  const dash = (score / 100) * circumference;

  return (
    <div className="flex flex-col items-center gap-2">
      <svg width="100" height="100" viewBox="0 0 100 100">
        <circle cx="50" cy="50" r="40" fill="none" stroke="#1e293b" strokeWidth="10" />
        <circle
          cx="50"
          cy="50"
          r="40"
          fill="none"
          stroke={colors.text}
          strokeWidth="10"
          strokeDasharray={`${dash} ${circumference - dash}`}
          strokeLinecap="round"
          transform="rotate(-90 50 50)"
        />
        <text x="50" y="54" textAnchor="middle" fontSize="20" fontWeight="700" fill={colors.text}>
          {Math.round(score)}
        </text>
      </svg>
      <span
        className="rounded-full px-3 py-0.5 text-xs font-bold uppercase"
        style={{ background: colors.bg, color: colors.text, border: `1px solid ${colors.border}` }}
      >
        {level}
      </span>
    </div>
  );
}

function SampleFindings() {
  return [
    { type: "credentials_found", severity: "critical", source: "LeakCheck", description: "Email found in 3 breach databases" },
    { type: "court_records_found", severity: "high", source: "CourtListener", description: "2 criminal cases found" },
    { type: "google_news_results", severity: "medium", source: "Google News", description: "5 negative news articles" },
  ];
}

export function RiskScoringPage() {
  const [investigationId, setInvestigationId] = useState("");

  const mutation = useMutation({
    mutationFn: (invId: string) =>
      axios
        .get<RiskScoreResponse>(`/api/v1/risk-scoring/investigation/${invId}`)
        .then((r) => r.data),
  });

  const manualMutation = useMutation({
    mutationFn: () =>
      axios
        .post<RiskScoreResponse>("/api/v1/risk-scoring/compute", {
          findings: SampleFindings(),
        })
        .then((r) => r.data),
  });

  const result = mutation.data || manualMutation.data;
  const isPending = mutation.isPending || manualMutation.isPending;

  return (
    <div className="min-h-screen p-6" style={{ background: "var(--bg-base)" }}>
      <div className="mx-auto max-w-3xl">
        {/* Header */}
        <div className="mb-8 flex items-center gap-3">
          <div
            className="flex h-10 w-10 items-center justify-center rounded-lg"
            style={{ background: "var(--danger-subtle, #450a0a)", border: "1px solid var(--danger-border, #7f1d1d)" }}
          >
            <ShieldAlert className="h-5 w-5" style={{ color: "var(--danger-400, #f87171)" }} />
          </div>
          <div>
            <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
              Risk Scoring Engine
            </h1>
            <p className="text-sm" style={{ color: "var(--text-tertiary)" }}>
              Compute a composite threat risk score from investigation findings
            </p>
          </div>
        </div>

        {/* Investigation lookup */}
        <div
          className="mb-6 rounded-xl border p-5"
          style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}
        >
          <label className="mb-2 block text-sm font-medium" style={{ color: "var(--text-secondary)" }}>
            Investigation ID
          </label>
          <div className="flex gap-3">
            <input
              type="text"
              placeholder="Enter investigation UUID..."
              value={investigationId}
              onChange={(e) => setInvestigationId(e.target.value)}
              className="flex-1 rounded-lg border px-3 py-2 text-sm font-mono outline-none"
              style={{
                background: "var(--bg-base)",
                borderColor: "var(--border-default)",
                color: "var(--text-primary)",
              }}
            />
            <button
              onClick={() => investigationId && mutation.mutate(investigationId)}
              disabled={!investigationId || isPending}
              className="rounded-lg px-4 py-2 text-sm font-semibold transition-all disabled:opacity-40"
              style={{ background: "var(--brand-500)", color: "#fff" }}
            >
              {mutation.isPending ? "Scoring..." : "Score"}
            </button>
          </div>
          <div className="mt-3 border-t pt-3" style={{ borderColor: "var(--border-subtle)" }}>
            <button
              onClick={() => manualMutation.mutate()}
              disabled={isPending}
              className="text-xs transition-opacity hover:opacity-70"
              style={{ color: "var(--text-tertiary)" }}
            >
              Or run with sample findings →
            </button>
          </div>
        </div>

        {/* Result */}
        {result && (
          <div className="space-y-4">
            {/* Score overview */}
            <div
              className="flex items-center gap-8 rounded-xl border p-6"
              style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}
            >
              <ScoreGauge score={result.score} level={result.risk_level} />
              <div className="flex-1">
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  {Object.entries(result.breakdown.severity_counts || {}).map(([sev, count]) => (
                    <div key={sev} className="rounded-lg border px-3 py-2" style={{ borderColor: "var(--border-subtle)", background: "var(--bg-base)" }}>
                      <div className="text-lg font-bold" style={{ color: "var(--text-primary)" }}>{count}</div>
                      <div className="text-xs capitalize" style={{ color: "var(--text-tertiary)" }}>{sev}</div>
                    </div>
                  ))}
                </div>
                <p className="mt-3 text-xs" style={{ color: "var(--text-tertiary)" }}>
                  {result.breakdown.total_findings} total findings &nbsp;·&nbsp; Raw score: {result.breakdown.raw_score}
                </p>
              </div>
            </div>

            {/* Top threats */}
            {result.top_threats.length > 0 && (
              <div
                className="rounded-xl border"
                style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}
              >
                <div className="border-b px-5 py-3" style={{ borderColor: "var(--border-subtle)" }}>
                  <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                    Top Threats
                  </h3>
                </div>
                <div className="divide-y" style={{ borderColor: "var(--border-subtle)" }}>
                  {result.top_threats.slice(0, 5).map((t, i) => (
                    <div key={i} className="flex items-start gap-3 px-5 py-3">
                      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" style={{ color: "var(--danger-400, #f87171)" }} />
                      <div>
                        <p className="text-sm" style={{ color: "var(--text-primary)" }}>{t.description}</p>
                        <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                          {t.source} &nbsp;·&nbsp; <span className="capitalize">{t.severity}</span>
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Recommendations */}
            {result.recommendations.length > 0 && (
              <div
                className="rounded-xl border"
                style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}
              >
                <div className="border-b px-5 py-3" style={{ borderColor: "var(--border-subtle)" }}>
                  <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                    Recommendations
                  </h3>
                </div>
                <div className="divide-y" style={{ borderColor: "var(--border-subtle)" }}>
                  {result.recommendations.map((rec, i) => (
                    <div key={i} className="flex items-start gap-3 px-5 py-3">
                      <Info className="mt-0.5 h-4 w-4 shrink-0" style={{ color: "var(--brand-400)" }} />
                      <p className="text-sm" style={{ color: "var(--text-secondary)" }}>{rec}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
