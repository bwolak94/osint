import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  KeyRound,
  Loader2,
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Terminal,
  Search,
  ShieldAlert,
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
  cve: string[];
  cwe: number | null;
  host: string | null;
  port: number | null;
  url: string | null;
  evidence: Record<string, unknown>;
}

interface ToolResult {
  tool: string;
  exit_code: int;
  duration_seconds: number;
  findings: Finding[];
  error: string | null;
  findings_count: number;
  metadata: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Severity badge
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
        {open ? (
          <ChevronDown className="h-3.5 w-3.5 shrink-0" style={{ color: "var(--text-tertiary)" }} />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 shrink-0" style={{ color: "var(--text-tertiary)" }} />
        )}
        <SeverityBadge severity={finding.severity} />
        <span className="flex-1 truncate text-xs font-medium" style={{ color: "var(--text-primary)" }}>{finding.title}</span>
        {finding.cwe && <Badge variant="neutral" size="sm">CWE-{finding.cwe}</Badge>}
        {finding.cve.map((c) => <Badge key={c} variant="warning" size="sm">{c}</Badge>)}
      </button>
      {open && (
        <div className="border-t px-4 py-3 space-y-2" style={{ borderColor: "var(--border-default)" }}>
          {finding.description && (
            <p className="text-xs" style={{ color: "var(--text-secondary)" }}>{finding.description}</p>
          )}
          {finding.url && (
            <p className="text-xs font-mono truncate" style={{ color: "var(--brand-400)" }}>{finding.url}</p>
          )}
          {finding.host && (
            <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
              Host: <span className="font-mono">{finding.host}</span>{finding.port ? `:${finding.port}` : ""}
            </p>
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
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3 flex-wrap">
        {result.error ? (
          <div className="flex items-center gap-2 text-xs" style={{ color: "var(--danger-400)" }}>
            <AlertTriangle className="h-4 w-4" />{result.error}
          </div>
        ) : (
          <div className="flex items-center gap-2 text-xs" style={{ color: "var(--success-400)" }}>
            <CheckCircle2 className="h-4 w-4" />Completed in {minutes > 0 ? `${minutes}m ` : ""}{seconds}s
          </div>
        )}
        <Badge variant="neutral" size="sm">{result.findings_count} findings</Badge>
        {result.metadata?.endpoint && (
          <Badge variant="neutral" size="sm">Endpoint: {String(result.metadata.endpoint)}</Badge>
        )}
      </div>
      {result.findings.length === 0 && !result.error && (
        <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>No issues detected.</p>
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
  extraFields?: (opts: string, setOpts: (v: string) => void) => React.ReactNode;
  buildPayload: (target: string, options: Record<string, unknown>) => Record<string, unknown>;
}

const TOOLS: ToolDef[] = [
  {
    id: "hydra",
    name: "Hydra",
    description: "Network login brute-force — SSH, FTP, HTTP, SMB, RDP and 15+ services",
    endpoint: "/auth-vuln-tools/hydra",
    targetLabel: "Target Host / IP",
    targetPlaceholder: "192.168.1.1",
    buildPayload: (target, options) => ({ target, service: "ssh", threads: 4, ...options }),
  },
  {
    id: "medusa",
    name: "Medusa",
    description: "Parallel login auditor — concurrent multi-host brute-force",
    endpoint: "/auth-vuln-tools/medusa",
    targetLabel: "Target Host / IP",
    targetPlaceholder: "192.168.1.1",
    buildPayload: (target, options) => ({ target, module: "ssh", threads: 4, ...options }),
  },
  {
    id: "jwt-attack",
    name: "JWT Attack",
    description: "JWT analysis: alg:none, weak secrets, missing expiry, sensitive payload, kid injection",
    endpoint: "/auth-vuln-tools/jwt-attack",
    targetLabel: "JWT Token",
    targetPlaceholder: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    buildPayload: (target, options) => ({ token: target, ...options }),
  },
  {
    id: "oauth-tester",
    name: "OAuth Tester",
    description: "OAuth 2.0 misconfigurations — open redirect, missing PKCE, implicit flow, state CSRF",
    endpoint: "/auth-vuln-tools/oauth-tester",
    targetLabel: "Authorization Endpoint URL",
    targetPlaceholder: "https://app.com/oauth/authorize",
    buildPayload: (target, options) => ({ authorization_endpoint: target, client_id: "test_client", redirect_uri: "https://localhost/callback", ...options }),
  },
  {
    id: "default-creds",
    name: "Default Creds",
    description: "Test web login forms against 20+ common default credential pairs",
    endpoint: "/auth-vuln-tools/default-creds",
    targetLabel: "Target URL",
    targetPlaceholder: "http://192.168.1.1/admin",
    buildPayload: (target, options) => ({ target, ...options }),
  },
  {
    id: "ssrf",
    name: "SSRF Scanner",
    description: "Inject cloud metadata URLs into URL parameters to detect SSRF",
    endpoint: "/auth-vuln-tools/ssrf",
    targetLabel: "Target URL",
    targetPlaceholder: "http://target.com/fetch?url=",
    buildPayload: (target, options) => ({ target, ...options }),
  },
  {
    id: "xxe",
    name: "XXE Scanner",
    description: "Inject XXE payloads into XML endpoints — file read and SSRF via external entities",
    endpoint: "/auth-vuln-tools/xxe",
    targetLabel: "Target Base URL",
    targetPlaceholder: "http://target.com",
    buildPayload: (target, options) => ({ target, method: "POST", ...options }),
  },
  {
    id: "ssti",
    name: "SSTI Scanner",
    description: "Server-Side Template Injection — Jinja2, Twig, Freemarker, ERB, Spring EL",
    endpoint: "/auth-vuln-tools/ssti",
    targetLabel: "Target URL",
    targetPlaceholder: "http://target.com/page?name=test",
    buildPayload: (target, options) => ({ target, ...options }),
  },
  {
    id: "cors",
    name: "CORS Tester",
    description: "CORS misconfiguration — origin reflection, null origin, wildcard with credentials",
    endpoint: "/auth-vuln-tools/cors",
    targetLabel: "Target Base URL",
    targetPlaceholder: "https://api.target.com",
    buildPayload: (target, options) => ({ target, ...options }),
  },
  {
    id: "graphql",
    name: "GraphQL Scanner",
    description: "GraphQL security — introspection, field suggestions, batching DoS, depth limit, CSRF",
    endpoint: "/auth-vuln-tools/graphql",
    targetLabel: "Target Base URL",
    targetPlaceholder: "https://api.target.com",
    buildPayload: (target, options) => ({ target, ...options }),
  },
];

// ---------------------------------------------------------------------------
// Single tool panel
// ---------------------------------------------------------------------------

function ToolPanel({ tool }: { tool: ToolDef }) {
  const [target, setTarget] = useState("");
  const [options, setOptions] = useState("{}");
  const [result, setResult] = useState<ToolResult | null>(null);

  const mutation = useMutation({
    mutationFn: async () => {
      let parsedOptions: Record<string, unknown> = {};
      try {
        parsedOptions = JSON.parse(options);
      } catch {
        throw new Error("Options must be valid JSON");
      }
      const payload = tool.buildPayload(target, parsedOptions);
      const res = await apiClient.post(tool.endpoint, payload);
      return res.data as ToolResult;
    },
    onSuccess: (data) => {
      setResult(data);
      if (data.error) {
        toast.error(`${tool.name}: ${data.error}`);
      } else {
        toast.success(`${tool.name} — ${data.findings_count} finding${data.findings_count !== 1 ? "s" : ""}`);
      }
    },
    onError: (err: Error) => toast.error(err.message),
  });

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-3">
          <ShieldAlert className="h-4 w-4 shrink-0" style={{ color: "var(--brand-500)" }} />
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
            rows={2}
            placeholder='{"cookie": "session=abc", "timeout": 60}'
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

export function AuthVulnToolsPage() {
  const [activeTab, setActiveTab] = useState("hydra");
  const activeTool = TOOLS.find((t) => t.id === activeTab) ?? TOOLS[0];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
          Auth &amp; Vulnerability Tools
        </h1>
        <p className="text-sm mt-1" style={{ color: "var(--text-secondary)" }}>
          Authentication attacks and web vulnerability scanners — Hydra, JWT, OAuth, SSRF, XXE, SSTI, CORS, GraphQL.
        </p>
      </div>

      {/* Tool tabs */}
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

      {/* Warning */}
      <div className="max-w-2xl">
        <div
          className="mb-3 flex items-center gap-2 rounded-md px-3 py-2 text-xs"
          style={{ background: "rgba(245,158,11,0.1)", borderLeft: "3px solid var(--warning-500)" }}
        >
          <AlertTriangle className="h-3.5 w-3.5 shrink-0" style={{ color: "var(--warning-400)" }} />
          <span style={{ color: "var(--warning-300)" }}>
            Only use against targets you own or have explicit written authorization to test.
          </span>
        </div>
        <ToolPanel tool={activeTool} />
      </div>
    </div>
  );
}
