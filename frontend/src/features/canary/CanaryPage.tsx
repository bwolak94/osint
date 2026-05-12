import { useState } from "react";
import { Bird, Plus, Zap, AlertCircle, Copy, CheckCircle } from "lucide-react";
import { Badge } from "@/shared/components/Badge";
import { Button } from "@/shared/components/Button";
import { Card, CardBody } from "@/shared/components/Card";
import { Input } from "@/shared/components/Input";
import { useCanaryTokens, useCanaryAlerts, useCreateToken, useTriggerToken } from "./hooks";
import type { CanaryToken } from "./types";

const STATUS_VARIANT: Record<string, "success" | "warning" | "danger" | "neutral"> = {
  active: "success",
  triggered: "danger",
  disabled: "neutral",
};

const TOKEN_TYPES = ["web_bug", "dns", "aws_key", "word_doc", "pdf", "email", "http"];

function TokenCard({ token, onTrigger }: { token: CanaryToken; onTrigger: (id: string) => void }) {
  const [copied, setCopied] = useState(false);

  const copy = () => {
    navigator.clipboard.writeText(token.token_url).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <Card>
      <CardBody className="space-y-3">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-semibold text-sm" style={{ color: "var(--text-primary)" }}>{token.name}</span>
              <Badge variant="neutral" size="sm">{token.type.replace("_", " ")}</Badge>
              <Badge variant={(STATUS_VARIANT[token.status] ?? "neutral") as "success" | "warning" | "danger" | "info" | "neutral" | "brand"} size="sm" dot>{token.status}</Badge>
            </div>
            {token.deployment_notes && (
              <p className="mt-1 text-xs" style={{ color: "var(--text-tertiary)" }}>{token.deployment_notes}</p>
            )}
          </div>
          <Button size="sm" variant="ghost" leftIcon={<Zap className="h-3.5 w-3.5" />} onClick={() => onTrigger(token.id)}>
            Test
          </Button>
        </div>
        <div className="flex items-center gap-2 rounded-md px-3 py-2" style={{ background: "var(--bg-elevated)" }}>
          <code className="flex-1 truncate text-xs" style={{ color: "var(--text-secondary)" }}>{token.token_url}</code>
          <button onClick={copy} className="shrink-0 rounded p-1 hover:bg-bg-overlay">
            {copied ? <CheckCircle className="h-3.5 w-3.5" style={{ color: "var(--success-400)" }} /> : <Copy className="h-3.5 w-3.5" style={{ color: "var(--text-tertiary)" }} />}
          </button>
        </div>
        <div className="flex gap-4 text-xs" style={{ color: "var(--text-tertiary)" }}>
          <span>Triggers: <strong style={{ color: token.trigger_count > 0 ? "var(--danger-400)" : "var(--text-primary)" }}>{token.trigger_count}</strong></span>
          {token.last_triggered && <span>Last: {new Date(token.last_triggered).toLocaleString()}</span>}
          <span>Created: {new Date(token.created_at).toLocaleDateString()}</span>
        </div>
      </CardBody>
    </Card>
  );
}

export function CanaryPage() {
  const { data: tokens = [] } = useCanaryTokens();
  const { data: alerts = [] } = useCanaryAlerts();
  const createToken = useCreateToken();
  const triggerToken = useTriggerToken();
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [tokenType, setTokenType] = useState("web_bug");
  const [notes, setNotes] = useState("");

  const handleCreate = () => {
    if (!name.trim()) return;
    createToken.mutate({ name: name.trim(), type: tokenType, deployment_notes: notes.trim() }, {
      onSuccess: () => { setShowForm(false); setName(""); setNotes(""); },
    });
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Bird className="h-6 w-6" style={{ color: "var(--brand-500)" }} />
          <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Canary Tokens</h1>
          <Badge variant="neutral" size="sm">{tokens.length} tokens</Badge>
          {alerts.length > 0 && <Badge variant="danger" size="sm">{alerts.length} alerts</Badge>}
        </div>
        <Button leftIcon={<Plus className="h-4 w-4" />} onClick={() => setShowForm((p) => !p)}>
          Deploy Token
        </Button>
      </div>

      {showForm && (
        <Card>
          <CardBody className="space-y-3">
            <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Deploy Canary Token</h3>
            <Input placeholder="Token name / label" value={name} onChange={(e) => setName(e.target.value)} />
            <div>
              <p className="mb-2 text-xs font-medium" style={{ color: "var(--text-tertiary)" }}>Token type</p>
              <div className="flex flex-wrap gap-1">
                {TOKEN_TYPES.map((t) => (
                  <button
                    key={t}
                    onClick={() => setTokenType(t)}
                    className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${tokenType === t ? "bg-brand-900 text-brand-400" : "text-text-secondary hover:bg-bg-overlay"}`}
                  >{t.replace("_", " ")}</button>
                ))}
              </div>
            </div>
            <Input placeholder="Deployment notes (where you placed it)" value={notes} onChange={(e) => setNotes(e.target.value)} />
            <div className="flex gap-2">
              <Button size="sm" onClick={handleCreate} loading={createToken.isPending}>Deploy</Button>
              <Button size="sm" variant="ghost" onClick={() => setShowForm(false)}>Cancel</Button>
            </div>
          </CardBody>
        </Card>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-3">
          <h2 className="text-sm font-medium" style={{ color: "var(--text-secondary)" }}>Active Tokens</h2>
          {tokens.length === 0 ? (
            <Card><CardBody><p className="text-center text-sm" style={{ color: "var(--text-tertiary)" }}>No tokens deployed yet.</p></CardBody></Card>
          ) : (
            tokens.map((t) => <TokenCard key={t.id} token={t} onTrigger={(id) => triggerToken.mutate(id)} />)
          )}
        </div>

        <div className="space-y-3">
          <h2 className="text-sm font-medium" style={{ color: "var(--text-secondary)" }}>Alert Feed</h2>
          <Card>
            <CardBody className="space-y-3 p-3">
              {alerts.length === 0 ? (
                <p className="text-center text-xs py-4" style={{ color: "var(--text-tertiary)" }}>No alerts — tokens are quiet.</p>
              ) : (
                alerts.slice().reverse().map((a) => (
                  <div key={a.id} className="rounded-md border p-3 space-y-1" style={{ background: "var(--danger-900)", borderColor: "var(--danger-500)" }}>
                    <div className="flex items-center gap-2">
                      <AlertCircle className="h-3.5 w-3.5 shrink-0" style={{ color: "var(--danger-400)" }} />
                      <span className="text-xs font-semibold" style={{ color: "var(--danger-400)" }}>{a.token_name}</span>
                    </div>
                    <p className="text-xs" style={{ color: "var(--text-secondary)" }}>From: <strong>{a.source_ip}</strong></p>
                    {a.geo_location && <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>Location: {a.geo_location}</p>}
                    <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>{new Date(a.triggered_at).toLocaleString()}</p>
                  </div>
                ))
              )}
            </CardBody>
          </Card>
        </div>
      </div>
    </div>
  );
}
