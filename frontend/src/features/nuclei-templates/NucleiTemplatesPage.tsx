import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, Loader2, AlertTriangle, Tag, FileCode } from "lucide-react";
import { apiClient } from "@/shared/api/client";
import { Badge } from "@/shared/components/Badge";
import { Card, CardBody, CardHeader } from "@/shared/components/Card";

interface NucleiTemplate {
  id: string;
  name: string;
  path: string;
  tags: string[];
  severity: string;
}

interface TemplatesResponse {
  templates: NucleiTemplate[];
  total_count: number;
  search: string | null;
}

const SEV_VARIANTS: Record<string, "danger" | "warning" | "neutral" | "success"> = {
  critical: "danger",
  high: "danger",
  medium: "warning",
  low: "neutral",
  info: "neutral",
};

export function NucleiTemplatesPage() {
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");

  const { data, isLoading, isError } = useQuery({
    queryKey: ["nuclei-templates", debouncedSearch],
    queryFn: async () => {
      const params = debouncedSearch ? { search: debouncedSearch } : {};
      const res = await apiClient.get("/advanced-scanners/nuclei/templates", { params });
      return res.data as TemplatesResponse;
    },
    staleTime: 300_000,
  });

  const handleSearchChange = (val: string) => {
    setSearch(val);
    clearTimeout((window as unknown as { _nucleiTimer?: ReturnType<typeof setTimeout> })._nucleiTimer);
    (window as unknown as { _nucleiTimer?: ReturnType<typeof setTimeout> })._nucleiTimer = setTimeout(
      () => setDebouncedSearch(val),
      400,
    );
  };

  const grouped = (data?.templates ?? []).reduce<Record<string, NucleiTemplate[]>>((acc, t) => {
    const cat = t.tags[0] ?? "other";
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(t);
    return acc;
  }, {});

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
          Nuclei Template Browser
        </h1>
        <p className="text-sm mt-1" style={{ color: "var(--text-secondary)" }}>
          Browse and search installed Nuclei templates. Select templates to use in the Advanced Scanners page.
        </p>
      </div>

      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4" style={{ color: "var(--text-tertiary)" }} />
          <input
            value={search}
            onChange={(e) => handleSearchChange(e.target.value)}
            placeholder="Search templates..."
            className="w-full rounded-md border pl-9 pr-3 py-2 text-sm"
            style={{ background: "var(--bg-elevated)", borderColor: "var(--border-default)", color: "var(--text-primary)" }}
          />
        </div>
        {data && (
          <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>
            {data.templates.length} / {data.total_count} templates
          </span>
        )}
      </div>

      {isLoading && (
        <div className="flex items-center gap-2" style={{ color: "var(--text-tertiary)" }}>
          <Loader2 className="h-4 w-4 animate-spin" />
          <span className="text-sm">Loading templates...</span>
        </div>
      )}

      {isError && (
        <div className="flex items-center gap-2 text-sm" style={{ color: "var(--danger-400)" }}>
          <AlertTriangle className="h-4 w-4" />
          Failed to load templates. Ensure nuclei is installed.
        </div>
      )}

      {!isLoading && data?.templates.length === 0 && (
        <div className="text-sm" style={{ color: "var(--text-tertiary)" }}>
          No templates found. Install nuclei templates with: <code className="font-mono">nuclei -update-templates</code>
        </div>
      )}

      {Object.entries(grouped).map(([category, templates]) => (
        <Card key={category}>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Tag className="h-3.5 w-3.5" style={{ color: "var(--brand-500)" }} />
              <p className="text-sm font-semibold capitalize" style={{ color: "var(--text-primary)" }}>{category}</p>
              <Badge variant="neutral" size="sm">{templates.length}</Badge>
            </div>
          </CardHeader>
          <CardBody>
            <div className="grid gap-1.5 sm:grid-cols-2">
              {templates.map((t) => (
                <div
                  key={t.id}
                  className="flex items-center gap-2 rounded-md px-3 py-1.5"
                  style={{ background: "var(--bg-base)" }}
                >
                  <FileCode className="h-3 w-3 shrink-0" style={{ color: "var(--text-tertiary)" }} />
                  <span className="flex-1 truncate text-xs font-mono" style={{ color: "var(--text-primary)" }} title={t.path}>
                    {t.id}
                  </span>
                  <Badge variant={SEV_VARIANTS[t.severity] ?? "neutral"} size="sm">
                    {t.severity.toUpperCase()}
                  </Badge>
                </div>
              ))}
            </div>
          </CardBody>
        </Card>
      ))}
    </div>
  );
}
