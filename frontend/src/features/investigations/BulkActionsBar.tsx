import { Archive, Trash2, Download, Play, Pause, Share2 } from "lucide-react";
import { apiClient } from "@/shared/api/client";
import { useMutation, useQueryClient } from "@tanstack/react-query";

interface BulkActionsBarProps {
  selectedIds: string[];
  onClearSelection: () => void;
}

export function BulkActionsBar({ selectedIds, onClearSelection }: BulkActionsBarProps) {
  const queryClient = useQueryClient();

  const bulkAction = useMutation({
    mutationFn: async ({ action, params }: { action: string; params?: Record<string, unknown> }) => {
      const resp = await apiClient.post("/investigations/bulk-action", {
        investigation_ids: selectedIds,
        action,
        params: params || {},
      });
      return resp.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["investigations"] });
      onClearSelection();
    },
  });

  if (selectedIds.length === 0) return null;

  const actions = [
    { action: "start", icon: Play, label: "Start", color: "var(--success-500)" },
    { action: "pause", icon: Pause, label: "Pause", color: "var(--warning-500)" },
    { action: "archive", icon: Archive, label: "Archive", color: "var(--text-secondary)" },
    { action: "export", icon: Download, label: "Export", color: "var(--info-500)" },
    { action: "share", icon: Share2, label: "Share", color: "var(--brand-400)" },
    { action: "delete", icon: Trash2, label: "Delete", color: "var(--danger-500)" },
  ];

  return (
    <div
      className="fixed bottom-6 left-1/2 z-50 flex -translate-x-1/2 items-center gap-2 rounded-lg border px-4 py-3 shadow-xl"
      style={{ background: "var(--bg-elevated)", borderColor: "var(--border-default)" }}
    >
      <span className="mr-2 text-sm font-medium" style={{ color: "var(--text-primary)" }}>
        {selectedIds.length} selected
      </span>

      {actions.map(({ action, icon: Icon, label, color }) => (
        <button
          key={action}
          onClick={() => bulkAction.mutate({ action })}
          disabled={bulkAction.isPending}
          className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors hover:bg-bg-overlay"
          style={{ color }}
          title={label}
        >
          <Icon className="h-3.5 w-3.5" />
          {label}
        </button>
      ))}

      <button
        onClick={onClearSelection}
        className="ml-2 text-xs underline"
        style={{ color: "var(--text-tertiary)" }}
      >
        Clear
      </button>
    </div>
  );
}
