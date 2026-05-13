import { useState } from "react";
import { AlertTriangle, Search, CheckCircle, Globe, Trash2 } from "lucide-react";
import { useSubdomainTakeover, useSubdomainTakeoverHistory, useDeleteSubdomainTakeoverScan } from "./hooks";
import type { SubdomainResult, SubdomainTakeoverResult } from "./types";
import { Button } from "@/shared/components/Button";
import { Input } from "@/shared/components/Input";
import { Card, CardBody } from "@/shared/components/Card";
import { Badge } from "@/shared/components/Badge";

function SubdomainRow({ sub, vulnerable }: { sub: SubdomainResult; vulnerable: boolean }) {
  return (
    <div
      className="flex items-start gap-3 rounded-lg border px-4 py-3"
      style={{
        background: "var(--bg-surface)",
        borderColor: vulnerable ? "var(--danger-500)" : "var(--border-subtle)",
      }}
    >
      {vulnerable ? (
        <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" style={{ color: "var(--danger-400)" }} />
      ) : (
        <CheckCircle className="h-4 w-4 mt-0.5 shrink-0" style={{ color: "var(--success-400, #4ade80)" }} />
      )}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-mono text-sm" style={{ color: "var(--text-primary)" }}>{sub.subdomain}</span>
          {sub.vulnerable_service && <Badge variant="danger" size="sm">{sub.vulnerable_service}</Badge>}
        </div>
        {sub.cname && (
          <p className="text-xs font-mono mt-0.5" style={{ color: "var(--text-tertiary)" }}>→ {sub.cname}</p>
        )}
        {sub.note && (
          <p className="text-xs mt-1" style={{ color: "var(--text-secondary)" }}>{sub.note}</p>
        )}
      </div>
    </div>
  );
}

function TakeoverResults({ data }: { data: SubdomainTakeoverResult }) {
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-3">
        {[
          { label: "Total Subdomains", value: data.total_subdomains, color: "var(--text-primary)" },
          { label: "Vulnerable", value: data.vulnerable.length, color: data.vulnerable.length > 0 ? "var(--danger-400)" : "var(--success-400, #4ade80)" },
          { label: "Safe", value: data.safe.length, color: "var(--success-400, #4ade80)" },
        ].map(({ label, value, color }) => (
          <div key={label} className="rounded-xl border p-4 text-center" style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}>
            <p className="text-3xl font-bold" style={{ color }}>{value}</p>
            <p className="text-xs mt-1" style={{ color: "var(--text-tertiary)" }}>{label}</p>
          </div>
        ))}
      </div>

      {data.vulnerable.length > 0 && (
        <div className="space-y-2">
          <p className="text-sm font-semibold" style={{ color: "var(--danger-400)" }}>Potentially Vulnerable ({data.vulnerable.length})</p>
          {data.vulnerable.map((s) => <SubdomainRow key={s.subdomain} sub={s} vulnerable />)}
        </div>
      )}

      {data.safe.length > 0 && (
        <details>
          <summary className="text-sm cursor-pointer py-2" style={{ color: "var(--text-tertiary)" }}>
            Safe subdomains ({data.safe.length})
          </summary>
          <div className="mt-2 space-y-1">
            {data.safe.map((s) => <SubdomainRow key={s.subdomain} sub={s} vulnerable={false} />)}
          </div>
        </details>
      )}
    </div>
  );
}

function SubdomainTakeoverHistory({ onSelect }: { onSelect: (item: SubdomainTakeoverResult) => void }) {
  const { data, isLoading } = useSubdomainTakeoverHistory();
  const deleteScan = useDeleteSubdomainTakeoverScan();

  if (isLoading) return <p className="text-xs py-4 text-center" style={{ color: "var(--text-tertiary)" }}>Loading history...</p>;
  if (!data?.items.length) return <p className="text-xs py-4 text-center" style={{ color: "var(--text-tertiary)" }}>No previous scans yet.</p>;

  return (
    <div className="space-y-1">
      {data.items.map((item) => (
        <div
          key={item.id}
          className="flex items-center justify-between rounded-lg px-3 py-2 cursor-pointer"
          style={{ background: "var(--bg-overlay)" }}
          onClick={() => onSelect(item)}
        >
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <p className="text-sm font-mono truncate" style={{ color: "var(--text-primary)" }}>{item.domain}</p>
              {item.vulnerable.length > 0 && (
                <span className="text-xs px-1.5 py-0.5 rounded font-medium" style={{ background: "var(--danger-900, rgba(239,68,68,0.15))", color: "var(--danger-400)" }}>
                  {item.vulnerable.length} vulnerable
                </span>
              )}
            </div>
            <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
              {item.total_subdomains} subdomains · {item.created_at ? new Date(item.created_at).toLocaleString() : ""}
            </p>
          </div>
          <button
            className="ml-2 p-1 rounded opacity-60 hover:opacity-100"
            onClick={(e) => { e.stopPropagation(); if (item.id) deleteScan.mutate(item.id); }}
          >
            <Trash2 className="h-3.5 w-3.5" style={{ color: "var(--danger-400)" }} />
          </button>
        </div>
      ))}
    </div>
  );
}

export function SubdomainTakeoverPage() {
  const [domain, setDomain] = useState("");
  const scan = useSubdomainTakeover();
  const [currentResult, setCurrentResult] = useState<SubdomainTakeoverResult | null>(null);

  const handleScan = () => {
    if (domain.trim()) scan.mutate(domain.trim(), { onSuccess: (d) => setCurrentResult(d) });
  };

  const result = scan.data ?? currentResult;

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <AlertTriangle className="h-6 w-6" style={{ color: "var(--warning-400)" }} />
        <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Subdomain Takeover Detection</h1>
      </div>

      <Card>
        <CardBody>
          <div className="flex gap-3">
            <div className="flex-1">
              <Input
                placeholder="example.com"
                prefixIcon={<Search className="h-4 w-4" />}
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleScan()}
              />
            </div>
            <Button onClick={handleScan} disabled={!domain.trim() || scan.isPending} leftIcon={<Globe className="h-4 w-4" />}>
              {scan.isPending ? "Scanning..." : "Scan Domain"}
            </Button>
          </div>
          <p className="mt-2 text-xs" style={{ color: "var(--text-tertiary)" }}>
            Discovers subdomains via crt.sh and checks CNAME records for dangling cloud service pointers.
          </p>
        </CardBody>
      </Card>

      {result && <TakeoverResults data={result} />}

      {!result && !scan.isPending && (
        <div className="rounded-xl border py-16 text-center" style={{ borderColor: "var(--border-subtle)" }}>
          <AlertTriangle className="mx-auto h-10 w-10 mb-3" style={{ color: "var(--text-tertiary)" }} />
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Enter a domain to check for subdomain takeover vulnerabilities</p>
        </div>
      )}

      <div className="rounded-xl border p-5" style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}>
        <h2 className="mb-3 text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Scan History</h2>
        <SubdomainTakeoverHistory onSelect={setCurrentResult} />
      </div>
    </div>
  );
}
