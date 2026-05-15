import { useState } from "react";
import { ShieldAlert, Search, DollarSign, Clock, AlertTriangle } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import apiClient from "@/shared/api/client";
import { Button } from "@/shared/components/Button";
import { Input } from "@/shared/components/Input";
import { Card, CardBody, CardHeader } from "@/shared/components/Card";
import { Badge } from "@/shared/components/Badge";
import { ScanResultErrorBoundary } from "@/shared/components/osint/ScanResultErrorBoundary";

interface IABListing       {mutationError && (
        <p role="alert" className="text-xs rounded-lg px-3 py-2 border" style={{ color: "var(--danger-400)", borderColor: "var(--danger-500)", background: "var(--bg-surface)" }}>
          {mutationError}
        </p>
      )}
      {
  listing_id: string;
  source: string;
  threat_actor: string;
  access_type: string;
  victim_domain: string | null;
  victim_sector: string;
  victim_country: string;
  employee_count: string;
  asking_price_usd: number | null;
  auction_ends: string | null;
  negotiable: boolean;
  access_description: string;
  antivirus_present: string | null;
  domain_admin: boolean;
  network_access: boolean;
  risk_score: number;
  ioc_overlap: string[];
}

interface IABScanResult {
  query: string;
  total_listings: number;
  critical_listings: number;
  estimated_exposure_usd: number;
  listings: IABListing[];
  top_threat_actors: string[];
}

const riskColor = (score: number) =>
  score >= 0.7 ? "var(--danger-400)" : score >= 0.5 ? "var(--warning-400)" : "var(--success-400)";

const riskLabel = (score: number) =>
  score >= 0.7 ? "critical" : score >= 0.5 ? "high" : score >= 0.3 ? "medium" : "low";

function ListingCard({ listing }: { listing: IABListing }) {
  return (
    <div
      className="rounded-xl border p-4 space-y-3"
      style={{ background: "var(--bg-surface)", borderColor: listing.risk_score >= 0.7 ? "var(--danger-500)" : "var(--border-subtle)" }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="flex items-center gap-2 flex-wrap">
            <Badge variant={listing.risk_score >= 0.7 ? "danger" : listing.risk_score >= 0.5 ? "warning" : "neutral"} size="sm">
              {riskLabel(listing.risk_score).toUpperCase()}
            </Badge>
            <span className="text-xs font-mono px-2 py-0.5 rounded" style={{ background: "var(--bg-raised)", color: "var(--text-secondary)" }}>
              {listing.access_type}
            </span>
            {listing.domain_admin && <Badge variant="danger" size="sm">Domain Admin</Badge>}
          </div>
          <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
            {listing.victim_sector} · {listing.victim_country} · {listing.employee_count} employees
          </p>
        </div>
        <div className="text-right shrink-0">
          {listing.asking_price_usd ? (
            <span className="text-sm font-bold" style={{ color: "var(--warning-400)" }}>
              ${listing.asking_price_usd.toLocaleString()}
            </span>
          ) : (
            <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>Negotiable</span>
          )}
          {listing.auction_ends && (
            <p className="text-xs mt-0.5" style={{ color: "var(--text-tertiary)" }}>
              <Clock className="inline h-3 w-3 mr-1" />
              Ends: {new Date(listing.auction_ends).toLocaleDateString()}
            </p>
          )}
        </div>
      </div>

      <p className="text-xs" style={{ color: "var(--text-secondary)" }}>{listing.access_description}</p>

      <div className="flex items-center gap-3 text-xs" style={{ color: "var(--text-tertiary)" }}>
        <span>Actor: <code className="px-1 rounded" style={{ background: "var(--bg-raised)" }}>{listing.threat_actor}</code></span>
        <span>Source: {listing.source}</span>
        {listing.antivirus_present && <span>AV: {listing.antivirus_present}</span>}
      </div>

      {listing.ioc_overlap.length > 0 && (
        <div className="flex gap-1 flex-wrap">
          {listing.ioc_overlap.map((ioc) => (
            <span key={ioc} className="text-xs px-1.5 py-0.5 rounded font-mono" style={{ background: "var(--danger-950)", color: "var(--danger-300)" }}>
              {ioc}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export function IABMonitorPage() {
  const [query, setQuery] = useState("");
  const [mutationError, setMutationError] = useState<string | null>(null);

  const scan = useMutation({
    mutationFn: (q: string) =>
      apiClient.post<IABScanResult>("/api/v1/iab-monitor/scan", { query: q }).then((r) => r.data),
  });

  const handleScan = () => {
    if (query.trim()) scan.mutate(query.trim());
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <ShieldAlert className="h-6 w-6" style={{ color: "var(--danger-400)" }} />
        <div>
          <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>IAB Monitor</h1>
          <p className="text-xs mt-0.5" style={{ color: "var(--text-tertiary)" }}>Initial Access Broker marketplace intelligence</p>
        </div>
      </div>

      <Card>
        <CardBody>
          <div className="flex gap-3">
            <div className="flex-1">
              <Input
                placeholder="Domain, org name, or IP range to match against IAB listings..."
                prefixIcon={<Search className="h-4 w-4" />}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleScan()}
              />
            </div>
            <Button onClick={handleScan} disabled={!query.trim() || scan.isPending} variant="danger" leftIcon={<ShieldAlert className="h-4 w-4" />}>
              {scan.isPending ? "Scanning..." : "Scan IAB"}
            </Button>
          </div>
          <p className="mt-2 text-xs" style={{ color: "var(--text-tertiary)" }}>
            Scans dark web IAB forums and marketplaces for access listings matching your target.
          </p>
        </CardBody>
      </Card>

      {scan.data && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[
              { label: "Total Listings", value: scan.data.total_listings, color: "var(--text-primary)" },
              { label: "Critical", value: scan.data.critical_listings, color: "var(--danger-400)" },
              { label: "Est. Exposure", value: `$${scan.data.estimated_exposure_usd.toLocaleString()}`, color: "var(--warning-400)" },
              { label: "Threat Actors", value: scan.data.top_threat_actors.length, color: "var(--text-primary)" },
            ].map(({ label, value, color }) => (
              <div key={label} className="rounded-xl border p-3 text-center" style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}>
                <p className="text-2xl font-bold" style={{ color }}>{value}</p>
                <p className="text-xs mt-1" style={{ color: "var(--text-tertiary)" }}>{label}</p>
              </div>
            ))}
          </div>

          {scan.data.listings.length === 0 ? (
            <div className="rounded-xl border py-10 text-center" style={{ borderColor: "var(--border-subtle)" }}>
              <p className="text-sm" style={{ color: "var(--text-secondary)" }}>No IAB listings found matching "{scan.data.query}"</p>
            </div>
          ) : (
            <div className="space-y-3">
              <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                Listings ({scan.data.listings.length})
              </p>
              {scan.data.listings.map((l) => <ListingCard key={l.listing_id} listing={l} />)}
            </div>
          )}
        </div>
      )}

      {!scan.data && !scan.isPending && (
        <div className="rounded-xl border py-16 text-center" style={{ borderColor: "var(--border-subtle)" }}>
          <ShieldAlert className="mx-auto h-10 w-10 mb-3" style={{ color: "var(--text-tertiary)" }} />
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Monitor IAB listings for your organization's infrastructure</p>
          <p className="text-xs mt-1" style={{ color: "var(--text-tertiary)" }}>Enter a domain name or company name to begin</p>
        </div>
      )}
    </div>
  );
}
