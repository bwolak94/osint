import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { GitMerge, Search, Loader2, Network, Link } from "lucide-react";
import { Card, CardBody, CardHeader } from "@/shared/components/Card";
import { Badge } from "@/shared/components/Badge";
import { Button } from "@/shared/components/Button";
import { apiClient } from "@/shared/api/client";
import { useInvestigations } from "@/features/investigations/hooks";

interface SharedEntity {
  entity_type: string;
  entity_value: string;
  investigation_ids: string[];
  investigation_titles: string[];
  occurrence_count: number;
  max_confidence: number;
  first_seen: string;
  last_seen: string;
  tags: string[];
}

interface CrossEdge {
  source_investigation_id: string;
  target_investigation_id: string;
  shared_entity_count: number;
  shared_entities: string[];
  link_strength: number;
}

interface MultiGraphResponse {
  investigation_ids: string[];
  shared_entities: SharedEntity[];
  cross_investigation_edges: CrossEdge[];
  total_shared: number;
  generated_at: string;
}

const TYPE_COLORS: Record<string, string> = {
  email: "var(--success-500)",
  domain: "var(--brand-400)",
  ip_address: "var(--danger-500)",
  username: "var(--warning-500)",
  phone: "var(--info-500)",
};

function StrengthBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color = pct >= 60 ? "var(--danger-500)" : pct >= 30 ? "var(--warning-500)" : "var(--brand-400)";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-20 rounded-full overflow-hidden" style={{ background: "var(--bg-overlay)" }}>
        <div className="h-1.5 rounded-full" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="text-[11px] font-mono" style={{ color }}>{pct}%</span>
    </div>
  );
}

