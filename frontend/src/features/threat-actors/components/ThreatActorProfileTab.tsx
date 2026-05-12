/**
 * Threat Actor Profile Builder (Feature 7)
 * MITRE tactic coverage heatmap, campaign timeline, IOC breakdown.
 */
import { Loader2, Swords, Radio, AlertTriangle } from "lucide-react";
import { Badge } from "@/shared/components/Badge";
import { useThreatActorProfile } from "../hooks";
import type { CampaignSummary } from "../types";

const SEVERITY_VARIANT: Record<string, "danger" | "warning" | "info" | "neutral"> = {
  critical: "danger",
  high: "warning",
  medium: "info",
  low: "neutral",
};

function CampaignRow({ campaign }: { campaign: CampaignSummary }) {
  return (
    <div
      className="flex items-start gap-3 rounded-md px-3 py-2.5"
      style={{ background: "var(--bg-elevated)" }}
    >
      <div
        className="mt-0.5 h-2 w-2 shrink-0 rounded-full"
        style={{
          background:
            campaign.severity === "critical"
              ? "var(--danger-500)"
              : campaign.severity === "high"
              ? "var(--warning-500)"
              : "var(--info-500)",
        }}
      />
      <div className="flex-1 min-w-0">
        <p className="text-xs font-medium truncate" style={{ color: "var(--text-primary)" }}>
          {campaign.name}
        </p>
        <div className="mt-0.5 flex flex-wrap gap-1">
          {campaign.targets.map((t) => (
            <span
              key={t}
              className="rounded-full px-1.5 py-0.5 text-[10px]"
              style={{ background: "var(--bg-overlay)", color: "var(--text-tertiary)" }}
            >
              {t}
            </span>
          ))}
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-1.5">
        <Badge variant={SEVERITY_VARIANT[campaign.severity] ?? "neutral"} size="sm">
          {campaign.severity}
        </Badge>
        <span className="text-[11px] font-mono" style={{ color: "var(--text-tertiary)" }}>
          {campaign.year}
        </span>
      </div>
    </div>
  );
}

interface Props {
  actorId: string;
}

export function ThreatActorProfileTab({ actorId }: Props) {
  const { data: profile, isLoading } = useThreatActorProfile(actorId);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-10">
        <Loader2 className="h-5 w-5 animate-spin" style={{ color: "var(--brand-500)" }} />
      </div>
    );
  }

  if (!profile) return null;

  return (
    <div className="space-y-5">
      {/* Risk score */}
      <div>
        <div className="flex items-center justify-between mb-1.5">
          <p className="text-xs font-semibold" style={{ color: "var(--text-secondary)" }}>
            Overall Risk Score
          </p>
          <span
            className="text-lg font-bold tabular-nums"
            style={{
              color:
                profile.risk_score >= 80
                  ? "var(--danger-400)"
                  : profile.risk_score >= 55
                  ? "var(--warning-400)"
                  : "var(--success-400)",
            }}
          >
            {profile.risk_score}
          </span>
        </div>
        <div
          className="h-2 w-full overflow-hidden rounded-full"
          style={{ background: "var(--bg-overlay)" }}
        >
          <div
            className="h-2 rounded-full transition-all duration-700"
            style={{
              width: `${profile.risk_score}%`,
              background:
                profile.risk_score >= 80
                  ? "var(--danger-500)"
                  : profile.risk_score >= 55
                  ? "var(--warning-500)"
                  : "var(--success-500)",
            }}
          />
        </div>
        <p className="mt-1 text-[10px]" style={{ color: "var(--text-tertiary)" }}>
          {profile.total_tactics_covered} tactics · {profile.total_techniques} techniques
        </p>
      </div>

      {/* MITRE tactic coverage */}
      {profile.tactic_coverage.length > 0 && (
        <div>
          <div className="flex items-center gap-1.5 mb-2">
            <Swords className="h-3.5 w-3.5" style={{ color: "var(--brand-400)" }} />
            <p className="text-xs font-semibold" style={{ color: "var(--text-secondary)" }}>
              MITRE ATT&amp;CK Coverage
            </p>
          </div>
          <div className="space-y-1.5">
            {profile.tactic_coverage.map((tc) => (
              <div key={tc.tactic}>
                <div className="flex items-center justify-between mb-0.5">
                  <span className="text-[11px]" style={{ color: "var(--text-secondary)" }}>
                    {tc.tactic}
                  </span>
                  <span className="text-[11px] font-mono" style={{ color: "var(--text-tertiary)" }}>
                    {tc.techniques.join(", ")}
                  </span>
                </div>
                <div
                  className="h-1.5 rounded-full overflow-hidden"
                  style={{ background: "var(--bg-overlay)" }}
                >
                  <div
                    className="h-1.5 rounded-full"
                    style={{
                      width: `${Math.min(tc.coverage_count * 25, 100)}%`,
                      background: "var(--brand-500)",
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* IOC breakdown */}
      {profile.ioc_breakdown.length > 0 && (
        <div>
          <div className="flex items-center gap-1.5 mb-2">
            <Radio className="h-3.5 w-3.5" style={{ color: "var(--danger-400)" }} />
            <p className="text-xs font-semibold" style={{ color: "var(--text-secondary)" }}>
              IOC Breakdown
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {profile.ioc_breakdown.map((ioc) => (
              <div
                key={ioc.category}
                className="flex-1 min-w-[80px] rounded-md px-3 py-2 text-center"
                style={{ background: "var(--bg-elevated)" }}
              >
                <p className="text-base font-bold tabular-nums" style={{ color: "var(--text-primary)" }}>
                  {ioc.count}
                </p>
                <p className="text-[10px] capitalize" style={{ color: "var(--text-tertiary)" }}>
                  {ioc.category}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Associated campaigns */}
      {profile.campaigns.length > 0 && (
        <div>
          <div className="flex items-center gap-1.5 mb-2">
            <AlertTriangle className="h-3.5 w-3.5" style={{ color: "var(--warning-400)" }} />
            <p className="text-xs font-semibold" style={{ color: "var(--text-secondary)" }}>
              Associated Campaigns ({profile.campaigns.length})
            </p>
          </div>
          <div className="space-y-1.5">
            {profile.campaigns.map((c) => (
              <CampaignRow key={c.id} campaign={c} />
            ))}
          </div>
        </div>
      )}

      {profile.campaigns.length === 0 && profile.ioc_breakdown.length === 0 && (
        <p className="text-center text-xs py-4" style={{ color: "var(--text-tertiary)" }}>
          No campaign or IOC data available for this actor.
        </p>
      )}
    </div>
  );
}
