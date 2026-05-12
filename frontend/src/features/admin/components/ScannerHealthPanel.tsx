import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, XCircle, RefreshCw } from "lucide-react";
import { Card, CardBody, CardHeader } from "@/shared/components/Card";
import { Badge } from "@/shared/components/Badge";
import { apiClient } from "@/shared/api/client";

interface ScannerHealth {
  name: string;
  enabled: boolean;
  reason?: string;
  category: string;
}

interface ScannerHealthResponse {
  scanners: ScannerHealth[];
}

function useScannerHealth() {
  return useQuery<ScannerHealthResponse>({
    queryKey: ["scanners", "health"],
    queryFn: async () => {
      const res = await apiClient.get<ScannerHealthResponse>("/v1/scanners/health");
      return res.data;
    },
    staleTime: 30_000,
    retry: 2,
  });
}

const ALL_FILTER = "All";

export function ScannerHealthPanel() {
  const { data, isLoading, error, refetch, isFetching } = useScannerHealth();
  const [activeCategory, setActiveCategory] = useState<string>(ALL_FILTER);

  const scanners = data?.scanners ?? [];

  const categories = useMemo(() => {
    const cats = new Set(scanners.map((s) => s.category));
    return [ALL_FILTER, ...Array.from(cats).sort()];
  }, [scanners]);

  const filtered = useMemo(
    () =>
      activeCategory === ALL_FILTER
        ? scanners
        : scanners.filter((s) => s.category === activeCategory),
    [scanners, activeCategory],
  );

  const enabledCount = scanners.filter((s) => s.enabled).length;
  const disabledCount = scanners.filter((s) => !s.enabled).length;
  const categoryCount = categories.length - 1; // exclude "All"

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
              Scanner Health
            </h2>
            <p className="text-xs mt-0.5" style={{ color: "var(--text-tertiary)" }}>
              Live status of all registered scanners
            </p>
          </div>
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs transition-colors hover:bg-bg-overlay disabled:opacity-50"
            style={{ color: "var(--text-secondary)", border: "1px solid var(--border-subtle)" }}
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>
      </CardHeader>

      <CardBody className="space-y-4">
        {/* Summary stats */}
        <div className="flex flex-wrap gap-3">
          <div
            className="flex items-center gap-2 rounded-lg px-3 py-2"
            style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-subtle)" }}
          >
            <CheckCircle2 className="h-4 w-4 text-success-500" />
            <span className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
              <span className="font-bold text-sm" style={{ color: "var(--text-primary)" }}>
                {enabledCount}
              </span>{" "}
              enabled
            </span>
          </div>
          <div
            className="flex items-center gap-2 rounded-lg px-3 py-2"
            style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-subtle)" }}
          >
            <XCircle className="h-4 w-4 text-text-tertiary" />
            <span className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
              <span className="font-bold text-sm" style={{ color: "var(--text-primary)" }}>
                {disabledCount}
              </span>{" "}
              disabled
            </span>
          </div>
          <div
            className="flex items-center gap-2 rounded-lg px-3 py-2"
            style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-subtle)" }}
          >
            <span className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
              <span className="font-bold text-sm" style={{ color: "var(--text-primary)" }}>
                {categoryCount}
              </span>{" "}
              {categoryCount === 1 ? "category" : "categories"}
            </span>
          </div>
        </div>

        {/* Category filter pills */}
        {categories.length > 1 && (
          <div className="flex flex-wrap gap-1.5">
            {categories.map((cat) => (
              <button
                key={cat}
                onClick={() => setActiveCategory(cat)}
                className="rounded-full px-3 py-1 text-xs font-medium transition-colors"
                style={
                  activeCategory === cat
                    ? {
                        background: "var(--brand-900)",
                        color: "var(--brand-400)",
                        border: "1px solid var(--brand-500)",
                      }
                    : {
                        background: "var(--bg-elevated)",
                        color: "var(--text-secondary)",
                        border: "1px solid var(--border-subtle)",
                      }
                }
              >
                {cat}
              </button>
            ))}
          </div>
        )}

        {/* Scanner list */}
        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <div
                key={i}
                className="h-10 animate-pulse rounded-lg"
                style={{ background: "var(--bg-elevated)" }}
              />
            ))}
          </div>
        ) : error ? (
          <p className="text-sm py-4 text-center" style={{ color: "var(--text-tertiary)" }}>
            Failed to load scanner health data.
          </p>
        ) : filtered.length === 0 ? (
          <p className="text-sm py-4 text-center" style={{ color: "var(--text-tertiary)" }}>
            No scanners found.
          </p>
        ) : (
          <div className="space-y-1.5">
            {filtered.map((scanner) => (
              <div
                key={scanner.name}
                className="flex items-center gap-3 rounded-lg px-3 py-2.5"
                style={{
                  background: "var(--bg-elevated)",
                  border: "1px solid var(--border-subtle)",
                }}
              >
                {/* Status dot */}
                <span
                  className="h-2 w-2 shrink-0 rounded-full"
                  style={{
                    background: scanner.enabled
                      ? "var(--success-500, #22c55e)"
                      : "var(--text-tertiary)",
                  }}
                />

                {/* Name */}
                <span className="flex-1 text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                  {scanner.name}
                </span>

                {/* Category */}
                <span className="text-xs hidden sm:block" style={{ color: "var(--text-tertiary)" }}>
                  {scanner.category}
                </span>

                {/* Reason (if disabled) */}
                {!scanner.enabled && scanner.reason && (
                  <span
                    className="max-w-[180px] truncate text-xs hidden md:block"
                    style={{ color: "var(--text-tertiary)" }}
                    title={scanner.reason}
                  >
                    {scanner.reason}
                  </span>
                )}

                {/* Status badge */}
                <Badge variant={scanner.enabled ? "success" : "neutral"} size="sm" dot>
                  {scanner.enabled ? "Enabled" : "Disabled"}
                </Badge>
              </div>
            ))}
          </div>
        )}
      </CardBody>
    </Card>
  );
}
