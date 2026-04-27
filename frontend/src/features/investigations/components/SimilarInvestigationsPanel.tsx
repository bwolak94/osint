/**
 * Investigation Similarity Clustering (Feature 5)
 * Shows investigations clustered by TF-IDF cosine similarity.
 */
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Layers, ExternalLink, Loader2 } from "lucide-react";
import { Badge } from "@/shared/components/Badge";
import { apiClient } from "@/shared/api/client";

interface SimilarityCluster {
  cluster_id: number;
  investigation_ids: string[];
  investigation_titles: string[];
  centroid_terms: string[];
  avg_similarity: number;
  size: number;
}

interface Props {
  currentInvestigationId: string;
}

export function SimilarInvestigationsPanel({ currentInvestigationId }: Props) {
  const navigate = useNavigate();

  const { data, isLoading } = useQuery({
    queryKey: ["similarity-clusters"],
    queryFn: async () => {
      const res = await apiClient.get("/ml/similarity-clusters");
      return res.data as { clusters: SimilarityCluster[]; total_clusters: number };
    },
    staleTime: 5 * 60 * 1000, // 5 min
  });

  // Find cluster(s) containing this investigation
  const myCluster = data?.clusters.find((c) => c.investigation_ids.includes(currentInvestigationId));

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-4">
        <Loader2 className="h-4 w-4 animate-spin" style={{ color: "var(--brand-500)" }} />
      </div>
    );
  }

  if (!myCluster) {
    return (
      <p className="text-xs py-2" style={{ color: "var(--text-tertiary)" }}>
        No similar investigations found yet.
      </p>
    );
  }

  const similarInvs = myCluster.investigation_ids
    .map((id, idx) => ({ id, title: myCluster.investigation_titles[idx] }))
    .filter((inv) => inv.id !== currentInvestigationId);

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Layers className="h-4 w-4 shrink-0" style={{ color: "var(--brand-400)" }} />
        <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
          Similar Investigations
        </p>
        <Badge variant="brand" size="sm">{similarInvs.length}</Badge>
      </div>

      {/* Cluster terms */}
      <div className="flex flex-wrap gap-1">
        {myCluster.centroid_terms.slice(0, 6).map((term) => (
          <span
            key={term}
            className="rounded-full px-2 py-0.5 text-[11px] font-mono"
            style={{ background: "var(--bg-overlay)", color: "var(--text-secondary)" }}
          >
            {term}
          </span>
        ))}
      </div>

      <div className="text-[11px] mb-1" style={{ color: "var(--text-tertiary)" }}>
        Avg similarity: {Math.round(myCluster.avg_similarity * 100)}%
      </div>

      <div className="space-y-1">
        {similarInvs.map((inv) => (
          <button
            key={inv.id}
            onClick={() => navigate(`/investigations/${inv.id}`)}
            className="flex w-full items-center justify-between rounded-md px-3 py-2 text-left transition-colors hover:bg-bg-overlay"
            style={{ background: "var(--bg-elevated)" }}
          >
            <span className="text-xs font-medium truncate flex-1" style={{ color: "var(--text-primary)" }}>
              {inv.title}
            </span>
            <ExternalLink className="ml-2 h-3.5 w-3.5 shrink-0" style={{ color: "var(--text-tertiary)" }} />
          </button>
        ))}
      </div>
    </div>
  );
}
