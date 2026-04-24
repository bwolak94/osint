import { useState } from "react";
import { Brain, Sparkles, Copy, Check, ChevronDown, ChevronUp } from "lucide-react";
import { useGenerateDebrief } from "./hooks";
import type { DebriefSection } from "./types";
import { Badge } from "@/shared/components/Badge";
import { Button } from "@/shared/components/Button";
import { Input } from "@/shared/components/Input";
import { Card, CardBody, CardHeader } from "@/shared/components/Card";

const severityVariant: Record<string, "danger" | "warning" | "info" | "neutral"> = {
  critical: "danger",
  high: "danger",
  medium: "warning",
  low: "neutral",
};

function FindingCard({ finding }: { finding: DebriefSection }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div
      className="rounded-lg border"
      style={{ background: "var(--bg-surface)", borderColor: "var(--border-default)" }}
    >
      <button
        className="w-full flex items-center justify-between p-4 text-left"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-2">
          {finding.severity && (
            <Badge variant={(severityVariant[finding.severity] ?? "neutral") as "success" | "warning" | "danger" | "info" | "neutral" | "brand"} size="sm">
              {finding.severity}
            </Badge>
          )}
          <span className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
            {finding.title}
          </span>
        </div>
        {expanded ? (
          <ChevronUp
            className="h-4 w-4 shrink-0"
            style={{ color: "var(--text-tertiary)" }}
          />
        ) : (
          <ChevronDown
            className="h-4 w-4 shrink-0"
            style={{ color: "var(--text-tertiary)" }}
          />
        )}
      </button>
      {expanded && (
        <div
          className="border-t px-4 pb-4 pt-3 text-sm"
          style={{ borderColor: "var(--border-subtle)", color: "var(--text-secondary)" }}
        >
          {finding.content}
        </div>
      )}
    </div>
  );
}

export function AiDebriefPage() {
  const [engagementId, setEngagementId] = useState("");
  const [scope, setScope] = useState("");
  const [copied, setCopied] = useState(false);
  const generate = useGenerateDebrief();

  const copyAll = () => {
    if (!generate.data) return;
    const text = `PENTEST DEBRIEF - ${generate.data.engagement_id}\n\nEXECUTIVE SUMMARY\n${
      generate.data.executive_summary
    }\n\nATTACK NARRATIVE\n${
      generate.data.attack_narrative
    }\n\nKEY FINDINGS\n${(generate.data.key_findings ?? [])
      .map((f) => `[${f.severity?.toUpperCase()}] ${f.title}\n${f.content}`)
      .join("\n\n")}`;
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <Brain className="h-6 w-6" style={{ color: "var(--brand-500)" }} />
        <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
          AI Debrief Generator
        </h1>
      </div>

      <Card>
        <CardBody>
          <div className="flex gap-3 flex-wrap">
            <div className="flex-1 min-w-48">
              <Input
                placeholder="Engagement ID (e.g., ENG-2024-001)..."
                value={engagementId}
                onChange={(e) => setEngagementId(e.target.value)}
              />
            </div>
            <div className="flex-1 min-w-48">
              <Input
                placeholder="Scope description (optional)..."
                value={scope}
                onChange={(e) => setScope(e.target.value)}
              />
            </div>
            <Button
              onClick={() => generate.mutate({ engagementId, scope })}
              disabled={!engagementId.trim() || generate.isPending}
              leftIcon={<Sparkles className="h-4 w-4" />}
            >
              {generate.isPending ? "Generating..." : "Generate Debrief"}
            </Button>
          </div>
        </CardBody>
      </Card>

      {generate.data && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm" style={{ color: "var(--text-tertiary)" }}>
              Generated for:{" "}
              <strong style={{ color: "var(--text-primary)" }}>
                {generate.data.engagement_id}
              </strong>
            </p>
            <Button
              variant="ghost"
              size="sm"
              leftIcon={
                copied ? (
                  <Check className="h-4 w-4" />
                ) : (
                  <Copy className="h-4 w-4" />
                )
              }
              onClick={copyAll}
            >
              {copied ? "Copied!" : "Copy All"}
            </Button>
          </div>

          <div className="grid gap-3 sm:grid-cols-4">
            {[
              {
                label: "Critical",
                value: generate.data.metrics.critical,
                color: "var(--danger-400)",
              },
              {
                label: "High",
                value: generate.data.metrics.high,
                color: "var(--warning-400)",
              },
              {
                label: "Total Findings",
                value: generate.data.metrics.total,
                color: "var(--text-primary)",
              },
              {
                label: "Avg CVSS",
                value: generate.data.metrics.avg_cvss,
                color: "var(--brand-400)",
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
                <p className="text-2xl font-bold" style={{ color }}>
                  {value}
                </p>
                <p className="text-xs mt-1" style={{ color: "var(--text-tertiary)" }}>
                  {label}
                </p>
              </div>
            ))}
          </div>

          <Card>
            <CardHeader>
              <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                Executive Summary
              </h3>
            </CardHeader>
            <CardBody>
              <p
                className="text-sm leading-relaxed"
                style={{ color: "var(--text-secondary)" }}
              >
                {generate.data.executive_summary}
              </p>
            </CardBody>
          </Card>

          <Card>
            <CardHeader>
              <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                Attack Narrative
              </h3>
            </CardHeader>
            <CardBody>
              <p
                className="text-sm leading-relaxed"
                style={{ color: "var(--text-secondary)" }}
              >
                {generate.data.attack_narrative}
              </p>
            </CardBody>
          </Card>

          <div>
            <h3
              className="text-sm font-semibold mb-3"
              style={{ color: "var(--text-primary)" }}
            >
              Key Findings
            </h3>
            <div className="space-y-2">
              {(generate.data.key_findings ?? []).map((f, i) => (
                <FindingCard key={i} finding={f} />
              ))}
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <h3
                  className="text-sm font-semibold"
                  style={{ color: "var(--text-primary)" }}
                >
                  Recommended Priorities
                </h3>
              </CardHeader>
              <CardBody>
                <ul className="space-y-2">
                  {(generate.data.recommended_priorities ?? []).map((r, i) => (
                    <li key={i} className="text-sm" style={{ color: "var(--text-secondary)" }}>
                      {r}
                    </li>
                  ))}
                </ul>
              </CardBody>
            </Card>
            <Card>
              <CardHeader>
                <h3
                  className="text-sm font-semibold"
                  style={{ color: "var(--text-primary)" }}
                >
                  Defensive Gaps
                </h3>
              </CardHeader>
              <CardBody>
                <ul className="space-y-1">
                  {(generate.data.defensive_gaps ?? []).map((g, i) => (
                    <li key={i} className="text-sm" style={{ color: "var(--text-secondary)" }}>
                      · {g}
                    </li>
                  ))}
                </ul>
              </CardBody>
            </Card>
          </div>
        </div>
      )}

      {!generate.data && !generate.isPending && (
        <div
          className="rounded-xl border py-16 text-center"
          style={{ borderColor: "var(--border-subtle)" }}
        >
          <Brain
            className="mx-auto h-10 w-10 mb-3"
            style={{ color: "var(--text-tertiary)" }}
          />
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Generate AI-powered debrief documents from engagement data
          </p>
        </div>
      )}
    </div>
  );
}
