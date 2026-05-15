import { useState } from "react";
import { Network, Search, AlertTriangle, ArrowRight, Shield } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import apiClient from "@/shared/api/client";
import { Button } from "@/shared/components/Button";
import { Input } from "@/shared/components/Input";
import { Card, CardBody, CardHeader } from "@/shared/components/Card";
import { Badge } from "@/shared/components/Badge";
import { ScanResultErrorBoundary } from "@/shared/components/osint/ScanResultErrorBoundary";

interface ADNode       {mutationError && (
        <p role="alert" className="text-xs rounded-lg px-3 py-2 border" style={{ color: "var(--danger-400)", borderColor: "var(--danger-500)", background: "var(--bg-surface)" }}>
          {mutationError}
        </p>
      )}
      {
  node_id: string;
  label: string;
  node_type: string;
  risk_score: number;
  osint_flags: string[];
}

interface AttackPath {
  path_id: string;
  path_name: string;
  severity: string;
  nodes: string[];
  total_steps: number;
  estimated_time_hours: number;
  techniques: string[];
  description: string;
}

interface ADAnalysisResult {
  domain_name: string;
  total_nodes: number;
  total_edges: number;
  nodes: ADNode[];
  attack_paths: AttackPath[];
  domain_admin_reachable: boolean;
  shortest_path_steps: number | null;
  critical_nodes: string[];
}

const nodeTypeIcon: Record<string, string> = {
  user: "👤",
  computer: "💻",
  group: "👥",
  gpo: "📋",
  domain: "🏢",
  ou: "📁",
};

const severityVariant = (s: string): "danger" | "warning" | "neutral" => {
  if (s === "critical") return "danger";
  if (s === "high") return "warning";
  return "neutral";
};

