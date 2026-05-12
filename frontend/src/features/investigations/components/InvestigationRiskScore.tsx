import { useQuery } from "@tanstack/react-query";
import { Shield, RefreshCw } from "lucide-react";
import { apiClient } from "@/shared/api/client";

interface RiskScoreData {
  investigation_id: string;
  score: number;
  label: "low" | "medium" | "high" | "critical";
  breach_count: number;
  exposed_services: number;
  avg_confidence: number;
  factors: Record<string, number>;
  computed_at: string;
}

interface Props {
  investigationId: string;
}

const labelConfig = {
  low: { color: "var(--success-500)", bg: "var(--success-950)", text: "Low Risk" },
  medium: { color: "var(--warning-500)", bg: "var(--warning-950)", text: "Medium Risk" },
  high: { color: "var(--danger-400)", bg: "var(--danger-950)", text: "High Risk" },
  critical: { color: "var(--danger-500)", bg: "var(--danger-900)", text: "Critical" },
};

export function InvestigationRiskScore({ investigationId }: Props) {
  const { data, isLoading, refetch, isFetching } = useQuery<RiskScoreData>({
    queryKey: ["risk-score", investigationId],
    queryFn: async () => {
      const resp = await apiClient.get(`/investigations/${investigationId}/risk-score`);
      return resp.data as RiskScoreData;
    },
    staleTime: 5 * 60 * 1000,
  });

  if (isLoading) {
    return (
      <div
        className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm animate-pulse"
        style={{ background: "var(--bg-overlay)" }}
      >
        <Shield className="h-4 w-4" style={{ color: "var(--text-tertiary)" }} />
        <span style={{ color: "var(--text-tertiary)" }}>Calculating risk…</span>
      </div>
    );
  }

  if (!data) return null;

  const cfg = labelConfig[data.label];

  return (
    <div
      className="flex items-center gap-3 rounded-lg px-4 py-3"
      style={{ background: cfg.bg, border: `1px solid ${cfg.color}33` }}
    >
      <Shield className="h-5 w-5 shrink-0" style={{ color: cfg.color }} />
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline gap-2">
          <span className="text-2xl font-bold" style={{ color: cfg.color }}>
            {Math.round(data.score)}
          </span>
          <span className="text-xs font-semibold uppercase tracking-wide" style={{ color: cfg.color }}>
            {cfg.text}
          </span>
        </div>
        <p className="text-xs mt-0.5 truncate" style={{ color: "var(--text-tertiary)" }}>
          <span title="Number of data breaches found in HIBP and similar sources">{data.breach_count} breaches</span>
          {" · "}
          <span title="Open / exposed network services detected by Shodan and port scanners">{data.exposed_services} services</span>
          {" · "}
          <span title="Average confidence score across all identity resolution results">{Math.round(data.avg_confidence * 100)}% confidence</span>
        </p>
      </div>
      <button
        onClick={() => refetch()}
        disabled={isFetching}
        title="Recompute risk score"
        className="rounded p-1 transition-colors hover:bg-bg-overlay"
        aria-label="Recompute risk score"
      >
        <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? "animate-spin" : ""}`} style={{ color: "var(--text-tertiary)" }} />
      </button>
    </div>
  );
}
