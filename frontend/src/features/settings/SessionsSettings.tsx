import { useState } from "react";
import { Monitor, Smartphone, Globe, Trash2, ShieldAlert } from "lucide-react";
import { apiClient } from "@/shared/api/client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

interface Session {
  id: string;
  ip_address: string | null;
  user_agent: string | null;
  device_info: string | null;
  location: string | null;
  is_current: boolean;
  created_at: string;
  last_active_at: string;
}

export function SessionsSettings() {
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["sessions"],
    queryFn: async () => {
      const resp = await apiClient.get<{ sessions: Session[]; total: number }>("/auth/sessions");
      return resp.data;
    },
  });

  const revokeMutation = useMutation({
    mutationFn: async (sessionId: string) => {
      await apiClient.delete(`/auth/sessions/${sessionId}`);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["sessions"] }),
  });

  const revokeAllMutation = useMutation({
    mutationFn: async () => {
      await apiClient.post("/auth/sessions/revoke-all");
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["sessions"] }),
  });

  const getDeviceIcon = (userAgent: string | null) => {
    if (!userAgent) return Monitor;
    if (/mobile|android|iphone/i.test(userAgent)) return Smartphone;
    return Monitor;
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>
            Active Sessions
          </h3>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Manage your active sessions across devices
          </p>
        </div>
        <button
          onClick={() => revokeAllMutation.mutate()}
          disabled={revokeAllMutation.isPending}
          className="flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-danger-500/10"
          style={{ color: "var(--danger-500)" }}
        >
          <ShieldAlert className="h-4 w-4" />
          Revoke All Sessions
        </button>
      </div>

      {isLoading ? (
        <div className="text-sm" style={{ color: "var(--text-secondary)" }}>Loading sessions...</div>
      ) : !data?.sessions.length ? (
        <div className="rounded-lg border p-8 text-center" style={{ borderColor: "var(--border-subtle)", background: "var(--bg-surface)" }}>
          <Monitor className="mx-auto h-8 w-8 mb-2" style={{ color: "var(--text-tertiary)" }} />
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>No active sessions found</p>
        </div>
      ) : (
        <div className="space-y-3">
          {data.sessions.map((session) => {
            const DeviceIcon = getDeviceIcon(session.user_agent);
            return (
              <div
                key={session.id}
                className="flex items-center gap-4 rounded-lg border p-4"
                style={{
                  borderColor: session.is_current ? "var(--brand-500)" : "var(--border-subtle)",
                  background: "var(--bg-surface)",
                }}
              >
                <DeviceIcon className="h-8 w-8 shrink-0" style={{ color: session.is_current ? "var(--brand-400)" : "var(--text-tertiary)" }} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                      {session.device_info || "Unknown Device"}
                    </span>
                    {session.is_current && (
                      <span className="rounded-full px-2 py-0.5 text-xs font-medium" style={{ background: "var(--brand-900)", color: "var(--brand-400)" }}>
                        Current
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 mt-1">
                    {session.ip_address && (
                      <span className="flex items-center gap-1 text-xs" style={{ color: "var(--text-tertiary)" }}>
                        <Globe className="h-3 w-3" />
                        {session.ip_address}
                      </span>
                    )}
                    {session.location && (
                      <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                        {session.location}
                      </span>
                    )}
                  </div>
                  <p className="text-xs mt-1" style={{ color: "var(--text-tertiary)" }}>
                    Last active: {formatDate(session.last_active_at)}
                  </p>
                </div>
                {!session.is_current && (
                  <button
                    onClick={() => revokeMutation.mutate(session.id)}
                    disabled={revokeMutation.isPending}
                    className="rounded-md p-2 transition-colors hover:bg-danger-500/10"
                    style={{ color: "var(--danger-500)" }}
                    title="Revoke session"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
