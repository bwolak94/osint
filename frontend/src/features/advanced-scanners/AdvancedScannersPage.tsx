import { useState, useCallback } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Loader2,
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Zap,
  Search,
  Download,
  BookmarkPlus,
  BookmarkCheck,
  Shield,
  CheckCircle,
  XCircle,
  Terminal,
  FileCode,
  Globe,
  Copy,
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

interface ToolBinaryStatus {
  name: string;
  category: string;
  available: boolean;
  path: string | null;
}

interface ToolHealthResponse {
  tools: ToolBinaryStatus[];
  available_count: number;
  missing_count: number;
  total_count: number;
}

// ---------------------------------------------------------------------------
// Shared UI helpers
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

async function downloadBlob(url: string, filename: string, body: unknown, method = "POST"): Promise<void> {
  const resp = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${localStorage.getItem("access_token") ?? ""}` },
    body: JSON.stringify(body),
  });
  if (!resp.ok) throw new Error(`Export failed: HTTP ${resp.status}`);
  const blob = await resp.blob();
  const objectUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = objectUrl;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(objectUrl);
}

function ResultPanel({ result }: { result: ToolResult }) {
  const minutes = Math.floor(result.duration_seconds / 60);
  const seconds = (result.duration_seconds % 60).toFixed(1);
  const [exportingHtml, setExportingHtml] = useState(false);
  const [exportingSarif, setExportingSarif] = useState(false);

  const handleExportJson = useCallback(() => {
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${result.tool}-findings-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [result]);

  const handleExportSarif = useCallback(async () => {
    setExportingSarif(true);
    try {
      await downloadBlob(
        "/api/v1/advanced-scanners/export-sarif",
        `${result.tool}-${Date.now()}.sarif.json`,
        { findings: result.findings },
      );
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setExportingSarif(false);
    }
  }, [result]);

  const handleExportHtml = useCallback(async () => {
    setExportingHtml(true);
    try {
      await downloadBlob(
        "/api/v1/advanced-scanners/export-html",
        `${result.tool}-report-${Date.now()}.html`,
        { findings: result.findings, title: `${result.tool} Pentest Report` },
      );
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setExportingHtml(false);
    }
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
          <>
            <button
              onClick={handleExportJson}
              className="flex items-center gap-1 text-xs rounded px-2 py-1 transition-colors"
              style={{ color: "var(--brand-400)", background: "rgba(var(--brand-500-rgb),0.1)" }}
            >
              <Download className="h-3 w-3" />JSON
            </button>
            {/* Improvement 28: SARIF export */}
            <button
              onClick={handleExportSarif}
              disabled={exportingSarif}
              className="flex items-center gap-1 text-xs rounded px-2 py-1 transition-colors disabled:opacity-50"
              style={{ color: "var(--brand-400)", background: "rgba(var(--brand-500-rgb),0.1)" }}
            >
              <FileCode className="h-3 w-3" />{exportingSarif ? "…" : "SARIF"}
            </button>
            {/* Improvement 29: HTML report */}
            <button
              onClick={handleExportHtml}
              disabled={exportingHtml}
              className="flex items-center gap-1 text-xs rounded px-2 py-1 transition-colors disabled:opacity-50"
              style={{ color: "var(--brand-400)", background: "rgba(var(--brand-500-rgb),0.1)" }}
            >
              <Globe className="h-3 w-3" />{exportingHtml ? "…" : "HTML"}
            </button>
          </>
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
  commandPreview: (target: string, options: Record<string, unknown>) => string;
  buildPayload: (target: string, options: Record<string, unknown>) => Record<string, unknown>;
}

const TOOLS: ToolDef[] = [
  {
    id: "nuclei",
    name: "Nuclei",
    description: "Template-based vulnerability scanner — CVE-mapped, MITRE ATT&CK tagged findings",
    endpoint: "/advanced-scanners/nuclei",
    targetLabel: "Target URL or IP",
    targetPlaceholder: "https://target.com",
    defaultOptions: '{"severity": "medium,high,critical", "timeout": 180}',
    commandPreview: (t, o) => `nuclei -target ${t} -json -silent -severity ${o.severity ?? "medium,high,critical"}${o.templates_path ? ` -t ${o.templates_path}` : ""}`,
    buildPayload: (target, options) => ({ target, ...options }),
  },
  {
    id: "subfinder",
    name: "Subfinder",
    description: "Passive subdomain enumeration using 50+ sources (Shodan, Censys, crt.sh, etc.)",
    endpoint: "/advanced-scanners/subfinder",
    targetLabel: "Domain",
    targetPlaceholder: "target.com",
    defaultOptions: '{"timeout": 120}',
    commandPreview: (t) => `subfinder -d ${t} -silent`,
    buildPayload: (target, options) => ({ target, ...options }),
  },
  {
    id: "ffuf",
    name: "FFUF",
    description: "Fast web fuzzer — directory, parameter, and virtual host discovery",
    endpoint: "/advanced-scanners/ffuf",
    targetLabel: "Target URL",
    targetPlaceholder: "https://target.com/FUZZ",
    defaultOptions: '{"extensions": "php,html,js,txt,bak", "timeout": 120}',
    commandPreview: (t, o) => `ffuf -u ${t} -w /usr/share/wordlists/dirb/common.txt -e ${o.extensions ?? "php,html,js"}`,
    buildPayload: (target, options) => ({ target, ...options }),
  },
  {
    id: "httpx",
    name: "HTTPx",
    description: "HTTP/HTTPS service probe — web server detection, status codes, redirects, tech stack",
    endpoint: "/advanced-scanners/httpx",
    targetLabel: "Target (domain, IP, or CIDR)",
    targetPlaceholder: "target.com",
    defaultOptions: '{"timeout": 30}',
    commandPreview: (t, o) => `httpx -target ${t} -json -title -tech-detect -status-code${o.ports ? ` -ports ${o.ports}` : ""}`,
    buildPayload: (target, options) => ({ target, ...options }),
  },
  {
    id: "sslyze",
    name: "SSLyze",
    description: "TLS/SSL configuration audit — weak ciphers, protocols, certificate issues, Heartbleed",
    endpoint: "/advanced-scanners/sslyze",
    targetLabel: "Hostname or IP",
    targetPlaceholder: "target.com",
    defaultOptions: '{"port": 443, "timeout": 60}',
    commandPreview: (t, o) => `sslyze --json_out=- ${t}:${o.port ?? 443}`,
    buildPayload: (target, options) => ({ target, ...options }),
  },
  {
    id: "zap",
    name: "OWASP ZAP",
    description: "Web application scanner — passive and active rules, OWASP Top 10, AJAX spider",
    endpoint: "/advanced-scanners/zap",
    targetLabel: "Target URL",
    targetPlaceholder: "https://target.com",
    defaultOptions: '{"scan_type": "passive", "zap_url": "http://127.0.0.1:8090", "timeout": 300}',
    commandPreview: (t, o) => `zaproxy -daemon -host 127.0.0.1 -port 8090 # then: zap-baseline.py -t ${t} -${o.scan_type === "active" ? "a" : "p"}`,
    buildPayload: (target, options) => ({ target, ...options }),
  },
];

