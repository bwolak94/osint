import { useState } from "react";
import { ShieldAlert, Search } from "lucide-react";
import { useBrandScan } from "./hooks";
import type { BrandThreat } from "./types";
import { Badge } from "@/shared/components/Badge";
import { Button } from "@/shared/components/Button";
import { Input } from "@/shared/components/Input";
import { Card, CardBody } from "@/shared/components/Card";

const riskVariant: Record<string, "danger" | "warning" | "info" | "neutral"> = {
  critical: "danger",
  high: "danger",
  medium: "warning",
  low: "neutral",
};

const statusVariant: Record<string, "danger" | "warning" | "neutral"> = {
  active: "danger",
  monitoring: "warning",
  taken_down: "neutral",
};

const typeLabel: Record<string, string> = {
  typosquat: "Typosquat",
  phishing_site: "Phishing Site",
  fake_social: "Fake Social",
  counterfeit_app: "Counterfeit App",
  impersonation: "Impersonation",
};

function ThreatCard({ threat }: { threat: BrandThreat }) {
  return (
    <div
      className="rounded-lg border p-4"
      style={{
        background: "var(--bg-surface)",
        borderColor:
          threat.risk_level === "critical" ? "var(--danger-500)" : "var(--border-default)",
      }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-2">
            <Badge variant={(riskVariant[threat.risk_level] ?? "neutral") as "success" | "warning" | "danger" | "info" | "neutral" | "brand"} size="sm">
              {threat.risk_level}
            </Badge>
            <Badge variant="neutral" size="sm">
              {typeLabel[threat.type]}
            </Badge>
            <Badge variant={(statusVariant[threat.status] ?? "neutral") as "success" | "warning" | "danger" | "info" | "neutral" | "brand"} size="sm">
              {threat.status.replace("_", " ")}
            </Badge>
          </div>
          <p className="font-mono text-sm font-medium" style={{ color: "var(--text-primary)" }}>
            {threat.threat_value}
          </p>
          <p className="text-xs mt-1" style={{ color: "var(--text-secondary)" }}>
            {threat.description}
          </p>
          {(threat.registrar || threat.hosting_ip) && (
            <p className="text-xs mt-1 font-mono" style={{ color: "var(--text-tertiary)" }}>
              {threat.registrar && `Registrar: ${threat.registrar}`}
              {threat.registrar && threat.hosting_ip && " · "}
              {threat.hosting_ip && `IP: ${threat.hosting_ip}`}
            </p>
          )}
        </div>
      </div>
      <p className="text-xs mt-2" style={{ color: "var(--text-tertiary)" }}>
        Detected: {new Date(threat.first_detected).toLocaleDateString()}
      </p>
    </div>
  );
}

const riskOrder: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };

export function BrandProtectionPage() {
  const [brand, setBrand] = useState("");
  const [filter, setFilter] = useState("all");
  const scan = useBrandScan();

  const threats =
    scan.data?.threats.filter(
      (t) => filter === "all" || t.status === filter || t.risk_level === filter
    ) ?? [];

  const sortedThreats = [...threats].sort(
    (a, b) => (riskOrder[a.risk_level] ?? 4) - (riskOrder[b.risk_level] ?? 4)
  );

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <ShieldAlert className="h-6 w-6" style={{ color: "var(--warning-400)" }} />
        <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
          Brand Protection Monitor
        </h1>
      </div>

      <Card>
        <CardBody>
          <div className="flex gap-3 flex-wrap">
            <div className="flex-1">
              <Input
                placeholder="Brand name, domain, product..."
                prefixIcon={<Search className="h-4 w-4" />}
                value={brand}
                onChange={(e) => setBrand(e.target.value)}
                onKeyDown={(e) =>
                  e.key === "Enter" && brand.trim() && scan.mutate(brand.trim())
                }
              />
            </div>
            <Button
              onClick={() => scan.mutate(brand.trim())}
              disabled={!brand.trim() || scan.isPending}
              leftIcon={<ShieldAlert className="h-4 w-4" />}
            >
              {scan.isPending ? "Scanning..." : "Scan Brand"}
            </Button>
          </div>
        </CardBody>
      </Card>

      {scan.data && (
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-4">
            {[
              { label: "Total Threats", value: scan.data.total_threats, color: "var(--text-primary)" },
              { label: "Critical", value: scan.data.critical_threats, color: "var(--danger-400)" },
              { label: "Active", value: scan.data.active_threats, color: "var(--warning-400)" },
              { label: "Taken Down", value: scan.data.taken_down, color: "var(--success-400)" },
            ].map(({ label, value, color }) => (
              <div
                key={label}
                className="rounded-xl border p-4 text-center"
                style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}
              >
                <p className="text-3xl font-bold" style={{ color }}>
                  {value}
                </p>
                <p className="text-xs mt-1" style={{ color: "var(--text-tertiary)" }}>
                  {label}
                </p>
              </div>
            ))}
          </div>

          <div className="flex gap-2 flex-wrap">
            {["all", "active", "monitoring", "taken_down", "critical", "high"].map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`rounded-md px-3 py-1.5 text-xs font-medium transition-all ${
                  filter === f
                    ? "bg-brand-900 text-brand-400"
                    : "text-text-secondary hover:bg-bg-overlay"
                }`}
              >
                {f.replace("_", " ")}
              </button>
            ))}
          </div>

          <div className="space-y-3">
            {sortedThreats.map((t) => (
              <ThreatCard key={t.id} threat={t} />
            ))}
          </div>
        </div>
      )}

      {!scan.data && !scan.isPending && (
        <div
          className="rounded-xl border py-16 text-center"
          style={{ borderColor: "var(--border-subtle)" }}
        >
          <ShieldAlert
            className="mx-auto h-10 w-10 mb-3"
            style={{ color: "var(--text-tertiary)" }}
          />
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Monitor brand impersonation, typosquats, and phishing threats
          </p>
        </div>
      )}
    </div>
  );
}
