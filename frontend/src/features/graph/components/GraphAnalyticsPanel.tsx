import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import { BarChart3, GitBranch, Layers, Clock, X } from "lucide-react";

interface GraphAnalytics {
  centrality: Array<{ node_id: string; label: string; node_type: string; score: number }>;
  communities: Array<{ community_id: number; nodes: string[]; size: number }>;
  density: number;
  connected_components: number;
  avg_path_length: number;
  clustering_coefficient: number;
}

interface GraphAnalyticsPanelProps {
  investigationId: string;
  isOpen: boolean;
  onClose: () => void;
}

export function GraphAnalyticsPanel({ investigationId, isOpen, onClose }: GraphAnalyticsPanelProps) {
  const [activeTab, setActiveTab] = useState<"metrics" | "centrality" | "communities" | "timeline">("metrics");

  const { data, isLoading } = useQuery({
    queryKey: ["graph-analytics", investigationId],
    queryFn: async () => {
      const resp = await apiClient.get<GraphAnalytics>(`/graph/${investigationId}/analytics`);
      return resp.data;
    },
    enabled: isOpen,
  });

  if (!isOpen) return null;

  const tabs = [
    { id: "metrics" as const, label: "Metrics", icon: BarChart3 },
    { id: "centrality" as const, label: "Centrality", icon: GitBranch },
    { id: "communities" as const, label: "Communities", icon: Layers },
    { id: "timeline" as const, label: "Time Travel", icon: Clock },
  ];

  return (
    <div
      className="absolute right-0 top-0 z-10 flex h-full w-80 flex-col border-l"
      style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}
    >
      <div
        className="flex items-center justify-between border-b px-4 py-3"
        style={{ borderColor: "var(--border-subtle)" }}
      >
        <span className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
          Graph Analytics
        </span>
        <button onClick={onClose} className="rounded p-1 hover:bg-bg-overlay">
          <X className="h-4 w-4" style={{ color: "var(--text-secondary)" }} />
        </button>
      </div>

      <div className="flex border-b" style={{ borderColor: "var(--border-subtle)" }}>
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex-1 px-2 py-2 text-xs font-medium transition-colors ${activeTab === tab.id ? "border-b-2" : ""}`}
            style={{
              borderColor: activeTab === tab.id ? "var(--brand-400)" : "transparent",
              color: activeTab === tab.id ? "var(--brand-400)" : "var(--text-tertiary)",
            }}
          >
            <tab.icon className="mx-auto h-3.5 w-3.5 mb-0.5" />
            {tab.label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {isLoading ? (
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Analyzing...
          </p>
        ) : activeTab === "metrics" ? (
          <div className="space-y-3">
            {[
              { label: "Density", value: data?.density?.toFixed(3) ?? "0" },
              { label: "Components", value: data?.connected_components ?? 0 },
              { label: "Avg Path Length", value: data?.avg_path_length?.toFixed(2) ?? "0" },
              { label: "Clustering", value: data?.clustering_coefficient?.toFixed(3) ?? "0" },
            ].map((m) => (
              <div
                key={m.label}
                className="flex justify-between rounded-md border p-2"
                style={{ borderColor: "var(--border-subtle)" }}
              >
                <span className="text-xs" style={{ color: "var(--text-secondary)" }}>
                  {m.label}
                </span>
                <span className="text-sm font-mono font-medium" style={{ color: "var(--text-primary)" }}>
                  {m.value}
                </span>
              </div>
            ))}
          </div>
        ) : activeTab === "centrality" ? (
          <div className="space-y-2">
            {(data?.centrality ?? []).length === 0 ? (
              <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                No centrality data available
              </p>
            ) : (
              data?.centrality.map((n) => (
                <div
                  key={n.node_id}
                  className="flex items-center justify-between rounded border p-2"
                  style={{ borderColor: "var(--border-subtle)" }}
                >
                  <span className="text-xs" style={{ color: "var(--text-primary)" }}>
                    {n.label}
                  </span>
                  <span className="text-xs font-mono" style={{ color: "var(--brand-400)" }}>
                    {n.score.toFixed(3)}
                  </span>
                </div>
              ))
            )}
          </div>
        ) : activeTab === "communities" ? (
          <div className="space-y-2">
            {(data?.communities ?? []).length === 0 ? (
              <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                No communities detected
              </p>
            ) : (
              data?.communities.map((c) => (
                <div
                  key={c.community_id}
                  className="rounded border p-2"
                  style={{ borderColor: "var(--border-subtle)" }}
                >
                  <div className="flex justify-between">
                    <span className="text-xs font-medium" style={{ color: "var(--text-primary)" }}>
                      Community {c.community_id}
                    </span>
                    <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                      {c.size} nodes
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        ) : (
          <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
            Graph time travel - select snapshots to compare
          </p>
        )}
      </div>
    </div>
  );
}
