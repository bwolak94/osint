import { useState } from "react";
import { Card, CardBody, CardHeader } from "@/shared/components/Card";
import { Button } from "@/shared/components/Button";
import { Save } from "lucide-react";

interface Toggle { label: string; description: string; key: string }

const emailToggles: Toggle[] = [
  { label: "Scan completed", description: "Receive an email when a scan finishes", key: "scan_complete" },
  { label: "New findings", description: "Get notified when new identities are discovered", key: "new_findings" },
  { label: "Weekly digest", description: "Summary of activity sent every Monday", key: "weekly_digest" },
];

export function NotificationSettings() {
  const [prefs, setPrefs] = useState<Record<string, boolean>>({
    scan_complete: true, new_findings: false, weekly_digest: true,
  });

  const toggle = (key: string) => setPrefs((p) => ({ ...p, [key]: !p[key] }));

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>Notifications</h2>
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Choose what you want to be notified about</p>
      </div>

      <Card>
        <CardHeader><h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Email Notifications</h3></CardHeader>
        <CardBody className="space-y-1 p-0">
          {emailToggles.map((t) => (
            <div key={t.key} className="flex items-center justify-between border-b px-5 py-3" style={{ borderColor: "var(--border-subtle)" }}>
              <div>
                <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>{t.label}</p>
                <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>{t.description}</p>
              </div>
              <button
                onClick={() => toggle(t.key)}
                className={`relative h-6 w-11 rounded-full transition-colors ${prefs[t.key] ? "bg-brand-500" : "bg-bg-overlay"}`}
              >
                <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition-transform ${prefs[t.key] ? "left-[22px]" : "left-0.5"}`} />
              </button>
            </div>
          ))}
        </CardBody>
      </Card>

      <Button leftIcon={<Save className="h-4 w-4" />}>Save Preferences</Button>
    </div>
  );
}
