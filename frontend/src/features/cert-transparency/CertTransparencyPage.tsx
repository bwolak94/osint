import { useState } from "react";
import { Shield, Search } from "lucide-react";
import { useCertSearch } from "./hooks";
import type { CertRecord } from "./types";
import { Badge } from "@/shared/components/Badge";
import { Button } from "@/shared/components/Button";
import { Input } from "@/shared/components/Input";
import { Card, CardBody, CardHeader } from "@/shared/components/Card";

function CertRow({ cert }: { cert: CertRecord }) {
  const [expanded, setExpanded] = useState(false);
  const statusVariant =
    cert.is_expired
      ? "danger"
      : (cert.days_until_expiry ?? 999) < 30
      ? "warning"
      : "neutral";
  const statusLabel = cert.is_expired
    ? "Expired"
    : (cert.days_until_expiry ?? 999) < 30
    ? `${cert.days_until_expiry}d left`
    : "Valid";

  return (
    <div className="border-b last:border-0" style={{ borderColor: "var(--border-subtle)" }}>
      <button
        className="w-full px-4 py-3 text-left hover:bg-bg-overlay transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 min-w-0">
            {cert.is_wildcard && (
              <Badge variant="info" size="sm">
                Wildcard
              </Badge>
            )}
            <span
              className="font-mono text-sm truncate"
              style={{ color: "var(--text-primary)" }}
            >
              {cert.common_name}
            </span>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <Badge variant={statusVariant} size="sm">
              {statusLabel}
            </Badge>
            <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>
              {cert.issuer.split(" ").slice(0, 2).join(" ")}
            </span>
          </div>
        </div>
      </button>
      {expanded && (
        <div
          className="px-4 pb-3 space-y-2 text-xs"
          style={{ color: "var(--text-secondary)" }}
        >
          <div>
            <span className="font-medium">SANs:</span> {cert.san_domains.join(", ")}
          </div>
          <div>
            <span className="font-medium">Issuer:</span> {cert.issuer}
          </div>
          <div>
            <span className="font-medium">Valid:</span>{" "}
            {new Date(cert.not_before).toLocaleDateString()} –{" "}
            {new Date(cert.not_after).toLocaleDateString()}
          </div>
          <div>
            <span className="font-medium">Serial:</span>{" "}
            <span className="font-mono">{cert.serial_number}</span>
          </div>
          <div className="font-mono break-all">
            <span className="font-sans font-medium">SHA256:</span>{" "}
            {cert.fingerprint_sha256}
          </div>
          <div>
            <span className="font-medium">CT Logs:</span> {cert.ct_logs.join(", ")}
          </div>
        </div>
      )}
    </div>
  );
}

export function CertTransparencyPage() {
  const [domain, setDomain] = useState("");
  const search = useCertSearch();

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <Shield className="h-6 w-6" style={{ color: "var(--brand-500)" }} />
        <h1
          className="text-xl font-semibold"
          style={{ color: "var(--text-primary)" }}
        >
          Certificate Transparency
        </h1>
      </div>

      <Card>
        <CardBody>
          <div className="flex gap-3">
            <div className="flex-1">
              <Input
                placeholder="Domain to search (e.g., example.com)..."
                prefixIcon={<Search className="h-4 w-4" />}
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
                onKeyDown={(e) =>
                  e.key === "Enter" &&
                  domain.trim() &&
                  search.mutate(domain.trim())
                }
              />
            </div>
            <Button
              onClick={() => search.mutate(domain.trim())}
              disabled={!domain.trim() || search.isPending}
              leftIcon={<Shield className="h-4 w-4" />}
            >
              {search.isPending ? "Searching..." : "Search CT Logs"}
            </Button>
          </div>
        </CardBody>
      </Card>

      {search.data && (
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-4">
            {[
              {
                label: "Total Certs",
                value: search.data.total_certs,
                color: "var(--text-primary)",
              },
              {
                label: "Wildcards",
                value: search.data.wildcard_count,
                color: "var(--brand-400)",
              },
              {
                label: "Expiring Soon",
                value: search.data.expiring_soon,
                color: "var(--warning-400)",
              },
              {
                label: "Expired",
                value: search.data.expired_count,
                color: "var(--danger-400)",
              },
            ].map(({ label, value, color }) => (
              <div
                key={label}
                className="rounded-xl border p-4 text-center"
                style={{
                  background: "var(--bg-surface)",
                  borderColor: "var(--border-subtle)",
                }}
              >
                <p className="text-3xl font-bold" style={{ color }}>
                  {value}
                </p>
                <p
                  className="text-xs mt-1"
                  style={{ color: "var(--text-tertiary)" }}
                >
                  {label}
                </p>
              </div>
            ))}
          </div>

          <Card>
            <CardHeader>
              <h3
                className="text-sm font-semibold"
                style={{ color: "var(--text-primary)" }}
              >
                Certificates ({search.data.certs.length})
              </h3>
            </CardHeader>
            <div>
              {search.data.certs.map((c) => (
                <CertRow key={c.id} cert={c} />
              ))}
            </div>
          </Card>
        </div>
      )}

      {!search.data && !search.isPending && (
        <div
          className="rounded-xl border py-16 text-center"
          style={{ borderColor: "var(--border-subtle)" }}
        >
          <Shield
            className="mx-auto h-10 w-10 mb-3"
            style={{ color: "var(--text-tertiary)" }}
          />
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Search Certificate Transparency logs for a domain
          </p>
        </div>
      )}
    </div>
  );
}
