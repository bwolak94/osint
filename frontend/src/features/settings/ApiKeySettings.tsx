import { useState } from "react";
import { Card, CardBody, CardHeader } from "@/shared/components/Card";
import { Button } from "@/shared/components/Button";
import { Badge } from "@/shared/components/Badge";
import { DataBadge } from "@/shared/components/DataBadge";
import { Key, AlertTriangle, ExternalLink, Lock } from "lucide-react";
import { useAuth } from "@/shared/hooks/useAuth";

export function ApiKeySettings() {
  const { isPro } = useAuth();
  const [hasKey, setHasKey] = useState(false);
  const [newKey, setNewKey] = useState<string | null>(null);
  const [_showConfirmRegenerate, setShowConfirmRegenerate] = useState(false);

  const generateKey = () => {
    const key = `osint_${Array.from({ length: 48 }, () => "0123456789abcdef"[Math.floor(Math.random() * 16)]).join("")}`;
    setNewKey(key);
    setHasKey(true);
  };

  if (!isPro) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>API Access</h2>
        </div>
        <Card>
          <CardBody className="flex flex-col items-center py-12 text-center">
            <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl" style={{ background: "var(--bg-elevated)" }}>
              <Lock className="h-6 w-6" style={{ color: "var(--text-tertiary)" }} />
            </div>
            <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>API access requires PRO</h3>
            <p className="mt-1 max-w-sm text-sm" style={{ color: "var(--text-secondary)" }}>
              Upgrade to PRO to generate API keys and access the platform programmatically.
            </p>
            <Button className="mt-4" onClick={() => window.location.href = "/billing"}>Upgrade to PRO</Button>
          </CardBody>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>API Access</h2>
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Manage your API keys</p>
      </div>

      {/* New key modal */}
      {newKey && (
        <Card className="border-warning-500/30">
          <CardBody className="space-y-3">
            <div className="flex items-start gap-2">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" style={{ color: "var(--warning-500)" }} />
              <div>
                <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Save your API key</p>
                <p className="text-xs" style={{ color: "var(--text-secondary)" }}>This key will only be shown once. Copy it now.</p>
              </div>
            </div>
            <div className="rounded-md p-3 font-mono text-xs break-all" style={{ background: "var(--bg-elevated)", color: "var(--text-primary)" }}>
              {newKey}
            </div>
            <div className="flex gap-2">
              <DataBadge value={newKey} />
              <Button variant="secondary" size="sm" onClick={() => setNewKey(null)}>I've saved my key</Button>
            </div>
          </CardBody>
        </Card>
      )}

      {/* Key status */}
      <Card>
        <CardHeader><h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>API Key</h3></CardHeader>
        <CardBody>
          {hasKey ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-mono text-sm" style={{ color: "var(--text-primary)" }}>
                    osint_••••••••••••••••••••1a2b
                  </p>
                  <p className="mt-0.5 text-xs" style={{ color: "var(--text-tertiary)" }}>Created: Jan 15, 2025</p>
                </div>
                <Badge variant="success" size="sm" dot>Active</Badge>
              </div>
              <div className="flex gap-2">
                <Button variant="danger" size="sm" onClick={() => setShowConfirmRegenerate(true)}>Regenerate</Button>
                <Button variant="ghost" size="sm" onClick={() => setHasKey(false)}>Revoke</Button>
              </div>
            </div>
          ) : (
            <div className="text-center py-6">
              <Key className="mx-auto h-8 w-8" style={{ color: "var(--text-tertiary)" }} />
              <p className="mt-2 text-sm" style={{ color: "var(--text-secondary)" }}>No API key generated</p>
              <Button className="mt-3" onClick={generateKey}>Generate API Key</Button>
            </div>
          )}
        </CardBody>
      </Card>

      {/* Documentation */}
      <Card>
        <CardHeader><h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Documentation</h3></CardHeader>
        <CardBody>
          <div className="flex gap-3">
            <Button variant="secondary" size="sm" leftIcon={<ExternalLink className="h-3.5 w-3.5" />}>API Docs</Button>
            <Button variant="ghost" size="sm" leftIcon={<ExternalLink className="h-3.5 w-3.5" />}>Examples</Button>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
