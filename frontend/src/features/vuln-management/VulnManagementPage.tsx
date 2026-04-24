import { useState } from "react";
import { ShieldAlert, Filter } from "lucide-react";
import { useVulnerabilities, useUpdateVuln } from "./hooks";
import type { Vulnerability } from "./types";
import { Badge } from "@/shared/components/Badge";
import { Card, CardBody } from "@/shared/components/Card";

const severityVariant: Record<string, "danger" | "warning" | "info" | "neutral"> = {
  critical: "danger",
  high: "danger",
  medium: "warning",
  low: "neutral",
};

const cvssColor = (score: number): string =>
  score >= 9
    ? "var(--danger-400)"
    : score >= 7
      ? "var(--warning-400)"
      : score >= 4
        ? "var(--brand-400)"
        : "var(--success-400)";

interface VulnRowProps {
  vuln: Vulnerability;
}

function VulnRow({ vuln }: VulnRowProps) {
  const update = useUpdateVuln();
  const statuses = ["open", "in_progress", "remediated", "accepted_risk"];

  return (
    <tr
      className="border-b transition-colors hover:bg-bg-overlay"
      style={{ borderColor: "var(--border-subtle)" }}
    >
      <td className="px-4 py-3">
        <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
          {vuln.title}
        </p>
        {vuln.cve_id && (
          <p className="text-xs font-mono" style={{ color: "var(--brand-400)" }}>
            {vuln.cve_id}
          </p>
        )}
      </td>
      <td className="px-4 py-3">
        <Badge variant={(severityVariant[vuln.severity] ?? "neutral") as "success" | "warning" | "danger" | "info" | "neutral" | "brand"} size="sm">
          {vuln.severity}
        </Badge>
      </td>
      <td className="px-4 py-3">
        <span className="text-sm font-bold" style={{ color: cvssColor(vuln.cvss_score) }}>
          {vuln.cvss_score}
        </span>
      </td>
      <td className="px-4 py-3">
        <select
          value={vuln.status}
          onChange={(e) => update.mutate({ id: vuln.id, status: e.target.value })}
          className="rounded border px-2 py-1 text-xs"
          style={{
            background: "var(--bg-surface)",
            borderColor: "var(--border-default)",
            color: "var(--text-primary)",
          }}
        >
          {statuses.map((s) => (
            <option key={s} value={s}>
              {s.replace("_", " ")}
            </option>
          ))}
        </select>
      </td>
      <td className="px-4 py-3 text-xs" style={{ color: "var(--text-tertiary)" }}>
        {(vuln.affected_assets ?? []).slice(0, 2).join(", ")}
        {(vuln.affected_assets?.length ?? 0) > 2
          ? ` +${(vuln.affected_assets?.length ?? 0) - 2}`
          : ""}
      </td>
      <td
        className="px-4 py-3 text-xs"
        style={{
          color:
            vuln.due_date && new Date(vuln.due_date) < new Date()
              ? "var(--danger-400)"
              : "var(--text-tertiary)",
        }}
      >
        {vuln.due_date ? new Date(vuln.due_date).toLocaleDateString() : "—"}
      </td>
    </tr>
  );
}

export function VulnManagementPage() {
  const [severityFilter, setSeverityFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const { data: vulns = [], isLoading } = useVulnerabilities(
    severityFilter || undefined,
    statusFilter || undefined,
  );

  const counts = {
    critical: vulns.filter((v) => v.severity === "critical").length,
    high: vulns.filter((v) => v.severity === "high").length,
    open: vulns.filter((v) => v.status === "open").length,
    remediated: vulns.filter((v) => v.status === "remediated").length,
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <ShieldAlert className="h-6 w-6" style={{ color: "var(--danger-400)" }} />
        <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
          Vulnerability Management
        </h1>
        <Badge variant="neutral" size="sm">
          {vulns.length} total
        </Badge>
      </div>

      <div className="grid gap-3 sm:grid-cols-4">
        {[
          { label: "Critical", value: counts.critical, color: "var(--danger-400)" },
          { label: "High", value: counts.high, color: "var(--warning-400)" },
          { label: "Open", value: counts.open, color: "var(--danger-400)" },
          { label: "Remediated", value: counts.remediated, color: "var(--success-400)" },
        ].map(({ label, value, color }) => (
          <div
            key={label}
            className="rounded-xl border p-4 text-center"
            style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}
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

      <div className="flex gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4" style={{ color: "var(--text-tertiary)" }} />
          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            className="rounded-md border px-3 py-1.5 text-sm"
            style={{
              background: "var(--bg-surface)",
              borderColor: "var(--border-default)",
              color: "var(--text-primary)",
            }}
          >
            <option value="">All Severities</option>
            {["critical", "high", "medium", "low"].map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-md border px-3 py-1.5 text-sm"
            style={{
              background: "var(--bg-surface)",
              borderColor: "var(--border-default)",
              color: "var(--text-primary)",
            }}
          >
            <option value="">All Statuses</option>
            {["open", "in_progress", "remediated", "accepted_risk"].map((s) => (
              <option key={s} value={s}>
                {s.replace("_", " ")}
              </option>
            ))}
          </select>
        </div>
      </div>

      <Card>
        <CardBody className="p-0">
          <table className="w-full">
            <thead>
              <tr
                className="border-b text-left text-xs font-medium"
                style={{ borderColor: "var(--border-subtle)", color: "var(--text-tertiary)" }}
              >
                <th className="px-4 py-3">Title / CVE</th>
                <th className="px-4 py-3">Severity</th>
                <th className="px-4 py-3">CVSS</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Affected Assets</th>
                <th className="px-4 py-3">Due Date</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td
                    colSpan={6}
                    className="px-4 py-8 text-center text-sm"
                    style={{ color: "var(--text-tertiary)" }}
                  >
                    Loading...
                  </td>
                </tr>
              ) : (
                vulns.map((v) => <VulnRow key={v.id} vuln={v} />)
              )}
            </tbody>
          </table>
        </CardBody>
      </Card>
    </div>
  );
}