export function MultiInvestigationGraphPage() {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [minOccurrences, setMinOccurrences] = useState(2);

  const { data: invData, isLoading: invLoading } = useInvestigations();
  const allInvestigations = invData?.items ?? [];

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["multi-graph", [...selected].sort(), minOccurrences],
    queryFn: async () => {
      const params = new URLSearchParams();
      for (const id of selected) params.append("investigation_ids", id);
      params.set("min_occurrences", String(minOccurrences));
      const res = await apiClient.post<MultiGraphResponse>(`/investigations/multi-graph?${params}`);
      return res.data;
    },
    enabled: selected.size >= 2,
  });

  const filtered = useMemo(() => {
    if (!data) return [];
    return data.shared_entities.filter((e) => {
      const matchSearch = !search || e.entity_value.toLowerCase().includes(search.toLowerCase());
      const matchType = typeFilter === "all" || e.entity_type === typeFilter;
      return matchSearch && matchType;
    });
  }, [data, search, typeFilter]);

  const entityTypes = useMemo(
    () => [...new Set((data?.shared_entities ?? []).map((e) => e.entity_type))],
    [data],
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
          Multi-Investigation Link Analysis
        </h1>
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
          Find shared entities and connection patterns across multiple investigations.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        {/* Investigation selector */}
        <div className="lg:col-span-1 space-y-3">
          <Card>
            <CardHeader>
              <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                Select Investigations ({selected.size}/10)
              </p>
              <p className="text-xs mt-0.5" style={{ color: "var(--text-tertiary)" }}>
                Choose ≥2 to find shared entities
              </p>
            </CardHeader>
            <CardBody className="pt-0 space-y-1 max-h-96 overflow-y-auto">
              {invLoading ? (
                <Loader2 className="h-5 w-5 animate-spin mx-auto my-4" style={{ color: "var(--brand-500)" }} />
              ) : (
                allInvestigations.map((inv) => (
                  <button
                    key={inv.id}
                    onClick={() => toggleSelect(inv.id)}
                    className={`w-full rounded-md px-3 py-2 text-left text-xs transition-colors ${selected.has(inv.id) ? "bg-brand-900 text-brand-300" : "hover:bg-bg-overlay text-text-secondary"}`}
                  >
                    <p className="font-medium truncate">{inv.title}</p>
                    <p className="text-[10px] opacity-60">{inv.status}</p>
                  </button>
                ))
              )}
            </CardBody>
          </Card>

          <div className="flex items-center gap-2">
            <label className="text-xs" style={{ color: "var(--text-secondary)" }}>
              Min shared occurrences: {minOccurrences}
            </label>
            <input
              type="range" min={2} max={10} step={1}
              value={minOccurrences}
              onChange={(e) => setMinOccurrences(Number(e.target.value))}
              className="flex-1"
            />
          </div>

          <Button
            className="w-full"
            leftIcon={<Network className="h-4 w-4" />}
            disabled={selected.size < 2}
            loading={isLoading}
            onClick={() => refetch()}
          >
            Analyze Links
          </Button>
        </div>

        {/* Results */}
        <div className="lg:col-span-2 space-y-4">
          {/* Cross-investigation edges */}
          {data && data.cross_investigation_edges.length > 0 && (
            <Card>
              <CardHeader>
                <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                  Investigation Connections ({data.cross_investigation_edges.length})
                </p>
              </CardHeader>
              <CardBody className="pt-0 space-y-2">
                {data.cross_investigation_edges.map((edge, i) => {
                  const srcTitle = allInvestigations.find((inv) => inv.id === edge.source_investigation_id)?.title ?? edge.source_investigation_id;
                  const tgtTitle = allInvestigations.find((inv) => inv.id === edge.target_investigation_id)?.title ?? edge.target_investigation_id;
                  return (
                    <div key={i} className="flex items-center gap-3 rounded-md px-3 py-2" style={{ background: "var(--bg-elevated)" }}>
                      <span className="max-w-[120px] truncate text-xs font-medium" style={{ color: "var(--text-primary)" }}>{srcTitle}</span>
                      <div className="flex flex-1 items-center gap-1">
                        <div className="flex-1 h-px" style={{ background: "var(--border-subtle)" }} />
                        <Link className="h-3 w-3 shrink-0" style={{ color: "var(--brand-400)" }} />
                        <div className="flex-1 h-px" style={{ background: "var(--border-subtle)" }} />
                      </div>
                      <span className="max-w-[120px] truncate text-xs font-medium" style={{ color: "var(--text-primary)" }}>{tgtTitle}</span>
                      <div className="shrink-0">
                        <StrengthBar value={edge.link_strength} />
                        <p className="text-[10px] mt-0.5" style={{ color: "var(--text-tertiary)" }}>
                          {edge.shared_entity_count} shared
                        </p>
                      </div>
                    </div>
                  );
                })}
              </CardBody>
            </Card>
          )}

          {/* Shared entities table */}
          <Card>
            <CardHeader className="flex items-center justify-between">
              <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                Shared Entities {data ? `(${data.total_shared})` : ""}
              </p>
            </CardHeader>
            <CardBody className="pt-0 space-y-3">
              {/* Filters */}
              <div className="flex flex-wrap gap-2">
                <div className="relative">
                  <Search className="absolute left-2.5 top-1/2 h-3 w-3 -translate-y-1/2 pointer-events-none" style={{ color: "var(--text-tertiary)" }} />
                  <input
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Search value…"
                    className="rounded-md border pl-7 pr-3 py-1.5 text-xs w-48"
                    style={{ background: "var(--bg-elevated)", borderColor: "var(--border-default)", color: "var(--text-primary)" }}
                  />
                </div>
                {["all", ...entityTypes].map((t) => (
                  <button
                    key={t}
                    onClick={() => setTypeFilter(t)}
                    className={`rounded-full px-2.5 py-0.5 text-[11px] font-medium border transition-colors ${typeFilter === t ? "border-brand-500 text-brand-400 bg-brand-950" : "border-transparent text-text-secondary hover:bg-bg-overlay"}`}
                  >
                    {t === "all" ? "All" : t}
                  </button>
                ))}
              </div>

              {/* No results states */}
              {selected.size < 2 && !data && (
                <div className="py-10 text-center">
                  <GitMerge className="mx-auto h-8 w-8 mb-3" style={{ color: "var(--text-tertiary)" }} />
                  <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
                    Select 2 or more investigations to find shared entities
                  </p>
                </div>
              )}

              {isLoading && (
                <div className="flex items-center justify-center py-10">
                  <Loader2 className="h-6 w-6 animate-spin" style={{ color: "var(--brand-500)" }} />
                </div>
              )}

              {data && filtered.length === 0 && !isLoading && (
                <p className="py-8 text-center text-sm" style={{ color: "var(--text-tertiary)" }}>
                  No shared entities found for current filters
                </p>
              )}

              {/* Entity rows */}
              {filtered.map((entity, i) => (
                <div
                  key={i}
                  className="flex items-center gap-3 rounded-md px-3 py-2"
                  style={{ background: "var(--bg-elevated)" }}
                >
                  <div
                    className="h-2 w-2 rounded-full shrink-0"
                    style={{ background: TYPE_COLORS[entity.entity_type] ?? "var(--text-tertiary)" }}
                  />
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-mono font-medium truncate" style={{ color: "var(--text-primary)" }}>
                      {entity.entity_value}
                    </p>
                    <p className="text-[10px] truncate" style={{ color: "var(--text-tertiary)" }}>
                      {entity.investigation_titles.join(" · ")}
                    </p>
                  </div>
                  <Badge variant="neutral" size="sm">{entity.entity_type}</Badge>
                  <Badge
                    variant={entity.occurrence_count >= 3 ? "danger" : "warning"}
                    size="sm"
                  >
                    ×{entity.occurrence_count}
                  </Badge>
                  <span className="text-[11px] font-mono" style={{ color: "var(--text-tertiary)" }}>
                    {Math.round(entity.max_confidence * 100)}%
                  </span>
                </div>
              ))}
            </CardBody>
          </Card>
        </div>
      </div>
    </div>
  );
}
