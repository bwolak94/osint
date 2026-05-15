import { useState } from "react";
import { Users, Search, AlertTriangle, Bot } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import apiClient from "@/shared/api/client";
import { Button } from "@/shared/components/Button";
import { Input } from "@/shared/components/Input";
import { Card, CardBody, CardHeader } from "@/shared/components/Card";
import { Badge } from "@/shared/components/Badge";
import { ScanResultErrorBoundary } from "@/shared/components/osint/ScanResultErrorBoundary";

interface AccountSignal       {mutationError && (
        <p role="alert" className="text-xs rounded-lg px-3 py-2 border" style={{ color: "var(--danger-400)", borderColor: "var(--danger-500)", background: "var(--bg-surface)" }}>
          {mutationError}
        </p>
      )}
      {
  handle: string;
  platform: string;
  follower_count: number;
  account_age_days: number;
  bot_probability: number;
  suspicious_signals: string[];
}

interface CIBCluster {
  cluster_id: string;
  cluster_size: number;
  coordination_type: string;
  accounts: AccountSignal[];
  posting_correlation_score: number;
  narrative_keywords: string[];
  confidence: number;
}

interface CIBAnalysisResult {
  analyzed_accounts: number;
  clusters_found: number;
  bot_accounts_detected: number;
  coordinated_accounts: number;
  clusters: CIBCluster[];
  top_narratives: string[];
  infrastructure_overlap: string[];
  overall_cib_score: number;
  verdict: string;
}

const PLATFORMS = ["twitter", "facebook", "telegram", "reddit"];

