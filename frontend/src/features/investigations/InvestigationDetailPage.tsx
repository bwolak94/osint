import { useState, useEffect, useCallback, useRef, Fragment } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Play, Pause, Network, Download, Clock, Activity, Users, Scan, Loader2, ChevronDown, ChevronRight, Building2, User as UserIcon, Copy, FileText, MessageSquare, Send, Timer, Brain, CheckCircle, AlertTriangle, Lightbulb, MapPin } from "lucide-react";
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
import { useInvestigation, useInvestigationResults, useStartInvestigation, usePauseInvestigation, useCreateInvestigation, useComments, useAddComment, useInvestigationSummary } from "./hooks";
import { apiClient } from "@/shared/api/client";
import { toast } from "@/shared/components/Toast";
import { TimelineTab } from "./TimelineTab";
import { MapTab } from "./MapTab";

const statusVariant: Record<string, "neutral" | "info" | "success" | "warning" | "danger"> = {
  draft: "neutral", running: "info", paused: "warning", completed: "success", archived: "danger",
};

type Tab = "overview" | "scans" | "identities" | "timeline" | "map" | "comments" | "summary";

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
  const { data: comments } = useComments(id ?? "");
  const { data: summaryData, isLoading: summaryLoading } = useInvestigationSummary(id ?? "");
  const addCommentMutation = useAddComment();
  const [commentText, setCommentText] = useState("");

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

  const handleDownloadReport = async () => {
    if (!id) return;
    try {
      const res = await apiClient.get(`/investigations/${id}/report`, { responseType: "blob" });
      const contentType = res.headers["content-type"] || "application/pdf";
      const ext = contentType.includes("pdf") ? "pdf" : "html";
      const url = window.URL.createObjectURL(new Blob([res.data], { type: contentType }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `report-${id}.${ext}`;
      a.click();
      window.URL.revokeObjectURL(url);
      toast.success("Report downloaded");
    } catch {
      toast.error("Report generation failed");
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
    { value: "timeline", label: "Timeline", icon: Timer },
    { value: "map", label: "Map", icon: MapPin },
    { value: "comments", label: "Comments", icon: MessageSquare },
    { value: "summary", label: "AI Summary", icon: Brain },
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
          <Button variant="ghost" size="sm" leftIcon={<FileText className="h-4 w-4" />} onClick={handleDownloadReport}>Report</Button>
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

      {tab === "timeline" && (
        <TimelineTab investigation={investigation} scanResults={scanResults} />
      )}

      {tab === "map" && (
        <MapTab scanResults={scanResults} />
      )}

      {tab === "comments" && (
        <div className="space-y-4">
          {/* Add comment form */}
          <Card>
            <CardBody>
              <form
                onSubmit={async (e) => {
                  e.preventDefault();
                  if (!id || !commentText.trim()) return;
                  try {
                    await addCommentMutation.mutateAsync({ investigationId: id, text: commentText.trim() });
                    setCommentText("");
                    toast.success("Comment added");
                  } catch {
                    toast.error("Failed to add comment");
                  }
                }}
                className="flex gap-2"
              >
                <input
                  type="text"
                  value={commentText}
                  onChange={(e) => setCommentText(e.target.value)}
                  placeholder="Add a comment..."
                  className="flex-1 rounded-md border px-3 py-2 text-sm"
                  style={{ borderColor: "var(--border-subtle)", backgroundColor: "var(--bg-surface)", color: "var(--text-primary)" }}
                  maxLength={5000}
                />
                <Button type="submit" size="sm" leftIcon={<Send className="h-4 w-4" />} loading={addCommentMutation.isPending} disabled={!commentText.trim()}>
                  Send
                </Button>
              </form>
            </CardBody>
          </Card>

          {/* Comments list */}
          {comments && (comments as any[]).length > 0 ? (
            (comments as any[]).map((c: any) => (
              <Card key={c.id}>
                <CardBody>
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-2">
                      <UserIcon className="h-4 w-4" style={{ color: "var(--brand-400)" }} />
                      <span className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>{c.user_email}</span>
                      <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                        {new Date(c.created_at).toLocaleString()}
                      </span>
                    </div>
                    {c.target_type !== "investigation" && (
                      <Badge variant="neutral" size="sm">{c.target_type}{c.target_id ? `: ${c.target_id}` : ""}</Badge>
                    )}
                  </div>
                  <p className="mt-2 text-sm" style={{ color: "var(--text-secondary)" }}>{c.text}</p>
                </CardBody>
              </Card>
            ))
          ) : (
            <EmptyState title="No comments yet" description="Be the first to add a comment to this investigation." />
          )}
        </div>
      )}

      {tab === "summary" && (
        <div className="space-y-4">
          {summaryLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin" style={{ color: "var(--brand-500)" }} />
            </div>
          ) : summaryData ? (
            <>
              {/* Risk score banner */}
              <Card>
                <CardBody className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Brain className="h-5 w-5" style={{ color: "var(--brand-400)" }} />
                    <div>
                      <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>AI Intelligence Summary</h3>
                      <p className="text-xs mt-0.5" style={{ color: "var(--text-tertiary)" }}>Rule-based analysis of all scan results</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium" style={{ color: "var(--text-tertiary)" }}>Risk Score</span>
                    <Badge variant={summaryData.risk_score >= 0.7 ? "danger" : summaryData.risk_score >= 0.4 ? "warning" : "success"}>
                      {(summaryData.risk_score * 100).toFixed(0)}%
                    </Badge>
                  </div>
                </CardBody>
              </Card>

              {/* Summary text */}
              <Card>
                <CardHeader><h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Summary</h3></CardHeader>
                <CardBody>
                  <p className="text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>{summaryData.summary}</p>
                </CardBody>
              </Card>

              {/* Key findings */}
              {summaryData.key_findings.length > 0 && (
                <Card>
                  <CardHeader><h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Key Findings</h3></CardHeader>
                  <CardBody>
                    <ul className="space-y-2">
                      {summaryData.key_findings.map((finding: string, i: number) => (
                        <li key={i} className="flex items-start gap-2">
                          <CheckCircle className="h-4 w-4 mt-0.5 shrink-0" style={{ color: "var(--brand-400)" }} />
                          <span className="text-sm" style={{ color: "var(--text-secondary)" }}>{finding}</span>
                        </li>
                      ))}
                    </ul>
                  </CardBody>
                </Card>
              )}

              {/* Risk indicators */}
              {summaryData.risk_indicators.length > 0 && (
                <Card>
                  <CardHeader><h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Risk Indicators</h3></CardHeader>
                  <CardBody>
                    <div className="flex flex-wrap gap-2">
                      {summaryData.risk_indicators.map((indicator: string, i: number) => (
                        <Badge key={i} variant="danger">
                          <AlertTriangle className="h-3 w-3 mr-1 inline" />
                          {indicator}
                        </Badge>
                      ))}
                    </div>
                  </CardBody>
                </Card>
              )}

              {/* Recommended actions */}
              {summaryData.recommended_actions.length > 0 && (
                <Card>
                  <CardHeader><h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Recommended Actions</h3></CardHeader>
                  <CardBody>
                    <ul className="space-y-2">
                      {summaryData.recommended_actions.map((action: string, i: number) => (
                        <li key={i} className="flex items-start gap-2">
                          <Lightbulb className="h-4 w-4 mt-0.5 shrink-0" style={{ color: "var(--warning-400, #f59e0b)" }} />
                          <span className="text-sm" style={{ color: "var(--text-secondary)" }}>{action}</span>
                        </li>
                      ))}
                    </ul>
                  </CardBody>
                </Card>
              )}

              {/* Scan recommendations */}
              {summaryData.scan_recommendations.length > 0 && (
                <Card>
                  <CardHeader><h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Smart Scan Recommendations</h3></CardHeader>
                  <CardBody>
                    <div className="space-y-3">
                      {summaryData.scan_recommendations.map((rec: any, i: number) => (
                        <div key={i} className="rounded-md border p-3" style={{ borderColor: "var(--border-subtle)", backgroundColor: "var(--bg-overlay)" }}>
                          <div className="flex items-center gap-2 mb-1">
                            <Badge variant="info" size="sm">{rec.scanner}</Badge>
                            <Badge variant="neutral" size="sm">{rec.type}</Badge>
                          </div>
                          <p className="text-xs mb-1" style={{ color: "var(--text-tertiary)" }}>{rec.reason}</p>
                          <div className="flex flex-wrap gap-1">
                            {rec.values.map((v: string) => (
                              <DataBadge key={v} value={v} />
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardBody>
                </Card>
              )}
            </>
          ) : (
            <EmptyState title="No summary available" description="Summary will be available once scan results are collected." />
          )}
        </div>
      )}
    </div>
  );
}
