/**
 * TaskList — displays and manages productivity tasks from the Hub task agent.
 *
 * Fetches from GET /api/v1/hub/productivity-tasks via TanStack Query.
 * Memoised: re-renders only on task data change.
 */

import { memo, useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckSquare, Circle, Clock, AlertCircle, Plus } from "lucide-react";
import apiClient from "@/shared/api/client";

interface Task {
  id: string;
  title: string;
  description: string | null;
  priority: number;
  status: string;
  due_at: string | null;
  source: string;
  created_at: string;
}

const PRIORITY_COLORS: Record<number, string> = {
  1: "var(--danger-500)",
  2: "var(--warning-500)",
  3: "var(--brand-400)",
  4: "var(--text-tertiary)",
  5: "var(--text-tertiary)",
};

const STATUS_ICON: Record<string, React.ElementType> = {
  todo: Circle,
  in_progress: Clock,
  done: CheckSquare,
  deferred: Clock,
  cancelled: AlertCircle,
};

async function fetchTasks(status?: string): Promise<{ tasks: Task[]; total: number }> {
  const params = status ? `?status=${status}` : "";
  const { data } = await apiClient.get(`/hub/productivity-tasks${params}`);
  return data;
}

async function createTask(title: string): Promise<Task> {
  const { data } = await apiClient.post("/hub/productivity-tasks", { title });
  return data;
}

async function cancelTask(taskId: string): Promise<void> {
  await apiClient.delete(`/hub/productivity-tasks/${taskId}`);
}

export const TaskList = memo(function TaskList() {
  const { t } = useTranslation("tasks");
  const labelId = useId();
  const [filter, setFilter] = useState<string | undefined>(undefined);
  const [newTitle, setNewTitle] = useState("");
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["hub", "productivity-tasks", filter],
    queryFn: () => fetchTasks(filter),
    staleTime: 30_000,
  });

  const createMutation = useMutation({
    mutationFn: createTask,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["hub", "productivity-tasks"] });
      setNewTitle("");
    },
  });

  const cancelMutation = useMutation({
    mutationFn: cancelTask,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["hub", "productivity-tasks"] });
    },
  });

  function handleCreate() {
    if (newTitle.trim()) createMutation.mutate(newTitle.trim());
  }

  const tasks = data?.tasks ?? [];

  return (
    <section aria-labelledby={labelId} className="flex flex-col gap-4">
      <h3
        id={labelId}
        className="text-sm font-semibold uppercase tracking-wide"
        style={{ color: "var(--text-tertiary)" }}
      >
        {t("title")}
      </h3>

      {/* Quick create */}
      <div className="flex gap-2">
        <input
          type="text"
          value={newTitle}
          onChange={(e) => setNewTitle(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") handleCreate(); }}
          placeholder={t("new_task")}
          className="flex-1 rounded-lg border px-3 py-2 text-sm outline-none"
          style={{
            background: "var(--bg-surface)",
            borderColor: "var(--border-default)",
            color: "var(--text-primary)",
          }}
          aria-label={t("new_task")}
        />
        <button
          type="button"
          onClick={handleCreate}
          disabled={!newTitle.trim() || createMutation.isPending}
          aria-label={t("create")}
          className="flex h-9 w-9 items-center justify-center rounded-lg transition-all hover:scale-105 disabled:opacity-40"
          style={{ background: "var(--brand-500)", color: "white" }}
        >
          <Plus className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>

      {/* Filter strip */}
      <div className="flex gap-1 text-xs">
        {[undefined, "todo", "in_progress", "done"].map((s) => (
          <button
            key={s ?? "all"}
            type="button"
            onClick={() => setFilter(s)}
            className={`rounded-md px-2.5 py-1 transition-colors ${
              filter === s ? "font-semibold" : "opacity-60 hover:opacity-100"
            }`}
            style={
              filter === s
                ? { background: "var(--bg-overlay)", color: "var(--brand-400)" }
                : { color: "var(--text-secondary)" }
            }
          >
            {s ? t(`status_${s}`) : "All"}
          </button>
        ))}
      </div>

      {/* Task list */}
      {isLoading && (
        <p className="text-sm" style={{ color: "var(--text-tertiary)" }}>
          {t("loading", { ns: "common" })}
        </p>
      )}
      {!isLoading && tasks.length === 0 && (
        <p className="text-sm italic" style={{ color: "var(--text-tertiary)" }}>
          {t("no_tasks")}
        </p>
      )}
      <ol className="space-y-2">
        {tasks.map((task) => {
          const Icon = STATUS_ICON[task.status] ?? Circle;
          return (
            <li
              key={task.id}
              className="flex items-center gap-3 rounded-lg border px-3 py-2.5"
              style={{
                background: "var(--bg-surface)",
                borderColor: "var(--border-subtle)",
              }}
            >
              <Icon
                className="h-4 w-4 shrink-0"
                style={{ color: PRIORITY_COLORS[task.priority] ?? "var(--text-tertiary)" }}
                aria-hidden="true"
              />
              <div className="flex-1 min-w-0">
                <p
                  className={`truncate text-sm font-medium ${
                    task.status === "done" || task.status === "cancelled"
                      ? "line-through opacity-50"
                      : ""
                  }`}
                  style={{ color: "var(--text-primary)" }}
                >
                  {task.title}
                </p>
                {task.due_at && (
                  <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                    {t("due")}: {new Date(task.due_at).toLocaleDateString()}
                  </p>
                )}
              </div>
              {task.status !== "cancelled" && task.status !== "done" && (
                <button
                  type="button"
                  onClick={() => cancelMutation.mutate(task.id)}
                  disabled={cancelMutation.isPending}
                  aria-label={t("delete", { ns: "common" })}
                  className="shrink-0 rounded p-1 text-xs opacity-0 transition-opacity group-hover:opacity-100 hover:opacity-100"
                  style={{ color: "var(--danger-500)" }}
                >
                  ✕
                </button>
              )}
            </li>
          );
        })}
      </ol>
    </section>
  );
});
