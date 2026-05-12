/**
 * Collaborative Annotation Layer (Feature 2)
 * Real-time annotations via polling (SSE upgrade path is ready on the backend).
 */
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { MessageSquarePlus, Pin, Loader2, AlertTriangle, Info, AlertCircle } from "lucide-react";
import { Badge } from "@/shared/components/Badge";
import { Button } from "@/shared/components/Button";
import { apiClient } from "@/shared/api/client";
import { toast } from "@/shared/components/Toast";
import { formatDistanceToNow } from "date-fns";

interface Annotation {
  id: string;
  investigation_id: string;
  target_type: string;
  target_id: string;
  content: string;
  severity: "info" | "low" | "medium" | "high" | "critical";
  pinned: boolean;
  author_id: string;
  created_at: string;
  updated_at: string;
}

interface AnnotationPanelProps {
  investigationId: string;
}

const SEVERITY_VARIANT: Record<string, "neutral" | "info" | "warning" | "danger"> = {
  info: "info",
  low: "neutral",
  medium: "warning",
  high: "danger",
  critical: "danger",
};

function SeverityIcon({ severity }: { severity: string }) {
  if (severity === "critical" || severity === "high")
    return <AlertTriangle className="h-3.5 w-3.5 shrink-0" style={{ color: "var(--danger-500)" }} />;
  if (severity === "medium")
    return <AlertCircle className="h-3.5 w-3.5 shrink-0" style={{ color: "var(--warning-500)" }} />;
  return <Info className="h-3.5 w-3.5 shrink-0" style={{ color: "var(--info-500)" }} />;
}

export function AnnotationPanel({ investigationId }: AnnotationPanelProps) {
  const queryClient = useQueryClient();
  const [content, setContent] = useState("");
  const [severity, setSeverity] = useState<Annotation["severity"]>("info");
  const [pinned, setPinned] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["annotations", investigationId],
    queryFn: async () => {
      const res = await apiClient.get(`/annotations/${investigationId}`);
      return res.data as { annotations: Annotation[]; total: number };
    },
    refetchInterval: 10_000, // Poll every 10s for real-time feel
  });

  const createMutation = useMutation({
    mutationFn: async () => {
      const res = await apiClient.post(`/annotations/${investigationId}`, {
        target_type: "investigation",
        target_id: investigationId,
        content,
        severity,
        pinned,
      });
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["annotations", investigationId] });
      setContent("");
      setPinned(false);
      toast.success("Annotation added");
    },
    onError: () => toast.error("Failed to add annotation"),
  });

  const annotations = data?.annotations ?? [];
  const pinnedAnnotations = annotations.filter((a) => a.pinned);
  const unpinnedAnnotations = annotations.filter((a) => !a.pinned);

  return (
    <div className="space-y-4">
      {/* New annotation form */}
      <div className="rounded-lg border p-3 space-y-2" style={{ borderColor: "var(--border-subtle)" }}>
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="Add a collaborative annotation…"
          rows={3}
          className="w-full rounded-md border px-3 py-2 text-sm resize-none"
          style={{ background: "var(--bg-elevated)", borderColor: "var(--border-default)", color: "var(--text-primary)" }}
        />
        <div className="flex items-center gap-2 flex-wrap">
          <select
            value={severity}
            onChange={(e) => setSeverity(e.target.value as Annotation["severity"])}
            className="rounded-md border px-2 py-1 text-xs"
            style={{ background: "var(--bg-elevated)", borderColor: "var(--border-default)", color: "var(--text-primary)" }}
          >
            {["info", "low", "medium", "high", "critical"].map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
          <button
            onClick={() => setPinned((p) => !p)}
            className={`flex items-center gap-1 rounded-md px-2 py-1 text-xs transition-colors ${pinned ? "bg-brand-900 text-brand-400" : "text-text-tertiary hover:bg-bg-overlay"}`}
          >
            <Pin className="h-3 w-3" />
            {pinned ? "Pinned" : "Pin"}
          </button>
          <div className="ml-auto">
            <Button
              size="sm"
              leftIcon={<MessageSquarePlus className="h-3.5 w-3.5" />}
              disabled={!content.trim()}
              loading={createMutation.isPending}
              onClick={() => createMutation.mutate()}
            >
              Add
            </Button>
          </div>
        </div>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-6">
          <Loader2 className="h-5 w-5 animate-spin" style={{ color: "var(--brand-500)" }} />
        </div>
      ) : (
        <>
          {/* Pinned annotations */}
          {pinnedAnnotations.length > 0 && (
            <div>
              <p className="text-xs font-semibold mb-2 flex items-center gap-1" style={{ color: "var(--brand-400)" }}>
                <Pin className="h-3 w-3" /> Pinned ({pinnedAnnotations.length})
              </p>
              <div className="space-y-2">
                {pinnedAnnotations.map((ann) => (
                  <AnnotationItem key={ann.id} annotation={ann} />
                ))}
              </div>
            </div>
          )}

          {/* Regular annotations */}
          <div>
            <p className="text-xs font-semibold mb-2" style={{ color: "var(--text-tertiary)" }}>
              All Annotations ({annotations.length})
            </p>
            {unpinnedAnnotations.length === 0 && annotations.length === 0 && (
              <p className="text-center text-xs py-4" style={{ color: "var(--text-tertiary)" }}>
                No annotations yet. Add one above to collaborate.
              </p>
            )}
            <div className="space-y-2">
              {unpinnedAnnotations.map((ann) => (
                <AnnotationItem key={ann.id} annotation={ann} />
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function AnnotationItem({ annotation: ann }: { annotation: Annotation }) {
  return (
    <div
      className="flex gap-2 rounded-md p-3"
      style={{
        background: "var(--bg-elevated)",
        borderLeft: ann.severity === "critical" ? "3px solid var(--danger-500)" :
                    ann.severity === "high" ? "3px solid var(--danger-400)" :
                    ann.severity === "medium" ? "3px solid var(--warning-500)" :
                    "3px solid var(--border-subtle)",
      }}
    >
      <SeverityIcon severity={ann.severity} />
      <div className="flex-1 min-w-0">
        <p className="text-sm" style={{ color: "var(--text-primary)" }}>{ann.content}</p>
        <div className="mt-1 flex items-center gap-2">
          <Badge variant={SEVERITY_VARIANT[ann.severity] ?? "neutral"} size="sm">{ann.severity}</Badge>
          {ann.pinned && <Pin className="h-3 w-3" style={{ color: "var(--brand-400)" }} />}
          <span className="text-[10px]" style={{ color: "var(--text-tertiary)" }}>
            {formatDistanceToNow(new Date(ann.created_at), { addSuffix: true })}
          </span>
        </div>
      </div>
    </div>
  );
}
