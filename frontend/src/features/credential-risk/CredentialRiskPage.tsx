import { useState } from "react";
import { Key, Search, ShieldCheck, AlertTriangle } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import apiClient from "@/shared/api/client";
import { Button } from "@/shared/components/Button";
import { Input } from "@/shared/components/Input";
import { Card, CardBody, CardHeader } from "@/shared/components/Card";
import { Badge } from "@/shared/components/Badge";

interface BreachRecord {
  breach_name: string;
  breach_date: string;
  data_classes: string[];
  password_exposed: boolean;
  verified: boolean;
  is_sensitive: boolean;
}

interface CredentialRiskScore {
  email: string;
  overall_risk_score: number;
  risk_level: string;
  breach_count: number;
  password_exposed_count: number;
  reuse_probability: number;
  mfa_bypass_risk: number;
  estimated_cracked_pct: number;
  breaches: BreachRecord[];
  exposed_data_classes: string[];
  risk_factors: string[];
  mitigations: string[];
  score_breakdown: Record<string, number>;
}

interface BatchResult {
  total_emails: number;
  critical_count: number;
  high_count: number;
  results: CredentialRiskScore[];
}

const riskVariant = (level: string): "danger" | "warning" | "neutral" | "success" => {
  if (level === "critical") return "danger";
  if (level === "high") return "warning";
  if (level === "medium") return "neutral";
  return "success";
};

function ScoreGauge({ score }: { score: number }) {
  const color = score >= 7 ? "var(--danger-500)" : score >= 5 ? "var(--warning-500)" : score >= 3 ? "var(--yellow-500, #eab308)" : "var(--success-500)";
  const level = score >= 7 ? "Critical" : score >= 5 ? "High" : score >= 3 ? "Medium" : "Low";
  return (
    <div className="flex items-center gap-3">
      <div className="relative h-16 w-16 shrink-0">
        {/* (#31) role+aria-label exposes risk score to screen readers */}
        <svg
          viewBox="0 0 36 36"
          className="h-16 w-16 -rotate-90"
          role="img"
          aria-label={`Risk score ${score.toFixed(1)} out of 10 — ${level} risk`}
        >
          <circle cx="18" cy="18" r="14" fill="none" stroke="var(--bg-raised)" strokeWidth="3" />
          <circle
            cx="18" cy="18" r="14" fill="none"
            stroke={color} strokeWidth="3"
            strokeDasharray={`${score / 10 * 87.96} 87.96`}
            strokeLinecap="round"
          />
        </svg>
        <span className="absolute inset-0 flex items-center justify-center text-lg font-bold" style={{ color }} aria-hidden="true">
          {score.toFixed(1)}
        </span>
      </div>
      <div>
        <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>Risk Score (0-10)</p>
        <Badge variant={riskVariant(score >= 7 ? "critical" : score >= 5 ? "high" : score >= 3 ? "medium" : "low")}>
          {score >= 7 ? "Critical" : score >= 5 ? "High" : score >= 3 ? "Medium" : "Low"} Risk
        </Badge>
      </div>
    </div>
  );
}

