import { useState } from "react";
import { Code2, Zap, Copy, CheckCheck, AlertTriangle } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import apiClient from "@/shared/api/client";
import { Button } from "@/shared/components/Button";
import { Input } from "@/shared/components/Input";
import { Card, CardBody, CardHeader } from "@/shared/components/Card";
import { Badge } from "@/shared/components/Badge";
import { ScanResultErrorBoundary } from "@/shared/components/osint/ScanResultErrorBoundary";

interface NucleiTemplate       {mutationError && (
        <p role="alert" className="text-xs rounded-lg px-3 py-2 border" style={{ color: "var(--danger-400)", borderColor: "var(--danger-500)", background: "var(--bg-surface)" }}>
          {mutationError}
        </p>
      )}
      {
  template_id: string;
  name: string;
  severity: string;
  tags: string[];
  description: string;
  yaml_content: string;
  cve_id: string | null;
  protocol: string;
  confidence: number;
  warnings: string[];
}

const severityVariant = (s: string): "danger" | "warning" | "neutral" | "success" => {
  if (s === "critical") return "danger";
  if (s === "high") return "warning";
  if (s === "medium") return "neutral";
  return "success";
};

const VULN_TYPES = [
  { value: "rce", label: "Remote Code Execution" },
  { value: "sqli", label: "SQL Injection" },
  { value: "xss", label: "Cross-Site Scripting" },
  { value: "ssrf", label: "SSRF" },
  { value: "lfi", label: "Local File Inclusion" },
  { value: "idor", label: "IDOR" },
  { value: "auth_bypass", label: "Auth Bypass" },
  { value: "info_disclosure", label: "Info Disclosure" },
];

export function NucleiGeneratorPage() {
  const [form, setForm] = useState({
    cve_id: "",
    vulnerability_title: "",
    affected_component: "",
    vuln_type: "rce",
    target_url_pattern: "",
    cvss_score: "",
  });
  const [mutationError, setMutationError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const generate = useMutation({
    mutationFn: (data: typeof form) =>
      apiClient.post<NucleiTemplate>("/api/v1/nuclei-generator/generate", {
        ...data,
        cve_id: data.cve_id.trim() || null,
        target_url_pattern: data.target_url_pattern.trim() || null,
        cvss_score: data.cvss_score ? parseFloat(data.cvss_score) : null,
      }).then((r) => r.data),
  });

  const handleCopy = () => {
    if (generate.data) {
      navigator.clipboard.writeText(generate.data.yaml_content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const update = (field: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm((f) => ({ ...f, [field]: e.target.value }));

  const canSubmit = form.vulnerability_title.trim().length >= 5 && form.affected_component.trim().length >= 2;

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <Zap className="h-6 w-6" style={{ color: "var(--brand-400)" }} />
        <div>
          <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Nuclei Template Generator</h1>
          <p className="text-xs mt-0.5" style={{ color: "var(--text-tertiary)" }}>Generate Nuclei YAML templates from CVE / vulnerability details</p>
        </div>
      </div>

      <Card>
        <CardHeader>
          <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>Vulnerability Details</p>
        </CardHeader>
        <CardBody className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs mb-1 block" style={{ color: "var(--text-tertiary)" }}>CVE ID (optional)</label>
              <Input placeholder="CVE-2024-12345" value={form.cve_id} onChange={update("cve_id")} />
            </div>
            <div>
              <label className="text-xs mb-1 block" style={{ color: "var(--text-tertiary)" }}>CVSS Score</label>
              <Input type="number" placeholder="9.8" min="0" max="10" step="0.1" value={form.cvss_score} onChange={update("cvss_score")} />
            </div>
          </div>

          <div>
            <label className="text-xs mb-1 block" style={{ color: "var(--text-tertiary)" }}>Vulnerability Title *</label>
            <Input placeholder="Remote Code Execution in Acme WebApp v2.3" value={form.vulnerability_title} onChange={update("vulnerability_title")} />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs mb-1 block" style={{ color: "var(--text-tertiary)" }}>Affected Component *</label>
              <Input placeholder="acme-webapp" value={form.affected_component} onChange={update("affected_component")} />
            </div>
            <div>
              <label className="text-xs mb-1 block" style={{ color: "var(--text-tertiary)" }}>Vulnerability Type *</label>
              <select
                className="w-full rounded-lg border px-3 py-2 text-sm"
                style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)", color: "var(--text-primary)" }}
                value={form.vuln_type}
                onChange={update("vuln_type")}
              >
                {VULN_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
          </div>

          <div>
            <label className="text-xs mb-1 block" style={{ color: "var(--text-tertiary)" }}>Target URL Pattern (optional)</label>
            <Input placeholder="{{BaseURL}}/api/v1/execute" value={form.target_url_pattern} onChange={update("target_url_pattern")} />
          </div>

          <Button
            onClick={() => generate.mutate(form)}
            disabled={!canSubmit || generate.isPending}
            leftIcon={<Zap className="h-4 w-4" />}
          >
            {generate.isPending ? "Generating..." : "Generate Template"}
          </Button>
        </CardBody>
      </Card>

      {generate.data && (
        <div className="space-y-4">
          <div className="rounded-xl border p-4 space-y-3" style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}>
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2 flex-wrap">
                <Badge variant={severityVariant(generate.data.severity)}>{generate.data.severity.toUpperCase()}</Badge>
                <Badge variant="neutral">{generate.data.protocol}</Badge>
                <span className="text-xs font-mono" style={{ color: "var(--text-tertiary)" }}>
                  confidence: {(generate.data.confidence * 100).toFixed(0)}%
                </span>
                {generate.data.tags.map((t) => (
                  <span key={t} className="text-xs px-1.5 py-0.5 rounded" style={{ background: "var(--bg-raised)", color: "var(--text-tertiary)" }}>
                    #{t}
                  </span>
                ))}
              </div>
              <Button size="sm" variant="ghost" onClick={handleCopy} leftIcon={copied ? <CheckCheck className="h-3 w-3" /> : <Copy className="h-3 w-3" />}>
                {copied ? "Copied!" : "Copy"}
              </Button>
            </div>

            {generate.data.warnings.map((w) => (
              <div key={w} className="flex items-start gap-2 text-xs">
                <AlertTriangle className="h-3 w-3 mt-0.5 shrink-0" style={{ color: "var(--warning-400)" }} />
                <span style={{ color: "var(--text-secondary)" }}>{w}</span>
              </div>
            ))}

            <pre
              className="rounded-lg p-4 text-xs font-mono overflow-auto max-h-96"
              style={{ background: "var(--bg-raised)", color: "var(--text-primary)" }}
            >
              {generate.data.yaml_content}
            </pre>
          </div>

          <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
            Save as <code className="px-1 rounded" style={{ background: "var(--bg-raised)" }}>{generate.data.template_id}.yaml</code>{" "}
            and run with: <code className="px-1 rounded" style={{ background: "var(--bg-raised)" }}>nuclei -t {generate.data.template_id}.yaml -u https://target.com</code>
          </p>
        </div>
      )}

      {!generate.data && !generate.isPending && (
        <div className="rounded-xl border py-16 text-center" style={{ borderColor: "var(--border-subtle)" }}>
          <Code2 className="mx-auto h-10 w-10 mb-3" style={{ color: "var(--text-tertiary)" }} />
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Fill in vulnerability details to generate a Nuclei template</p>
        </div>
      )}
    </div>
  );
}
