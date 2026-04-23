/**
 * NewsTopicsPanel — manage user topic subscriptions.
 * Topics are saved to Redis and can be used to filter the scraped feed.
 */

import { memo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, Loader2, Plus, Save, Tag, X } from "lucide-react";
import { getNewsTopics, updateNewsTopics } from "../api";

export const NewsTopicsPanel = memo(function NewsTopicsPanel() {
  const qc = useQueryClient();
  const [newTopic, setNewTopic] = useState("");
  const [localTopics, setLocalTopics] = useState<string[] | null>(null);
  const [saved, setSaved] = useState(false);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["news", "topics"],
    queryFn: getNewsTopics,
    staleTime: 60_000,
    select: (d) => d.topics ?? [],
  });

  // Use local draft if user has made edits, else use server data
  const topics: string[] = localTopics ?? data ?? [];

  const saveMutation = useMutation({
    mutationFn: (t: string[]) => updateNewsTopics(t),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["news", "topics"] });
      setLocalTopics(null);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    },
  });

  function addTopic() {
    const t = newTopic.trim().toLowerCase();
    if (!t || topics.includes(t)) {
      setNewTopic("");
      return;
    }
    setLocalTopics([...topics, t]);
    setNewTopic("");
  }

  function removeTopic(t: string) {
    setLocalTopics(topics.filter((x) => x !== t));
  }

  function handleSave() {
    saveMutation.mutate(topics);
  }

  const isDirty = localTopics !== null;

  if (isLoading) {
    return (
      <div className="flex justify-center py-16">
        <Loader2 className="h-4 w-4 animate-spin" style={{ color: "var(--text-tertiary)" }} />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 h-full overflow-hidden">
      {isError && (
        <div
          className="flex items-center gap-2 rounded-xl border px-3 py-2 flex-shrink-0"
          style={{ borderColor: "var(--danger-500)", background: "var(--danger-50)" }}
        >
          <AlertCircle className="h-3.5 w-3.5 shrink-0" style={{ color: "var(--danger-500)" }} />
          <p className="text-xs" style={{ color: "var(--danger-600)" }}>Could not load topics.</p>
        </div>
      )}

      <p className="text-xs flex-shrink-0" style={{ color: "var(--text-tertiary)" }}>
        Subscribe to topics to prioritise relevant articles in your feed.
      </p>

      {/* Add topic */}
      <div className="flex gap-2 flex-shrink-0">
        <input
          type="text"
          placeholder="e.g. cybersecurity"
          value={newTopic}
          onChange={(e) => setNewTopic(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && addTopic()}
          className="flex-1 text-xs rounded-lg border px-3 py-2"
          style={{
            background: "var(--bg-input)",
            borderColor: "var(--border-default)",
            color: "var(--text-primary)",
          }}
        />
        <button
          onClick={addTopic}
          disabled={!newTopic.trim()}
          className="flex items-center gap-1 rounded-lg px-3 py-2 text-xs font-medium transition-opacity disabled:opacity-40"
          style={{ background: "var(--brand-500)", color: "white" }}
        >
          <Plus className="h-3 w-3" />
          Add
        </button>
      </div>

      {/* Topic chips */}
      <div className="flex-1 overflow-y-auto">
        {topics.length === 0 ? (
          <div
            className="flex flex-col items-center gap-2 py-12 rounded-xl border border-dashed"
            style={{ borderColor: "var(--border-subtle)" }}
          >
            <Tag className="h-6 w-6" style={{ color: "var(--text-tertiary)" }} />
            <p className="text-xs text-center" style={{ color: "var(--text-tertiary)" }}>
              No topics yet. Add topics above to personalise your news feed.
            </p>
          </div>
        ) : (
          <div className="flex flex-wrap gap-2">
            {topics.map((t) => (
              <span
                key={t}
                className="inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs"
                style={{ background: "var(--brand-50)", color: "var(--brand-600)" }}
              >
                {t}
                <button
                  onClick={() => removeTopic(t)}
                  className="rounded-full hover:opacity-70 transition-opacity"
                  aria-label={`Remove topic ${t}`}
                >
                  <X className="h-3 w-3" />
                </button>
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Save button */}
      <div className="flex items-center justify-between flex-shrink-0">
        {saved && (
          <p className="text-xs" style={{ color: "var(--success-500)" }}>
            Topics saved!
          </p>
        )}
        {!saved && <span />}
        <button
          onClick={handleSave}
          disabled={!isDirty || saveMutation.isPending}
          className="flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-medium transition-opacity disabled:opacity-40"
          style={{
            background: isDirty ? "var(--brand-500)" : "var(--bg-elevated)",
            color: isDirty ? "white" : "var(--text-tertiary)",
          }}
        >
          {saveMutation.isPending ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <Save className="h-3 w-3" />
          )}
          Save topics
        </button>
      </div>
    </div>
  );
});
