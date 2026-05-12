import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, Download, RefreshCw, Loader2 } from "lucide-react";
import { Card, CardBody } from "@/shared/components/Card";
import { Badge } from "@/shared/components/Badge";
import { Button } from "@/shared/components/Button";
import { apiClient } from "@/shared/api/client";

interface IOCEntry {
  type: string;
  value: string;
  confidence: number;
  source_scanner: string;
  investigation_id: string;
  first_seen: string;
  last_seen: string;
  tags: string[];
  tlp: string;
}

interface IOCSourceStatus {
  source: string;
  last_polled: string | null;
  ioc_count: number;
  status: string;
}

interface IOCFeedStats {
  total_iocs: number;
  by_type: Record<string, number>;
  by_tlp: Record<string, number>;
  by_source: Record<string, number>;
  sources: IOCSourceStatus[];
}

const TLP_COLORS: Record<string, string> = {
  white: "var(--text-secondary)",
  green: "var(--success-500)",
  amber: "var(--warning-500)",
  red: "var(--danger-500)",
};

const TYPE_BADGE: Record<string, "info" | "warning" | "danger" | "neutral" | "brand"> = {
  ip: "danger",
  domain: "warning",
  url: "info",
  email: "neutral",
  hash: "brand",
};

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color = pct >= 80 ? "var(--danger-500)" : pct >= 50 ? "var(--warning-500)" : "var(--success-500)";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 rounded-full overflow-hidden" style={{ background: "var(--bg-overlay)" }}>
        <div className="h-1.5 rounded-full" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="text-[11px] font-mono" style={{ color }}>{pct}%</span>
    </div>
  );
}

