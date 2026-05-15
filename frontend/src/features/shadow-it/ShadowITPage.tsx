import { useState } from "react";
import { Cloud, Search, AlertTriangle, Globe, Shield } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import apiClient from "@/shared/api/client";
import { Button } from "@/shared/components/Button";
import { Input } from "@/shared/components/Input";
import { Card, CardBody, CardHeader } from "@/shared/components/Card";
import { Badge } from "@/shared/components/Badge";
import { ScanResultErrorBoundary } from "@/shared/components/osint/ScanResultErrorBoundary";

interface ShadowAsset       {mutationError && (
        <p role="alert" className="text-xs rounded-lg px-3 py-2 border" style={{ color: "var(--danger-400)", borderColor: "var(--danger-500)", background: "var(--bg-surface)" }}>
          {mutationError}
        </p>
      )}
      {
  asset_id: string;
  asset_type: string;
  cloud_provider: string;
  identifier: string;
  region: string | null;
  ports_open: number[];
  services: string[];
  is_public: boolean;
  misconfiguration_flags: string[];
  data_sensitivity_estimate: string;
  risk_score: number;
  likely_team: string | null;
}

interface ShadowITResult {
  org_name: string;
  total_assets: number;
  high_risk_assets: number;
  public_assets: number;
  misconfigured_assets: number;
  assets: ShadowAsset[];
  top_misconfiguration_types: string[];
  estimated_data_exposure: string;
}

const providerColor: Record<string, string> = {
  aws: "#FF9900",
  azure: "#0078D4",
  gcp: "#4285F4",
  unknown: "var(--text-tertiary)",
};

const sensitivityVariant = (s: string): "danger" | "warning" | "neutral" => {
  if (s === "high") return "danger";
  if (s === "medium") return "warning";
  return "neutral";
};

