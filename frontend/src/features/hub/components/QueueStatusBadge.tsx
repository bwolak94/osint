/**
 * QueueStatusBadge — compact Celery worker status indicator.
 * Shows active + queued task counts. Refreshes every 30s.
 */

import { memo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Activity, Loader2 } from "lucide-react";
import { getQueueStatus } from "../api";

interface QueueStatus {
  active_tasks: number;
  queued_tasks: number;
  workers: string[];
}

export const QueueStatusBadge = memo(function QueueStatusBadge() {
  const { data, isLoading, isError } = useQuery<QueueStatus>({
    queryKey: ["hub", "queue-status"],
    queryFn: () => getQueueStatus() as unknown as Promise<QueueStatus>,
    refetchInterval: 30_000,
    staleTime: 15_000,
    retry: false,
  });

  if (isLoading) {
    return (
      <div
        className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs"
        style={{ background: "var(--bg-elevated)", color: "var(--text-tertiary)" }}
      >
        <Loader2 className="h-2.5 w-2.5 animate-spin" />
        workers
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div
        className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs"
        style={{ background: "var(--bg-elevated)", color: "var(--text-tertiary)" }}
        title="Could not reach workers"
      >
        <span
          className="inline-block h-1.5 w-1.5 rounded-full"
          style={{ background: "var(--text-tertiary)" }}
        />
        offline
      </div>
    );
  }

  const total = data.active_tasks + data.queued_tasks;
  const isBusy = data.active_tasks > 0;

  return (
    <div
      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs"
      style={{
        background: isBusy ? "var(--brand-50)" : "var(--bg-elevated)",
        color: isBusy ? "var(--brand-600)" : "var(--text-tertiary)",
      }}
      title={`${data.workers.length} worker${data.workers.length !== 1 ? "s" : ""} online`}
    >
      <Activity className="h-3 w-3" aria-hidden="true" />
      <span>
        {data.workers.length}w ·{" "}
        {isBusy ? (
          <>
            <span
              className="inline-block h-1.5 w-1.5 rounded-full animate-pulse"
              style={{ background: "var(--brand-500)" }}
            />{" "}
            {total} task{total !== 1 ? "s" : ""}
          </>
        ) : (
          "idle"
        )}
      </span>
    </div>
  );
});
