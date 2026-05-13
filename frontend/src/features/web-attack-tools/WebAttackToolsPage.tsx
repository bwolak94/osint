import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  Shield,
  Loader2,
  AlertTriangle,
  CheckCircle2,
  Globe,
  ChevronDown,
  ChevronRight,
  Terminal,
  Search,
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
  exit_code: number;
  duration_seconds: number;
  findings: Finding[];
  error: string | null;
  findings_count: number;
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
  return (
    <Badge variant={SEVERITY_VARIANTS[s] ?? "neutral"} size="sm">
      {s.toUpperCase()}
    </Badge>
  );
}

// ---------------------------------------------------------------------------
// Finding row
// ---------------------------------------------------------------------------

function FindingRow({ finding }: { finding: Finding }) {
  const [open, setOpen] = useState(false);
  return (
    <div
      className="rounded-md border"
      style={{ borderColor: "var(--border-default)", background: "var(--bg-elevated)" }}
    >
      <button
        className="flex w-full items-center gap-3 px-3 py-2 text-left"
        onClick={() => setOpen((p) => !p)}
      >
        {open ? (
          <ChevronDown className="h-3.5 w-3.5 shrink-0" style={{ color: "var(--text-tertiary)" }} />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 shrink-0" style={{ color: "var(--text-tertiary)" }} />
        )}
        <SeverityBadge severity={finding.severity} />
        <span className="flex-1 truncate text-xs font-medium" style={{ color: "var(--text-primary)" }}>
          {finding.title}
        </span>
        {finding.cwe && (
          <Badge variant="neutral" size="sm">CWE-{finding.cwe}</Badge>
        )}
        {finding.cve.map((c) => (
          <Badge key={c} variant="warning" size="sm">{c}</Badge>
        ))}
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
              Host: <span className="font-mono">{finding.host}</span>
              {finding.port ? `:${finding.port}` : ""}
            </p>
          )}
          {Object.keys(finding.evidence).length > 0 && (
            <pre
              className="rounded p-2 text-xs font-mono overflow-x-auto"
              style={{ background: "var(--bg-base)", color: "var(--text-tertiary)" }}
            >
              {JSON.stringify(finding.evidence, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Result panel
// ---------------------------------------------------------------------------

function ResultPanel({ result }: { result: ToolResult }) {
  const hasError = Boolean(result.error);
  const minutes = Math.floor(result.duration_seconds / 60);
  const seconds = (result.duration_seconds % 60).toFixed(1);

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3 flex-wrap">
        {hasError ? (
          <div className="flex items-center gap-2 text-xs" style={{ color: "var(--danger-400)" }}>
            <AlertTriangle className="h-4 w-4" />
            {result.error}
          </div>
        ) : (
          <div className="flex items-center gap-2 text-xs" style={{ color: "var(--success-400)" }}>
            <CheckCircle2 className="h-4 w-4" />
            Completed in {minutes > 0 ? `${minutes}m ` : ""}{seconds}s
          </div>
        )}
        <Badge variant="neutral" size="sm">{result.findings_count} findings</Badge>
      </div>

      {result.findings.length === 0 && !hasError && (
        <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>No findings detected.</p>
      )}

      <div className="space-y-1.5 max-h-[500px] overflow-y-auto pr-1">
        {result.findings.map((f, i) => (
          <FindingRow key={i} finding={f} />
        ))}
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
  placeholder: string;
  extraFields?: React.ReactNode;
}

const TOOLS: ToolDef[] = [
  {
    id: "nikto",
    name: "Nikto",
    description: "Web server misconfig scanner — outdated software, dangerous files, HTTP headers",
    endpoint: "/web-attack-tools/nikto",
    placeholder: "http://target.com",
  },
  {
    id: "wpscan",
    name: "WPScan",
    description: "WordPress plugin/theme/user enumeration + CVE vulnerability lookup",
    endpoint: "/web-attack-tools/wpscan",
    placeholder: "http://wordpress-site.com",
  },
  {
    id: "commix",
    name: "Commix",
    description: "Automated OS command injection detection — GET/POST params, cookies, headers",
    endpoint: "/web-attack-tools/commix",
    placeholder: "http://target.com/page?param=val",
  },
  {
    id: "xsser",
    name: "XSSer",
    description: "Cross-Site Scripting detection — reflected, DOM, stored",
    endpoint: "/web-attack-tools/xsser",
    placeholder: "http://target.com/search?q=test",
  },
  {
    id: "wfuzz",
    name: "wfuzz",
    description: "Web fuzzer — URL paths, parameters, headers. Append FUZZ to URL for injection point",
    endpoint: "/web-attack-tools/wfuzz",
    placeholder: "http://target.com/FUZZ",
  },
  {
    id: "dirsearch",
    name: "dirsearch",
    description: "Directory and file brute-force with extension permutations",
    endpoint: "/web-attack-tools/dirsearch",
    placeholder: "http://target.com",
  },
  {
    id: "skipfish",
    name: "Skipfish",
    description: "Active web app security recon — recursive crawl + injection probes",
    endpoint: "/web-attack-tools/skipfish",
    placeholder: "http://target.com",
  },
  {
    id: "sqlninja",
    name: "SQLNinja",
    description: "MS-SQL injection fingerprinting (detection mode only)",
    endpoint: "/web-attack-tools/sqlninja",
    placeholder: "http://target.com/login.asp",
  },
  {
    id: "masscan",
    name: "Masscan",
    description: "High-speed port scanner — entire IP ranges in seconds (requires root)",
    endpoint: "/web-attack-tools/masscan",
    placeholder: "192.168.1.0/24",
  },
  {
    id: "beef",
    name: "BeEF",
    description: "Connect to BeEF instance — enumerate hooked browsers and collected data",
    endpoint: "/web-attack-tools/beef",
    placeholder: "http://localhost:3000",
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

      const payload: Record<string, unknown> = { target, options: parsedOptions };
      if (tool.id === "beef") {
        payload.beef_url = target;
      }

      const res = await apiClient.post(tool.endpoint, payload);
      return res.data as ToolResult;
    },
    onSuccess: (data) => {
      setResult(data);
      if (data.error) {
        toast.error(`${tool.name}: ${data.error}`);
      } else {
        toast.success(`${tool.name} complete — ${data.findings_count} findings`);
      }
    },
    onError: (err: Error) => toast.error(err.message),
  });

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-3">
          <Terminal className="h-4 w-4 shrink-0" style={{ color: "var(--brand-500)" }} />
          <div>
            <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{tool.name}</p>
            <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>{tool.description}</p>
          </div>
        </div>
      </CardHeader>
      <CardBody className="space-y-3">
        <div>
          <label className="text-xs font-medium mb-1 block" style={{ color: "var(--text-secondary)" }}>
            {tool.id === "beef" ? "BeEF URL" : "Target"}
          </label>
          <input
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            placeholder={tool.placeholder}
            className="w-full rounded-md border px-3 py-2 text-xs font-mono"
            style={{
              background: "var(--bg-elevated)",
              borderColor: "var(--border-default)",
              color: "var(--text-primary)",
            }}
          />
        </div>

        <div>
          <label className="text-xs font-medium mb-1 block" style={{ color: "var(--text-secondary)" }}>
            Options (JSON)
          </label>
          <textarea
            value={options}
            onChange={(e) => setOptions(e.target.value)}
            rows={2}
            placeholder='{"timeout": 120}'
            className="w-full rounded-md border px-3 py-2 text-xs font-mono resize-none"
            style={{
              background: "var(--bg-elevated)",
              borderColor: "var(--border-default)",
              color: "var(--text-primary)",
            }}
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

export function WebAttackToolsPage() {
  const [activeTab, setActiveTab] = useState("nikto");
  const activeTool = TOOLS.find((t) => t.id === activeTab) ?? TOOLS[0];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
          Web Attack Tools
        </h1>
        <p className="text-sm mt-1" style={{ color: "var(--text-secondary)" }}>
          Kali Linux web application attack and reconnaissance tools. For authorized testing only.
        </p>
      </div>

      {/* Tool tabs */}
      <div
        className="flex flex-wrap gap-1 rounded-lg p-1"
        style={{ background: "var(--bg-elevated)" }}
      >
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

      {/* Active tool */}
      <div className="max-w-2xl">
        <div
          className="mb-3 flex items-center gap-2 rounded-md px-3 py-2 text-xs"
          style={{ background: "rgba(245,158,11,0.1)", borderLeft: "3px solid var(--warning-500)" }}
        >
          <AlertTriangle className="h-3.5 w-3.5 shrink-0" style={{ color: "var(--warning-400)" }} />
          <span style={{ color: "var(--warning-300)" }}>
            Only use against targets you own or have explicit written authorization to test.
            Unauthorized scanning is illegal.
          </span>
        </div>
        <ToolPanel tool={activeTool} />
      </div>
    </div>
  );
}