function PathCard({ path, nodes }: { path: AttackPath; nodes: ADNode[] }) {
  const [expanded, setExpanded] = useState(false);
  const nodeMap = Object.fromEntries(nodes.map((n) => [n.node_id, n]));

  return (
    <div className="rounded-xl border p-4 space-y-3" style={{ background: "var(--bg-surface)", borderColor: path.severity === "critical" ? "var(--danger-500)" : "var(--border-subtle)" }}>
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Badge variant={severityVariant(path.severity)}>{path.severity.toUpperCase()}</Badge>
            <span className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>{path.path_name}</span>
          </div>
          <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
            {path.total_steps} steps · ~{path.estimated_time_hours}h estimated
          </p>
        </div>
        <button
          className="text-xs underline shrink-0"
          style={{ color: "var(--brand-400)" }}
          onClick={() => setExpanded((e) => !e)}
        >
          {expanded ? "Collapse" : "Details"}
        </button>
      </div>

      {/* Attack path visualization */}
      <div className="flex items-center gap-1 flex-wrap text-xs">
        {path.nodes.map((nodeId, i) => {
          const node = nodeMap[nodeId];
          return (
            <div key={nodeId} className="flex items-center gap-1">
              <span
                className="px-2 py-1 rounded-lg flex items-center gap-1"
                style={{
                  background: "var(--bg-raised)",
                  color: node?.risk_score >= 0.8 ? "var(--danger-400)" : "var(--text-secondary)",
                  border: `1px solid ${node?.risk_score >= 0.8 ? "var(--danger-500)" : "var(--border-subtle)"}`,
                }}
              >
                {nodeTypeIcon[node?.node_type || ""] || "?"}
                <span className="max-w-[80px] truncate">{node?.label.split("@")[0] || nodeId}</span>
              </span>
              {i < path.nodes.length - 1 && (
                <ArrowRight className="h-3 w-3 shrink-0" style={{ color: "var(--text-tertiary)" }} />
              )}
            </div>
          );
        })}
      </div>

      {expanded && (
        <div className="space-y-2 pt-2 border-t" style={{ borderColor: "var(--border-subtle)" }}>
          <p className="text-xs" style={{ color: "var(--text-secondary)" }}>{path.description}</p>
          <div className="flex gap-1 flex-wrap">
            {path.techniques.map((t) => (
              <a
                key={t}
                href={`https://attack.mitre.org/techniques/${t.replace(".", "/")}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs px-1.5 py-0.5 rounded font-mono"
                style={{ background: "var(--bg-raised)", color: "var(--brand-400)" }}
              >
                {t}
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function ADAttackPathPage() {
  const [domain, setDomain] = useState("");
  const [mutationError, setMutationError] = useState<string | null>(null);
  const [startNode, setStartNode] = useState("");

  const analyze = useMutation({
    mutationFn: (data: { domain_name: string; starting_node?: string }) =>
      apiClient.post<ADAnalysisResult>("/api/v1/ad-attack-path/analyze", data).then((r) => r.data),
  });

  const handleAnalyze = () => {
    if (!domain.trim()) return;
    analyze.mutate({
      domain_name: domain.trim(),
      starting_node: startNode.trim() || undefined,
    });
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <Network className="h-6 w-6" style={{ color: "var(--brand-400)" }} />
        <div>
          <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>AD Attack Path Visualizer</h1>
          <p className="text-xs mt-0.5" style={{ color: "var(--text-tertiary)" }}>BloodHound-powered attack path analysis with OSINT overlay</p>
        </div>
      </div>

      <Card>
        <CardHeader>
          <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>Analysis Parameters</p>
        </CardHeader>
        <CardBody className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs mb-1 block" style={{ color: "var(--text-tertiary)" }}>Target Domain *</label>
              <Input
                placeholder="corp.example.com"
                prefixIcon={<Network className="h-4 w-4" />}
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
              />
            </div>
            <div>
              <label className="text-xs mb-1 block" style={{ color: "var(--text-tertiary)" }}>Starting Node (optional)</label>
              <Input placeholder="jdoe@corp.example.com" value={startNode} onChange={(e) => setStartNode(e.target.value)} />
            </div>
          </div>

          <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
            Upload BloodHound JSON via API or use demo analysis mode below.
          </p>

          <Button
            onClick={handleAnalyze}
            disabled={!domain.trim() || analyze.isPending}
            leftIcon={<Search className="h-4 w-4" />}
          >
            {analyze.isPending ? "Analyzing..." : "Analyze Attack Paths"}
          </Button>
        </CardBody>
      </Card>

      {analyze.data && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[
              { label: "Nodes", value: analyze.data.total_nodes },
              { label: "Edges", value: analyze.data.total_edges },
              { label: "Attack Paths", value: analyze.data.attack_paths.length, color: "var(--danger-400)" },
              { label: "Shortest Path", value: analyze.data.shortest_path_steps ? `${analyze.data.shortest_path_steps} steps` : "—" },
            ].map(({ label, value, color }) => (
              <div key={label} className="rounded-xl border p-3 text-center" style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}>
                <p className="text-2xl font-bold" style={{ color: color || "var(--text-primary)" }}>{value}</p>
                <p className="text-xs mt-1" style={{ color: "var(--text-tertiary)" }}>{label}</p>
              </div>
            ))}
          </div>

          {analyze.data.domain_admin_reachable && (
            <div className="rounded-xl border p-4 flex items-center gap-3" style={{ background: "var(--bg-surface)", borderColor: "var(--danger-500)" }}>
              <AlertTriangle className="h-5 w-5 shrink-0" style={{ color: "var(--danger-400)" }} />
              <div>
                <p className="text-sm font-semibold" style={{ color: "var(--danger-400)" }}>Domain Admin Reachable</p>
                <p className="text-xs mt-0.5" style={{ color: "var(--text-secondary)" }}>
                  {analyze.data.shortest_path_steps} step path to full domain compromise identified
                </p>
              </div>
            </div>
          )}

          {analyze.data.attack_paths.length > 0 && (
            <div className="space-y-3">
              <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                Attack Paths ({analyze.data.attack_paths.length})
              </p>
              {analyze.data.attack_paths.map((path) => (
                <PathCard key={path.path_id} path={path} nodes={analyze.data.nodes} />
              ))}
            </div>
          )}

          <div className="space-y-2">
            <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Critical Nodes</p>
            <div className="flex flex-wrap gap-2">
              {analyze.data.nodes
                .filter((n) => analyze.data.critical_nodes.includes(n.node_id))
                .map((n) => (
                  <div key={n.node_id} className="flex items-center gap-1.5 text-xs px-2 py-1 rounded-lg border" style={{ background: "var(--bg-surface)", borderColor: "var(--danger-500)" }}>
                    <span>{nodeTypeIcon[n.node_type] || "?"}</span>
                    <span style={{ color: "var(--text-primary)" }}>{n.label.split("@")[0]}</span>
                    {n.osint_flags.length > 0 && <Badge variant="danger" size="sm">{n.osint_flags[0]}</Badge>}
                  </div>
                ))}
            </div>
          </div>
        </div>
      )}

      {!analyze.data && !analyze.isPending && (
        <div className="rounded-xl border py-16 text-center" style={{ borderColor: "var(--border-subtle)" }}>
          <Network className="mx-auto h-10 w-10 mb-3" style={{ color: "var(--text-tertiary)" }} />
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Enter a domain to analyze Active Directory attack paths</p>
          <p className="text-xs mt-1" style={{ color: "var(--text-tertiary)" }}>Supports BloodHound JSON upload via API</p>
        </div>
      )}
    </div>
  );
}
