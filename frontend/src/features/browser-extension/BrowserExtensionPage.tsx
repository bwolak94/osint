/**
 * Browser Extension Passive Capture (Feature 6)
 * Configuration and status page for the OSINT browser extension.
 */
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Copy, CheckCircle, Chrome, Zap, Shield, ExternalLink } from "lucide-react";
import { Card, CardBody, CardHeader } from "@/shared/components/Card";
import { Badge } from "@/shared/components/Badge";
import { Button } from "@/shared/components/Button";
import { apiClient } from "@/shared/api/client";
import { toast } from "@/shared/components/Toast";


const ENTITY_TYPES = [
  { type: "email", label: "Emails", icon: "📧", description: "Auto-detect email addresses on pages" },
  { type: "domain", label: "Domains", icon: "🌐", description: "Extract domain names from links" },
  { type: "ip_address", label: "IP Addresses", icon: "🖥️", description: "Detect IPv4/IPv6 addresses" },
  { type: "username", label: "Usernames", icon: "👤", description: "Identify social media usernames" },
  { type: "phone", label: "Phone Numbers", icon: "📞", description: "Parse phone number formats" },
];

const SETUP_STEPS = [
  {
    step: 1,
    title: "Install the Extension",
    description: "Download from the Chrome Web Store or load unpacked from source.",
    action: "Install from Chrome Store",
    icon: Chrome,
  },
  {
    step: 2,
    title: "Authenticate",
    description: "Click the extension icon and sign in with your OSINT platform credentials.",
    action: null,
    icon: Shield,
  },
  {
    step: 3,
    title: "Configure Capture",
    description: "Select which entity types to auto-detect and set your scan preferences below.",
    action: null,
    icon: Zap,
  },
];

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <button onClick={handleCopy} className="ml-2 rounded p-1 transition-colors hover:bg-bg-overlay">
      {copied
        ? <CheckCircle className="h-3.5 w-3.5" style={{ color: "var(--success-500)" }} />
        : <Copy className="h-3.5 w-3.5" style={{ color: "var(--text-tertiary)" }} />
      }
    </button>
  );
}

