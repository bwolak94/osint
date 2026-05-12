import { useState } from "react";
import { Network, Search, Users, Link2 } from "lucide-react";
import { useSocialGraphMap } from "./hooks";
import type { GraphNode } from "./types";
import { Badge } from "@/shared/components/Badge";
import { Button } from "@/shared/components/Button";
import { Input } from "@/shared/components/Input";
import { Card, CardBody, CardHeader } from "@/shared/components/Card";

const nodeTypeColors: Record<string, string> = {
  person: "var(--brand-400)",
  organization: "var(--success-400)",
  location: "var(--warning-400)",
  email: "var(--info-400)",
  username: "var(--text-secondary)",
  phone: "var(--danger-400)",
};

function NodeCard({ node }: { node: GraphNode }) {
  return (
    <div
      className="flex items-center justify-between rounded-lg border p-3"
      style={{ background: "var(--bg-elevated)", borderColor: "var(--border-subtle)" }}
    >
      <div className="flex items-center gap-2">
        <div
          className="h-2 w-2 rounded-full shrink-0"
          style={{ background: nodeTypeColors[node.type] ?? "var(--text-tertiary)" }}
        />
        <div>
          <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
            {node.label}
          </p>
          <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
            {node.type}
            {node.platform ? ` · ${node.platform}` : ""}
          </p>
        </div>
      </div>
      <div className="text-right">
        <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
          {node.connections} connections
        </p>
        {node.risk_score > 0 && (
          <p
            className="text-xs"
            style={{
              color: node.risk_score > 60 ? "var(--danger-400)" : "var(--text-tertiary)",
            }}
          >
            Risk: {node.risk_score}
          </p>
        )}
      </div>
    </div>
  );
}

export function SocialGraphPage() {
  const [target, setTarget] = useState("");
  const [depth, setDepth] = useState(2);
  const graph = useSocialGraphMap();

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <Network className="h-6 w-6" style={{ color: "var(--brand-500)" }} />
        <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
          Social Graph Mapper
        </h1>
      </div>

      <Card>
        <CardBody>
          <div className="flex gap-3 flex-wrap">
            <div className="flex-1">
              <Input
                placeholder="Username, email, real name..."
                prefixIcon={<Users className="h-4 w-4" />}
                value={target}
                onChange={(e) => setTarget(e.target.value)}
                onKeyDown={(e) =>
                  e.key === "Enter" &&
                  target.trim() &&
                  graph.mutate({ target: target.trim(), depth })
                }
              />
            </div>
            <select
              value={depth}
              onChange={(e) => setDepth(Number(e.target.value))}
              className="rounded-md border px-3 py-2 text-sm"
              style={{
                background: "var(--bg-surface)",
                borderColor: "var(--border-default)",
                color: "var(--text-primary)",
              }}
            >
              <option value={1}>Depth 1</option>
              <option value={2}>Depth 2</option>
              <option value={3}>Depth 3</option>
            </select>
            <Button
              onClick={() => graph.mutate({ target: target.trim(), depth })}
              disabled={!target.trim() || graph.isPending}
              leftIcon={<Search className="h-4 w-4" />}
            >
              {graph.isPending ? "Mapping..." : "Map Graph"}
            </Button>
          </div>
        </CardBody>
      </Card>

      {graph.data && (
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-3">
            {[
              { label: "Nodes Found", value: graph.data.nodes.length },
              { label: "Connections", value: graph.data.edges.length },
              { label: "Platforms", value: graph.data.platforms_covered.length },
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

          <div className="flex flex-wrap gap-2">
            {graph.data.platforms_covered.map((p) => (
              <Badge key={p} variant="neutral">
                {p}
              </Badge>
            ))}
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                  Discovered Nodes
                </h3>
              </CardHeader>
              <CardBody className="space-y-2">
                {graph.data.nodes.map((n) => (
                  <NodeCard key={n.id} node={n} />
                ))}
              </CardBody>
            </Card>

            <Card>
              <CardHeader>
                <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                  Relationships
                </h3>
              </CardHeader>
              <CardBody className="space-y-2">
                {graph.data.edges.map((e, i) => (
                  <div key={i} className="flex items-center gap-2 text-sm">
                    <span
                      className="font-medium truncate"
                      style={{ color: "var(--text-primary)" }}
                    >
                      {graph.data.nodes.find((n) => n.id === e.source)?.label ?? e.source}
                    </span>
                    <Link2
                      className="h-3 w-3 shrink-0"
                      style={{ color: "var(--text-tertiary)" }}
                    />
                    <span
                      className="text-xs px-1.5 py-0.5 rounded"
                      style={{
                        background: "var(--bg-elevated)",
                        color: "var(--text-secondary)",
                      }}
                    >
                      {e.relationship}
                    </span>
                    <Link2
                      className="h-3 w-3 shrink-0"
                      style={{ color: "var(--text-tertiary)" }}
                    />
                    <span
                      className="font-medium truncate"
                      style={{ color: "var(--text-primary)" }}
                    >
                      {graph.data.nodes.find((n) => n.id === e.target)?.label ?? e.target}
                    </span>
                  </div>
                ))}
              </CardBody>
            </Card>
          </div>
        </div>
      )}

      {!graph.data && !graph.isPending && (
        <div
          className="rounded-xl border py-16 text-center"
          style={{ borderColor: "var(--border-subtle)" }}
        >
          <Network
            className="mx-auto h-10 w-10 mb-3"
            style={{ color: "var(--text-tertiary)" }}
          />
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Map social connections across platforms to reveal networks and relationships
          </p>
        </div>
      )}
    </div>
  );
}
