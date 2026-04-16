import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Play, Pause, Network, Download, Clock, Activity, Users, Scan, Loader2 } from "lucide-react";
import { Button } from "@/shared/components/Button";
import { Badge } from "@/shared/components/Badge";
import { Card, CardBody, CardHeader } from "@/shared/components/Card";
import { DataBadge } from "@/shared/components/DataBadge";
import { ScanStatusBadge } from "@/shared/components/osint/ScanStatusBadge";
import { ScannerBadge } from "@/shared/components/osint/ScannerBadge";
import { ConfidenceIndicator } from "@/shared/components/osint/ConfidenceIndicator";
import { EmptyState } from "@/shared/components/EmptyState";
import { ScanProgressPanel } from "./ScanProgressPanel";
import { useInvestigationWebSocket } from "./useInvestigationWebSocket";
import { useInvestigation, useInvestigationResults, useStartInvestigation, usePauseInvestigation } from "./hooks";

const statusVariant: Record<string, "neutral" | "info" | "success" | "warning" | "danger"> = {
  draft: "neutral", running: "info", paused: "warning", completed: "success", archived: "danger",
};

type Tab = "overview" | "scans" | "identities";

export function InvestigationDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>("overview");

  const { data: investigation, isLoading } = useInvestigation(id ?? "");
  const { data: results } = useInvestigationResults(id ?? "");
  const { progress, connected } = useInvestigationWebSocket(id, investigation?.status === "running");

  const tabs: { value: Tab; label: string; icon: typeof Activity }[] = [
    { value: "overview", label: "Overview", icon: Activity },
    { value: "scans", label: "Scans", icon: Scan },
    { value: "identities", label: "Identities", icon: Users },
  ];

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin" style={{ color: "var(--brand-500)" }} />
      </div>
    );
  }

  if (!investigation) {
    return (
      <div className="py-20">
        <EmptyState
          title="Investigation not found"
          description="The investigation you are looking for does not exist or you do not have access."
          action={<Button onClick={() => navigate("/investigations")}>Back to Investigations</Button>}
        />
      </div>
    );
  }

  const scanResults = results?.scan_results ?? results?.items ?? [];
  const identities = results?.identities ?? [];

  // Compute overview stats from results when available
  const statsData = {
    nodes: results?.stats?.nodes ?? scanResults.length,
    edges: results?.stats?.edges ?? 0,
    identities: identities.length,
    duration: results?.stats?.duration ?? "—",
  };

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-start gap-4">
        <button onClick={() => navigate("/investigations")} className="mt-1 rounded-md p-1 transition-colors hover:bg-bg-overlay">
          <ArrowLeft className="h-5 w-5" style={{ color: "var(--text-secondary)" }} />
        </button>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-3">
            <h1 className="truncate text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
              {investigation.title}
            </h1>
            <Badge variant={statusVariant[investigation.status]} dot>{investigation.status}</Badge>
          </div>
          <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
            {investigation.description}
          </p>
        </div>
        <div className="flex shrink-0 gap-2">
          {investigation.status === "running" ? (
            <Button variant="secondary" size="sm" leftIcon={<Pause className="h-4 w-4" />}>Pause</Button>
          ) : investigation.status === "draft" || investigation.status === "paused" ? (
            <Button size="sm" leftIcon={<Play className="h-4 w-4" />}>Start</Button>
          ) : null}
          <Button variant="secondary" size="sm" leftIcon={<Network className="h-4 w-4" />} onClick={() => navigate(`/investigations/${id}/graph`)}>
            Graph
          </Button>
          <Button variant="ghost" size="sm" leftIcon={<Download className="h-4 w-4" />}>Export</Button>
        </div>
      </div>

      {/* Live progress (only when running) */}
      {investigation.status === "running" && (
        <ScanProgressPanel
          completed={progress.completed || investigation.scan_progress?.completed || 0}
          total={progress.total || investigation.scan_progress?.total || 0}
          percentage={progress.percentage || investigation.scan_progress?.percentage || 0}
          currentScanner={progress.currentScanner || ""}
          nodesDiscovered={progress.nodesDiscovered || 0}
          edgesDiscovered={progress.edgesDiscovered || 0}
          events={progress.events}
          connected={connected}
        />
      )}

      {/* Tab navigation */}
      <div className="flex gap-1 border-b" style={{ borderColor: "var(--border-subtle)" }}>
        {tabs.map((t) => (
          <button
            key={t.value}
            onClick={() => setTab(t.value)}
            className={`flex items-center gap-1.5 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors ${
              tab === t.value
                ? "border-brand-500 text-brand-400"
                : "border-transparent text-text-secondary hover:text-text-primary"
            }`}
          >
            <t.icon className="h-4 w-4" />
            {t.label}
          </button>
        ))}
        <button
          onClick={() => navigate(`/investigations/${id}/graph`)}
          className="flex items-center gap-1.5 border-b-2 border-transparent px-4 py-2.5 text-sm font-medium text-text-secondary hover:text-text-primary"
        >
          <Network className="h-4 w-4" />
          Graph
          <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>&rarr;</span>
        </button>
      </div>

      {/* Tab content */}
      {tab === "overview" && (
        <div className="space-y-4">
          {/* Stats cards */}
          <div className="grid grid-cols-4 gap-3">
            {[
              { label: "Nodes", value: statsData.nodes, icon: Network },
              { label: "Edges", value: statsData.edges, icon: Activity },
              { label: "Identities", value: statsData.identities, icon: Users },
              { label: "Duration", value: statsData.duration, icon: Clock },
            ].map((s) => (
              <Card key={s.label}>
                <CardBody className="flex items-center gap-3 py-3">
                  <s.icon className="h-4 w-4" style={{ color: "var(--brand-400)" }} />
                  <div>
                    <p className="text-lg font-bold font-mono" style={{ color: "var(--text-primary)" }}>{s.value}</p>
                    <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>{s.label}</p>
                  </div>
                </CardBody>
              </Card>
            ))}
          </div>

          {/* Seeds */}
          <Card>
            <CardHeader><h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Seed Inputs</h3></CardHeader>
            <CardBody>
              <div className="flex flex-wrap gap-2">
                {(investigation.seed_inputs ?? []).map((s, i) => (
                  <div key={i} className="flex items-center gap-1.5">
                    <Badge variant="neutral" size="sm">{s.type}</Badge>
                    <DataBadge value={s.value} type={s.type as any} />
                  </div>
                ))}
              </div>
            </CardBody>
          </Card>
        </div>
      )}

      {tab === "scans" && (
        <Card>
          <CardBody className="p-0">
            {scanResults.length === 0 ? (
              <div className="p-6">
                <EmptyState title="No scan results yet" description="Scan results will appear here once scans are executed." />
              </div>
            ) : (
              <table className="w-full">
                <thead>
                  <tr className="border-b text-left text-xs font-medium" style={{ borderColor: "var(--border-subtle)", color: "var(--text-tertiary)" }}>
                    <th className="px-5 py-3">Scanner</th>
                    <th className="px-5 py-3">Input</th>
                    <th className="px-5 py-3">Status</th>
                    <th className="px-5 py-3">Findings</th>
                    <th className="px-5 py-3">Duration</th>
                  </tr>
                </thead>
                <tbody>
                  {scanResults.map((r: any) => (
                    <tr key={r.id} className="border-b transition-colors hover:bg-bg-overlay" style={{ borderColor: "var(--border-subtle)" }}>
                      <td className="px-5 py-3"><ScannerBadge scanner={r.scanner} /></td>
                      <td className="px-5 py-3"><DataBadge value={r.input} /></td>
                      <td className="px-5 py-3"><ScanStatusBadge status={r.status} /></td>
                      <td className="px-5 py-3 font-mono text-sm" style={{ color: "var(--text-primary)" }}>{r.findings ?? 0}</td>
                      <td className="px-5 py-3 text-sm" style={{ color: "var(--text-secondary)" }}>
                        {r.duration_ms > 0 ? `${(r.duration_ms / 1000).toFixed(1)}s` : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </CardBody>
        </Card>
      )}

      {tab === "identities" && (
        <div className="space-y-3">
          {identities.length === 0 ? (
            <EmptyState title="No identities resolved yet" description="Identities will appear as scans complete and entity resolution runs." />
          ) : (
            identities.map((ident: any) => (
              <Card key={ident.id}>
                <CardBody>
                  <div className="flex items-start justify-between">
                    <div>
                      <h4 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{ident.name}</h4>
                      <div className="mt-1"><ConfidenceIndicator value={ident.confidence} /></div>
                    </div>
                    <div className="flex gap-1">
                      {(ident.sources ?? []).map((s: string) => <ScannerBadge key={s} scanner={s} />)}
                    </div>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {(ident.emails ?? []).map((e: string) => <DataBadge key={e} value={e} type="email" />)}
                    {(ident.phones ?? []).map((p: string) => <DataBadge key={p} value={p} type="phone" />)}
                    {(ident.usernames ?? []).map((u: string) => <DataBadge key={u} value={u} />)}
                  </div>
                </CardBody>
              </Card>
            ))
          )}
        </div>
      )}
    </div>
  );
}
