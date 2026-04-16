import { useState, useEffect, useCallback, useRef, Fragment } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Play, Pause, Network, Download, Clock, Activity, Users, Scan, Loader2, ChevronDown, ChevronRight, Building2, User as UserIcon, Copy } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
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
import { useInvestigation, useInvestigationResults, useStartInvestigation, usePauseInvestigation, useCreateInvestigation } from "./hooks";
import { apiClient } from "@/shared/api/client";
import { toast } from "@/shared/components/Toast";

const statusVariant: Record<string, "neutral" | "info" | "success" | "warning" | "danger"> = {
  draft: "neutral", running: "info", paused: "warning", completed: "success", archived: "danger",
};

type Tab = "overview" | "scans" | "identities";

export function InvestigationDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<Tab>("overview");
  const [expandedScanId, setExpandedScanId] = useState<string | null>(null);

  const { data: investigation, isLoading } = useInvestigation(id ?? "");
  const isRunning = investigation?.status === "running";
  const { data: results, refetch: refetchResults } = useInvestigationResults(id ?? "", isRunning);
  const startMutation = useStartInvestigation();
  const pauseMutation = usePauseInvestigation();
  const createMutation = useCreateInvestigation();

  const handleRerun = async () => {
    if (!id || !investigation) return;
    // Create a new investigation with same seeds and start it
    try {
      const newInv = await createMutation.mutateAsync({
        title: `${investigation.title} (re-run)`,
        description: investigation.description,
        seed_inputs: investigation.seed_inputs ?? [],
        tags: investigation.tags ?? [],
      });
      await startMutation.mutateAsync(newInv.id);
      navigate(`/investigations/${newInv.id}`);
    } catch {
      // Errors handled by mutation toast callbacks
    }
  };

  const handleDuplicate = async () => {
    if (!investigation) return;
    try {
      const newInv = await createMutation.mutateAsync({
        title: `${investigation.title} (copy)`,
        description: investigation.description,
        seed_inputs: investigation.seed_inputs ?? [],
        tags: investigation.tags ?? [],
      });
      navigate(`/investigations/${newInv.id}`);
    } catch {
      // Errors handled by mutation toast callbacks
    }
  };

  const handleExport = async () => {
    if (!id) return;
    try {
      const res = await apiClient.post(`/investigations/${id}/export`, null, { responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([JSON.stringify(res.data, null, 2)]));
      const a = document.createElement("a");
      a.href = url;
      a.download = `investigation-${id}.json`;
      a.click();
      window.URL.revokeObjectURL(url);
      toast.success("Investigation exported");
    } catch {
      toast.error("Export failed");
    }
  };

  // Track previous status to detect transitions
  const prevStatusRef = useRef<string | undefined>(undefined);

  // Only enable WebSocket while investigation is running
  const { progress, connected } = useInvestigationWebSocket(id, isRunning);

  // Refetch results when status transitions from "running" to "completed"
  useEffect(() => {
    const currentStatus = investigation?.status;
    if (prevStatusRef.current === "running" && currentStatus === "completed") {
      // Investigation just completed, refetch results
      refetchResults();
      queryClient.invalidateQueries({ queryKey: ["investigation-results", id] });
    }
    prevStatusRef.current = currentStatus;
  }, [investigation?.status, refetchResults, queryClient, id]);


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

  const scanResults = results?.scan_results ?? [];
  const totalFindings = scanResults.reduce((sum: number, r) => sum + (r.findings_count ?? 0), 0);
  const totalDuration = scanResults.reduce((sum: number, r) => sum + (r.duration_ms ?? 0), 0);

  const statsData = {
    scans: results?.total_scans ?? scanResults.length,
    findings: totalFindings,
    successful: results?.successful_scans ?? 0,
    duration: totalDuration > 0 ? `${(totalDuration / 1000).toFixed(1)}s` : "\u2014",
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
            <Button variant="secondary" size="sm" leftIcon={<Pause className="h-4 w-4" />} loading={pauseMutation.isPending} onClick={() => id && pauseMutation.mutate(id)}>Pause</Button>
          ) : investigation.status === "draft" || investigation.status === "paused" ? (
            <Button size="sm" leftIcon={<Play className="h-4 w-4" />} loading={startMutation.isPending} onClick={() => id && startMutation.mutate(id)}>Start</Button>
          ) : null}
          {investigation.status === "completed" && (
            <>
              <Button size="sm" leftIcon={<Play className="h-4 w-4" />} onClick={handleRerun}>
                Re-run
              </Button>
              <Button variant="secondary" size="sm" leftIcon={<Copy className="h-4 w-4" />} onClick={handleDuplicate}>
                Duplicate
              </Button>
            </>
          )}
          <Button variant="secondary" size="sm" leftIcon={<Network className="h-4 w-4" />} onClick={() => navigate(`/investigations/${id}/graph`)}>
            Graph
          </Button>
          <Button variant="ghost" size="sm" leftIcon={<Download className="h-4 w-4" />} onClick={handleExport}>Export</Button>
        </div>
      </div>

      {/* Live progress — only shown while investigation is actively running */}
      {isRunning && (
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
              { label: "Scans", value: statsData.scans, icon: Scan },
              { label: "Findings", value: statsData.findings, icon: Activity },
              { label: "Successful", value: statsData.successful, icon: Users },
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
                    <th className="w-8 px-3 py-3"></th>
                    <th className="px-5 py-3">Scanner</th>
                    <th className="px-5 py-3">Input</th>
                    <th className="px-5 py-3">Status</th>
                    <th className="px-5 py-3">Findings</th>
                    <th className="px-5 py-3">Duration</th>
                  </tr>
                </thead>
                <tbody>
                  {scanResults.map((r) => {
                    const isExpanded = expandedScanId === r.id;
                    const hasRawData = r.raw_data && Object.keys(r.raw_data).length > 0;
                    // Keys to display as labeled fields (exclude meta keys)
                    const displayKeys = Object.keys(r.raw_data || {}).filter(
                      (k) => !["raw_results", "_stub", "_extracted_identifiers", "extracted_identifiers", "found"].includes(k)
                    );
                    return (
                      <Fragment key={r.id}>
                        <tr
                          className="border-b transition-colors hover:bg-bg-overlay cursor-pointer"
                          style={{ borderColor: "var(--border-subtle)" }}
                          onClick={() => setExpandedScanId(isExpanded ? null : r.id)}
                        >
                          <td className="px-3 py-3">
                            {hasRawData && (
                              isExpanded
                                ? <ChevronDown className="h-4 w-4" style={{ color: "var(--text-tertiary)" }} />
                                : <ChevronRight className="h-4 w-4" style={{ color: "var(--text-tertiary)" }} />
                            )}
                          </td>
                          <td className="px-5 py-3"><ScannerBadge scanner={r.scanner_name} /></td>
                          <td className="px-5 py-3"><DataBadge value={r.input_value} /></td>
                          <td className="px-5 py-3"><ScanStatusBadge status={r.status} /></td>
                          <td className="px-5 py-3 font-mono text-sm" style={{ color: "var(--text-primary)" }}>{r.findings_count}</td>
                          <td className="px-5 py-3 text-sm" style={{ color: "var(--text-secondary)" }}>
                            {r.duration_ms > 0 ? `${(r.duration_ms / 1000).toFixed(1)}s` : "\u2014"}
                          </td>
                        </tr>
                        {isExpanded && hasRawData && (
                          <tr key={`${r.id}-detail`} style={{ borderColor: "var(--border-subtle)" }} className="border-b">
                            <td colSpan={6} className="px-5 py-4" style={{ backgroundColor: "var(--bg-overlay)" }}>
                              <div className="space-y-3">
                                <h4 className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--text-tertiary)" }}>
                                  Raw Findings
                                </h4>
                                <div className="grid grid-cols-2 gap-x-6 gap-y-2">
                                  {displayKeys.map((key) => {
                                    const val = r.raw_data[key];
                                    // Bank accounts rendered as a list of copyable badges
                                    if (key === "bank_accounts" && Array.isArray(val)) {
                                      return (
                                        <div key={key} className="col-span-2">
                                          <p className="text-xs font-medium mb-1" style={{ color: "var(--text-tertiary)" }}>
                                            {key.replace(/_/g, " ")}
                                          </p>
                                          <div className="flex flex-wrap gap-1">
                                            {val.map((acc: string) => (
                                              <DataBadge key={acc} value={acc} />
                                            ))}
                                          </div>
                                        </div>
                                      );
                                    }
                                    return (
                                      <div key={key} className="flex flex-col">
                                        <span className="text-xs font-medium" style={{ color: "var(--text-tertiary)" }}>
                                          {key.replace(/_/g, " ")}
                                        </span>
                                        <DataBadge value={String(val)} />
                                      </div>
                                    );
                                  })}
                                </div>
                              </div>
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    );
                  })}
                </tbody>
              </table>
            )}
          </CardBody>
        </Card>
      )}

      {tab === "identities" && (
        <div className="space-y-3">
          {results?.identities && results.identities.length > 0 ? (
            results.identities.map((ident) => {
              const dataKeys = Object.keys(ident.data || {}).filter(
                (k) => !["bank_accounts", "found"].includes(k)
              );
              const bankAccounts: string[] = ident.data?.bank_accounts ?? [];
              return (
                <Card key={ident.id}>
                  <CardBody>
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-2">
                        {ident.type === "company" ? (
                          <Building2 className="h-5 w-5" style={{ color: "var(--brand-400)" }} />
                        ) : (
                          <UserIcon className="h-5 w-5" style={{ color: "var(--brand-400)" }} />
                        )}
                        <div>
                          <h4 className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>{ident.name}</h4>
                          <div className="flex items-center gap-2 mt-0.5">
                            <Badge variant={ident.type === "company" ? "info" : "neutral"} size="sm">
                              {ident.type}
                            </Badge>
                            <ConfidenceIndicator value={ident.confidence} />
                          </div>
                        </div>
                      </div>
                      <div className="flex gap-1">
                        {(ident.sources ?? []).map((s: string) => <ScannerBadge key={s} scanner={s} />)}
                      </div>
                    </div>

                    {/* Data fields as labeled key-value pairs */}
                    <div className="mt-3 grid grid-cols-2 gap-x-6 gap-y-2">
                      {dataKeys.map((key) => (
                        <div key={key} className="flex flex-col">
                          <span className="text-xs font-medium" style={{ color: "var(--text-tertiary)" }}>
                            {key.replace(/_/g, " ")}
                          </span>
                          <DataBadge value={String(ident.data[key])} />
                        </div>
                      ))}
                    </div>

                    {/* Bank accounts as DataBadge list */}
                    {bankAccounts.length > 0 && (
                      <div className="mt-3">
                        <p className="text-xs font-medium mb-1" style={{ color: "var(--text-tertiary)" }}>
                          bank accounts
                        </p>
                        <div className="flex flex-wrap gap-1">
                          {bankAccounts.map((acc: string) => (
                            <DataBadge key={acc} value={acc} />
                          ))}
                        </div>
                      </div>
                    )}
                  </CardBody>
                </Card>
              );
            })
          ) : (
            <EmptyState title="No identities resolved yet" description="Identities will appear as scans complete and entity resolution runs." />
          )}
        </div>
      )}
    </div>
  );
}
