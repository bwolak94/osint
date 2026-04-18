import { useState, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertCircle, RefreshCw } from "lucide-react";
import { formatDistanceToNow, parseISO } from "date-fns";
import { Button } from "@/shared/components/Button";
import { Badge } from "@/shared/components/Badge";
import apiClient from "@/shared/api/client";

export interface ActivityEntry {
  id: string;
  action: string;
  user_name: string;
  user_avatar?: string;
  entity_type?: string;
  entity_value?: string;
  details: Record<string, unknown>;
  created_at: string;
}

interface ActivityFeedResponse {
  items: ActivityEntry[];
  total: number;
  has_more: boolean;
}

interface ActivityFeedProps {
  investigationId: string;
}

const ACTION_LABELS: Record<string, string> = {
  node_added: "added node",
  scan_started: "started scan",
  scan_completed: "completed scan",
  comment_posted: "commented",
  investigation_forked: "forked investigation",
  annotation_added: "annotated",
};

const ACTION_BADGE_VARIANT: Record<
  string,
  "success" | "info" | "warning" | "neutral" | "brand"
> = {
  node_added: "success",
  scan_started: "info",
  scan_completed: "success",
  comment_posted: "neutral",
  investigation_forked: "brand",
  annotation_added: "info",
};

const PAGE_SIZE = 20;

async function fetchActivity(
  investigationId: string,
  page: number,
): Promise<ActivityFeedResponse> {
  const { data } = await apiClient.get<ActivityFeedResponse>(
    `/investigations/${investigationId}/activity`,
    { params: { page, limit: PAGE_SIZE } },
  );
  return data;
}