function ClusterCard({ cluster }: { cluster: CIBCluster }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-xl border p-4 space-y-3" style={{ background: "var(--bg-surface)", borderColor: cluster.confidence >= 0.7 ? "var(--danger-500)" : "var(--border-subtle)" }}>
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="flex items-center gap-2 flex-wrap">
            <Badge variant={cluster.confidence >= 0.7 ? "danger" : cluster.confidence >= 0.5 ? "warning" : "neutral"}>
              {cluster.coordination_type.replace("_", " ")}
            </Badge>
            <span className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
              {cluster.cluster_size} account{cluster.cluster_size !== 1 ? "s" : ""}
            </span>
          </div>
          <div className="flex gap-3 text-xs" style={{ color: "var(--text-tertiary)" }}>
            <span>Correlation: {(cluster.posting_correlation_score * 100).toFixed(0)}%</span>
            <span>Confidence: {(cluster.confidence * 100).toFixed(0)}%</span>
          </div>
        </div>
        <button className="text-xs underline shrink-0" style={{ color: "var(--brand-400)" }} onClick={() => setExpanded((e) => !e)}>
          {expanded ? "Collapse" : "Show accounts"}
        </button>
      </div>

      <div className="flex gap-1 flex-wrap">
        {cluster.narrative_keywords.map((kw) => (
          <span key={kw} className="text-xs px-1.5 py-0.5 rounded" style={{ background: "var(--bg-raised)", color: "var(--text-tertiary)" }}>
            #{kw}
          </span>
        ))}
      </div>

      {expanded && (
        <div className="space-y-2 pt-2 border-t" style={{ borderColor: "var(--border-subtle)" }}>
          {cluster.accounts.map((acc) => (
            <div key={acc.handle} className="flex items-center gap-3 text-xs">
              <Bot className="h-3 w-3 shrink-0" style={{ color: acc.bot_probability >= 0.6 ? "var(--danger-400)" : "var(--text-tertiary)" }} />
              <span className="font-mono" style={{ color: "var(--text-primary)" }}>@{acc.handle}</span>
              <span style={{ color: "var(--text-tertiary)" }}>{acc.account_age_days}d old</span>
              <span style={{ color: "var(--text-tertiary)" }}>{acc.follower_count.toLocaleString()} followers</span>
              <Badge
                variant={acc.bot_probability >= 0.6 ? "danger" : "neutral"}
                size="sm"
                className="ml-auto"
              >
                {(acc.bot_probability * 100).toFixed(0)}% bot
              </Badge>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function CIBDetectorPage() {
  const [handles, setHandles] = useState("");
  const [mutationError, setMutationError] = useState<string | null>(null);
  const [platform, setPlatform] = useState("twitter");

  const analyze = useMutation({
    mutationFn: (data: { accounts: string[]; platform: string }) =>
      apiClient.post<CIBAnalysisResult>("/api/v1/cib-detector/analyze", data).then((r) => r.data),
  });

  const handleAnalyze = () => {
    const accounts = handles.split("\n").map((s) => s.trim().replace(/^@/, "")).filter(Boolean);
    if (accounts.length < 2) return;
    analyze.mutate({ accounts, platform });
  };

  const scoreColor = (s: number) => s >= 0.7 ? "var(--danger-400)" : s >= 0.4 ? "var(--warning-400)" : "var(--success-400)";

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <Users className="h-6 w-6" style={{ color: "var(--brand-400)" }} />
        <div>
          <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>CIB Detector</h1>
          <p className="text-xs mt-0.5" style={{ color: "var(--text-tertiary)" }}>Coordinated Inauthentic Behavior detection across social platforms</p>
        </div>
      </div>

      <Card>
        <CardHeader>
          <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>Accounts to Analyze</p>
        </CardHeader>
        <CardBody className="space-y-3">
          <div className="grid grid-cols-4 gap-3">
            <div className="col-span-3">
              <label className="text-xs mb-1 block" style={{ color: "var(--text-tertiary)" }}>
                Account handles (one per line, min 2)
              </label>
              <textarea
                className="w-full rounded-lg border px-3 py-2 text-sm resize-none h-24"
                style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)", color: "var(--text-primary)" }}
                placeholder={"@user1\n@user2\n@user3"}
                value={handles}
                onChange={(e) => setHandles(e.target.value)}
              />
            </div>
            <div>
              <label className="text-xs mb-1 block" style={{ color: "var(--text-tertiary)" }}>Platform</label>
              <select
                className="w-full rounded-lg border px-3 py-2 text-sm"
                style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)", color: "var(--text-primary)" }}
                value={platform}
                onChange={(e) => setPlatform(e.target.value)}
              >
                {PLATFORMS.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>
          </div>

          <Button
            onClick={handleAnalyze}
            disabled={handles.split("\n").filter((s) => s.trim()).length < 2 || analyze.isPending}
            leftIcon={<Search className="h-4 w-4" />}
          >
            {analyze.isPending ? "Analyzing..." : "Detect CIB"}
          </Button>
        </CardBody>
      </Card>

      {analyze.data && (
        <div className="space-y-4">
          {/* Verdict */}
          <div
            className="rounded-xl border p-4 flex items-start gap-3"
            style={{
              background: "var(--bg-surface)",
              borderColor: analyze.data.overall_cib_score >= 0.7 ? "var(--danger-500)" : "var(--border-subtle)",
            }}
          >
            <AlertTriangle
              className="h-5 w-5 shrink-0 mt-0.5"
              style={{ color: scoreColor(analyze.data.overall_cib_score) }}
            />
            <div>
              <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>{analyze.data.verdict}</p>
              <p className="text-xs mt-0.5" style={{ color: "var(--text-tertiary)" }}>
                CIB Score: <strong style={{ color: scoreColor(analyze.data.overall_cib_score) }}>
                  {(analyze.data.overall_cib_score * 100).toFixed(0)}%
                </strong>
              </p>
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[
              { label: "Analyzed", value: analyze.data.analyzed_accounts },
              { label: "Clusters Found", value: analyze.data.clusters_found, color: "var(--warning-400)" },
              { label: "Bot Accounts", value: analyze.data.bot_accounts_detected, color: "var(--danger-400)" },
              { label: "Coordinated", value: analyze.data.coordinated_accounts, color: "var(--danger-400)" },
            ].map(({ label, value, color }) => (
              <div key={label} className="rounded-xl border p-3 text-center" style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}>
                <p className="text-2xl font-bold" style={{ color: color || "var(--text-primary)" }}>{value}</p>
                <p className="text-xs mt-1" style={{ color: "var(--text-tertiary)" }}>{label}</p>
              </div>
            ))}
          </div>

          {analyze.data.clusters.length > 0 && (
            <div className="space-y-3">
              <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>CIB Clusters</p>
              {analyze.data.clusters.map((c) => <ClusterCard key={c.cluster_id} cluster={c} />)}
            </div>
          )}
        </div>
      )}

      {!analyze.data && !analyze.isPending && (
        <div className="rounded-xl border py-16 text-center" style={{ borderColor: "var(--border-subtle)" }}>
          <Users className="mx-auto h-10 w-10 mb-3" style={{ color: "var(--text-tertiary)" }} />
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Add account handles to detect coordinated behavior</p>
          <p className="text-xs mt-1" style={{ color: "var(--text-tertiary)" }}>Minimum 2 accounts required</p>
        </div>
      )}
    </div>
  );
}
