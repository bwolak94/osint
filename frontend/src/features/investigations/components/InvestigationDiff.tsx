import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Plus, Minus, Equal, AlertCircle } from "lucide-react";
import { Badge } from "@/shared/components/Badge";
import { LoadingSpinner } from "@/shared/components/LoadingSpinner";
import { NodeTypeIcon } from "@/shared/components/osint/NodeTypeIcon";
import apiClient from "@/shared/api/client";

export interface DiffNode {
  id: string;
  type: string;
  value: string;
  status: "added" | "removed" | "unchanged";
}

interface DiffEdge {
  id: string;
  source: string;
  target: string;
  status: "added" | "removed" | "unchanged";
}

interface GraphSnapshot {
  nodes: Array<{ id: string; type: string; label: string }>;
  edges: Array<{ id: string; source: string; target: string }>;
}

interface InvestigationDiffProps {
  investigationIdA: string;
  investigationIdB: string;
  snapshotIdA?: string;
  snapshotIdB?: string;
}

type DiffTab = "added" | "removed" | "unchanged";

const STATUS_COLORS: Record<DiffNode["status"], string> = {
  added: "var(--success-500, #22c55e)",
  removed: "var(--danger-500, #ef4444)",
  unchanged: "var(--text-tertiary)",
};

const STATUS_BG: Record<DiffNode["status"], string> = {
  added: "rgba(34,197,94,0.08)",
  removed: "rgba(239,68,68,0.08)",
  unchanged: "transparent",
};

function computeDiff(
  snapshotA: GraphSnapshot | undefined,
  snapshotB: GraphSnapshot | undefined,
): { nodes: DiffNode[]; edges: DiffEdge[] } {
  if (!snapshotA || !snapshotB) return { nodes: [], edges: [] };

  const nodesA = new Map(snapshotA.nodes.map((n) => [n.id, n]));
  const nodesB = new Map(snapshotB.nodes.map((n) => [n.id, n]));
  const edgesA = new Set(snapshotA.edges.map((e) => e.id));
  const edgesB = new Set(snapshotB.edges.map((e) => e.id));

  const nodes: DiffNode[] = [];

  for (const [id, n] of nodesB) {
    nodes.push({
      id,
      type: n.type,
      value: n.label,
      status: nodesA.has(id) ? "unchanged" : "added",
    });
  }
  for (const [id, n] of nodesA) {
    if (!nodesB.has(id)) {
      nodes.push({ id, type: n.type, value: n.label, status: "removed" });
    }
  }

  const allEdgeIds = new Set([...edgesA, ...edgesB]);
  const edges: DiffEdge[] = [];
  for (const id of allEdgeIds) {
    const inA = edgesA.has(id);
    const inB = edgesB.has(id);
    const edgeData =
      snapshotB.edges.find((e) => e.id === id) ??
      snapshotA.edges.find((e) => e.id === id);
    if (!edgeData) continue;
    edges.push({
      id,
      source: edgeData.source,
      target: edgeData.target,
      status: inA && inB ? "unchanged" : inB ? "added" : "removed",
    });
  }

  return { nodes, edges };
}

async function fetchSnapshot(
  investigationId: string,
  snapshotId?: string,
): Promise<GraphSnapshot> {
  const url = snapshotId
    ? `/investigations/${investigationId}/snapshots/${snapshotId}`
    : `/investigations/${investigationId}/graph`;
  const { data } = await apiClient.get<GraphSnapshot>(url);
  return data;
}

