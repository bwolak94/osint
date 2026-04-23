/**
 * NewsSourcesPanel — manage RSS feed sources.
 * Add, remove, and enable/disable individual feeds.
 */

import { memo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, CheckCircle, Loader2, Plus, Trash2, ToggleLeft, ToggleRight, Rss } from "lucide-react";
import { getNewsSources, addNewsSource, removeNewsSource } from "../api";
import type { NewsSource } from "../types";
import apiClient from "@/shared/api/client";

async function toggleSource(url: string, enabled: boolean): Promise<void> {
  await apiClient.patch("/hub/news/sources", { url, enabled });
}

export const NewsSourcesPanel = memo(function NewsSourcesPanel() {
  const qc = useQueryClient();
  const [newUrl, setNewUrl] = useState("");
  const [newName, setNewName] = useState("");
  const [addError, setAddError] = useState<string | null>(null);

  const { data: sources = [], isLoading, isError } = useQuery<NewsSource[]>({
    queryKey: ["news", "sources"],
    queryFn: getNewsSources,
    staleTime: 30_000,
  });

  const addMutation = useMutation({
    mutationFn: () => addNewsSource({ url: newUrl.trim(), name: newName.trim() || newUrl.trim() }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["news", "sources"] });
      setNewUrl("");
      setNewName("");
      setAddError(null);
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : "Failed to add source";
      setAddError(msg);
    },
  });

  const removeMutation = useMutation({
    mutationFn: (url: string) => removeNewsSource(url),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["news", "sources"] }),
  });

  const toggleMutation = useMutation({
    mutationFn: ({ url, enabled }: { url: string; enabled: boolean }) =>
      toggleSource(url, enabled),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["news", "sources"] }),
  });

  function handleAdd() {
    const url = newUrl.trim();
    if (!url.startsWith("http")) {
      setAddError("URL must start with http:// or https://");
      return;
    }
    setAddError(null);
    addMutation.mutate();
  }

  return (
    <div className="flex flex-col gap-4 h-full overflow-hidden">
      {/* Add new source */}
      <div
        className="rounded-xl border p-3 flex-shrink-0"
        style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}
      >
        <p className="text-xs font-semibold mb-2" style={{ color: "var(--text-secondary)" }}>
          Add RSS Feed
        </p>
        <div className="flex flex-col gap-2">
          <input
            type="url"
            placeholder="https://feeds.example.com/rss"
            value={newUrl}
            onChange={(e) => setNewUrl(e.target.value)}
            className="text-xs rounded-lg border px-3 py-2 w-full"
            style={{
              background: "var(--bg-input)",
              borderColor: "var(--border-default)",
              color: "var(--text-primary)",
            }}
            onKeyDown={(e) => e.key === "Enter" && handleAdd()}
          />
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="Display name (optional)"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              className="text-xs rounded-lg border px-3 py-2 flex-1"
              style={{
                background: "var(--bg-input)",
                borderColor: "var(--border-default)",
                color: "var(--text-primary)",
              }}
            />
            <button
              onClick={handleAdd}
              disabled={!newUrl.trim() || addMutation.isPending}
              className="flex items-center gap-1 rounded-lg px-3 py-2 text-xs font-medium transition-opacity disabled:opacity-40"
              style={{ background: "var(--brand-500)", color: "white" }}
            >
              {addMutation.isPending ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <Plus className="h-3 w-3" />
              )}
              Add
            </button>
          </div>
          {addError && (
            <p className="text-xs" style={{ color: "var(--danger-500)" }}>
              {addError}
            </p>
          )}
        </div>
      </div>

      {/* Sources list */}
      <div className="flex-1 overflow-y-auto space-y-1.5">
        {isLoading && (
          <div className="flex justify-center py-8">
            <Loader2 className="h-4 w-4 animate-spin" style={{ color: "var(--text-tertiary)" }} />
          </div>
        )}

        {isError && (
          <div
            className="flex items-center gap-2 rounded-xl border px-3 py-2"
            style={{ borderColor: "var(--danger-500)", background: "var(--danger-50)" }}
          >
            <AlertCircle className="h-3.5 w-3.5 shrink-0" style={{ color: "var(--danger-500)" }} />
            <p className="text-xs" style={{ color: "var(--danger-600)" }}>Failed to load sources.</p>
          </div>
        )}

        {!isLoading && !isError && sources.length === 0 && (
          <div
            className="flex flex-col items-center gap-2 py-12 rounded-xl border border-dashed"
            style={{ borderColor: "var(--border-subtle)" }}
          >
            <Rss className="h-6 w-6" style={{ color: "var(--text-tertiary)" }} />
            <p className="text-xs text-center" style={{ color: "var(--text-tertiary)" }}>
              No RSS sources configured. Add one above to start scraping news.
            </p>
          </div>
        )}

        {sources.map((src) => (
          <div
            key={src.url}
            className="flex items-center gap-2 rounded-xl border px-3 py-2.5"
            style={{
              background: "var(--bg-surface)",
              borderColor: src.enabled ? "var(--border-subtle)" : "var(--border-faint)",
              opacity: src.enabled ? 1 : 0.6,
            }}
          >
            <Rss
              className="h-3.5 w-3.5 shrink-0"
              style={{ color: src.enabled ? "var(--brand-500)" : "var(--text-tertiary)" }}
            />
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium truncate" style={{ color: "var(--text-primary)" }}>
                {src.name || src.url}
              </p>
              <p className="text-xs truncate" style={{ color: "var(--text-tertiary)" }}>
                {src.url}
              </p>
            </div>

            <div className="flex items-center gap-1 shrink-0">
              {/* Toggle enabled/disabled */}
              <button
                onClick={() =>
                  toggleMutation.mutate({ url: src.url, enabled: !src.enabled })
                }
                disabled={toggleMutation.isPending}
                className="rounded p-1 hover:opacity-70 transition-opacity disabled:opacity-40"
                title={src.enabled ? "Disable feed" : "Enable feed"}
                aria-label={src.enabled ? "Disable feed" : "Enable feed"}
              >
                {src.enabled ? (
                  <ToggleRight className="h-4 w-4" style={{ color: "var(--success-500)" }} />
                ) : (
                  <ToggleLeft className="h-4 w-4" style={{ color: "var(--text-tertiary)" }} />
                )}
              </button>

              {/* Remove */}
              <button
                onClick={() => removeMutation.mutate(src.url)}
                disabled={removeMutation.isPending}
                className="rounded p-1 hover:opacity-70 transition-opacity disabled:opacity-40"
                title="Remove feed"
                aria-label="Remove feed"
              >
                <Trash2 className="h-3.5 w-3.5" style={{ color: "var(--danger-500)" }} />
              </button>
            </div>
          </div>
        ))}
      </div>

      <p className="text-xs text-center flex-shrink-0" style={{ color: "var(--text-tertiary)" }}>
        {sources.length} source{sources.length !== 1 ? "s" : ""} ·{" "}
        {sources.filter((s) => s.enabled).length} active
      </p>
    </div>
  );
});