export function IOCFeedPage() {
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [tlpFilter, setTlpFilter] = useState("all");
  const [minConfidence] = useState(0);

  const { data: iocs, isLoading: iocsLoading, refetch } = useQuery({
    queryKey: ["ioc-feed", typeFilter, tlpFilter, minConfidence],
    queryFn: async () => {
      const params: Record<string, string> = {};
      if (typeFilter !== "all") params.ioc_type = typeFilter;
      if (tlpFilter !== "all") params.tlp = tlpFilter;
      if (minConfidence > 0) params.min_confidence = String(minConfidence / 100);
      const res = await apiClient.get("/ioc-feed", { params });
      return res.data as { iocs: IOCEntry[]; total: number; generated_at: string };
    },
  });

  const { data: stats } = useQuery({
    queryKey: ["ioc-feed-stats"],
    queryFn: async () => {
      const res = await apiClient.get("/ioc-feed/stats");
      return res.data as IOCFeedStats;
    },
  });

  const filtered = (iocs?.iocs ?? []).filter(
    (ioc) =>
      !search ||
      ioc.value.toLowerCase().includes(search.toLowerCase()) ||
      ioc.tags.some((t) => t.toLowerCase().includes(search.toLowerCase())),
  );

  const handleExport = async (format: string) => {
    const res = await apiClient.get(`/ioc-feed?format=${format}`);
    const blob = new Blob([JSON.stringify(res.data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `ioc-feed.${format}`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>IOC Reputation Feed</h1>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Aggregated indicators from VirusTotal, OTX, ThreatFox, MalwareBazaar, and URLhaus
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="ghost" size="sm" leftIcon={<RefreshCw className="h-3.5 w-3.5" />} onClick={() => refetch()}>
            Refresh
          </Button>
          <Button size="sm" leftIcon={<Download className="h-3.5 w-3.5" />} onClick={() => handleExport("json")}>
            Export JSON
          </Button>
        </div>
      </div>

      {/* Source status cards */}
      {stats && (
        <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {stats.sources.map((src) => (
            <Card key={src.source}>
              <CardBody className="p-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-medium truncate" style={{ color: "var(--text-primary)" }}>{src.source}</span>
                  <Badge variant={src.status === "active" ? "success" : "danger"} size="sm" dot>
                    {src.status}
                  </Badge>
                </div>
                <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                  {src.last_polled
                    ? new Date(src.last_polled).toLocaleTimeString()
                    : "Never polled"}
                </p>
              </CardBody>
            </Card>
          ))}
        </div>
      )}

      {/* Stats overview */}
      {stats && (
        <div className="grid gap-3 sm:grid-cols-4">
          <Card>
            <CardBody className="p-3 text-center">
              <p className="text-2xl font-bold font-mono" style={{ color: "var(--text-primary)" }}>{stats.total_iocs}</p>
              <p className="text-xs mt-0.5" style={{ color: "var(--text-tertiary)" }}>Total IOCs</p>
            </CardBody>
          </Card>
          {Object.entries(stats.by_type).map(([type, count]) => (
            <Card key={type}>
              <CardBody className="p-3 text-center">
                <p className="text-2xl font-bold font-mono" style={{ color: "var(--text-primary)" }}>{count}</p>
                <p className="text-xs mt-0.5 capitalize" style={{ color: "var(--text-tertiary)" }}>{type}</p>
              </CardBody>
            </Card>
          ))}
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex-1 relative">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 pointer-events-none" style={{ color: "var(--text-tertiary)" }} />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search IOC value or tag..."
            className="w-full rounded-md border pl-8 pr-3 py-2 text-sm"
            style={{ background: "var(--bg-elevated)", borderColor: "var(--border-default)", color: "var(--text-primary)" }}
          />
        </div>
        {["all", "ip", "domain", "url", "email", "hash"].map((t) => (
          <button
            key={t}
            onClick={() => setTypeFilter(t)}
            className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${typeFilter === t ? "bg-brand-900 text-brand-400" : "text-text-secondary hover:bg-bg-overlay"}`}
          >
            {t === "all" ? "All Types" : t.toUpperCase()}
          </button>
        ))}
        {["all", "white", "green", "amber", "red"].map((t) => (
          <button
            key={t}
            onClick={() => setTlpFilter(t)}
            className={`rounded-full px-2.5 py-0.5 text-[11px] font-medium transition-colors border ${tlpFilter === t ? "border-brand-500 text-brand-400 bg-brand-950" : "border-transparent text-text-secondary hover:bg-bg-overlay"}`}
          >
            TLP:{t.toUpperCase()}
          </button>
        ))}
      </div>

      {/* IOC table */}
      <Card>
        <CardBody className="p-0">
          {iocsLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin" style={{ color: "var(--brand-500)" }} />
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b text-left text-xs font-medium" style={{ borderColor: "var(--border-subtle)", color: "var(--text-tertiary)" }}>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3">Indicator</th>
                  <th className="px-4 py-3">Source</th>
                  <th className="px-4 py-3">Confidence</th>
                  <th className="px-4 py-3">TLP</th>
                  <th className="px-4 py-3">Tags</th>
                  <th className="px-4 py-3">Last Seen</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((ioc, i) => (
                  <tr
                    key={i}
                    className="border-b transition-colors hover:bg-bg-overlay"
                    style={{ borderColor: "var(--border-subtle)" }}
                  >
                    <td className="px-4 py-3">
                      <Badge variant={TYPE_BADGE[ioc.type] ?? "neutral"} size="sm">{ioc.type}</Badge>
                    </td>
                    <td className="px-4 py-3">
                      <span className="font-mono text-sm" style={{ color: "var(--text-primary)" }}>{ioc.value}</span>
                    </td>
                    <td className="px-4 py-3 text-xs" style={{ color: "var(--text-secondary)" }}>{ioc.source_scanner}</td>
                    <td className="px-4 py-3"><ConfidenceBar value={ioc.confidence} /></td>
                    <td className="px-4 py-3">
                      <span className="text-xs font-semibold" style={{ color: TLP_COLORS[ioc.tlp] ?? "var(--text-secondary)" }}>
                        TLP:{ioc.tlp.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-1">
                        {ioc.tags.map((t) => (
                          <Badge key={t} variant="neutral" size="sm">{t}</Badge>
                        ))}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-xs" style={{ color: "var(--text-tertiary)" }}>
                      {new Date(ioc.last_seen).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
                {filtered.length === 0 && (
                  <tr>
                    <td colSpan={7} className="px-4 py-12 text-center text-sm" style={{ color: "var(--text-tertiary)" }}>
                      No IOCs match the current filters
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
