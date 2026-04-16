import { useState } from "react";
import { User, Shield, Bell, Key, Lock, AlertTriangle } from "lucide-react";
import { Badge } from "@/shared/components/Badge";
import { useAuth } from "@/shared/hooks/useAuth";
import { ProfileSettings } from "./ProfileSettings";
import { SecuritySettings } from "./SecuritySettings";
import { NotificationSettings } from "./NotificationSettings";
import { ApiKeySettings } from "./ApiKeySettings";
import { GdprSettings } from "./GdprSettings";

type SettingsSection = "profile" | "security" | "notifications" | "api" | "gdpr";

const sections: { id: SettingsSection; label: string; icon: typeof User; badge?: string; danger?: boolean }[] = [
  { id: "profile", label: "Profile", icon: User },
  { id: "security", label: "Security", icon: Shield },
  { id: "notifications", label: "Notifications", icon: Bell },
  { id: "api", label: "API Access", icon: Key, badge: "PRO" },
  { id: "gdpr", label: "Privacy & GDPR", icon: Lock },
];

export function SettingsPage() {
  const [active, setActive] = useState<SettingsSection>("profile");

  return (
    <div className="flex gap-6">
      {/* Sidebar */}
      <nav className="hidden w-52 shrink-0 space-y-1 md:block">
        {sections.map((s) => (
          <button
            key={s.id}
            onClick={() => setActive(s.id)}
            className={`flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
              active === s.id
                ? "bg-brand-900 text-brand-400"
                : s.danger
                ? "text-danger-500 hover:bg-bg-overlay"
                : "text-text-secondary hover:bg-bg-overlay hover:text-text-primary"
            }`}
          >
            <s.icon className="h-4 w-4 shrink-0" />
            <span className="flex-1 text-left">{s.label}</span>
            {s.badge && <Badge variant="brand" size="sm">{s.badge}</Badge>}
          </button>
        ))}
      </nav>

      {/* Mobile tabs */}
      <div className="flex gap-1 overflow-x-auto border-b pb-2 md:hidden" style={{ borderColor: "var(--border-subtle)" }}>
        {sections.map((s) => (
          <button
            key={s.id}
            onClick={() => setActive(s.id)}
            className={`whitespace-nowrap rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
              active === s.id ? "bg-brand-900 text-brand-400" : "text-text-secondary"
            }`}
          >
            {s.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="min-w-0 flex-1">
        {active === "profile" && <ProfileSettings />}
        {active === "security" && <SecuritySettings />}
        {active === "notifications" && <NotificationSettings />}
        {active === "api" && <ApiKeySettings />}
        {active === "gdpr" && <GdprSettings />}
      </div>
    </div>
  );
}
