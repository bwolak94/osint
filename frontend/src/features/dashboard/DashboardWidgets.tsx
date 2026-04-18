import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import { BarChart3, Shield, Search, AlertTriangle, TrendingUp, Activity } from "lucide-react";

interface DashboardStats {
  total_investigations: number;
  active_investigations: number;
  completed_investigations: number;
  total_scans: number;
  successful_scans: number;
  failed_scans: number;
  total_identities: number;
  total_iocs: number;
  avg_scan_duration_ms: number;
}

interface ScannerPerformance {
  scanner_name: string;
  total_runs: number;
  success_rate: number;
  avg_duration_ms: number;
}

interface DashboardData {
  stats: DashboardStats;
  scanner_performance: ScannerPerformance[];
  top_findings: Array<{ type: string; value: string; count: number; severity: string }>;
}

export function DashboardWidgets() {
  const { data, isLoading } = useQuery({
    queryKey: ["dashboard-widgets"],
    queryFn: async () => {
      const resp = await apiClient.get<DashboardData>("/dashboard/widgets");
      return resp.data;
    },
  });

  const stats = data?.stats;

  const statCards = [
    { label: "Total Investigations", value: stats?.total_investigations ?? 0, icon: Search, color: "var(--brand-400)" },
    { label: "Active", value: stats?.active_investigations ?? 0, icon: Activity, color: "var(--success-500)" },
    { label: "Total Scans", value: stats?.total_scans ?? 0, icon: BarChart3, color: "var(--info-500)" },
    { label: "Identities Found", value: stats?.total_identities ?? 0, icon: Shield, color: "var(--warning-500)" },
    { label: "IOCs Detected", value: stats?.total_iocs ?? 0, icon: AlertTriangle, color: "var(--danger-500)" },
    { label: "Avg Duration", value: `${stats?.avg_scan_duration_ms ?? 0}ms`, icon: TrendingUp, color: "var(--text-secondary)" },
  ];

  if (isLoading) {
    return <div className="text-sm" style={{ color: "var(--text-secondary)" }}>Loading dashboard...</div>;
  }

  return (
    <div className="space-y-6">
      {/* Stats Grid */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-6">
        {statCards.map((card) => (
          <div
            key={card.label}
            className="rounded-lg border p-4"
            style={{ borderColor: "var(--border-subtle)", background: "var(--bg-surface)" }}
          >
            <div className="flex items-center gap-2 mb-2">
              <card.icon className="h-4 w-4" style={{ color: card.color }} />
              <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>{card.label}</span>
            </div>
            <p className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>
              {card.value}
            </p>
          </div>
        ))}
      </div>

      {/* Scanner Performance */}
      {data?.scanner_performance && data.scanner_performance.length > 0 && (
        <div
          className="rounded-lg border p-4"
          style={{ borderColor: "var(--border-subtle)", background: "var(--bg-surface)" }}
        >
          <h3 className="text-sm font-semibold mb-3" style={{ color: "var(--text-primary)" }}>
            Scanner Performance
          </h3>
          <div className="space-y-2">
            {data.scanner_performance.map((scanner) => (
              <div key={scanner.scanner_name} className="flex items-center justify-between text-sm">
                <span style={{ color: "var(--text-primary)" }}>{scanner.scanner_name}</span>
                <div className="flex items-center gap-4">
                  <span style={{ color: "var(--text-tertiary)" }}>{scanner.total_runs} runs</span>
                  <span
                    style={{
                      color: scanner.success_rate > 0.9 ? "var(--success-500)" : scanner.success_rate > 0.7 ? "var(--warning-500)" : "var(--danger-500)",
                    }}
                  >
                    {(scanner.success_rate * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
