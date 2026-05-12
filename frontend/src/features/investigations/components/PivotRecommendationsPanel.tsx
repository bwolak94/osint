import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Sparkles, ChevronDown, ChevronUp, SearchX } from "lucide-react";
import { apiClient } from "@/shared/api/client";

interface Recommendation {
  scanner: string;
  reason: string;
  target: string;
  confidence: "high" | "medium" | "low";
}

interface RecommendationsData {
  investigation_id: string;
  recommendations: Recommendation[];
  summary: string;
}

interface Props {
  investigationId: string;
}

const confidenceColor: Record<string, string> = {
  high: "var(--success-500)",
  medium: "var(--warning-500)",
  low: "var(--text-tertiary)",
};

export function PivotRecommendationsPanel({ investigationId }: Props) {
  const [expanded, setExpanded] = useState(false);

  const { data, isLoading, error } = useQuery<RecommendationsData>({
    queryKey: ["pivot-recommendations", investigationId],
    queryFn: async () => {
      const resp = await apiClient.get(`/investigations/${investigationId}/pivot-recommendations`);
      return resp.data as RecommendationsData;
    },
    enabled: expanded,
    staleTime: 10 * 60 * 1000,
  });

  return (
    <div
      className="rounded-lg border overflow-hidden"
      style={{ borderColor: "var(--border-subtle)", background: "var(--bg-surface)" }}
    >
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center gap-2 px-4 py-3 text-sm font-medium transition-colors hover:bg-bg-overlay"
        aria-expanded={expanded}
        aria-label="Toggle AI pivot recommendations"
      >
        <Sparkles className="h-4 w-4" style={{ color: "var(--brand-400)" }} />
        <span style={{ color: "var(--text-primary)" }}>AI Pivot Recommendations</span>
        <span className="ml-auto">
          {expanded ? (
            <ChevronUp className="h-4 w-4" style={{ color: "var(--text-tertiary)" }} />
          ) : (
            <ChevronDown className="h-4 w-4" style={{ color: "var(--text-tertiary)" }} />
          )}
        </span>
      </button>

      {expanded && (
        <div className="border-t px-4 pb-4 pt-3 space-y-3" style={{ borderColor: "var(--border-subtle)" }}>
          {isLoading && (
            <p className="text-sm animate-pulse" style={{ color: "var(--text-tertiary)" }}>
              Analysing investigation graph…
            </p>
          )}
          {error && (
            <p className="text-sm" style={{ color: "var(--danger-400)" }}>
              Unable to load recommendations. Check LLM configuration.
            </p>
          )}
          {data && (
            <>
              {data.summary && (
                <p className="text-xs italic" style={{ color: "var(--text-secondary)" }}>
                  {data.summary}
                </p>
              )}
              {data.recommendations.length === 0 && (
                <div className="flex flex-col items-center gap-2 py-4 text-center">
                  <SearchX className="h-8 w-8" style={{ color: "var(--text-tertiary)" }} />
                  <p className="text-sm font-medium" style={{ color: "var(--text-secondary)" }}>
                    No pivot recommendations yet
                  </p>
                  <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                    Run more scanners to generate AI-powered investigation suggestions.
                  </p>
                </div>
              )}
              <ul className="space-y-2">
                {data.recommendations.map((rec, i) => (
                  <li
                    key={i}
                    className="flex items-start gap-3 rounded-md p-3"
                    style={{ background: "var(--bg-overlay)" }}
                  >
                    <span
                      className="mt-0.5 h-2 w-2 shrink-0 rounded-full"
                      style={{ background: confidenceColor[rec.confidence] }}
                      aria-label={`${rec.confidence} confidence`}
                    />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                        <code className="text-xs mr-1 rounded px-1" style={{ background: "var(--bg-elevated)", color: "var(--brand-400)" }}>
                          {rec.scanner}
                        </code>
                        {rec.target}
                      </p>
                      <p className="text-xs mt-0.5" style={{ color: "var(--text-secondary)" }}>
                        {rec.reason}
                      </p>
                    </div>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </div>
  );
}
