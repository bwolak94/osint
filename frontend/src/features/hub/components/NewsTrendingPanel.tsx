/**
 * NewsTrendingPanel — displays trending tags from recent news articles.
 * Tags are ranked by article count. Clicking a tag applies it as a filter.
 */

import { memo } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertCircle, Loader2, TrendingUp } from "lucide-react";
import { getNewsTrending } from "../api";

interface NewsTrendingPanelProps {
  onTagSelect?: (tag: string) => void;
}

export const NewsTrendingPanel = memo(function NewsTrendingPanel({
  onTagSelect,
}: NewsTrendingPanelProps) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["news", "trending"],
    queryFn: getNewsTrending,
    staleTime: 5 * 60 * 1000,
  });

  const tags = data?.trending ?? [];
  const maxCount = tags[0]?.count ?? 1;

  if (isLoading) {
    return (
      <div className="flex justify-center py-16">
        <Loader2 className="h-4 w-4 animate-spin" style={{ color: "var(--text-tertiary)" }} />
      </div>
    );
  }

  if (isError) {
    return (
      <div
        className="flex items-center gap-2 rounded-xl border px-4 py-3"
        style={{ borderColor: "var(--danger-500)", background: "var(--danger-50)" }}
        role="alert"
      >
        <AlertCircle className="h-4 w-4 shrink-0" style={{ color: "var(--danger-500)" }} />
        <p className="text-xs" style={{ color: "var(--danger-600)" }}>
          Failed to load trending.{" "}
          <button onClick={() => refetch()} className="underline hover:opacity-70">
            Retry
          </button>
        </p>
      </div>
    );
  }

  if (tags.length === 0) {
    return (
      <div
        className="flex flex-col items-center justify-center py-16 gap-3 rounded-xl border border-dashed"
        style={{ borderColor: "var(--border-subtle)" }}
      >
        <TrendingUp className="h-8 w-8" style={{ color: "var(--text-tertiary)" }} />
        <p className="text-sm text-center max-w-xs" style={{ color: "var(--text-tertiary)" }}>
          No trending data yet. Tags are computed from stored articles.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-2 overflow-y-auto">
      <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
        Top tags by article volume. Click to filter the feed.
      </p>

      {tags.map((item, idx) => {
        const pct = Math.round((item.count / maxCount) * 100);
        return (
          <button
            key={item.tag}
            onClick={() => onTagSelect?.(item.tag)}
            className="w-full text-left rounded-xl border px-3 py-2 transition-opacity hover:opacity-80"
            style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}
          >
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-2">
                <span
                  className="text-xs font-mono w-5 text-right shrink-0"
                  style={{ color: "var(--text-tertiary)" }}
                >
                  {idx + 1}
                </span>
                <span
                  className="text-xs font-medium px-1.5 py-0.5 rounded-full"
                  style={{ background: "var(--brand-50)", color: "var(--brand-600)" }}
                >
                  {item.tag}
                </span>
              </div>
              <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                {item.count} article{item.count !== 1 ? "s" : ""}
              </span>
            </div>

            {/* Progress bar */}
            <div
              className="h-1 rounded-full overflow-hidden"
              style={{ background: "var(--bg-elevated)" }}
            >
              <div
                className="h-full rounded-full transition-all"
                style={{
                  width: `${pct}%`,
                  background: idx === 0
                    ? "var(--brand-500)"
                    : idx < 3
                    ? "var(--brand-400)"
                    : "var(--brand-300)",
                }}
              />
            </div>
          </button>
        );
      })}
    </div>
  );
});