function RiskCard({ result }: { result: CredentialRiskScore }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      className="rounded-xl border p-4 space-y-3"
      style={{ background: "var(--bg-surface)", borderColor: result.risk_level === "critical" ? "var(--danger-500)" : "var(--border-subtle)" }}
    >
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>{result.email}</p>
          <p className="text-xs mt-0.5" style={{ color: "var(--text-tertiary)" }}>
            {result.breach_count} breach{result.breach_count !== 1 ? "es" : ""} ·{" "}
            {result.password_exposed_count} password exposure{result.password_exposed_count !== 1 ? "s" : ""}
          </p>
        </div>
        <ScoreGauge score={result.overall_risk_score} />
      </div>

      <div className="grid grid-cols-3 gap-2 text-xs text-center">
        <div className="rounded-lg p-2" style={{ background: "var(--bg-raised)" }}>
          <p className="font-bold" style={{ color: "var(--warning-400)" }}>{(result.reuse_probability * 100).toFixed(0)}%</p>
          <p style={{ color: "var(--text-tertiary)" }}>Reuse Risk</p>
        </div>
        <div className="rounded-lg p-2" style={{ background: "var(--bg-raised)" }}>
          <p className="font-bold" style={{ color: "var(--danger-400)" }}>{result.estimated_cracked_pct.toFixed(0)}%</p>
          <p style={{ color: "var(--text-tertiary)" }}>Cracked Est.</p>
        </div>
        <div className="rounded-lg p-2" style={{ background: "var(--bg-raised)" }}>
          <p className="font-bold" style={{ color: "var(--text-primary)" }}>{(result.mfa_bypass_risk * 100).toFixed(0)}%</p>
          <p style={{ color: "var(--text-tertiary)" }}>MFA Bypass</p>
        </div>
      </div>

      {result.risk_factors.length > 0 && (
        <div className="space-y-1">
          {result.risk_factors.map((f) => (
            <div key={f} className="flex items-start gap-2 text-xs">
              <AlertTriangle className="h-3 w-3 mt-0.5 shrink-0" style={{ color: "var(--danger-400)" }} />
              <span style={{ color: "var(--text-secondary)" }}>{f}</span>
            </div>
          ))}
        </div>
      )}

      <button
        className="text-xs underline"
        style={{ color: "var(--brand-400)" }}
        onClick={() => setExpanded((e) => !e)}
      >
        {expanded ? "Hide" : "Show"} breach details ({result.breaches.length})
      </button>

      {expanded && result.breaches.length > 0 && (
        <div className="space-y-2 pt-2 border-t" style={{ borderColor: "var(--border-subtle)" }}>
          {result.breaches.map((b) => (
            <div key={b.breach_name} className="flex items-center gap-2 text-xs">
              {b.password_exposed ? (
                <Key className="h-3 w-3 shrink-0" style={{ color: "var(--danger-400)" }} />
              ) : (
                <ShieldCheck className="h-3 w-3 shrink-0" style={{ color: "var(--text-tertiary)" }} />
              )}
              <span className="font-medium" style={{ color: "var(--text-primary)" }}>{b.breach_name}</span>
              <span style={{ color: "var(--text-tertiary)" }}>{b.breach_date.substring(0, 7)}</span>
              <div className="flex gap-1 ml-auto flex-wrap justify-end">
                {b.data_classes.slice(0, 3).map((dc) => (
                  <span key={dc} className="px-1.5 py-0.5 rounded" style={{ background: "var(--bg-raised)", color: "var(--text-tertiary)" }}>{dc}</span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {result.mitigations.length > 0 && (
        <div className="pt-2 border-t space-y-1" style={{ borderColor: "var(--border-subtle)" }}>
          <p className="text-xs font-medium" style={{ color: "var(--text-primary)" }}>Mitigations</p>
          {result.mitigations.map((m) => (
            <div key={m} className="flex items-start gap-2 text-xs">
              <ShieldCheck className="h-3 w-3 mt-0.5 shrink-0" style={{ color: "var(--success-400)" }} />
              <span style={{ color: "var(--text-secondary)" }}>{m}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function CredentialRiskPage() {
  const [emails, setEmails] = useState("");
  const [mutationError, setMutationError] = useState<string | null>(null);

  const score = useMutation({
    mutationFn: (emailList: string[]) =>
      apiClient.post<BatchResult>("/api/v1/credential-risk/batch-score", {
        emails: emailList,
        include_breach_detail: true,
      }).then((r) => r.data),
    onError: (err: Error) => setMutationError(err.message),  // (#30)
    onSuccess: () => setMutationError(null),
  });

  const handleScore = () => {
    const emailList = emails.split("\n").map((e) => e.trim()).filter(Boolean);
    if (emailList.length) score.mutate(emailList);
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <Key className="h-6 w-6" style={{ color: "var(--warning-400)" }} />
        <div>
          <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Credential Risk Scoring</h1>
          <p className="text-xs mt-0.5" style={{ color: "var(--text-tertiary)" }}>Breach exposure, reuse probability, and attack surface scoring</p>
        </div>
      </div>

      <Card>
        <CardHeader>
          <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>Email Addresses to Analyze</p>
        </CardHeader>
        <CardBody className="space-y-3">
          <textarea
            className="w-full rounded-lg border px-3 py-2 text-sm resize-none h-28"
            style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)", color: "var(--text-primary)" }}
            placeholder={"user@example.com\nadmin@company.org\nsupport@domain.net"}
            value={emails}
            onChange={(e) => setEmails(e.target.value)}
          />
          <Button onClick={handleScore} disabled={!emails.trim() || score.isPending} leftIcon={<Search className="h-4 w-4" />}>
            {score.isPending ? "Scoring..." : "Score Credentials"}
          </Button>
          {mutationError && (
            <p role="alert" className="text-xs mt-1" style={{ color: "var(--danger-400)" }}>
              {mutationError}
            </p>
          )}
        </CardBody>
      </Card>

      {score.data && (
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-3">
            {[
              { label: "Analyzed", value: score.data.total_emails },
              { label: "Critical", value: score.data.critical_count, color: "var(--danger-400)" },
              { label: "High Risk", value: score.data.high_count, color: "var(--warning-400)" },
            ].map(({ label, value, color }) => (
              <div key={label} className="rounded-xl border p-3 text-center" style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}>
                <p className="text-2xl font-bold" style={{ color: color || "var(--text-primary)" }}>{value}</p>
                <p className="text-xs mt-1" style={{ color: "var(--text-tertiary)" }}>{label}</p>
              </div>
            ))}
          </div>

          <div className="space-y-3">
            {score.data.results.map((r) => <RiskCard key={r.email} result={r} />)}
          </div>
        </div>
      )}

      {!score.data && !score.isPending && (
        <div className="rounded-xl border py-16 text-center" style={{ borderColor: "var(--border-subtle)" }}>
          <Key className="mx-auto h-10 w-10 mb-3" style={{ color: "var(--text-tertiary)" }} />
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Enter email addresses to score credential exposure risk</p>
        </div>
      )}
    </div>
  );
}
