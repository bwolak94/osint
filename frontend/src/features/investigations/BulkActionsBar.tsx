import { useCallback, useEffect, useRef, useState } from "react";
import { Archive, Trash2, Download, Play, Pause, Share2, Undo2, X, AlertTriangle } from "lucide-react";
import { apiClient } from "@/shared/api/client";
import { useMutation, useQueryClient } from "@tanstack/react-query";

interface BulkActionsBarProps {
  selectedIds: string[];
  onClearSelection: () => void;
}

interface UndoState {
  action: string;
  ids: string[];
}

const DESTRUCTIVE_ACTIONS = new Set(["delete", "archive"]);

interface ConfirmState {
  action: string;
  count: number;
}

export function BulkActionsBar({ selectedIds, onClearSelection }: BulkActionsBarProps) {
  const queryClient = useQueryClient();
  const [undoState, setUndoState] = useState<UndoState | null>(null);
  const [undoCountdown, setUndoCountdown] = useState(0);
  const countdownRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [confirmState, setConfirmState] = useState<ConfirmState | null>(null);

  const bulkAction = useMutation({
    mutationFn: async ({ action, params }: { action: string; params?: Record<string, unknown> }) => {
      const resp = await apiClient.post("/investigations/bulk-action", {
        investigation_ids: selectedIds,
        action,
        params: params ?? {},
      });
      return resp.data;
    },
    onSuccess: (_, { action }) => {
      if (action === "delete" || action === "archive") {
        // Optimistically invalidate immediately but offer a 30s undo window
        queryClient.invalidateQueries({ queryKey: ["investigations"] });
        startUndoCountdown(action, [...selectedIds]);
      } else {
        queryClient.invalidateQueries({ queryKey: ["investigations"] });
      }
      onClearSelection();
    },
  });

  const undoMutation = useMutation({
    mutationFn: async ({ action, ids }: { action: string; ids: string[] }) => {
      const reverseAction = action === "delete" ? "restore" : "unarchive";
      const resp = await apiClient.post("/investigations/bulk-action", {
        investigation_ids: ids,
        action: reverseAction,
        params: {},
      });
      return resp.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["investigations"] });
      dismissUndo();
    },
  });

  const UNDO_WINDOW = 30;

  const dismissUndo = useCallback(() => {
    if (countdownRef.current) {
      clearInterval(countdownRef.current);
      countdownRef.current = null;
    }
    setUndoState(null);
    setUndoCountdown(0);
  }, []);

  function startUndoCountdown(action: string, ids: string[]) {
    if (countdownRef.current) clearInterval(countdownRef.current);
    setUndoCountdown(UNDO_WINDOW);
    setUndoState({ action, ids });

    // Single interval drives both the countdown display and the auto-dismiss.
    // No separate setTimeout needed — eliminates the double-timer bug.
    countdownRef.current = setInterval(() => {
      setUndoCountdown((prev) => {
        if (prev <= 1) {
          dismissUndo();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  }

  // Clean up interval on unmount
  useEffect(() => () => { if (countdownRef.current) clearInterval(countdownRef.current); }, []);

  // Escape key clears the bulk selection
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape" && selectedIds.length > 0) {
        onClearSelection();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [selectedIds, onClearSelection]);

  if (selectedIds.length === 0 && !undoState) return null;

  const handleActionClick = (action: string) => {
    if (DESTRUCTIVE_ACTIONS.has(action)) {
      setConfirmState({ action, count: selectedIds.length });
    } else {
      bulkAction.mutate({ action });
    }
  };

  const handleConfirm = () => {
    if (!confirmState) return;
    bulkAction.mutate({ action: confirmState.action });
    setConfirmState(null);
  };

  const actions = [
    { action: "start", icon: Play, label: "Start", color: "var(--success-500)" },
    { action: "pause", icon: Pause, label: "Pause", color: "var(--warning-500)" },
    { action: "archive", icon: Archive, label: "Archive", color: "var(--text-secondary)" },
    { action: "export", icon: Download, label: "Export", color: "var(--info-500)" },
    { action: "share", icon: Share2, label: "Share", color: "var(--brand-400)" },
    { action: "delete", icon: Trash2, label: "Delete", color: "var(--danger-500)" },
  ];

  return (
    <>
      {/* Confirm dialog for destructive actions */}
      {confirmState && (
        <div
          className="fixed inset-0 z-60 flex items-center justify-center bg-black/50"
          role="dialog"
          aria-modal="true"
          aria-labelledby="confirm-dialog-title"
        >
          <div
            className="w-full max-w-sm rounded-xl border p-6 shadow-2xl"
            style={{ background: "var(--bg-surface)", borderColor: "var(--border-default)" }}
          >
            <div className="flex items-center gap-3 mb-3">
              <AlertTriangle className="h-5 w-5 shrink-0" style={{ color: "var(--danger-500)" }} />
              <h2 id="confirm-dialog-title" className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                Confirm {confirmState.action === "delete" ? "Delete" : "Archive"}
              </h2>
            </div>
            <p className="text-sm mb-5" style={{ color: "var(--text-secondary)" }}>
              {confirmState.action === "delete"
                ? `Permanently delete ${confirmState.count} investigation${confirmState.count !== 1 ? "s" : ""}? This cannot be undone.`
                : `Archive ${confirmState.count} investigation${confirmState.count !== 1 ? "s" : ""}?`}
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setConfirmState(null)}
                className="rounded-md px-3 py-1.5 text-xs font-medium transition-colors hover:bg-bg-overlay"
                style={{ color: "var(--text-secondary)" }}
              >
                Cancel
              </button>
              <button
                onClick={handleConfirm}
                className="rounded-md px-3 py-1.5 text-xs font-semibold transition-colors"
                style={{
                  background: confirmState.action === "delete" ? "var(--danger-500)" : "var(--bg-overlay)",
                  color: confirmState.action === "delete" ? "#fff" : "var(--text-primary)",
                }}
              >
                {confirmState.action === "delete" ? "Delete" : "Archive"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Undo toast */}
      {undoState && (
        <div
          className="fixed bottom-20 left-1/2 z-50 flex -translate-x-1/2 items-center gap-3 rounded-lg border px-4 py-3 shadow-xl"
          style={{ background: "var(--bg-elevated)", borderColor: "var(--border-default)" }}
          role="status"
          aria-live="polite"
        >
          <span className="text-sm" style={{ color: "var(--text-primary)" }}>
            {undoState.action === "delete"
              ? `${undoState.ids.length} investigation(s) deleted`
              : `${undoState.ids.length} investigation(s) archived`}
          </span>
          <button
            onClick={() => undoMutation.mutate({ action: undoState.action, ids: undoState.ids })}
            className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-semibold transition-colors hover:bg-bg-overlay"
            style={{ color: "var(--brand-400)" }}
            aria-label="Undo last bulk action"
          >
            <Undo2 className="h-3.5 w-3.5" />
            Undo ({undoCountdown}s)
          </button>
          <button
            onClick={dismissUndo}
            className="rounded p-1 transition-colors hover:bg-bg-overlay"
            aria-label="Dismiss undo notification"
            style={{ color: "var(--text-tertiary)" }}
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {/* Main bar */}
      {selectedIds.length > 0 && (
        <div
          className="fixed bottom-6 left-1/2 z-50 flex -translate-x-1/2 items-center gap-2 rounded-lg border px-4 py-3 shadow-xl"
          style={{ background: "var(--bg-elevated)", borderColor: "var(--border-default)" }}
          role="toolbar"
          aria-label="Bulk actions"
        >
          <span className="mr-2 text-sm font-medium" style={{ color: "var(--text-primary)" }}>
            {selectedIds.length} selected
          </span>

          {actions.map(({ action, icon: Icon, label, color }) => (
            <button
              key={action}
              onClick={() => handleActionClick(action)}
              disabled={bulkAction.isPending}
              className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors hover:bg-bg-overlay disabled:opacity-50"
              style={{ color }}
              title={label}
              aria-label={`${label} selected investigations`}
            >
              <Icon className="h-3.5 w-3.5" />
              {label}
            </button>
          ))}

          <button
            onClick={onClearSelection}
            className="ml-2 text-xs underline"
            style={{ color: "var(--text-tertiary)" }}
            aria-label="Clear selection"
          >
            Clear
          </button>
        </div>
      )}
    </>
  );
}
