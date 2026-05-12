import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Shield, Plus, Play, Trash2, AlertTriangle, Globe, Server, Lock, Loader2, ChevronDown, ChevronRight } from "lucide-react";
import { Card, CardBody, CardHeader } from "@/shared/components/Card";
import { Badge } from "@/shared/components/Badge";
import { Button } from "@/shared/components/Button";
import { apiClient } from "@/shared/api/client";
import { toast } from "@/shared/components/Toast";

interface AssetSeed {
  type: "domain" | "ip_cidr" | "asn" | "org";
  value: string;
}

interface Subscription {
  id: string;
  name: string;
  seeds: AssetSeed[];
  scan_interval_hours: number;
  alert_on: string[];
  last_scan_at: string | null;
  asset_count: number;
  created_at: string;
  status: string;
}

interface AssetRecord {
  asset_id: string;
  type: string;
  value: string;
  first_seen: string;
  last_seen: string;
  tags: string[];
  risk_score: number;
}

interface DeltaAlert {
  alert_id: string;
  type: string;
  asset: AssetRecord;
  detected_at: string;
}

const ASSET_ICONS: Record<string, typeof Globe> = {
  ip: Server,
  subdomain: Globe,
  port: Lock,
  cert: Lock,
  domain: Globe,
};

function RiskBadge({ score }: { score: number }) {
  const variant = score >= 0.7 ? "danger" : score >= 0.4 ? "warning" : "success";
  return <Badge variant={variant} size="sm">{Math.round(score * 100)}%</Badge>;
}

