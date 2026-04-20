import { useState } from "react";
import { User, Shield, Bell, Key, Lock, AlertTriangle, Link2 } from "lucide-react";
import { Badge } from "@/shared/components/Badge";
import { useAuth } from "@/shared/hooks/useAuth";
import { ProfileSettings } from "./ProfileSettings";
import { SecuritySettings } from "./SecuritySettings";
import { NotificationSettings } from "./NotificationSettings";
import { ApiKeySettings } from "./ApiKeySettings";
import { GdprSettings } from "./GdprSettings";

type SettingsSection = "profile" | "security" | "notifications" | "api" | "integrations" | "gdpr";

const sections: { id: SettingsSection; label: string; icon: typeof User; badge?: string; danger?: boolean }[] = [
  { id: "profile", label: "Profile", icon: User },
  { id: "security", label: "Security", icon: Shield },
  { id: "notifications", label: "Notifications", icon: Bell },
  { id: "api", label: "API Access", icon: Key, badge: "PRO" },
  { id: "integrations", label: "Integrations", icon: Link2 },
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
        {active === "integrations" && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>Integrations</h2>
            <div className="rounded-lg border p-4" style={{ borderColor: "var(--border-default)", background: "var(--bg-surface)" }}>
              <h3 className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>Jira / Linear</h3>
              <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
                Export findings directly to Jira or Linear issues. OAuth integration is planned for a future release.
              </p>
              <Badge variant="neutral" size="sm" className="mt-2">Coming Soon</Badge>
            </div>
            <div className="rounded-lg border p-4" style={{ borderColor: "var(--border-default)", background: "var(--bg-surface)" }}>
              <h3 className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>Maltego</h3>
              <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
                Use the OSINT platform as a Maltego remote transform server. Configure the endpoint at <code className="text-xs">/api/v1/maltego/transform</code>.
              </p>
              <Badge variant="brand" size="sm" className="mt-2">Available</Badge>
            </div>
          </div>
        )}
        {active === "gdpr" && <GdprSettings />}
      </div>
    </div>
  );
}
