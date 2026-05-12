import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Plus, Search, LayoutGrid, LayoutList, MoreHorizontal, X, Loader2, FlaskConical, SlidersHorizontal,
} from "lucide-react";
import { Button } from "@/shared/components/Button";
import { Input } from "@/shared/components/Input";
import { Badge } from "@/shared/components/Badge";
import { Card, CardBody } from "@/shared/components/Card";
import { EmptyState } from "@/shared/components/EmptyState";
import { InvestigationCard } from "@/shared/components/osint/InvestigationCard";
import { CreateInvestigationModal } from "@/features/investigations/CreateInvestigationModal";
import { useInvestigationsInfinite } from "./hooks";

type ViewMode = "grid" | "table";
type StatusFilter = "all" | "draft" | "running" | "paused" | "completed" | "archived";

type ColumnKey = "status" | "tags" | "seeds" | "progress" | "created";

const ALL_COLUMNS: { key: ColumnKey; label: string }[] = [
  { key: "status", label: "Status" },
  { key: "tags", label: "Tags" },
  { key: "seeds", label: "Seeds" },
  { key: "progress", label: "Progress" },
  { key: "created", label: "Created" },
];

const DEFAULT_COLUMNS: ColumnKey[] = ["status", "seeds", "progress", "created"];

function useColumnPrefs(): [Set<ColumnKey>, (col: ColumnKey) => void] {
  const [cols, setCols] = useState<Set<ColumnKey>>(() => {
    try {
      const saved = localStorage.getItem("inv-table-columns");
      if (saved) return new Set(JSON.parse(saved) as ColumnKey[]);
    } catch { /* ignore */ }
    return new Set(DEFAULT_COLUMNS);
  });
  const toggle = (col: ColumnKey) => {
    setCols((prev) => {
      const next = new Set(prev);
      if (next.has(col)) next.delete(col);
      else next.add(col);
      localStorage.setItem("inv-table-columns", JSON.stringify([...next]));
      return next;
    });
  };
  return [cols, toggle];
}

// Use localStorage for view preference
function useViewMode(): [ViewMode, (mode: ViewMode) => void] {
  const [mode, setMode] = useState<ViewMode>(() => {
    return (localStorage.getItem("inv-view-mode") as ViewMode) ?? "grid";
  });
  const set = (m: ViewMode) => { localStorage.setItem("inv-view-mode", m); setMode(m); };
  return [mode, set];
}

const statusFilters: { value: StatusFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "draft", label: "Draft" },
  { value: "running", label: "Running" },
  { value: "paused", label: "Paused" },
  { value: "completed", label: "Completed" },
  { value: "archived", label: "Archived" },
];

const statusVariant: Record<string, "neutral" | "info" | "success" | "warning" | "danger"> = {
  draft: "neutral", running: "info", paused: "warning", completed: "success", archived: "danger",
};