function SubscriptionCard({ sub, onScan, onDelete }: { sub: Subscription; onScan: (id: string) => void; onDelete: (id: string) => void }) {
  const [expanded, setExpanded] = useState(false);

  const { data: detail } = useQuery({
    queryKey: ["attack-surface-detail", sub.id],
    queryFn: async () => {
      const res = await apiClient.get(`/attack-surface/subscriptions/${sub.id}`);
      return res.data as Subscription & { assets: AssetRecord[]; recent_alerts: DeltaAlert[] };
    },
    enabled: expanded,
  });

  return (
    <Card>
      <CardHeader className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Shield className="h-4 w-4 shrink-0" style={{ color: "var(--brand-500)" }} />
          <div>
            <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{sub.name}</p>
            <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
              {sub.seeds.map((s) => s.value).join(", ")} · Every {sub.scan_interval_hours}h
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="neutral" size="sm">{sub.asset_count} assets</Badge>
          <Badge variant={sub.status === "active" ? "success" : "warning"} size="sm" dot>{sub.status}</Badge>
          <Button variant="ghost" size="sm" leftIcon={<Play className="h-3.5 w-3.5" />} onClick={() => onScan(sub.id)}>
            Scan
          </Button>
          <button onClick={() => onDelete(sub.id)} className="rounded p-1 hover:bg-bg-overlay" title="Delete subscription">
            <Trash2 className="h-3.5 w-3.5" style={{ color: "var(--danger-500)" }} />
          </button>
          <button onClick={() => setExpanded((p) => !p)} className="rounded p-1 hover:bg-bg-overlay">
            {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          </button>
        </div>
      </CardHeader>

      {expanded && detail && (
        <CardBody className="pt-0 space-y-3">
          {detail.recent_alerts.length > 0 && (
            <div>
              <p className="text-xs font-semibold mb-2" style={{ color: "var(--warning-400)" }}>
                <AlertTriangle className="inline h-3 w-3 mr-1" />
                {detail.recent_alerts.length} New Alert{detail.recent_alerts.length !== 1 ? "s" : ""}
              </p>
              {detail.recent_alerts.map((alert) => (
                <div
                  key={alert.alert_id}
                  className="flex items-center gap-3 rounded-md px-3 py-2 text-xs mb-1"
                  style={{ background: "rgba(245,158,11,0.1)", borderLeft: "3px solid var(--warning-500)" }}
                >
                  <span style={{ color: "var(--warning-400)" }}>{alert.type.replace(/_/g, " ")}</span>
                  <span className="font-mono" style={{ color: "var(--text-primary)" }}>{alert.asset.value}</span>
                  <span className="ml-auto" style={{ color: "var(--text-tertiary)" }}>
                    {new Date(alert.detected_at).toLocaleTimeString()}
                  </span>
                </div>
              ))}
            </div>
          )}

          <div>
            <p className="text-xs font-semibold mb-2" style={{ color: "var(--text-secondary)" }}>
              Discovered Assets ({detail.assets.length})
            </p>
            <div className="space-y-1 max-h-48 overflow-y-auto">
              {detail.assets.map((asset) => {
                const Icon = ASSET_ICONS[asset.type] ?? Globe;
                return (
                  <div
                    key={asset.asset_id}
                    className="flex items-center gap-2 rounded-md px-3 py-1.5"
                    style={{ background: "var(--bg-elevated)" }}
                  >
                    <Icon className="h-3.5 w-3.5 shrink-0" style={{ color: "var(--text-tertiary)" }} />
                    <span className="flex-1 text-xs font-mono truncate" style={{ color: "var(--text-primary)" }}>{asset.value}</span>
                    <Badge variant="neutral" size="sm">{asset.type}</Badge>
                    <RiskBadge score={asset.risk_score} />
                  </div>
                );
              })}
            </div>
          </div>
        </CardBody>
      )}
    </Card>
  );
}

function CreateSubscriptionModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [seeds, setSeeds] = useState<AssetSeed[]>([{ type: "domain", value: "" }]);
  const [intervalHours, setIntervalHours] = useState(24);

  const createMutation = useMutation({
    mutationFn: async () => {
      const res = await apiClient.post("/attack-surface/subscriptions", {
        name,
        seeds: seeds.filter((s) => s.value.trim()),
        scan_interval_hours: intervalHours,
        alert_on: ["new_asset", "port_change", "vuln_detected"],
      });
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["attack-surface-subscriptions"] });
      toast.success("Subscription created");
      onClose();
    },
    onError: () => toast.error("Failed to create subscription"),
  });

  const addSeed = () => setSeeds([...seeds, { type: "domain", value: "" }]);
  const updateSeed = (i: number, field: keyof AssetSeed, value: string) => {
    setSeeds(seeds.map((s, idx) => (idx === i ? { ...s, [field]: value } : s)));
  };
  const removeSeed = (i: number) => setSeeds(seeds.filter((_, idx) => idx !== i));

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div
        className="w-full max-w-md rounded-xl border p-6 shadow-2xl"
        style={{ background: "var(--bg-surface)", borderColor: "var(--border-default)" }}
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-sm font-semibold mb-4" style={{ color: "var(--text-primary)" }}>New Attack Surface Subscription</h2>

        <div className="space-y-3">
          <div>
            <label className="text-xs font-medium mb-1 block" style={{ color: "var(--text-secondary)" }}>Name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="My Company Surface"
              className="w-full rounded-md border px-3 py-2 text-sm"
              style={{ background: "var(--bg-elevated)", borderColor: "var(--border-default)", color: "var(--text-primary)" }}
            />
          </div>

          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>Seeds</label>
              <button onClick={addSeed} className="text-xs" style={{ color: "var(--brand-400)" }}>+ Add</button>
            </div>
            {seeds.map((seed, i) => (
              <div key={i} className="flex gap-2 mb-1">
                <select
                  value={seed.type}
                  onChange={(e) => updateSeed(i, "type", e.target.value)}
                  className="rounded-md border px-2 py-1.5 text-xs w-28"
                  style={{ background: "var(--bg-elevated)", borderColor: "var(--border-default)", color: "var(--text-primary)" }}
                >
                  {["domain", "ip_cidr", "asn", "org"].map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
                <input
                  value={seed.value}
                  onChange={(e) => updateSeed(i, "value", e.target.value)}
                  placeholder={seed.type === "domain" ? "example.com" : seed.type === "ip_cidr" ? "10.0.0.0/24" : seed.type === "asn" ? "AS15169" : "Company Name"}
                  className="flex-1 rounded-md border px-2 py-1.5 text-xs font-mono"
                  style={{ background: "var(--bg-elevated)", borderColor: "var(--border-default)", color: "var(--text-primary)" }}
                />
                {seeds.length > 1 && (
                  <button onClick={() => removeSeed(i)} className="text-xs" style={{ color: "var(--danger-500)" }}>✕</button>
                )}
              </div>
            ))}
          </div>

          <div>
            <label className="text-xs font-medium mb-1 block" style={{ color: "var(--text-secondary)" }}>
              Scan Interval: every {intervalHours}h
            </label>
            <input
              type="range" min={1} max={168} step={1}
              value={intervalHours}
              onChange={(e) => setIntervalHours(Number(e.target.value))}
              className="w-full"
            />
          </div>

          <div className="flex justify-end gap-2 pt-1">
            <Button variant="ghost" size="sm" onClick={onClose}>Cancel</Button>
            <Button
              size="sm"
              leftIcon={<Plus className="h-3.5 w-3.5" />}
              loading={createMutation.isPending}
              disabled={!name.trim() || seeds.every((s) => !s.value.trim())}
              onClick={() => createMutation.mutate()}
            >
              Create
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

export function AttackSurfacePage() {
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);

  const { data: subscriptions, isLoading } = useQuery({
    queryKey: ["attack-surface-subscriptions"],
    queryFn: async () => {
      const res = await apiClient.get("/attack-surface/subscriptions");
      return res.data as Subscription[];
    },
  });

  const scanMutation = useMutation({
    mutationFn: async (subId: string) => {
      const res = await apiClient.post(`/attack-surface/subscriptions/${subId}/scan`);
      return res.data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["attack-surface-subscriptions"] });
      queryClient.invalidateQueries({ queryKey: ["attack-surface-detail", data.sub_id] });
      toast.success(`Scan complete: ${data.assets_discovered} assets, ${data.new_alerts} alerts`);
    },
    onError: () => toast.error("Scan failed"),
  });

  const deleteMutation = useMutation({
    mutationFn: async (subId: string) => apiClient.delete(`/attack-surface/subscriptions/${subId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["attack-surface-subscriptions"] });
      toast.success("Subscription deleted");
    },
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Attack Surface Monitor</h1>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Continuously discover and track your organization's external attack surface with delta alerts.
          </p>
        </div>
        <Button leftIcon={<Plus className="h-4 w-4" />} onClick={() => setShowCreate(true)}>
          New Subscription
        </Button>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-6 w-6 animate-spin" style={{ color: "var(--brand-500)" }} />
        </div>
      ) : subscriptions?.length === 0 ? (
        <Card>
          <CardBody className="py-16 text-center">
            <Shield className="mx-auto h-8 w-8 mb-3" style={{ color: "var(--text-tertiary)" }} />
            <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>No subscriptions yet</p>
            <p className="text-xs mt-1 mb-4" style={{ color: "var(--text-tertiary)" }}>
              Add a domain, IP range, or ASN to start monitoring
            </p>
            <Button size="sm" leftIcon={<Plus className="h-3.5 w-3.5" />} onClick={() => setShowCreate(true)}>
              New Subscription
            </Button>
          </CardBody>
        </Card>
      ) : (
        <div className="space-y-3">
          {(subscriptions ?? []).map((sub) => (
            <SubscriptionCard
              key={sub.id}
              sub={sub}
              onScan={(id) => scanMutation.mutate(id)}
              onDelete={(id) => deleteMutation.mutate(id)}
            />
          ))}
        </div>
      )}

      {showCreate && <CreateSubscriptionModal onClose={() => setShowCreate(false)} />}
    </div>
  );
}
