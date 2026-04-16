import { useState, useEffect } from "react";
import { Card, CardBody, CardHeader } from "@/shared/components/Card";
import { Input } from "@/shared/components/Input";
import { Button } from "@/shared/components/Button";
import { Badge } from "@/shared/components/Badge";
import { Save, CheckCircle2, Loader2 } from "lucide-react";
import { useAuth } from "@/shared/hooks/useAuth";
import { useUserSettings, useUpdateSettings } from "./hooks";

export function ProfileSettings() {
  const { user } = useAuth();
  const { data: settings, isLoading } = useUserSettings();
  const updateMutation = useUpdateSettings();

  const [name, setName] = useState("");
  const [company, setCompany] = useState("");
  const [timezone, setTimezone] = useState("Europe/Warsaw");
  const [language, setLanguage] = useState("pl");
  const [dateFormat, setDateFormat] = useState("DD.MM.YYYY");
  const [theme, setTheme] = useState("dark");
  const [saved, setSaved] = useState(false);

  // Populate form from API settings when loaded
  useEffect(() => {
    if (settings) {
      setTimezone(settings.timezone ?? "Europe/Warsaw");
      setLanguage(settings.language ?? "pl");
      setDateFormat(settings.date_format ?? "DD.MM.YYYY");
      setTheme(settings.theme ?? "dark");
    }
  }, [settings]);

  const handleSave = async () => {
    try {
      await updateMutation.mutateAsync({
        timezone,
        language,
        date_format: dateFormat,
        theme,
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch {
      // Error is handled by the mutation
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin" style={{ color: "var(--brand-500)" }} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>Profile</h2>
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Manage your personal information</p>
      </div>

      {/* Personal Info */}
      <Card>
        <CardHeader>
          <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Personal Information</h3>
        </CardHeader>
        <CardBody className="space-y-4">
          <Input label="Full Name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Your name" />
          <div>
            <Input label="Email" value={user?.email ?? ""} disabled />
            <div className="mt-1">
              {user?.is_email_verified ? (
                <Badge variant="success" size="sm" dot>Verified</Badge>
              ) : (
                <div className="flex items-center gap-2">
                  <Badge variant="warning" size="sm" dot>Unverified</Badge>
                  <Button variant="ghost" size="sm">Verify Email</Button>
                </div>
              )}
            </div>
          </div>
          <Input label="Company (optional)" value={company} onChange={(e) => setCompany(e.target.value)} placeholder="Acme Inc." />
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="mb-1.5 block text-sm font-medium" style={{ color: "var(--text-secondary)" }}>Timezone</label>
              <select value={timezone} onChange={(e) => setTimezone(e.target.value)} className="w-full rounded-md border px-3 py-2 text-sm" style={{ background: "var(--bg-elevated)", borderColor: "var(--border-default)", color: "var(--text-primary)" }}>
                <option value="Europe/Warsaw">Europe/Warsaw</option>
                <option value="Europe/London">Europe/London</option>
                <option value="America/New_York">America/New York</option>
                <option value="UTC">UTC</option>
              </select>
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium" style={{ color: "var(--text-secondary)" }}>Language</label>
              <select value={language} onChange={(e) => setLanguage(e.target.value)} className="w-full rounded-md border px-3 py-2 text-sm" style={{ background: "var(--bg-elevated)", borderColor: "var(--border-default)", color: "var(--text-primary)" }}>
                <option value="pl">Polski</option>
                <option value="en">English</option>
              </select>
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium" style={{ color: "var(--text-secondary)" }}>Date Format</label>
              <select value={dateFormat} onChange={(e) => setDateFormat(e.target.value)} className="w-full rounded-md border px-3 py-2 text-sm" style={{ background: "var(--bg-elevated)", borderColor: "var(--border-default)", color: "var(--text-primary)" }}>
                <option value="DD.MM.YYYY">DD.MM.YYYY</option>
                <option value="MM/DD/YYYY">MM/DD/YYYY</option>
                <option value="YYYY-MM-DD">YYYY-MM-DD</option>
              </select>
            </div>
          </div>
        </CardBody>
      </Card>

      {/* Appearance */}
      <Card>
        <CardHeader>
          <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Appearance</h3>
        </CardHeader>
        <CardBody>
          <div className="flex gap-3">
            {(["dark", "light", "system"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTheme(t)}
                className={`flex-1 rounded-lg border p-3 text-center text-sm font-medium capitalize transition-all ${
                  theme === t
                    ? "border-brand-500 bg-brand-900/30 text-brand-400"
                    : "border-border bg-bg-elevated text-text-secondary hover:bg-bg-overlay"
                }`}
              >
                {t}
              </button>
            ))}
          </div>
        </CardBody>
      </Card>

      {/* Save */}
      <div className="flex items-center gap-3">
        <Button
          onClick={handleSave}
          loading={updateMutation.isPending}
          leftIcon={saved ? <CheckCircle2 className="h-4 w-4" /> : <Save className="h-4 w-4" />}
        >
          {saved ? "Saved" : "Save Changes"}
        </Button>
        {saved && <span className="text-sm text-success-500">Settings updated</span>}
      </div>
    </div>
  );
}
