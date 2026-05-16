import { useEffect, useState, useCallback } from "react";
import { Activity, Database, Server, Cpu, BarChart2, RefreshCw } from "lucide-react";

interface ServiceHealth {
  name: string;
  status: "healthy" | "degraded" | "down";
  latency_ms: number | null;
  detail: string | null;
}

interface HealthDashboardData {
  overall_status: "healthy" | "degraded" | "down";
  services: ServiceHealth[];
  scanner_count: number;
  checked_at: string;
}

interface QueueDepth {
  queue_name: string;
  pending_tasks: number;
  is_congested: boolean;
}

interface QueueMonitorData {
  queues: QueueDepth[];
  total_pending: number;
  congested_queues: string[];
  worker_status: "healthy" | "congested";
}

interface CacheStatsData {
  hit_rate: number;
  total_hits: number;
  total_misses: number;
  scanner_cache_keys: number;
  memory_used: string;
  total_commands: number;
}

const AUTO_REFRESH_INTERVAL_MS = 30_000;

function statusColor(status: string): string {
  switch (status) {
    case "healthy":
      return "text-green-400";
    case "degraded":
      return "text-yellow-400";
    case "down":
      return "text-red-400";
    default:
      return "text-text-secondary";
  }
}

function statusBg(status: string): string {
  switch (status) {
    case "healthy":
      return "bg-green-500/10 border-green-500/30";
    case "degraded":
      return "bg-yellow-500/10 border-yellow-500/30";
    case "down":
      return "bg-red-500/10 border-red-500/30";
    default:
      return "bg-bg-overlay border-border-subtle";
  }
}

function serviceIcon(name: string): React.ReactElement {
  switch (name) {
    case "postgresql":
      return <Database className="h-5 w-5" />;
    case "redis":
      return <Server className="h-5 w-5" />;
    case "neo4j":
      return <Cpu className="h-5 w-5" />;
    case "scanner_registry":
      return <Activity className="h-5 w-5" />;
    default:
      return <Server className="h-5 w-5" />;
  }
}