export function BrowserExtensionPage() {
  const [enabledTypes, setEnabledTypes] = useState<Set<string>>(new Set(["email", "domain", "ip_address"]));
  const [autoScan, setAutoScan] = useState(false);
  const [passiveMode, setPassiveMode] = useState(true);

  const toggleType = (type: string) => {
    setEnabledTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  };

  // Quick scan test
  const quickScanMutation = useMutation({
    mutationFn: async (data: { input_value: string; input_type: string }) => {
      const res = await apiClient.post("/extension/quick-scan", {
        ...data,
        url: window.location.href,
        page_title: document.title,
        selected_text: "",
      });
      return res.data;
    },
    onSuccess: (data) => toast.success(`Scan queued: ${data.scan_id}`),
    onError: () => toast.error("Quick scan failed"),
  });

  // API base URL for extension config
  const apiBase = window.location.origin + "/api/v1";
  const apiKey = "ext-demo-key-" + Math.random().toString(36).slice(2, 10);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Browser Extension</h1>
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
          Passive capture mode — automatically detect and investigate OSINT entities as you browse.
        </p>
      </div>

      {/* Setup steps */}
      <div className="grid gap-3 sm:grid-cols-3">
        {SETUP_STEPS.map(({ step, title, description, action, icon: Icon }) => (
          <Card key={step}>
            <CardBody className="space-y-2">
              <div className="flex items-center gap-2">
                <div
                  className="flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold"
                  style={{ background: "var(--brand-900)", color: "var(--brand-400)" }}
                >
                  {step}
                </div>
                <Icon className="h-4 w-4 shrink-0" style={{ color: "var(--brand-400)" }} />
              </div>
              <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>{title}</p>
              <p className="text-xs" style={{ color: "var(--text-secondary)" }}>{description}</p>
              {action && (
                <Button size="sm" variant="secondary" leftIcon={<ExternalLink className="h-3.5 w-3.5" />}>
                  {action}
                </Button>
              )}
            </CardBody>
          </Card>
        ))}
      </div>

      {/* Config card */}
      <Card>
        <CardHeader>
          <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Extension Configuration</p>
        </CardHeader>
        <CardBody className="space-y-4">
          {/* API endpoint */}
          <div>
            <p className="text-xs font-medium mb-1" style={{ color: "var(--text-secondary)" }}>API Endpoint</p>
            <div
              className="flex items-center justify-between rounded-md border px-3 py-2 font-mono text-xs"
              style={{ background: "var(--bg-elevated)", borderColor: "var(--border-default)", color: "var(--text-primary)" }}
            >
              <span className="truncate">{apiBase}</span>
              <CopyButton text={apiBase} />
            </div>
          </div>

          {/* API key */}
          <div>
            <p className="text-xs font-medium mb-1" style={{ color: "var(--text-secondary)" }}>Extension API Key</p>
            <div
              className="flex items-center justify-between rounded-md border px-3 py-2 font-mono text-xs"
              style={{ background: "var(--bg-elevated)", borderColor: "var(--border-default)", color: "var(--text-primary)" }}
            >
              <span className="truncate">{apiKey}</span>
              <CopyButton text={apiKey} />
            </div>
            <p className="mt-1 text-[10px]" style={{ color: "var(--text-tertiary)" }}>
              Paste this into the extension's settings. Regenerate from API Keys settings if compromised.
            </p>
          </div>

          {/* Toggle settings */}
          <div className="space-y-2">
            <label className="flex items-center justify-between cursor-pointer">
              <div>
                <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>Passive Mode</p>
                <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>Detect entities without auto-scanning</p>
              </div>
              <button
                onClick={() => setPassiveMode((p) => !p)}
                className={`relative h-5 w-9 rounded-full transition-colors ${passiveMode ? "bg-brand-600" : "bg-bg-overlay"}`}
                role="switch"
                aria-checked={passiveMode}
              >
                <span
                  className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform ${passiveMode ? "translate-x-4" : "translate-x-0.5"}`}
                />
              </button>
            </label>

            <label className="flex items-center justify-between cursor-pointer">
              <div>
                <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>Auto-Scan Detected Entities</p>
                <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>Automatically queue scans when entities are detected</p>
              </div>
              <button
                onClick={() => setAutoScan((p) => !p)}
                className={`relative h-5 w-9 rounded-full transition-colors ${autoScan ? "bg-brand-600" : "bg-bg-overlay"}`}
                role="switch"
                aria-checked={autoScan}
              >
                <span
                  className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform ${autoScan ? "translate-x-4" : "translate-x-0.5"}`}
                />
              </button>
            </label>
          </div>

          {/* Entity types */}
          <div>
            <p className="text-xs font-medium mb-2" style={{ color: "var(--text-secondary)" }}>Capture Entity Types</p>
            <div className="space-y-1">
              {ENTITY_TYPES.map(({ type, label, icon, description }) => (
                <label
                  key={type}
                  className="flex items-center gap-3 rounded-md px-3 py-2 cursor-pointer transition-colors hover:bg-bg-overlay"
                  style={{ background: enabledTypes.has(type) ? "var(--bg-overlay)" : "transparent" }}
                >
                  <input
                    type="checkbox"
                    checked={enabledTypes.has(type)}
                    onChange={() => toggleType(type)}
                    className="rounded"
                  />
                  <span className="text-base">{icon}</span>
                  <div>
                    <p className="text-xs font-medium" style={{ color: "var(--text-primary)" }}>{label}</p>
                    <p className="text-[10px]" style={{ color: "var(--text-tertiary)" }}>{description}</p>
                  </div>
                  {enabledTypes.has(type) && <Badge variant="success" size="sm" className="ml-auto">Active</Badge>}
                </label>
              ))}
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-1">
            <Button size="sm" variant="secondary">
              Save Configuration
            </Button>
          </div>
        </CardBody>
      </Card>

      {/* Quick scan test */}
      <Card>
        <CardHeader>
          <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Test Quick Scan</p>
        </CardHeader>
        <CardBody>
          <div className="flex gap-2">
            <input
              id="test-value"
              placeholder="user@example.com"
              className="flex-1 rounded-md border px-3 py-2 text-sm font-mono"
              style={{ background: "var(--bg-elevated)", borderColor: "var(--border-default)", color: "var(--text-primary)" }}
            />
            <Button
              size="sm"
              leftIcon={<Zap className="h-3.5 w-3.5" />}
              loading={quickScanMutation.isPending}
              onClick={() => {
                const input = document.getElementById("test-value") as HTMLInputElement;
                if (input?.value) quickScanMutation.mutate({ input_value: input.value, input_type: "email" });
              }}
            >
              Test Scan
            </Button>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