function AssetCard({ asset }: { asset: ShadowAsset }) {
  return (
    <div
      className="rounded-xl border p-4 space-y-2"
      style={{
        background: "var(--bg-surface)",
        borderColor: asset.risk_score >= 0.6 ? "var(--danger-500)" : "var(--border-subtle)",
      }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span
              className="text-xs font-bold px-1.5 py-0.5 rounded"
              style={{ background: "var(--bg-raised)", color: providerColor[asset.cloud_provider] || "var(--text-secondary)" }}
            >
              {asset.cloud_provider.toUpperCase()}
            </span>
            <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>{asset.asset_type}</span>
            {asset.is_public && <Badge variant="danger" size="sm">Public</Badge>}
            <Badge variant={sensitivityVariant(asset.data_sensitivity_estimate)} size="sm">
              {asset.data_sensitivity_estimate} sensitivity
            </Badge>
          </div>
          <p className="text-xs font-mono truncate" style={{ color: "var(--text-primary)" }}>{asset.identifier}</p>
          {asset.region && <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>{asset.region}</p>}
        </div>
        <div className="text-right shrink-0">
          <p className="text-lg font-bold" style={{ color: asset.risk_score >= 0.6 ? "var(--danger-400)" : "var(--warning-400)" }}>
            {(asset.risk_score * 10).toFixed(1)}
          </p>
          <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>risk</p>
        </div>
      </div>

      {asset.misconfiguration_flags.length > 0 && (
        <div className="space-y-1">
          {asset.misconfiguration_flags.map((flag) => (
            <div key={flag} className="flex items-start gap-2 text-xs">
              <AlertTriangle className="h-3 w-3 shrink-0 mt-0.5" style={{ color: "var(--danger-400)" }} />
              <span style={{ color: "var(--text-secondary)" }}>{flag}</span>
            </div>
          ))}
        </div>
      )}

      <div className="flex items-center gap-3 text-xs" style={{ color: "var(--text-tertiary)" }}>
        {asset.ports_open.length > 0 && <span>Ports: {asset.ports_open.join(", ")}</span>}
        {asset.likely_team && <span>Team: {asset.likely_team}</span>}
      </div>
    </div>
  );
}

export function ShadowITPage() {
  const [orgName, setOrgName] = useState("");
  const [mutationError, setMutationError] = useState<string | null>(null);
  const [domain, setDomain] = useState("");

  const discover = useMutation({
    mutationFn: (data: { org_name: string; domains: string[] }) =>
      apiClient.post<ShadowITResult>("/api/v1/shadow-it/discover", data).then((r) => r.data),
  });

  const handleDiscover = () => {
    if (!orgName.trim()) return;
    discover.mutate({
      org_name: orgName.trim(),
      domains: domain.trim() ? [domain.trim()] : [],
    });
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <Cloud className="h-6 w-6" style={{ color: "var(--brand-400)" }} />
        <div>
          <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Shadow IT Discovery</h1>
          <p className="text-xs mt-0.5" style={{ color: "var(--text-tertiary)" }}>Discover unenumerated cloud assets and shadow infrastructure</p>
        </div>
      </div>

      <Card>
        <CardHeader>
          <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>Organization Discovery</p>
        </CardHeader>
        <CardBody className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs mb-1 block" style={{ color: "var(--text-tertiary)" }}>Organization Name *</label>
              <Input
                placeholder="Acme Corporation"
                prefixIcon={<Globe className="h-4 w-4" />}
                value={orgName}
                onChange={(e) => setOrgName(e.target.value)}
              />
            </div>
            <div>
              <label className="text-xs mb-1 block" style={{ color: "var(--text-tertiary)" }}>Primary Domain</label>
              <Input placeholder="acme.com" value={domain} onChange={(e) => setDomain(e.target.value)} />
            </div>
          </div>
          <Button
            onClick={handleDiscover}
            disabled={!orgName.trim() || discover.isPending}
            leftIcon={<Search className="h-4 w-4" />}
          >
            {discover.isPending ? "Discovering..." : "Discover Assets"}
          </Button>
        </CardBody>
      </Card>

      {discover.data && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[
              { label: "Total Assets", value: discover.data.total_assets, color: "var(--text-primary)" },
              { label: "High Risk", value: discover.data.high_risk_assets, color: "var(--danger-400)" },
              { label: "Public", value: discover.data.public_assets, color: "var(--warning-400)" },
              { label: "Misconfigured", value: discover.data.misconfigured_assets, color: "var(--warning-400)" },
            ].map(({ label, value, color }) => (
              <div key={label} className="rounded-xl border p-3 text-center" style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}>
                <p className="text-2xl font-bold" style={{ color }}>{value}</p>
                <p className="text-xs mt-1" style={{ color: "var(--text-tertiary)" }}>{label}</p>
              </div>
            ))}
          </div>

          {discover.data.top_misconfiguration_types.length > 0 && (
            <div className="rounded-xl border p-4" style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}>
              <p className="text-xs font-medium mb-2" style={{ color: "var(--text-primary)" }}>Top Misconfigurations</p>
              <div className="space-y-1">
                {discover.data.top_misconfiguration_types.map((m) => (
                  <div key={m} className="flex items-start gap-2 text-xs">
                    <AlertTriangle className="h-3 w-3 shrink-0 mt-0.5" style={{ color: "var(--danger-400)" }} />
                    <span style={{ color: "var(--text-secondary)" }}>{m}</span>
                  </div>
                ))}
              </div>
              <p className="text-xs mt-2" style={{ color: "var(--text-tertiary)" }}>{discover.data.estimated_data_exposure}</p>
            </div>
          )}

          <div className="space-y-3">
            <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Discovered Assets</p>
            {discover.data.assets.map((a) => <AssetCard key={a.asset_id} asset={a} />)}
          </div>
        </div>
      )}

      {!discover.data && !discover.isPending && (
        <div className="rounded-xl border py-16 text-center" style={{ borderColor: "var(--border-subtle)" }}>
          <Cloud className="mx-auto h-10 w-10 mb-3" style={{ color: "var(--text-tertiary)" }} />
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Enter organization details to discover shadow IT assets</p>
        </div>
      )}
    </div>
  );
}
