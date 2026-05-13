import { useState } from "react";
import { Mail, Search, AlertTriangle, CheckCircle, ExternalLink } from "lucide-react";
import { useEmailPivot } from "./hooks";
import type { EmailPivotResult } from "./types";
import { Button } from "@/shared/components/Button";
import { Input } from "@/shared/components/Input";
import { Card, CardBody } from "@/shared/components/Card";
import { Badge } from "@/shared/components/Badge";

function EmailResults({ data }: { data: EmailPivotResult }) {
  return (
    <div className="space-y-4">
      {/* Status row */}
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-xl border p-4 text-center" style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}>
          <p className="text-2xl font-bold" style={{ color: data.linked_accounts.length > 0 ? "var(--brand-400)" : "var(--text-tertiary)" }}>
            {data.linked_accounts.length}
          </p>
          <p className="text-xs mt-1" style={{ color: "var(--text-tertiary)" }}>Linked Accounts</p>
        </div>
        <div className="rounded-xl border p-4 text-center" style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}>
          <p className="text-2xl font-bold" style={{ color: data.hibp_breaches.length > 0 ? "var(--danger-400)" : "var(--success-400, #4ade80)" }}>
            {data.hibp_breaches.length}
          </p>
          <p className="text-xs mt-1" style={{ color: "var(--text-tertiary)" }}>Breaches</p>
        </div>
        <div className="rounded-xl border p-4 text-center" style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}>
          <p className="text-2xl font-bold" style={{ color: data.disposable ? "var(--warning-400)" : "var(--success-400, #4ade80)" }}>
            {data.disposable ? "Yes" : "No"}
          </p>
          <p className="text-xs mt-1" style={{ color: "var(--text-tertiary)" }}>Disposable</p>
        </div>
      </div>

      {/* Breach warning */}
      {data.hibp_breaches.length > 0 && (
        <div className="flex items-start gap-3 rounded-xl border px-4 py-3" style={{ borderColor: "var(--danger-500)", background: "var(--danger-900, rgba(239,68,68,0.1))" }}>
          <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" style={{ color: "var(--danger-400)" }} />
          <div>
            <p className="text-sm font-semibold" style={{ color: "var(--danger-400)" }}>Found in {data.hibp_breaches.length} data breach(es)</p>
            <div className="flex flex-wrap gap-1 mt-1">
              {data.hibp_breaches.map((b) => <Badge key={b} variant="danger" size="sm">{b}</Badge>)}
            </div>
          </div>
        </div>
      )}

      {/* Linked accounts */}
      {data.linked_accounts.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--text-tertiary)" }}>Linked Accounts</p>
          {data.linked_accounts.map((acct) => (
            <div key={acct.platform} className="flex items-center gap-3 rounded-lg border px-4 py-3" style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}>
              {acct.avatar_url && (
                <img src={acct.avatar_url} alt={acct.display_name ?? acct.platform} className="h-8 w-8 rounded-full" />
              )}
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>{acct.platform}</p>
                {acct.display_name && <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>{acct.display_name}</p>}
              </div>
              {acct.profile_url && (
                <a href={acct.profile_url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 text-xs hover:underline" style={{ color: "var(--brand-400)" }}>
                  <ExternalLink className="h-3 w-3" /> View
                </a>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function EmailPivotPage() {
  const [email, setEmail] = useState("");
  const [hibpKey, setHibpKey] = useState("");
  const pivot = useEmailPivot();

  const handleSearch = () => {
    if (email.trim()) pivot.mutate({ email: email.trim(), hibpKey });
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <Mail className="h-6 w-6" style={{ color: "var(--brand-400)" }} />
        <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Email Pivot</h1>
      </div>

      <Card>
        <CardBody>
          <div className="flex flex-col gap-3">
            <div className="flex gap-3">
              <div className="flex-1">
                <Input
                  placeholder="Email address to investigate..."
                  prefixIcon={<Search className="h-4 w-4" />}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                />
              </div>
              <Button onClick={handleSearch} disabled={!email.trim() || pivot.isPending} leftIcon={<Mail className="h-4 w-4" />}>
                {pivot.isPending ? "Pivoting..." : "Investigate"}
              </Button>
            </div>
            <Input
              placeholder="HIBP API key (optional — enables breach lookup)"
              value={hibpKey}
              onChange={(e) => setHibpKey(e.target.value)}
            />
            <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
              Checks Gravatar, GitHub public API, HaveIBeenPwned (requires key), and disposable email detection.
            </p>
          </div>
        </CardBody>
      </Card>

      {pivot.data && <EmailResults data={pivot.data} />}

      {!pivot.data && !pivot.isPending && (
        <div className="rounded-xl border py-16 text-center" style={{ borderColor: "var(--border-subtle)" }}>
          <Mail className="mx-auto h-10 w-10 mb-3" style={{ color: "var(--text-tertiary)" }} />
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Enter an email address to pivot and find linked accounts</p>
        </div>
      )}
    </div>
  );
}
