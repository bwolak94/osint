import { useState } from "react";
import { Timer, AlertTriangle, AlertOctagon } from "lucide-react";
import { useSlaMetrics } from "./hooks";
import type { SlaItem } from "./types";
import { Badge } from "@/shared/components/Badge";
import { Card, CardBody } from "@/shared/components/Card";

const statusVariant: Record<string, "neutral" | "info" | "warning" | "danger"> = {
  on_track: "neutral",
  at_risk: "warning",
  breached: "danger",
  completed: "neutral",
};

const severityVariant: Record<string, "danger" | "warning" | "info" | "neutral"> = {
  critical: "danger",
  high: "danger",
  medium: "warning",
  low: "neutral",
};

const escalationLabels = ["", "Manager", "Director", "Executive"];

function SlaRow({ item }: { item: SlaItem }) {
  return (
    <div
      className={`flex items-center gap-4 px-4 py-3 border-b last:border-0 ${
        item.status === "breached"
          ? "bg-danger-900/20"
          : item.status === "at_risk"
          ? "bg-warning-900/10"
          : ""
      }`}
      style={{ borderColor: "var(--border-subtle)" }}
    >
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          {item.escalated && (
            <AlertOctagon
              className="h-3.5 w-3.5 shrink-0"
              style={{ color: "var(--danger-400)" }}
            />
          )}
          <p className="text-sm truncate" style={{ color: "var(--text-primary)" }}>
            {item.title}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={(severityVariant[item.severity] ?? "neutral") as "success" | "warning" | "danger" | "info" | "neutral" | "brand"} size="sm">
            {item.severity}
          </Badge>
          <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>
            {item.type} · {item.engagement_id}
          </span>
          {item.escalated && (
            <Badge variant="danger" size="sm">
              Escalated to {escalationLabels[item.escalation_level]}
            </Badge>
          )}
        </div>
      </div>
      <div className="text-right shrink-0">
        <Badge variant={(statusVariant[item.status] ?? "neutral") as "success" | "warning" | "danger" | "info" | "neutral" | "brand"} size="sm">
          {item.status.replace("_", " ")}
        </Badge>
        <p
          className="text-xs mt-1"
          style={{
            color:
              item.days_remaining < 0
                ? "var(--danger-400)"
                : item.days_remaining < 5
                ? "var(--warning-400)"
                : "var(--text-tertiary)",
          }}
        >
          {item.days_remaining < 0
            ? `${Math.abs(item.days_remaining)}d overdue`
            : item.status === "completed"
            ? "Done"
            : `${item.days_remaining}d left`}
        </p>
      </div>
    </div>
  );
}

export function SlaPage() {
  const { data } = useSlaMetrics();
  const [filter, setFilter] = useState("all");

  const filtered =
    data?.items.filter((i) => filter === "all" || i.status === filter) ?? [];

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <Timer className="h-6 w-6" style={{ color: "var(--brand-500)" }} />
        <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
          SLA Dashboard & Escalations
        </h1>
      </div>

      {data && (
        <>
          <div className="grid gap-3 sm:grid-cols-4">
            {[
              { label: "On Track", value: data.on_track, color: "var(--success-400)" },
              { label: "At Risk", value: data.at_risk, color: "var(--warning-400)" },
              { label: "Breached", value: data.breached, color: "var(--danger-400)" },
              {
                label: "Breach Rate",
                value: `${data.breach_rate}%`,
                color:
                  data.breach_rate > 20 ? "var(--danger-400)" : "var(--text-primary)",
              },
            ].map(({ label, value, color }) => (
              <div
                key={label}
                className="rounded-xl border p-4 text-center"
                style={{
                  background: "var(--bg-surface)",
                  borderColor: "var(--border-subtle)",
                }}
              >
                <p className="text-3xl font-bold" style={{ color }}>
                  {value}
                </p>
                <p className="text-xs mt-1" style={{ color: "var(--text-tertiary)" }}>
                  {label}
                </p>
              </div>
            ))}
          </div>

          {data.breached > 0 && (
            <div
              className="flex items-center gap-2 rounded-lg border px-4 py-3"
              style={{
                background: "var(--danger-900)",
                borderColor: "var(--danger-500)",
              }}
            >
              <AlertTriangle
                className="h-4 w-4 shrink-0"
                style={{ color: "var(--danger-400)" }}
              />
              <span
                className="text-sm font-medium"
                style={{ color: "var(--danger-400)" }}
              >
                {data.breached} SLA{data.breached > 1 ? "s" : ""} breached — escalation
                may be required
              </span>
            </div>
          )}

          <div className="flex gap-2 flex-wrap">
            {["all", "breached", "at_risk", "on_track", "completed"].map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`rounded-md px-3 py-1.5 text-xs font-medium transition-all ${
                  filter === f
                    ? "bg-brand-900 text-brand-400"
                    : "text-text-secondary hover:bg-bg-overlay"
                }`}
              >
                {f.replace("_", " ")}
              </button>
            ))}
          </div>

          <Card>
            <CardBody className="p-0">
              {filtered
                .sort((a, b) => a.days_remaining - b.days_remaining)
                .map((i) => (
                  <SlaRow key={i.id} item={i} />
                ))}
            </CardBody>
          </Card>
        </>
      )}
    </div>
  );
}
