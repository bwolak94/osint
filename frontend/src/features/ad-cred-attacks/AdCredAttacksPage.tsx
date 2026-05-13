import { useState, useCallback } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  Loader2,
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  KeyRound,
  Search,
  Download,
  Shield,
} from "lucide-react";
import { apiClient } from "@/shared/api/client";
import { toast } from "@/shared/components/Toast";
import { Card, CardBody, CardHeader } from "@/shared/components/Card";
import { Badge } from "@/shared/components/Badge";
import { Button } from "@/shared/components/Button";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Finding {
  tool: string;
  title: string;
  severity: string | null;
  description: string | null;
  cvss_v3: number | null;
  cve: string[];
  cwe: number | null;
  host: string | null;
  port: number | null;
  url: string | null;
  evidence: Record<string, unknown>;
  mitre_techniques: string[];
}

interface ToolResult {
  tool: string;
  exit_code: number;
  duration_seconds: number;
  findings: Finding[];
  error: string | null;
  findings_count: number;
  metadata: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Shared UI
// ---------------------------------------------------------------------------

const SEVERITY_VARIANTS: Record<string, "danger" | "warning" | "neutral" | "success"> = {
  critical: "danger",
  high: "danger",
  medium: "warning",
  low: "neutral",
  info: "neutral",
};

function SeverityBadge({ severity }: { severity: string | null }) {
  const s = severity?.toLowerCase() ?? "info";
  return <Badge variant={SEVERITY_VARIANTS[s] ?? "neutral"} size="sm">{s.toUpperCase()}</Badge>;
}

function FindingRow({ finding }: { finding: Finding }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-md border" style={{ borderColor: "var(--border-default)", background: "var(--bg-elevated)" }}>
      <button className="flex w-full items-center gap-3 px-3 py-2 text-left" onClick={() => setOpen((p) => !p)}>
        {open ? <ChevronDown className="h-3.5 w-3.5 shrink-0" style={{ color: "var(--text-tertiary)" }} />
               : <ChevronRight className="h-3.5 w-3.5 shrink-0" style={{ color: "var(--text-tertiary)" }} />}
        <SeverityBadge severity={finding.severity} />
        <span className="flex-1 truncate text-xs font-medium" style={{ color: "var(--text-primary)" }}>{finding.title}</span>
        {finding.cvss_v3 != null && <Badge variant="warning" size="sm">CVSS {finding.cvss_v3.toFixed(1)}</Badge>}
        {finding.cwe && <Badge variant="neutral" size="sm">CWE-{finding.cwe}</Badge>}
        {finding.cve.map((c) => <Badge key={c} variant="warning" size="sm">{c}</Badge>)}
      </button>
      {open && (
        <div className="border-t px-4 py-3 space-y-2" style={{ borderColor: "var(--border-default)" }}>
          {finding.description && <p className="text-xs" style={{ color: "var(--text-secondary)" }}>{finding.description}</p>}
          {(finding.host || finding.port) && (
            <p className="text-xs font-mono" style={{ color: "var(--text-tertiary)" }}>
              {finding.host}{finding.port ? `:${finding.port}` : ""}
            </p>
          )}
          {finding.mitre_techniques.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {finding.mitre_techniques.map((t) => (
                <Badge key={t} variant="neutral" size="sm">
                  <Shield className="h-2.5 w-2.5 mr-1 inline" />{t}
                </Badge>
              ))}
            </div>
          )}
          {Object.keys(finding.evidence).length > 0 && (
            <pre className="rounded p-2 text-xs font-mono overflow-x-auto" style={{ background: "var(--bg-base)", color: "var(--text-tertiary)" }}>
              {JSON.stringify(finding.evidence, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

function ResultPanel({ result }: { result: ToolResult }) {
  const minutes = Math.floor(result.duration_seconds / 60);
  const seconds = (result.duration_seconds % 60).toFixed(1);

  const handleExport = useCallback(() => {
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${result.tool}-findings-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [result]);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        {result.error ? (
          <span className="flex items-center gap-2 text-xs" style={{ color: "var(--danger-400)" }}>
            <AlertTriangle className="h-4 w-4" />{result.error}
          </span>
        ) : (
          <span className="flex items-center gap-2 text-xs" style={{ color: "var(--success-400)" }}>
            <CheckCircle2 className="h-4 w-4" />Done in {minutes > 0 ? `${minutes}m ` : ""}{seconds}s
          </span>
        )}
        <Badge variant="neutral" size="sm">{result.findings_count} findings</Badge>
        {result.findings_count > 0 && (
          <button
            onClick={handleExport}
            className="flex items-center gap-1 text-xs rounded px-2 py-1 transition-colors"
            style={{ color: "var(--brand-400)", background: "rgba(var(--brand-500-rgb),0.1)" }}
          >
            <Download className="h-3 w-3" />Export JSON
          </button>
        )}
      </div>
      {result.findings.length === 0 && !result.error && (
        <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>No findings.</p>
      )}
      <div className="space-y-1.5 max-h-[500px] overflow-y-auto pr-1">
        {result.findings.map((f, i) => <FindingRow key={i} finding={f} />)}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tool definitions
// ---------------------------------------------------------------------------

interface ToolDef {
  id: string;
  name: string;
  description: string;
  endpoint: string;
  targetLabel: string;
  targetPlaceholder: string;
  defaultOptions: string;
  buildPayload: (target: string, options: Record<string, unknown>) => Record<string, unknown>;
}

const TOOLS: ToolDef[] = [
  {
    id: "kerberoast",
    name: "Kerberoast",
    description: "Enumerate SPN service accounts and request TGS tickets for offline cracking (MITRE T1558.003)",
    endpoint: "/ad-cred-attacks/kerberoast",
    targetLabel: "DC IP or Hostname",
    targetPlaceholder: "192.168.1.10",
    defaultOptions: '{"domain": "corp.local", "username": "user", "password": "pass", "request_tgs": true}',
    buildPayload: (target, options) => ({ target, ...options }),
  },
  {
    id: "asreproast",
    name: "AS-REP Roast",
    description: "Find accounts without Kerberos pre-auth and capture AS-REP hashes (MITRE T1558.004)",
    endpoint: "/ad-cred-attacks/asreproast",
    targetLabel: "DC IP or Hostname",
    targetPlaceholder: "192.168.1.10",
    defaultOptions: '{"domain": "corp.local", "userfile": "/tmp/users.txt"}',
    buildPayload: (target, options) => ({ target, ...options }),
  },
  {
    id: "spray",
    name: "Password Spray",
    description: "Low-and-slow credential spray across multiple accounts (MITRE T1110.003)",
    endpoint: "/ad-cred-attacks/spray",
    targetLabel: "Target IP / CIDR",
    targetPlaceholder: "192.168.1.0/24",
    defaultOptions: '{"password": "Password1!", "domain": "corp.local", "protocol": "smb", "delay": 1.0}',
    buildPayload: (target, options) => ({ target, ...options }),
  },
  {
    id: "hashcat",
    name: "Hashcat",
    description: "Offline hash cracking for NTLM, NetNTLMv2, Kerberoast TGS, AS-REP (MITRE T1110.002)",
    endpoint: "/ad-cred-attacks/hashcat",
    targetLabel: "Hash file path or inline hash",
    targetPlaceholder: "/tmp/hashes.txt",
    defaultOptions: '{"hash_type": 1000, "attack_mode": 0, "timeout": 300}',
    buildPayload: (target, options) => ({ target, ...options }),
  },
  {
    id: "responder",
    name: "Responder",
    description: "LLMNR/NBT-NS/mDNS poisoning to capture NTLM hashes (MITRE T1557.001). Requires root.",
    endpoint: "/ad-cred-attacks/responder",
    targetLabel: "Network Interface",
    targetPlaceholder: "eth0",
    defaultOptions: '{"interface": "eth0", "duration": 60, "active_poisoning": false}',
    buildPayload: (target, options) => ({ target, ...options }),
  },
];

// ---------------------------------------------------------------------------
// Tool Panel
// ---------------------------------------------------------------------------

function ToolPanel({ tool }: { tool: ToolDef }) {
  const [target, setTarget] = useState("");
  const [options, setOptions] = useState(tool.defaultOptions);
  const [result, setResult] = useState<ToolResult | null>(null);

  const mutation = useMutation({
    mutationFn: async () => {
      let parsed: Record<string, unknown> = {};
      try { parsed = JSON.parse(options); } catch { throw new Error("Options must be valid JSON"); }
      const payload = tool.buildPayload(target, parsed);
      const res = await apiClient.post(tool.endpoint, payload);
      return res.data as ToolResult;
    },
    onSuccess: (data) => {
      setResult(data);
      if (data.error) toast.error(`${tool.name}: ${data.error}`);
      else toast.success(`${tool.name} — ${data.findings_count} finding${data.findings_count !== 1 ? "s" : ""}`);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-3">
          <KeyRound className="h-4 w-4 shrink-0" style={{ color: "var(--brand-500)" }} />
          <div>
            <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{tool.name}</p>
            <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>{tool.description}</p>
          </div>
        </div>
      </CardHeader>
      <CardBody className="space-y-3">
        <div>
          <label className="text-xs font-medium mb-1 block" style={{ color: "var(--text-secondary)" }}>{tool.targetLabel}</label>
          <input
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            placeholder={tool.targetPlaceholder}
            className="w-full rounded-md border px-3 py-2 text-xs font-mono"
            style={{ background: "var(--bg-elevated)", borderColor: "var(--border-default)", color: "var(--text-primary)" }}
          />
        </div>
        <div>
          <label className="text-xs font-medium mb-1 block" style={{ color: "var(--text-secondary)" }}>Options (JSON)</label>
          <textarea
            value={options}
            onChange={(e) => setOptions(e.target.value)}
            rows={3}
            className="w-full rounded-md border px-3 py-2 text-xs font-mono resize-none"
            style={{ background: "var(--bg-elevated)", borderColor: "var(--border-default)", color: "var(--text-primary)" }}
          />
        </div>
        <Button
          size="sm"
          leftIcon={mutation.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Search className="h-3.5 w-3.5" />}
          loading={mutation.isPending}
          disabled={!target.trim() || mutation.isPending}
          onClick={() => mutation.mutate()}
        >
          Run {tool.name}
        </Button>
        {result && <ResultPanel result={result} />}
      </CardBody>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function AdCredAttacksPage() {
  const [activeTab, setActiveTab] = useState("kerberoast");
  const activeTool = TOOLS.find((t) => t.id === activeTab) ?? TOOLS[0];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
          AD Credential Attacks
        </h1>
        <p className="text-sm mt-1" style={{ color: "var(--text-secondary)" }}>
          Active Directory credential attack tools — Kerberoasting, AS-REP Roasting, Password Spray, Hashcat, Responder. All findings enriched with MITRE ATT&CK techniques and deduplicated.
        </p>
      </div>

      <div className="flex flex-wrap gap-1 rounded-lg p-1" style={{ background: "var(--bg-elevated)" }}>
        {TOOLS.map((tool) => (
          <button
            key={tool.id}
            onClick={() => setActiveTab(tool.id)}
            className="rounded-md px-3 py-1.5 text-xs font-medium transition-colors"
            style={{
              background: activeTab === tool.id ? "var(--bg-surface)" : "transparent",
              color: activeTab === tool.id ? "var(--text-primary)" : "var(--text-tertiary)",
              boxShadow: activeTab === tool.id ? "0 1px 3px rgba(0,0,0,0.2)" : "none",
            }}
          >
            {tool.name}
          </button>
        ))}
      </div>

      <div className="max-w-2xl">
        <div
          className="mb-3 flex items-center gap-2 rounded-md px-3 py-2 text-xs"
          style={{ background: "rgba(239,68,68,0.1)", borderLeft: "3px solid var(--danger-500)" }}
        >
          <AlertTriangle className="h-3.5 w-3.5 shrink-0" style={{ color: "var(--danger-400)" }} />
          <span style={{ color: "var(--danger-300)" }}>
            High-impact AD attacks. Authorized use only. Kerberoast/AS-REP require domain credentials. Responder requires root + network access.
          </span>
        </div>
        <ToolPanel tool={activeTool} />
      </div>
    </div>
  );
}
