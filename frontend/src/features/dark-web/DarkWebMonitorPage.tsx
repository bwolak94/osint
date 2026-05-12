import { useState } from "react";
import { AlertTriangle, Search, Shield, Eye, Clock } from "lucide-react";
import { useDarkWebScan } from "./hooks";
import type { DarkWebMention } from "./types";
import { Badge } from "@/shared/components/Badge";
import { Button } from "@/shared/components/Button";
import { Input } from "@/shared/components/Input";
import { Card, CardBody } from "@/shared/components/Card";

const riskVariant: Record<string, "danger" | "warning" | "info" | "neutral"> =
  {
    critical: "danger",
    high: "danger",
    medium: "warning",
    low: "info",
  };

const sourceLabel: Record<string, string> = {
  tor_forum: "Tor Forum",
  paste_site: "Paste Site",
  marketplace: "Marketplace",
  telegram_channel: "Telegram",
};

const riskOrder: Record<string, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
};

function MentionCard({ mention }: { mention: DarkWebMention }) {
  return (
    <div
      className="rounded-lg border p-4"
      style={{
        background: "var(--bg-surface)",
        borderColor:
          mention.risk_level === "critical"
            ? "var(--danger-500)"
            : "var(--border-default)",
      }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-2">
            <Badge variant={(riskVariant[mention.risk_level] ?? "neutral") as "success" | "warning" | "danger" | "info" | "neutral" | "brand"} size="sm">
              {mention.risk_level.toUpperCase()}
            </Badge>
            <Badge variant="neutral" size="sm">
              {sourceLabel[mention.source] ?? mention.source}
            </Badge>
          </div>
          <p
            className="text-sm font-medium mb-1"
            style={{ color: "var(--text-primary)" }}
          >
            {mention.title}
          </p>
          <p
            className="text-xs font-mono"
            style={{ color: "var(--text-secondary)" }}
          >
            {mention.snippet}
          </p>
          <div className="flex items-center gap-3 mt-2">
            <span
              className="flex items-center gap-1 text-xs"
              style={{ color: "var(--text-tertiary)" }}
            >
              <Clock className="h-3 w-3" />
              {new Date(mention.first_seen).toLocaleDateString()}
            </span>
            <span
              className="font-mono text-xs"
              style={{ color: "var(--text-tertiary)" }}
            >
              #{mention.url_hash.slice(0, 8)}
            </span>
          </div>
        </div>
      </div>
      {mention.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-2">
          {mention.tags.map((t) => (
            <Badge key={t} variant="neutral" size="sm">
              {t}
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}

export function DarkWebMonitorPage() {
  const [query, setQuery] = useState("");
  const [daysBack, setDaysBack] = useState(30);
  const scan = useDarkWebScan();

  const handleScan = () => {
    if (query.trim()) scan.mutate({ query: query.trim(), daysBack });
  };

  const sortedMentions = scan.data?.mentions
    .slice()
    .sort(
      (a, b) =>
        (riskOrder[a.risk_level] ?? 4) - (riskOrder[b.risk_level] ?? 4)
    );

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <Eye className="h-6 w-6" style={{ color: "var(--danger-400)" }} />
        <h1
          className="text-xl font-semibold"
          style={{ color: "var(--text-primary)" }}
        >
          Dark Web Monitor
        </h1>
      </div>

      <Card>
        <CardBody>
          <div className="flex gap-3 flex-wrap">
            <div className="flex-1">
              <Input
                placeholder="Email, domain, username, company name..."
                prefixIcon={<Search className="h-4 w-4" />}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleScan()}
              />
            </div>
            <select
              value={daysBack}
              onChange={(e) => setDaysBack(Number(e.target.value))}
              className="rounded-md border px-3 py-2 text-sm"
              style={{
                background: "var(--bg-surface)",
                borderColor: "var(--border-default)",
                color: "var(--text-primary)",
              }}
            >
              <option value={7}>Last 7 days</option>
              <option value={30}>Last 30 days</option>
              <option value={90}>Last 90 days</option>
            </select>
            <Button
              onClick={handleScan}
              disabled={!query.trim() || scan.isPending}
              leftIcon={<Shield className="h-4 w-4" />}
            >
              {scan.isPending ? "Scanning..." : "Scan Dark Web"}
            </Button>
          </div>
        </CardBody>
      </Card>

      {scan.data && (
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-4">
            {[
              {
                label: "Total",
                value: scan.data.total_mentions,
                color: "var(--text-primary)",
              },
              {
                label: "Critical",
                value: scan.data.critical_count,
                color: "var(--danger-400)",
              },
              {
                label: "High",
                value: scan.data.high_count,
                color: "var(--warning-400)",
              },
              {
                label: "Medium",
                value: scan.data.medium_count,
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
                <p className="text-3xl font-bold" style={{ color }}>
                  {value}
                </p>
                <p
                  className="text-xs mt-1"
                  style={{ color: "var(--text-tertiary)" }}
                >
                  {label}
                </p>
              </div>
            ))}
          </div>

          {scan.data.critical_count > 0 && (
            <div
              className="flex items-center gap-2 rounded-lg border px-4 py-3"
              style={{
                background: "var(--danger-900)",
                borderColor: "var(--danger-500)",
              }}
            >
              <AlertTriangle
                className="h-4 w-4 shrink-0"
                style={{ color: "var(--danger-500)" }}
              />
              <span
                className="text-sm font-medium"
                style={{ color: "var(--danger-400)" }}
              >
                {scan.data.critical_count} critical finding
                {scan.data.critical_count !== 1 ? "s" : ""} require immediate
                attention
              </span>
            </div>
          )}

          <div className="space-y-3">
            {sortedMentions?.map((m) => (
              <MentionCard key={m.id} mention={m} />
            ))}
          </div>
        </div>
      )}

      {!scan.data && !scan.isPending && (
        <div
          className="rounded-xl border py-16 text-center"
          style={{ borderColor: "var(--border-subtle)" }}
        >
          <Eye
            className="mx-auto h-10 w-10 mb-3"
            style={{ color: "var(--text-tertiary)" }}
          />
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Enter a query to scan dark web sources for mentions
          </p>
        </div>
      )}
    </div>
  );
}
