/**
 * NewsBookmarksPanel — browse and manage bookmarked articles.
 */

import { memo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, Bookmark, ExternalLink, Loader2, Trash2 } from "lucide-react";
import { getNewsBookmarks, removeNewsBookmark } from "../api";
import type { NewsBookmark } from "../types";

export const NewsBookmarksPanel = memo(function NewsBookmarksPanel() {
  const qc = useQueryClient();

  const { data: bookmarks = [], isLoading, isError, refetch } = useQuery<NewsBookmark[]>({
    queryKey: ["news", "bookmarks"],
    queryFn: getNewsBookmarks,
    staleTime: 30_000,
  });

  const removeMutation = useMutation({
    mutationFn: (articleId: string) => removeNewsBookmark(articleId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["news", "bookmarks"] }),
  });

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
          Failed to load bookmarks.{" "}
          <button onClick={() => refetch()} className="underline hover:opacity-70">
            Retry
          </button>
        </p>
      </div>
    );
  }

  if (bookmarks.length === 0) {
    return (
      <div
        className="flex flex-col items-center justify-center py-16 gap-3 rounded-xl border border-dashed"
        style={{ borderColor: "var(--border-subtle)" }}
      >
        <Bookmark className="h-8 w-8" style={{ color: "var(--text-tertiary)" }} />
        <p className="text-sm text-center max-w-xs" style={{ color: "var(--text-tertiary)" }}>
          No bookmarks yet. Click the bookmark icon on any article to save it here.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-2 overflow-y-auto">
      {bookmarks.map((bm) => (
        <div
          key={bm.article_id}
          className="flex items-start gap-2 rounded-xl border p-3"
          style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}
        >
          <Bookmark
            className="h-3.5 w-3.5 mt-0.5 shrink-0"
            style={{ color: "var(--brand-500)" }}
          />

          <div className="flex-1 min-w-0">
            {bm.url ? (
              <a
                href={bm.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs font-medium hover:underline inline-flex items-start gap-1"
                style={{ color: "var(--text-primary)" }}
              >
                <span className="line-clamp-2">{bm.title || bm.article_id}</span>
                <ExternalLink className="h-2.5 w-2.5 mt-0.5 shrink-0 opacity-60" />
              </a>
            ) : (
              <p className="text-xs font-medium line-clamp-2" style={{ color: "var(--text-primary)" }}>
                {bm.title || bm.article_id}
              </p>
            )}
            <div className="flex items-center gap-2 mt-0.5">
              {bm.source_domain && (
                <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                  {bm.source_domain}
                </span>
              )}
              <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                {new Date(bm.bookmarked_at).toLocaleDateString()}
              </span>
            </div>
          </div>

          <button
            onClick={() => removeMutation.mutate(bm.article_id)}
            disabled={removeMutation.isPending}
            className="shrink-0 rounded p-1 hover:opacity-70 transition-opacity disabled:opacity-40"
            aria-label="Remove bookmark"
            title="Remove bookmark"
          >
            <Trash2 className="h-3.5 w-3.5" style={{ color: "var(--danger-500)" }} />
          </button>
        </div>
      ))}
    </div>
  );
});