export function InvestigationsPage() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [viewMode, setViewMode] = useViewMode();
  const [visibleColumns, toggleColumn] = useColumnPrefs();
  const [showColumnMenu, setShowColumnMenu] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const navigate = useNavigate();

  const { data, isLoading, isFetching, fetchNextPage, hasNextPage } = useInvestigationsInfinite();

  // Map API items to the shape expected by the UI
  const allApiItems = data?.pages.flatMap(p => p.items) ?? [];
  const investigations = allApiItems.map((item) => ({
    id: item.id,
    title: item.title,
    status: item.status,
    seedCount: item.seed_inputs?.length ?? 0,
    progress: item.scan_progress?.percentage,
    tags: item.tags ?? [],
    createdAt: item.created_at,
  }));

  const filtered = investigations.filter((inv) => {
    const matchesSearch = inv.title.toLowerCase().includes(search.toLowerCase()) ||
      inv.tags.some((t) => t.toLowerCase().includes(search.toLowerCase()));
    const matchesStatus = statusFilter === "all" || inv.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin" style={{ color: "var(--brand-500)" }} />
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
            Investigations
          </h1>
          <Badge variant="neutral" size="sm">{data?.pages[0]?.total ?? 0}</Badge>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => navigate("/deep-research")}
            className="inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium transition-colors hover:opacity-80"
            style={{
              background: "var(--bg-elevated)",
              borderColor: "var(--border-subtle)",
              color: "var(--text-secondary)",
            }}
          >
            <FlaskConical className="h-4 w-4" style={{ color: "var(--brand-400)" }} />
            Deep Research
          </button>
          <Button leftIcon={<Plus className="h-4 w-4" />} onClick={() => setShowCreateModal(true)}>
            New Investigation
          </Button>
        </div>
      </div>

      {/* Filters bar */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex-1">
          <Input
            placeholder="Search by title or tags..."
            prefixIcon={<Search className="h-4 w-4" />}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            suffixIcon={search ? (
              <button onClick={() => setSearch("")} className="cursor-pointer">
                <X className="h-4 w-4" />
              </button>
            ) : undefined}
          />
        </div>
        <div className="flex gap-1">
          {statusFilters.map((f) => (
            <button
              key={f.value}
              onClick={() => setStatusFilter(f.value)}
              className={`rounded-md px-3 py-1.5 text-xs font-medium transition-all ${
                statusFilter === f.value
                  ? "bg-brand-900 text-brand-400"
                  : "text-text-secondary hover:bg-bg-overlay hover:text-text-primary"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
        <div className="flex gap-1 rounded-md border p-0.5" style={{ borderColor: "var(--border-default)" }}>
          <button
            onClick={() => setViewMode("grid")}
            className={`rounded p-1.5 transition-colors ${viewMode === "grid" ? "bg-bg-overlay text-text-primary" : "text-text-tertiary"}`}
          >
            <LayoutGrid className="h-4 w-4" />
          </button>
          <button
            onClick={() => setViewMode("table")}
            className={`rounded p-1.5 transition-colors ${viewMode === "table" ? "bg-bg-overlay text-text-primary" : "text-text-tertiary"}`}
          >
            <LayoutList className="h-4 w-4" />
          </button>
        </div>

        {viewMode === "table" && (
          <div className="relative">
            <button
              onClick={() => setShowColumnMenu((p) => !p)}
              className="flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs font-medium transition-colors hover:bg-bg-overlay"
              style={{ borderColor: "var(--border-default)", color: "var(--text-secondary)" }}
              title="Choose visible columns"
            >
              <SlidersHorizontal className="h-3.5 w-3.5" />
              Columns
            </button>
            {showColumnMenu && (
              <div
                className="absolute right-0 top-full z-30 mt-1 w-40 rounded-lg border py-1 shadow-xl"
                style={{ background: "var(--bg-surface)", borderColor: "var(--border-default)" }}
              >
                {ALL_COLUMNS.map(({ key, label }) => (
                  <button
                    key={key}
                    onClick={() => toggleColumn(key)}
                    className="flex w-full items-center gap-2 px-3 py-2 text-xs transition-colors hover:bg-bg-overlay"
                    style={{ color: visibleColumns.has(key) ? "var(--text-primary)" : "var(--text-tertiary)" }}
                  >
                    <span
                      className="flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded border text-[9px]"
                      style={{
                        borderColor: visibleColumns.has(key) ? "var(--brand-500)" : "var(--border-default)",
                        background: visibleColumns.has(key) ? "var(--brand-500)" : "transparent",
                        color: "#fff",
                      }}
                    >
                      {visibleColumns.has(key) ? "✓" : ""}
                    </span>
                    {label}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Content */}
      {filtered.length === 0 ? (
        <EmptyState
          variant={search || statusFilter !== "all" ? "search-empty" : "no-data"}
          title={search ? "No matching investigations" : "No investigations yet"}
          description={search ? "Try different search terms or filters" : "Create your first investigation to get started"}
          action={!search ? <Button leftIcon={<Plus className="h-4 w-4" />} onClick={() => setShowCreateModal(true)}>Create Investigation</Button> : undefined}
        />
      ) : viewMode === "grid" ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map(({ progress, ...inv }) => (
            <InvestigationCard key={inv.id} {...inv} {...(progress !== undefined ? { progress } : {})} />
          ))}
        </div>
      ) : (
        <Card>
          <CardBody className="p-0">
            <table className="w-full">
              <thead>
                <tr className="border-b text-left text-xs font-medium" style={{ borderColor: "var(--border-subtle)", color: "var(--text-tertiary)" }}>
                  <th className="px-4 py-3">Title</th>
                  {visibleColumns.has("status") && <th className="px-4 py-3">Status</th>}
                  {visibleColumns.has("tags") && <th className="px-4 py-3">Tags</th>}
                  {visibleColumns.has("seeds") && <th className="px-4 py-3">Seeds</th>}
                  {visibleColumns.has("progress") && <th className="px-4 py-3">Progress</th>}
                  {visibleColumns.has("created") && <th className="px-4 py-3">Created</th>}
                  <th className="w-10 px-4 py-3"></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((inv) => (
                  <tr
                    key={inv.id}
                    onClick={() => navigate(`/investigations/${inv.id}`)}
                    className="cursor-pointer border-b transition-colors hover:bg-bg-overlay"
                    style={{ borderColor: "var(--border-subtle)" }}
                  >
                    <td className="px-4 py-3">
                      <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>{inv.title}</p>
                    </td>
                    {visibleColumns.has("status") && (
                      <td className="px-4 py-3">
                        <Badge variant={(statusVariant[inv.status] ?? "neutral") as "success" | "warning" | "danger" | "info" | "neutral" | "brand"} size="sm" dot>{inv.status}</Badge>
                      </td>
                    )}
                    {visibleColumns.has("tags") && (
                      <td className="px-4 py-3">
                        <div className="flex gap-1">
                          {inv.tags.slice(0, 2).map((t) => (
                            <Badge key={t} variant="neutral" size="sm">{t}</Badge>
                          ))}
                        </div>
                      </td>
                    )}
                    {visibleColumns.has("seeds") && (
                      <td className="px-4 py-3 text-sm" style={{ color: "var(--text-secondary)" }}>{inv.seedCount}</td>
                    )}
                    {visibleColumns.has("progress") && (
                      <td className="px-4 py-3 font-mono text-sm" style={{ color: "var(--text-primary)" }}>
                        {inv.progress != null ? `${inv.progress}%` : "—"}
                      </td>
                    )}
                    {visibleColumns.has("created") && (
                      <td className="px-4 py-3 text-xs" style={{ color: "var(--text-tertiary)" }}>
                        {new Date(inv.createdAt).toLocaleDateString()}
                      </td>
                    )}
                    <td className="px-4 py-3">
                      <button onClick={(e) => e.stopPropagation()} className="rounded p-1 hover:bg-bg-elevated">
                        <MoreHorizontal className="h-4 w-4" style={{ color: "var(--text-tertiary)" }} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardBody>
        </Card>
      )}

      {/* Load more */}
      {hasNextPage && (
        <div className="flex justify-center pt-2">
          <button
            onClick={() => fetchNextPage()}
            disabled={isFetching}
            className="flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-colors"
            style={{ background: 'var(--bg-elevated)', color: 'var(--text-secondary)', opacity: isFetching ? 0.6 : 1 }}
          >
            {isFetching ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            Load more
          </button>
        </div>
      )}

      {/* Create modal */}
      {showCreateModal && (
        <CreateInvestigationModal onClose={() => setShowCreateModal(false)} />
      )}
    </div>
  );
}
