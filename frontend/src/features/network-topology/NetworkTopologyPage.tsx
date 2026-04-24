import { useState } from "react";
import { Network, Search, Monitor, Server, Shield, Printer, Cpu } from "lucide-react";
import { useNetworkDiscover } from "./hooks";
import type { NetworkNode } from "./types";
import { Badge } from "@/shared/components/Badge";
import { Button } from "@/shared/components/Button";
import { Input } from "@/shared/components/Input";
import { Card, CardBody, CardHeader } from "@/shared/components/Card";

const typeIcons: Record<string, React.ElementType> = {
  router: Cpu,
  switch: Network,
  server: Server,
  workstation: Monitor,
  firewall: Shield,
  printer: Printer,
  unknown: Monitor,
};

const typeColors: Record<string, string> = {
  router: "var(--warning-400)",
  switch: "var(--brand-400)",
  server: "var(--success-400)",
  workstation: "var(--text-secondary)",
  firewall: "var(--danger-400)",
  printer: "var(--text-tertiary)",
};

const riskColor = (score: number): string =>
  score > 70 ? "var(--danger-400)" : score > 40 ? "var(--warning-400)" : "var(--success-400)";

function NodeRow({ node }: { node: NetworkNode }) {
  const Icon = typeIcons[node.type] ?? Monitor;
  return (
    <div
      className="flex items-center gap-4 px-4 py-3 border-b last:border-0"
      style={{ borderColor: "var(--border-subtle)" }}
    >
      <Icon
        className="h-4 w-4 shrink-0"
        style={{ color: typeColors[node.type] ?? "var(--text-secondary)" }}
      />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm font-medium" style={{ color: "var(--text-primary)" }}>
            {node.ip}
          </span>
          {node.hostname && (
            <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>
              {node.hostname}
            </span>
          )}
        </div>
        <div className="flex flex-wrap gap-1 mt-0.5">
          {(node.services ?? []).slice(0, 4).map((s) => (
            <Badge key={s} variant="neutral" size="sm">
              {s}
            </Badge>
          ))}
          {(node.services?.length ?? 0) > 4 && (
            <Badge variant="neutral" size="sm">
              +{(node.services?.length ?? 0) - 4}
            </Badge>
          )}
        </div>
      </div>
      <div className="shrink-0 text-right">
        <p className="text-sm font-bold" style={{ color: riskColor(node.risk_score) }}>
          {node.risk_score}
        </p>
        <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
          {node.type}
        </p>
        {node.vulnerabilities_count > 0 && (
          <Badge variant="danger" size="sm">
            {node.vulnerabilities_count} vulns
          </Badge>
        )}
      </div>
    </div>
  );
}

export function NetworkTopologyPage() {
  const [network, setNetwork] = useState("192.168.1.0/24");
  const discover = useNetworkDiscover();

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <Network className="h-6 w-6" style={{ color: "var(--brand-500)" }} />
        <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
          Network Topology Diagrammer
        </h1>
      </div>

      <Card>
        <CardBody>
          <div className="flex gap-3">
            <div className="flex-1">
              <Input
                placeholder="CIDR range (e.g., 192.168.1.0/24)..."
                prefixIcon={<Network className="h-4 w-4" />}
                value={network}
                onChange={(e) => setNetwork(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && discover.mutate({ network })}
              />
            </div>
            <Button
              onClick={() => discover.mutate({ network })}
              disabled={!network.trim() || discover.isPending}
              leftIcon={<Search className="h-4 w-4" />}
            >
              {discover.isPending ? "Discovering..." : "Discover"}
            </Button>
          </div>
        </CardBody>
      </Card>

      {discover.data && (
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-4">
            {[
              { label: "Total Hosts", value: discover.data.total_hosts },
              { label: "Live Hosts", value: discover.data.live_hosts },
              { label: "Subnets", value: discover.data.subnets.length },
              { label: "Services", value: Object.keys(discover.data.services_found).length },
            ].map(({ label, value }) => (
              <div
                key={label}
                className="rounded-xl border p-4 text-center"
                style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}
              >
                <p className="text-3xl font-bold" style={{ color: "var(--text-primary)" }}>
                  {value}
                </p>
                <p className="text-xs mt-1" style={{ color: "var(--text-tertiary)" }}>
                  {label}
                </p>
              </div>
            ))}
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            <div className="md:col-span-2">
              <Card>
                <CardHeader>
                  <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                    Discovered Hosts ({discover.data.live_hosts})
                  </h3>
                </CardHeader>
                <div>
                  {discover.data.nodes
                    .sort((a, b) => b.risk_score - a.risk_score)
                    .map((n) => (
                      <NodeRow key={n.id} node={n} />
                    ))}
                </div>
              </Card>
            </div>
            <Card>
              <CardHeader>
                <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                  Services Breakdown
                </h3>
              </CardHeader>
              <CardBody className="space-y-2">
                {Object.entries(discover.data.services_found)
                  .sort(([, a], [, b]) => b - a)
                  .map(([service, count]) => (
                    <div key={service} className="flex items-center justify-between">
                      <span className="text-sm" style={{ color: "var(--text-primary)" }}>
                        {service}
                      </span>
                      <Badge variant="neutral" size="sm">
                        {count} hosts
                      </Badge>
                    </div>
                  ))}
              </CardBody>
            </Card>
          </div>
        </div>
      )}

      {!discover.data && !discover.isPending && (
        <div
          className="rounded-xl border py-16 text-center"
          style={{ borderColor: "var(--border-subtle)" }}
        >
          <Network
            className="mx-auto h-10 w-10 mb-3"
            style={{ color: "var(--text-tertiary)" }}
          />
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Discover and map network topology from a CIDR range
          </p>
        </div>
      )}
    </div>
  );
}
