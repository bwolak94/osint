import { Clock, Activity, Users, Scan } from "lucide-react";
import { Card, CardBody, CardHeader } from "@/shared/components/Card";
import { Badge } from "@/shared/components/Badge";
import { DataBadge } from "@/shared/components/DataBadge";
import { InvestigationRiskScore } from "../components/InvestigationRiskScore";
import { PivotRecommendationsPanel } from "../components/PivotRecommendationsPanel";

interface Props {
  investigationId: string;
  investigation: { seed_inputs?: { type: string; value: string }[] };
  stats: { scans: number; findings: number; successful: number; duration: string };
}

const STAT_ICONS = [Scan, Activity, Users, Clock] as const;

export function OverviewTab({ investigationId, investigation, stats }: Props) {
  const statItems = [
    { label: "Scans", value: stats.scans, icon: STAT_ICONS[0] },
    { label: "Findings", value: stats.findings, icon: STAT_ICONS[1] },
    { label: "Successful", value: stats.successful, icon: STAT_ICONS[2] },
    { label: "Duration", value: stats.duration, icon: STAT_ICONS[3] },
  ];

  return (
    <div className="space-y-4">
      <InvestigationRiskScore investigationId={investigationId} />

      <div className="grid grid-cols-4 gap-3">
        {statItems.map((s) => (
          <Card key={s.label}>
            <CardBody className="flex items-center gap-3 py-3">
              <s.icon className="h-4 w-4" style={{ color: "var(--brand-400)" }} />
              <div>
                <p className="text-lg font-bold font-mono" style={{ color: "var(--text-primary)" }}>{s.value}</p>
                <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>{s.label}</p>
              </div>
            </CardBody>
          </Card>
        ))}
      </div>

      <PivotRecommendationsPanel investigationId={investigationId} />

      <Card>
        <CardHeader><h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Seed Inputs</h3></CardHeader>
        <CardBody>
          <div className="flex flex-wrap gap-2">
            {(investigation.seed_inputs ?? []).map((s, i) => (
              <div key={i} className="flex items-center gap-1.5">
                <Badge variant="neutral" size="sm">{s.type}</Badge>
                <DataBadge value={s.value} type={s.type as "email" | "username" | "ip" | "domain" | "phone" | "nip" | "hash" | "default"} />
              </div>
            ))}
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