export function SystemHealthPage(): React.ReactElement {
  const [healthData, setHealthData] = useState<HealthDashboardData | null>(null);
  const [queueData, setQueueData] = useState<QueueMonitorData | null>(null);
  const [cacheData, setCacheData] = useState<CacheStatsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);
  const [errors, setErrors] = useState<string[]>([]);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    const errs: string[] = [];

    const [healthRes, queueRes, cacheRes] = await Promise.allSettled([
      fetch("/api/v1/health/dashboard"),
      fetch("/api/v1/workers/queue-depth", {
        headers: { Authorization: `Bearer ${localStorage.getItem("access_token") ?? ""}` },
      }),
      fetch("/api/v1/cache/stats", {
        headers: { Authorization: `Bearer ${localStorage.getItem("access_token") ?? ""}` },
      }),
    ]);

    if (healthRes.status === "fulfilled" && healthRes.value.ok) {
      setHealthData((await healthRes.value.json()) as HealthDashboardData);
    } else {
      errs.push("Health dashboard unavailable");
    }

    if (queueRes.status === "fulfilled" && queueRes.value.ok) {
      setQueueData((await queueRes.value.json()) as QueueMonitorData);
    } else {
      errs.push("Queue monitor unavailable");
    }

    if (cacheRes.status === "fulfilled" && cacheRes.value.ok) {
      setCacheData((await cacheRes.value.json()) as CacheStatsData);
    } else {
      errs.push("Cache stats unavailable");
    }

    setErrors(errs);
    setLastRefreshed(new Date());
    setLoading(false);
  }, []);

  useEffect(() => {
    void fetchAll();
    const interval = setInterval(() => void fetchAll(), AUTO_REFRESH_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [fetchAll]);

  const overallStatus = healthData?.overall_status ?? "down";

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Activity className="h-6 w-6" style={{ color: "var(--brand-500)" }} />
          <h1 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>
            System Health
          </h1>
          {healthData && (
            <span
              className={`rounded-full px-3 py-0.5 text-xs font-semibold border capitalize ${statusBg(overallStatus)} ${statusColor(overallStatus)}`}
            >
              {overallStatus}
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          {lastRefreshed && (
            <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>
              Last refreshed {lastRefreshed.toLocaleTimeString()}
            </span>
          )}
          <button
            onClick={() => void fetchAll()}
            disabled={loading}
            className="flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors hover:bg-bg-overlay disabled:opacity-50"
            style={{ color: "var(--text-secondary)", border: "1px solid var(--border-subtle)" }}
            aria-label="Refresh health data"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>
      </div>

      {errors.length > 0 && (
        <div
          className="rounded-md border px-4 py-3 text-sm"
          style={{ borderColor: "var(--warning-500)", color: "var(--warning-500)", background: "var(--warning-500)10" }}
        >
          {errors.join(" · ")}
        </div>
      )}

      {/* Service cards */}
      <section aria-labelledby="services-heading">
        <h2
          id="services-heading"
          className="mb-3 text-sm font-semibold uppercase tracking-wide"
          style={{ color: "var(--text-tertiary)" }}
        >
          Services
        </h2>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {loading && !healthData
            ? Array.from({ length: 4 }).map((_, i) => (
                <div
                  key={i}
                  className="animate-pulse rounded-lg border p-4 h-24"
                  style={{ background: "var(--bg-overlay)", borderColor: "var(--border-subtle)" }}
                />
              ))
            : healthData?.services.map((svc) => (
                <div
                  key={svc.name}
                  className={`rounded-lg border p-4 space-y-2 ${statusBg(svc.status)}`}
                >
                  <div className={`flex items-center gap-2 ${statusColor(svc.status)}`}>
                    {serviceIcon(svc.name)}
                    <span className="text-sm font-semibold capitalize">
                      {svc.name.replace(/_/g, " ")}
                    </span>
                  </div>
                  <div>
                    <span className={`text-xs font-bold uppercase ${statusColor(svc.status)}`}>
                      {svc.status}
                    </span>
                    {svc.latency_ms !== null && (
                      <span className="ml-2 text-xs" style={{ color: "var(--text-tertiary)" }}>
                        {svc.latency_ms}ms
                      </span>
                    )}
                  </div>
                  {svc.detail && (
                    <p className="text-xs truncate" style={{ color: "var(--text-tertiary)" }} title={svc.detail}>
                      {svc.detail}
                    </p>
                  )}
                </div>
              ))}
        </div>
        {healthData && (
          <p className="mt-2 text-xs" style={{ color: "var(--text-tertiary)" }}>
            {healthData.scanner_count} scanners registered · checked at{" "}
            {new Date(healthData.checked_at).toLocaleTimeString()}
          </p>
        )}
      </section>

      {/* Queue depth table */}
      <section aria-labelledby="queues-heading">
        <h2
          id="queues-heading"
          className="mb-3 text-sm font-semibold uppercase tracking-wide"
          style={{ color: "var(--text-tertiary)" }}
        >
          Worker Queues
        </h2>
        <div
          className="rounded-lg border overflow-hidden"
          style={{ borderColor: "var(--border-subtle)", background: "var(--bg-surface)" }}
        >
          {loading && !queueData ? (
            <div className="animate-pulse h-32" style={{ background: "var(--bg-overlay)" }} />
          ) : queueData ? (
            <>
              <div className="flex items-center justify-between px-4 py-2 border-b" style={{ borderColor: "var(--border-subtle)" }}>
                <span className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                  Total pending: {queueData.total_pending}
                </span>
                <span
                  className={`text-xs font-semibold uppercase ${queueData.worker_status === "healthy" ? "text-green-400" : "text-red-400"}`}
                >
                  {queueData.worker_status}
                </span>
              </div>
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                    {["Queue", "Pending", "Status"].map((h) => (
                      <th
                        key={h}
                        className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wide"
                        style={{ color: "var(--text-tertiary)" }}
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {queueData.queues.map((q) => (
                    <tr
                      key={q.queue_name}
                      className="border-b last:border-0"
                      style={{ borderColor: "var(--border-subtle)" }}
                    >
                      <td className="px-4 py-2 font-mono text-xs" style={{ color: "var(--text-primary)" }}>
                        {q.queue_name}
                      </td>
                      <td className="px-4 py-2" style={{ color: "var(--text-primary)" }}>
                        {q.pending_tasks}
                      </td>
                      <td className="px-4 py-2">
                        {q.is_congested ? (
                          <span className="rounded-full bg-red-500/10 border border-red-500/30 px-2 py-0.5 text-xs text-red-400">
                            congested
                          </span>
                        ) : (
                          <span className="rounded-full bg-green-500/10 border border-green-500/30 px-2 py-0.5 text-xs text-green-400">
                            ok
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          ) : (
            <p className="px-4 py-6 text-sm text-center" style={{ color: "var(--text-tertiary)" }}>
              Queue data unavailable
            </p>
          )}
        </div>
      </section>

      {/* Cache stats */}
      <section aria-labelledby="cache-heading">
        <h2
          id="cache-heading"
          className="mb-3 text-sm font-semibold uppercase tracking-wide"
          style={{ color: "var(--text-tertiary)" }}
        >
          Cache Statistics
        </h2>
        {loading && !cacheData ? (
          <div
            className="animate-pulse rounded-lg border h-28"
            style={{ background: "var(--bg-overlay)", borderColor: "var(--border-subtle)" }}
          />
        ) : cacheData ? (
          <div
            className="rounded-lg border p-4 space-y-4"
            style={{ borderColor: "var(--border-subtle)", background: "var(--bg-surface)" }}
          >
            <div className="space-y-1">
              <div className="flex justify-between text-sm">
                <span style={{ color: "var(--text-secondary)" }}>Hit rate</span>
                <span className="font-semibold" style={{ color: "var(--text-primary)" }}>
                  {(cacheData.hit_rate * 100).toFixed(1)}%
                </span>
              </div>
              <div className="h-2 rounded-full overflow-hidden" style={{ background: "var(--bg-overlay)" }}>
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{
                    width: `${Math.min(100, cacheData.hit_rate * 100).toFixed(1)}%`,
                    background: cacheData.hit_rate >= 0.7 ? "var(--brand-500)" : "var(--warning-500)",
                  }}
                  role="progressbar"
                  aria-valuenow={Math.round(cacheData.hit_rate * 100)}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-label="Cache hit rate"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 text-sm">
              <div>
                <p style={{ color: "var(--text-tertiary)" }} className="text-xs">Hits</p>
                <p className="font-semibold" style={{ color: "var(--text-primary)" }}>
                  {cacheData.total_hits.toLocaleString()}
                </p>
              </div>
              <div>
                <p style={{ color: "var(--text-tertiary)" }} className="text-xs">Misses</p>
                <p className="font-semibold" style={{ color: "var(--text-primary)" }}>
                  {cacheData.total_misses.toLocaleString()}
                </p>
              </div>
              <div>
                <p style={{ color: "var(--text-tertiary)" }} className="text-xs">Scanner Keys</p>
                <p className="font-semibold" style={{ color: "var(--text-primary)" }}>
                  {cacheData.scanner_cache_keys.toLocaleString()}
                </p>
              </div>
              <div>
                <p style={{ color: "var(--text-tertiary)" }} className="text-xs">Memory Used</p>
                <p className="font-semibold" style={{ color: "var(--text-primary)" }}>
                  {cacheData.memory_used}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2 text-xs" style={{ color: "var(--text-tertiary)" }}>
              <BarChart2 className="h-3.5 w-3.5" />
              <span>{cacheData.total_commands.toLocaleString()} total commands processed</span>
            </div>
          </div>
        ) : (
          <p className="text-sm" style={{ color: "var(--text-tertiary)" }}>
            Cache stats unavailable (Redis may be down)
          </p>
        )}
      </section>
    </div>
  );
}