// ---------------------------------------------------------------------------
// Presets (localStorage)
// ---------------------------------------------------------------------------

const PRESETS_KEY = "advanced-scanner-presets";

function loadPresets(toolId: string): Record<string, string> {
  try {
    const raw = localStorage.getItem(PRESETS_KEY);
    if (!raw) return {};
    const all = JSON.parse(raw) as Record<string, Record<string, string>>;
    return all[toolId] ?? {};
  } catch {
    return {};
  }
}

function savePreset(toolId: string, name: string, options: string): void {
  try {
    const raw = localStorage.getItem(PRESETS_KEY);
    const all = raw ? JSON.parse(raw) as Record<string, Record<string, string>> : {};
    all[toolId] = { ...(all[toolId] ?? {}), [name]: options };
    localStorage.setItem(PRESETS_KEY, JSON.stringify(all));
  } catch {
    // ignore storage errors
  }
}

// ---------------------------------------------------------------------------
// Tool Panel (with command preview, presets, export)
// ---------------------------------------------------------------------------

function ToolPanel({ tool }: { tool: ToolDef }) {
  const [target, setTarget] = useState("");
  const [options, setOptions] = useState(tool.defaultOptions);
  const [result, setResult] = useState<ToolResult | null>(null);
  const [presets, setPresets] = useState<Record<string, string>>(() => loadPresets(tool.id));
  const [presetName, setPresetName] = useState("");
  const [showPreview, setShowPreview] = useState(false);

  const parsedOptions = (() => {
    try { return JSON.parse(options) as Record<string, unknown>; } catch { return {}; }
  })();

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

  const handleSavePreset = () => {
    if (!presetName.trim()) return;
    savePreset(tool.id, presetName.trim(), options);
    setPresets(loadPresets(tool.id));
    setPresetName("");
    toast.success(`Preset "${presetName.trim()}" saved`);
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-3">
          <Zap className="h-4 w-4 shrink-0" style={{ color: "var(--brand-500)" }} />
          <div>
            <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{tool.name}</p>
            <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>{tool.description}</p>
          </div>
        </div>
      </CardHeader>
      <CardBody className="space-y-3">
        {/* Target */}
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

        {/* Options */}
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

        {/* Presets row */}
        <div className="flex flex-wrap items-center gap-2">
          {Object.entries(presets).map(([name, opts]) => (
            <button
              key={name}
              onClick={() => setOptions(opts)}
              className="flex items-center gap-1 text-xs rounded-full px-2 py-0.5 border transition-colors"
              style={{ borderColor: "var(--border-default)", color: "var(--text-secondary)", background: "var(--bg-elevated)" }}
            >
              <BookmarkCheck className="h-2.5 w-2.5" />{name}
            </button>
          ))}
          <div className="flex items-center gap-1 ml-auto">
            <input
              value={presetName}
              onChange={(e) => setPresetName(e.target.value)}
              placeholder="preset name"
              className="rounded border px-2 py-0.5 text-xs"
              style={{ background: "var(--bg-elevated)", borderColor: "var(--border-default)", color: "var(--text-primary)", width: 90 }}
            />
            <button
              onClick={handleSavePreset}
              disabled={!presetName.trim()}
              className="flex items-center gap-1 text-xs rounded px-2 py-0.5 transition-colors disabled:opacity-40"
              style={{ color: "var(--brand-400)" }}
              title="Save current options as preset"
            >
              <BookmarkPlus className="h-3 w-3" />Save
            </button>
          </div>
        </div>

        {/* Command preview toggle */}
        {target.trim() && (
          <div>
            <button
              onClick={() => setShowPreview((p) => !p)}
              className="flex items-center gap-1 text-xs"
              style={{ color: "var(--text-tertiary)" }}
            >
              <Terminal className="h-3 w-3" />
              {showPreview ? "Hide" : "Show"} command preview
            </button>
            {showPreview && (
              <pre
                className="mt-1 rounded p-2 text-xs font-mono overflow-x-auto"
                style={{ background: "var(--bg-base)", color: "var(--success-400)" }}
              >
                {tool.commandPreview(target, parsedOptions)}
              </pre>
            )}
          </div>
        )}

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
// Tool Health Panel
// ---------------------------------------------------------------------------

function ToolHealthPanel() {
  const { data, isLoading } = useQuery({
    queryKey: ["pentest-tool-health"],
    queryFn: async () => {
      const res = await apiClient.get("/advanced-scanners/tool-health");
      return res.data as ToolHealthResponse;
    },
    staleTime: 60_000,
  });

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-xs" style={{ color: "var(--text-tertiary)" }}>
        <Loader2 className="h-3.5 w-3.5 animate-spin" />Checking tools...
      </div>
    );
  }

  if (!data) return null;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Pentest Tool Health</p>
          <div className="flex gap-2">
            <Badge variant="success" size="sm">{data.available_count} available</Badge>
            <Badge variant="danger" size="sm">{data.missing_count} missing</Badge>
          </div>
        </div>
      </CardHeader>
      <CardBody>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 sm:grid-cols-3 max-h-48 overflow-y-auto">
          {data.tools.map((t) => (
            <div key={t.name} className="flex items-center gap-1.5 py-0.5">
              {t.available
                ? <CheckCircle className="h-3 w-3 shrink-0" style={{ color: "var(--success-400)" }} />
                : <XCircle className="h-3 w-3 shrink-0" style={{ color: "var(--danger-400)" }} />}
              <span className="text-xs font-mono truncate" style={{ color: t.available ? "var(--text-primary)" : "var(--text-tertiary)" }}>
                {t.name}
              </span>
            </div>
          ))}
        </div>
      </CardBody>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Improvement 30: OOB interaction helper (Interactsh)
// ---------------------------------------------------------------------------

interface OobSession {
  oob_url: string;
  listen_duration: number;
  interactions_count: number;
  tool: string;
}

function OobHelperPanel() {
  const [duration, setDuration] = useState(60);
  const [session, setSession] = useState<OobSession | null>(null);
  const [copied, setCopied] = useState(false);

  const mutation = useMutation({
    mutationFn: async () => {
      const res = await apiClient.post("/advanced-scanners/interactsh", { duration });
      return (res.data as { metadata: OobSession }).metadata;
    },
    onSuccess: (data) => setSession(data),
    onError: (err: Error) => toast.error(err.message),
  });

  const handleCopy = useCallback(() => {
    if (!session?.oob_url) return;
    navigator.clipboard.writeText(session.oob_url).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [session]);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Globe className="h-4 w-4" style={{ color: "var(--brand-500)" }} />
          <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>OOB Interaction Helper</p>
        </div>
      </CardHeader>
      <CardBody className="space-y-3">
        <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
          Register a unique out-of-band URL for SSRF, XXE, and blind injection testing.
        </p>
        <div className="flex items-center gap-3">
          <div>
            <label className="text-xs block mb-1" style={{ color: "var(--text-secondary)" }}>Listen duration (s)</label>
            <input
              type="number"
              value={duration}
              onChange={(e) => setDuration(Number(e.target.value))}
              min={10}
              max={600}
              className="rounded-md border px-3 py-1.5 text-xs font-mono w-24"
              style={{ background: "var(--bg-elevated)", borderColor: "var(--border-default)", color: "var(--text-primary)" }}
            />
          </div>
          <div className="mt-4">
            <Button size="sm" loading={mutation.isPending} onClick={() => mutation.mutate()}>
              Start Session
            </Button>
          </div>
        </div>
        {session && (
          <div className="rounded-md p-3 space-y-2" style={{ background: "var(--bg-base)" }}>
            <div className="flex items-center gap-2">
              <code className="flex-1 text-xs font-mono break-all" style={{ color: "var(--success-400)" }}>
                {session.oob_url}
              </code>
              <button onClick={handleCopy} title="Copy OOB URL">
                {copied
                  ? <CheckCircle className="h-3.5 w-3.5" style={{ color: "var(--success-400)" }} />
                  : <Copy className="h-3.5 w-3.5" style={{ color: "var(--text-tertiary)" }} />}
              </button>
            </div>
            <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
              Interactions received: <strong>{session.interactions_count}</strong> | Duration: {session.listen_duration}s
            </p>
          </div>
        )}
      </CardBody>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function AdvancedScannersPage() {
  const [activeTab, setActiveTab] = useState("nuclei");
  const activeTool = TOOLS.find((t) => t.id === activeTab) ?? TOOLS[0];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
          Advanced Scanners
        </h1>
        <p className="text-sm mt-1" style={{ color: "var(--text-secondary)" }}>
          Nuclei, Subfinder, FFUF, HTTPx, SSLyze, ZAP — with MITRE ATT&CK enrichment, finding deduplication, command preview, and preset management.
        </p>
      </div>

      <ToolHealthPanel />

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

      <div
        className="mb-3 flex items-center gap-2 rounded-md px-3 py-2 text-xs max-w-2xl"
        style={{ background: "rgba(245,158,11,0.1)", borderLeft: "3px solid var(--warning-500)" }}
      >
        <AlertTriangle className="h-3.5 w-3.5 shrink-0" style={{ color: "var(--warning-400)" }} />
        <span style={{ color: "var(--warning-300)" }}>
          Authorized use only. Findings enriched with MITRE ATT&CK technique IDs automatically.
        </span>
      </div>

      <div className="max-w-2xl space-y-4">
        <ToolPanel tool={activeTool} />
        <OobHelperPanel />
      </div>
    </div>
  );
}
