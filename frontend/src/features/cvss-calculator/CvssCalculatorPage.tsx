import { useState } from "react";
import { CVSSCalculator } from "@/features/pentesting/components/CVSSCalculator";
import { Badge } from "@/shared/components/Badge";
import { Card, CardBody, CardHeader } from "@/shared/components/Card";
import { Copy, CheckCircle } from "lucide-react";

function severityFromScore(score: number): { label: string; variant: "danger" | "warning" | "neutral" | "success" } {
  if (score >= 9.0) return { label: "CRITICAL", variant: "danger" };
  if (score >= 7.0) return { label: "HIGH", variant: "danger" };
  if (score >= 4.0) return { label: "MEDIUM", variant: "warning" };
  if (score > 0)    return { label: "LOW", variant: "neutral" };
  return { label: "NONE", variant: "success" };
}

export function CvssCalculatorPage() {
  const [score, setScore] = useState(0);
  const [vector, setVector] = useState("");
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    if (!vector) return;
    navigator.clipboard.writeText(vector).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const severity = severityFromScore(score);

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
          CVSS v3 Calculator
        </h1>
        <p className="text-sm mt-1" style={{ color: "var(--text-secondary)" }}>
          Calculate CVSS v3.1 scores for vulnerability findings. Use the vector string in reports and findings.
        </p>
      </div>

      {score > 0 && (
        <div className="flex items-center gap-4 rounded-lg px-4 py-3" style={{ background: "var(--bg-elevated)" }}>
          <div>
            <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>Base Score</p>
            <p className="text-3xl font-bold tabular-nums" style={{ color: "var(--text-primary)" }}>
              {score.toFixed(1)}
            </p>
          </div>
          <Badge variant={severity.variant} size="sm" className="text-sm px-3 py-1">
            {severity.label}
          </Badge>
          {vector && (
            <div className="flex-1 min-w-0">
              <p className="text-xs mb-1" style={{ color: "var(--text-tertiary)" }}>Vector String</p>
              <div className="flex items-center gap-2">
                <code className="text-xs font-mono truncate" style={{ color: "var(--text-secondary)" }}>
                  {vector}
                </code>
                <button onClick={handleCopy} className="shrink-0" title="Copy vector string">
                  {copied
                    ? <CheckCircle className="h-3.5 w-3.5" style={{ color: "var(--success-400)" }} />
                    : <Copy className="h-3.5 w-3.5" style={{ color: "var(--text-tertiary)" }} />}
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      <Card>
        <CardHeader>
          <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
            CVSS v3.1 Base Metrics
          </p>
        </CardHeader>
        <CardBody>
          <CVSSCalculator onChange={(s, v) => { setScore(s); setVector(v); }} />
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Score Reference</p>
        </CardHeader>
        <CardBody>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[
              { range: "9.0 – 10.0", label: "Critical", variant: "danger" as const },
              { range: "7.0 – 8.9", label: "High", variant: "danger" as const },
              { range: "4.0 – 6.9", label: "Medium", variant: "warning" as const },
              { range: "0.1 – 3.9", label: "Low", variant: "neutral" as const },
            ].map((row) => (
              <div key={row.label} className="rounded-md p-2 text-center" style={{ background: "var(--bg-base)" }}>
                <Badge variant={row.variant} size="sm">{row.label}</Badge>
                <p className="text-xs mt-1 font-mono" style={{ color: "var(--text-tertiary)" }}>{row.range}</p>
              </div>
            ))}
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