function ActivitySkeleton() {
  return (
    <div className="space-y-3 animate-pulse">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="flex items-start gap-3 py-2">
          <div
            className="h-7 w-7 shrink-0 rounded-full"
            style={{ background: "var(--bg-overlay)" }}
          />
          <div className="flex-1 space-y-1.5">
            <div
              className="h-3 w-3/4 rounded"
              style={{ background: "var(--bg-overlay)" }}
            />
            <div
              className="h-2.5 w-1/3 rounded"
              style={{ background: "var(--bg-overlay)" }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

function UserAvatar({
  name,
  avatarUrl,
}: {
  name: string;
  avatarUrl?: string;
}) {
  const initials = name
    .split(" ")
    .map((p) => p[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);

  if (avatarUrl) {
    return (
      <img
        src={avatarUrl}
        alt={name}
        className="h-7 w-7 shrink-0 rounded-full object-cover"
      />
    );
  }

  return (
    <div
      className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[10px] font-bold"
      style={{ background: "var(--brand-500)", color: "white" }}
      aria-label={name}
    >
      {initials}
    </div>
  );
}

export function ActivityFeed({ investigationId }: ActivityFeedProps) {
  const [page, setPage] = useState(1);
  const [allItems, setAllItems] = useState<ActivityEntry[]>([]);

  const { data, isLoading, isFetching, error, refetch } = useQuery({
    queryKey: ["investigation-activity", investigationId, page],
    queryFn: async () => {
      const result = await fetchActivity(investigationId, page);
      if (page === 1) {
        setAllItems(result.items);
      } else {
        setAllItems((prev) => {
          const existingIds = new Set(prev.map((i) => i.id));
          const newItems = result.items.filter((i) => !existingIds.has(i.id));
          return [...prev, ...newItems];
        });
      }
      return result;
    },
    refetchInterval: 30_000,
    staleTime: 25_000,
  });

  const handleLoadMore = useCallback(() => {
    setPage((p) => p + 1);
  }, []);

  const handleRefresh = useCallback(() => {
    setPage(1);
    setAllItems([]);
    refetch();
  }, [refetch]);

  return (
    <div
      className="flex flex-col rounded-xl border"
      style={{
        borderColor: "var(--border-default)",
        background: "var(--bg-surface)",
      }}
      aria-label="Activity feed"
    >
      {/* Header */}
      <div
        className="flex items-center justify-between border-b px-4 py-3"
        style={{ borderColor: "var(--border-subtle)" }}
      >
        <h3
          className="text-sm font-semibold"
          style={{ color: "var(--text-primary)" }}
        >
          Activity
        </h3>
        <button
          onClick={handleRefresh}
          aria-label="Refresh activity"
          disabled={isFetching}
          className="rounded-md p-1 transition-colors hover:bg-bg-overlay disabled:opacity-50"
        >
          <RefreshCw
            className={`h-3.5 w-3.5 ${isFetching ? "animate-spin" : ""}`}
            style={{ color: "var(--text-tertiary)" }}
          />
        </button>
      </div>

      {/* Feed */}
      <div className="flex-1 overflow-y-auto px-4 py-3">
        {isLoading && page === 1 ? (
          <ActivitySkeleton />
        ) : error ? (
          <div
            className="flex items-center gap-2 rounded-md border px-3 py-2"
            style={{
              borderColor: "var(--border-default)",
              background: "var(--bg-elevated)",
            }}
          >
            <AlertCircle
              className="h-4 w-4 shrink-0"
              style={{ color: "var(--danger-500, #ef4444)" }}
            />
            <p className="text-xs" style={{ color: "var(--danger-500, #ef4444)" }}>
              Failed to load activity
            </p>
            <button
              onClick={handleRefresh}
              className="ml-auto text-xs underline"
              style={{ color: "var(--brand-500)" }}
            >
              Retry
            </button>
          </div>
        ) : allItems.length === 0 ? (
          <p
            className="py-6 text-center text-sm"
            style={{ color: "var(--text-tertiary)" }}
          >
            No activity yet
          </p>
        ) : (
          <ul className="space-y-0.5" role="feed" aria-label="Activity entries">
            {allItems.map((entry) => {
              const actionLabel =
                ACTION_LABELS[entry.action] ?? entry.action.replace(/_/g, " ");
              const badgeVariant =
                ACTION_BADGE_VARIANT[entry.action] ?? "neutral";

              return (
                <li
                  key={entry.id}
                  className="flex items-start gap-3 rounded-md px-2 py-2 transition-colors hover:bg-bg-elevated"
                  role="article"
                  aria-label={`${entry.user_name} ${actionLabel}`}
                >
                  <UserAvatar
                    name={entry.user_name}
                    avatarUrl={entry.user_avatar}
                  />
                  <div className="flex-1 min-w-0">
                    <p
                      className="text-xs leading-relaxed"
                      style={{ color: "var(--text-secondary)" }}
                    >
                      <span
                        className="font-semibold"
                        style={{ color: "var(--text-primary)" }}
                      >
                        {entry.user_name}
                      </span>{" "}
                      <span>{actionLabel}</span>
                      {entry.entity_type && entry.entity_value && (
                        <>
                          {" "}
                          <span
                            className="font-mono text-[11px]"
                            style={{ color: "var(--text-primary)" }}
                          >
                            {entry.entity_type}:{entry.entity_value}
                          </span>
                        </>
                      )}
                    </p>
                    <div className="mt-1 flex items-center gap-2">
                      <Badge variant={badgeVariant} size="sm">
                        {actionLabel}
                      </Badge>
                      <time
                        dateTime={entry.created_at}
                        className="text-[10px]"
                        style={{ color: "var(--text-tertiary)" }}
                        title={entry.created_at}
                      >
                        {formatDistanceToNow(parseISO(entry.created_at), {
                          addSuffix: true,
                        })}
                      </time>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}

        {/* Load more */}
        {data?.has_more && (
          <div className="mt-3 flex justify-center">
            <Button
              variant="ghost"
              size="sm"
              onClick={handleLoadMore}
              loading={isFetching && page > 1}
            >
              Load more
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
