import { useState } from "react";
import { Network, Search, Trash2 } from "lucide-react";
import { useAsnIntelLookup, useAsnIntelHistory, useDeleteAsnIntelScan } from "./hooks";
import type { AsnIntelResult, AsnPeer, AsnPrefix } from "./types";
import { Button } from "@/shared/components/Button";
import { Input } from "@/shared/components/Input";
import { Card, CardBody } from "@/shared/components/Card";
import { Badge } from "@/shared/components/Badge";

function InfoRow({ label, value }: { label: string; value: string | number | null | undefined }) {
  if (!value && value !== 0) return null;
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs font-medium" style={{ color: "var(--text-tertiary)" }}>{label}</span>
      <span className="text-sm font-mono break-all" style={{ color: "var(--text-primary)" }}>{String(value)}</span>
    </div>
  );
}

function PrefixTable({ prefixes, title }: { prefixes: AsnPrefix[]; title: string }) {
  if (!prefixes.length) return null;
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: "var(--text-tertiary)" }}>{title} ({prefixes.length})</p>
      <div className="space-y-1">
        {prefixes.map((p) => (
          <div key={p.prefix} className="flex items-center justify-between rounded px-3 py-2 text-xs" style={{ background: "var(--bg-overlay)" }}>
            <span className="font-mono font-medium" style={{ color: "var(--text-primary)" }}>{p.prefix}</span>
            <span style={{ color: "var(--text-tertiary)" }}>{[p.name, p.country].filter(Boolean).join(" · ")}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function PeerList({ peers, title }: { peers: AsnPeer[]; title: string }) {
  if (!peers.length) return null;
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: "var(--text-tertiary)" }}>{title} ({peers.length})</p>
      <div className="flex flex-wrap gap-2">
        {peers.map((p) => (
          <Badge key={p.asn} variant="neutral" size="sm">AS{p.asn} {p.name ?? ""}</Badge>
        ))}
      </div>
    </div>
  );
}

function AsnResults({ data }: { data: AsnIntelResult }) {
  if (!data.found) {
    return (
      <div className="rounded-xl border py-10 text-center" style={{ borderColor: "var(--border-subtle)" }}>
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>No ASN found for query "{data.query}"</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <InfoRow label="ASN" value={data.asn ? `AS${data.asn}` : null} />
        <InfoRow label="Name" value={data.name} />
        <InfoRow label="Country" value={data.country} />
        <InfoRow label="RIR" value={data.rir} />
        <InfoRow label="Website" value={data.website} />
        <InfoRow label="Description" value={data.description} />
      </div>
      {data.email_contacts.length > 0 && (
        <div>
          <p className="text-xs font-medium mb-1" style={{ color: "var(--text-tertiary)" }}>Email Contacts</p>
          <div className="flex flex-wrap gap-1">{data.email_contacts.map((e) => <Badge key={e} variant="neutral" size="sm">{e}</Badge>)}</div>
        </div>
      )}
      {data.abuse_contacts.length > 0 && (
        <div>
          <p className="text-xs font-medium mb-1" style={{ color: "var(--text-tertiary)" }}>Abuse Contacts</p>
          <div className="flex flex-wrap gap-1">{data.abuse_contacts.map((e) => <Badge key={e} variant="warning" size="sm">{e}</Badge>)}</div>
        </div>
      )}
      <PrefixTable prefixes={data.prefixes_v4} title="IPv4 Prefixes" />
      <PrefixTable prefixes={data.prefixes_v6} title="IPv6 Prefixes" />
      <PeerList peers={data.peers} title="Peers" />
      <PeerList peers={data.upstreams} title="Upstreams" />
      <PeerList peers={data.downstreams} title="Downstreams" />
    </div>
  );
}

function AsnHistory({ onSelect }: { onSelect: (item: AsnIntelResult) => void }) {
  const { data, isLoading } = useAsnIntelHistory();
  const deleteScan = useDeleteAsnIntelScan();

  if (isLoading) return <p className="text-xs py-4 text-center" style={{ color: "var(--text-tertiary)" }}>Loading history...</p>;
  if (!data?.items.length) return <p className="text-xs py-4 text-center" style={{ color: "var(--text-tertiary)" }}>No previous scans yet.</p>;

  return (
    <div className="space-y-1">
      {data.items.map((item) => (
        <div
          key={item.id}
          className="flex items-center justify-between rounded-lg px-3 py-2 cursor-pointer hover:bg-opacity-80"
          style={{ background: "var(--bg-overlay)" }}
          onClick={() => onSelect(item)}
        >
          <div className="flex-1 min-w-0">
            <p className="text-sm font-mono truncate" style={{ color: "var(--text-primary)" }}>{item.query}</p>
            <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
              {item.found ? `AS${item.asn} · ${item.name ?? ""}` : "Not found"} · {item.created_at ? new Date(item.created_at).toLocaleString() : ""}
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

export function AsnIntelPage() {
  const [query, setQuery] = useState("");
  const lookup = useAsnIntelLookup();
  const [currentResult, setCurrentResult] = useState<AsnIntelResult | null>(null);

  const handleLookup = () => {
    if (query.trim()) lookup.mutate(query.trim(), { onSuccess: (d) => setCurrentResult(d) });
  };

  const result = lookup.data ?? currentResult;

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <Network className="h-6 w-6" style={{ color: "var(--brand-400)" }} />
        <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>ASN Intelligence</h1>
      </div>

      <Card>
        <CardBody>
          <div className="flex gap-3">
            <div className="flex-1">
              <Input
                placeholder="ASN number (e.g. 15169 or AS15169) or IP address..."
                prefixIcon={<Search className="h-4 w-4" />}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleLookup()}
              />
            </div>
            <Button onClick={handleLookup} disabled={!query.trim() || lookup.isPending} leftIcon={<Network className="h-4 w-4" />}>
              {lookup.isPending ? "Looking up..." : "Lookup ASN"}
            </Button>
          </div>
          <p className="mt-2 text-xs" style={{ color: "var(--text-tertiary)" }}>
            BGP routing data via BGPView API — free, no API key required.
          </p>
        </CardBody>
      </Card>

      {result && <AsnResults data={result} />}

      {!result && !lookup.isPending && (
        <div className="rounded-xl border py-16 text-center" style={{ borderColor: "var(--border-subtle)" }}>
          <Network className="mx-auto h-10 w-10 mb-3" style={{ color: "var(--text-tertiary)" }} />
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Enter an ASN number or IP to look up BGP routing details</p>
        </div>
      )}

      <div className="rounded-xl border p-5" style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}>
        <h2 className="mb-3 text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Scan History</h2>
        <AsnHistory onSelect={setCurrentResult} />
      </div>
    </div>
  );
}