export function InvestigationDiff({
  investigationIdA,
  investigationIdB,
  snapshotIdA,
  snapshotIdB,
}: InvestigationDiffProps) {
  const [activeTab, setActiveTab] = useState<DiffTab>("added");

  const queryA = useQuery({
    queryKey: ["investigation-snapshot", investigationIdA, snapshotIdA],
    queryFn: () => fetchSnapshot(investigationIdA, snapshotIdA),
  });

  const queryB = useQuery({
    queryKey: ["investigation-snapshot", investigationIdB, snapshotIdB],
    queryFn: () => fetchSnapshot(investigationIdB, snapshotIdB),
  });

  const { nodes: diffNodes, edges: diffEdges } = useMemo(
    () => computeDiff(queryA.data, queryB.data),
    [queryA.data, queryB.data],
  );

  const stats = useMemo(
    () => ({
      nodesAdded: diffNodes.filter((n) => n.status === "added").length,
      nodesRemoved: diffNodes.filter((n) => n.status === "removed").length,
      nodesUnchanged: diffNodes.filter((n) => n.status === "unchanged").length,
      edgesAdded: diffEdges.filter((e) => e.status === "added").length,
      edgesRemoved: diffEdges.filter((e) => e.status === "removed").length,
    }),
    [diffNodes, diffEdges],
  );

  const filteredNodes = useMemo(
    () => diffNodes.filter((n) => n.status === activeTab),
    [diffNodes, activeTab],
  );

  const isLoading = queryA.isLoading || queryB.isLoading;
  const error = queryA.error ?? queryB.error;

  if (isLoading) {
    return (
      <div className="flex h-48 items-center justify-center">
        <LoadingSpinner />
      </div>
    );
  }

  if (error) {
    return (
      <div
        className="flex items-center gap-2 rounded-lg border px-4 py-3"
        style={{
          borderColor: "var(--border-default)",
          background: "var(--bg-surface)",
          color: "var(--danger-500, #ef4444)",
        }}
      >
        <AlertCircle className="h-4 w-4 shrink-0" />
        <p className="text-sm">Failed to load investigation snapshots</p>
      </div>
    );
  }

  return (
    <div
      className="flex flex-col gap-4 rounded-xl border"
      style={{
        borderColor: "var(--border-default)",
        background: "var(--bg-surface)",
      }}
    >
      {/* Stats bar */}
      <div
        className="flex flex-wrap items-center gap-4 border-b px-5 py-3"
        style={{ borderColor: "var(--border-subtle)" }}
        aria-label="Diff summary"
      >
        <div className="flex items-center gap-1.5">
          <Plus className="h-3.5 w-3.5" style={{ color: "var(--success-500, #22c55e)" }} />
          <span className="text-sm font-semibold" style={{ color: "var(--success-500, #22c55e)" }}>
            {stats.nodesAdded} nodes
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <Minus className="h-3.5 w-3.5" style={{ color: "var(--danger-500, #ef4444)" }} />
          <span className="text-sm font-semibold" style={{ color: "var(--danger-500, #ef4444)" }}>
            {stats.nodesRemoved} nodes
          </span>
        </div>
        <div className="h-4 w-px" style={{ background: "var(--border-default)" }} />
        <div className="flex items-center gap-1.5">
          <Plus className="h-3.5 w-3.5" style={{ color: "var(--success-500, #22c55e)" }} />
          <span className="text-sm font-semibold" style={{ color: "var(--success-500, #22c55e)" }}>
            {stats.edgesAdded} edges
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <Minus className="h-3.5 w-3.5" style={{ color: "var(--danger-500, #ef4444)" }} />
          <span className="text-sm font-semibold" style={{ color: "var(--danger-500, #ef4444)" }}>
            {stats.edgesRemoved} edges
          </span>
        </div>
        <div className="ml-auto flex items-center gap-1.5">
          <Equal className="h-3.5 w-3.5" style={{ color: "var(--text-tertiary)" }} />
          <span className="text-sm" style={{ color: "var(--text-tertiary)" }}>
            {stats.nodesUnchanged} unchanged
          </span>
        </div>
      </div>

      {/* Split view labels */}
      <div className="grid grid-cols-2 gap-4 px-5">
        <div
          className="rounded-lg border p-3"
          style={{
            borderColor: "var(--border-subtle)",
            background: "var(--bg-elevated)",
          }}
        >
          <p
            className="text-xs font-medium"
            style={{ color: "var(--text-tertiary)" }}
          >
            Before
          </p>
          <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
            Investigation A
            {snapshotIdA && (
              <span className="ml-1 text-xs font-normal" style={{ color: "var(--text-tertiary)" }}>
                #{snapshotIdA.slice(0, 8)}
              </span>
            )}
          </p>
          <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
            {queryA.data?.nodes.length ?? 0} nodes
          </p>
        </div>
        <div
          className="rounded-lg border p-3"
          style={{
            borderColor: "var(--border-subtle)",
            background: "var(--bg-elevated)",
          }}
        >
          <p
            className="text-xs font-medium"
            style={{ color: "var(--text-tertiary)" }}
          >
            After
          </p>
          <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
            Investigation B
            {snapshotIdB && (
              <span className="ml-1 text-xs font-normal" style={{ color: "var(--text-tertiary)" }}>
                #{snapshotIdB.slice(0, 8)}
              </span>
            )}
          </p>
          <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
            {queryB.data?.nodes.length ?? 0} nodes
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="px-5">
        <div
          className="flex border-b"
          style={{ borderColor: "var(--border-subtle)" }}
          role="tablist"
          aria-label="Diff filter"
        >
          {(
            [
              { key: "added", label: "Added", count: stats.nodesAdded, variant: "success" },
              { key: "removed", label: "Removed", count: stats.nodesRemoved, variant: "danger" },
              { key: "unchanged", label: "Unchanged", count: stats.nodesUnchanged, variant: "neutral" },
            ] as const
          ).map(({ key, label, count, variant }) => (
            <button
              key={key}
              role="tab"
              aria-selected={activeTab === key}
              aria-controls={`diff-panel-${key}`}
              onClick={() => setActiveTab(key)}
              className={`flex items-center gap-2 px-4 py-2.5 text-xs font-medium transition-colors ${
                activeTab === key
                  ? "border-b-2 border-brand-500 text-text-primary"
                  : "text-text-tertiary hover:text-text-secondary"
              }`}
            >
              {label}
              <Badge variant={variant} size="sm">
                {count}
              </Badge>
            </button>
          ))}
        </div>
      </div>

      {/* Node list */}
      <div
        id={`diff-panel-${activeTab}`}
        role="tabpanel"
        className="max-h-72 overflow-y-auto px-5 pb-4"
      >
        {filteredNodes.length === 0 ? (
          <p
            className="py-6 text-center text-sm"
            style={{ color: "var(--text-tertiary)" }}
          >
            No {activeTab} nodes
          </p>
        ) : (
          <ul className="space-y-1" aria-label={`${activeTab} nodes`}>
            {filteredNodes.map((node) => (
              <li
                key={node.id}
                className="flex items-center gap-3 rounded-md px-3 py-2"
                style={{ background: STATUS_BG[node.status] }}
              >
                <NodeTypeIcon type={node.type} size="sm" />
                <span
                  className="flex-1 truncate text-sm"
                  style={{ color: "var(--text-primary)" }}
                >
                  {node.value}
                </span>
                <span
                  className="text-xs capitalize"
                  style={{ color: STATUS_COLORS[node.status] }}
                >
                  {node.status}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
