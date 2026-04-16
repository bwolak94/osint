import { useQuery } from "@tanstack/react-query";
import { Card, CardBody, CardHeader } from "@/shared/components/Card";
import { Badge } from "@/shared/components/Badge";
import { EmptyState } from "@/shared/components/EmptyState";
import { apiClient } from "@/shared/api/client";
import { useAuth } from "@/shared/hooks/useAuth";
import { Users, Activity, Search, Shield, BarChart3 } from "lucide-react";

function useAdminStats() {
  return useQuery({
    queryKey: ["admin", "stats"],
    queryFn: async () => {
      const res = await apiClient.get("/admin/stats");
      return res.data;
    },
  });
}

function useAdminUsers() {
  return useQuery({
    queryKey: ["admin", "users"],
    queryFn: async () => {
      const res = await apiClient.get("/admin/users");
      return res.data;
    },
  });
}

export function AdminPage() {
  const { isAdmin } = useAuth();
  const { data: stats } = useAdminStats();
  const { data: users } = useAdminUsers();

  if (!isAdmin) {
    return (
      <EmptyState
        variant="error"
        title="Access Denied"
        description="You need admin privileges to view this page."
      />
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Admin Panel</h1>
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Platform management and user administration</p>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[
            { label: "Total Users", value: stats.total_users, icon: Users },
            { label: "Total Investigations", value: stats.total_investigations, icon: Search },
            { label: "Total Scans", value: stats.total_scans, icon: Activity },
            { label: "Successful Scans", value: stats.successful_scans, icon: Shield },
            { label: "Failed Scans", value: stats.failed_scans, icon: BarChart3 },
            { label: "Active Users", value: stats.active_users, icon: Users },
          ].map((s) => (
            <Card key={s.label}>
              <CardBody className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg" style={{ background: "var(--brand-900)" }}>
                  <s.icon className="h-5 w-5" style={{ color: "var(--brand-400)" }} />
                </div>
                <div>
                  <p className="text-2xl font-bold font-mono" style={{ color: "var(--text-primary)" }}>{s.value}</p>
                  <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>{s.label}</p>
                </div>
              </CardBody>
            </Card>
          ))}
        </div>
      )}

      {/* Users table */}
      <Card>
        <CardHeader><h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Users</h2></CardHeader>
        <CardBody className="p-0">
          <table className="w-full">
            <thead>
              <tr className="border-b text-left text-xs font-medium" style={{ borderColor: "var(--border-subtle)", color: "var(--text-tertiary)" }}>
                <th className="px-5 py-3">Email</th>
                <th className="px-5 py-3">Role</th>
                <th className="px-5 py-3">Tier</th>
                <th className="px-5 py-3">Status</th>
                <th className="px-5 py-3">Joined</th>
              </tr>
            </thead>
            <tbody>
              {(users ?? []).map((u: any) => (
                <tr key={u.id} className="border-b" style={{ borderColor: "var(--border-subtle)" }}>
                  <td className="px-5 py-3 text-sm font-mono" style={{ color: "var(--text-primary)" }}>{u.email}</td>
                  <td className="px-5 py-3"><Badge variant={u.role === "admin" ? "danger" : "neutral"} size="sm">{u.role}</Badge></td>
                  <td className="px-5 py-3"><Badge variant={u.subscription_tier === "enterprise" ? "warning" : u.subscription_tier === "pro" ? "brand" : "neutral"} size="sm">{u.subscription_tier}</Badge></td>
                  <td className="px-5 py-3"><Badge variant={u.is_active ? "success" : "danger"} size="sm" dot>{u.is_active ? "Active" : "Inactive"}</Badge></td>
                  <td className="px-5 py-3 text-xs" style={{ color: "var(--text-tertiary)" }}>{new Date(u.created_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardBody>
      </Card>
    </div>
  );
}
