import { useEffect, useState } from "react";
import { apiClient } from "@/shared/api/client";

interface UserPresence {
  user_id: string;
  email: string;
  cursor_position: { x: number; y: number } | null;
  selected_node_id: string | null;
  color: string;
  last_seen_at: string;
}

interface PresenceIndicatorsProps {
  investigationId: string;
}

export function PresenceIndicators({ investigationId }: PresenceIndicatorsProps) {
  const [users, setUsers] = useState<UserPresence[]>([]);

  useEffect(() => {
    const fetchPresence = async () => {
      try {
        const resp = await apiClient.get<{ users: UserPresence[] }>(
          `/presence/${investigationId}`
        );
        setUsers(resp.data.users);
      } catch {
        // Silently fail - presence is non-critical
      }
    };

    fetchPresence();
    const interval = setInterval(fetchPresence, 3000);
    return () => clearInterval(interval);
  }, [investigationId]);

  if (users.length === 0) return null;

  return (
    <div className="flex items-center gap-1">
      {users.map((user) => (
        <div
          key={user.user_id}
          className="relative flex h-7 w-7 items-center justify-center rounded-full text-xs font-medium text-white"
          style={{ backgroundColor: user.color }}
          title={`${user.email} is viewing this investigation`}
        >
          {user.email.charAt(0).toUpperCase()}
          <span
            className="absolute bottom-0 right-0 h-2 w-2 rounded-full border border-white"
            style={{ backgroundColor: "#10b981" }}
          />
        </div>
      ))}
      {users.length > 0 && (
        <span className="ml-1 text-xs" style={{ color: "var(--text-tertiary)" }}>
          {users.length} online
        </span>
      )}
    </div>
  );
}
