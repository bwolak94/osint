import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  Loader2,
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Network,
  Search,
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
// Shared components
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
        {Object.entries(result.metadata).map(([k, v]) => (
          <Badge key={k} variant="neutral" size="sm">{k}: {String(v)}</Badge>
        ))}
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
    id: "crackmapexec",
    name: "CrackMapExec",
    description: "SMB/LDAP network pentesting — shares, users, pass-the-hash, exec. Supports NetExec (nxc).",
    endpoint: "/ad-infra-tools/crackmapexec",
    targetLabel: "Target IP / CIDR",
    targetPlaceholder: "192.168.1.0/24",
    defaultOptions: '{"protocol": "smb", "action": "enum"}',
    buildPayload: (target, options) => ({ target, ...options }),
  },
  {
    id: "impacket",
    name: "Impacket",
    description: "secretsdump, GetUserSPNs, GetNPUsers, lookupsid, samrdump, rpcdump",
    endpoint: "/ad-infra-tools/impacket",
    targetLabel: "Target (DC IP or hostname)",
    targetPlaceholder: "192.168.1.10",
    defaultOptions: '{"tool": "secretsdump", "username": "admin", "password": "pass", "domain": "CORP"}',
    buildPayload: (target, options) => ({ target, ...options }),
  },
  {
    id: "bloodhound",
    name: "BloodHound",
    description: "Collect AD attack paths — users, groups, GPOs, trusts, ACLs, sessions",
    endpoint: "/ad-infra-tools/bloodhound",
    targetLabel: "Domain Name",
    targetPlaceholder: "corp.local",
    defaultOptions: '{"dc_ip": "192.168.1.10", "username": "user", "password": "pass", "collection": "All"}',
    buildPayload: (target, options) => ({ domain: target, ...options }),
  },
  {
    id: "enum4linux",
    name: "Enum4linux",
    description: "Windows/Samba enumeration — users, shares, password policy, OS via RPC",
    endpoint: "/ad-infra-tools/enum4linux",
    targetLabel: "Target IP / Hostname",
    targetPlaceholder: "192.168.1.5",
    defaultOptions: '{}',
    buildPayload: (target, options) => ({ target, ...options }),
  },
  {
    id: "certipy",
    name: "Certipy",
    description: "AD Certificate Services abuse — ESC1-ESC8 template misconfigurations",
    endpoint: "/ad-infra-tools/certipy",
    targetLabel: "Domain / DC IP",
    targetPlaceholder: "192.168.1.10",
    defaultOptions: '{"action": "find", "domain": "corp.local", "username": "user", "password": "pass"}',
    buildPayload: (target, options) => ({ target, ...options }),
  },
  {
    id: "bettercap",
    name: "Bettercap",
    description: "MitM framework — ARP/DNS spoofing, credential capture, host discovery",
    endpoint: "/ad-infra-tools/bettercap",
    targetLabel: "Target IP / Subnet",
    targetPlaceholder: "192.168.1.0/24",
    defaultOptions: '{"interface": "eth0", "mode": "probe", "duration": 30}',
    buildPayload: (target, options) => ({ target, ...options }),
  },
  {
    id: "aircrack",
    name: "Aircrack-ng",
    description: "WiFi security — crack WPA/WPA2 handshakes, scan for APs, check capture files",
    endpoint: "/ad-infra-tools/aircrack",
    targetLabel: "Capture file path or interface",
    targetPlaceholder: "/tmp/capture.cap",
    defaultOptions: '{"action": "crack", "wordlist": "/usr/share/wordlists/rockyou.txt"}',
    buildPayload: (target, options) => ({ target, ...options }),
  },
  {
    id: "metasploit",
    name: "Metasploit",
    description: "MSF RPC — list sessions, search modules, run exploits, kill sessions",
    endpoint: "/ad-infra-tools/metasploit",
    targetLabel: "Target IP (RHOSTS)",
    targetPlaceholder: "192.168.1.100",
    defaultOptions: '{"rpc_url": "http://127.0.0.1:55553", "rpc_user": "msf", "rpc_password": "pass", "action": "sessions"}',
    buildPayload: (target, options) => ({ target, ...options }),
  },
  {
    id: "openvas",
    name: "OpenVAS",
    description: "Full vulnerability scan via GVM API — CVE-mapped findings with CVSS scores",
    endpoint: "/ad-infra-tools/openvas",
    targetLabel: "Target IP / Hostname",
    targetPlaceholder: "192.168.1.50",
    defaultOptions: '{"gvm_host": "localhost", "username": "admin", "password": "pass", "action": "scan"}',
    buildPayload: (target, options) => ({ target, ...options }),
  },
  {
    id: "burp",
    name: "Burp Suite",
    description: "Burp REST API — retrieve issues, start scans, check scan status",
    endpoint: "/ad-infra-tools/burp",
    targetLabel: "Target URL (for new scan)",
    targetPlaceholder: "https://target.com",
    defaultOptions: '{"burp_url": "http://127.0.0.1:1337", "action": "get_issues"}',
    buildPayload: (target, options) => ({ target, ...options }),
  },
];

// ---------------------------------------------------------------------------
// Tool panel
// ---------------------------------------------------------------------------

function ToolPanel({ tool }: { tool: ToolDef }) {
  const [target, setTarget] = useState("");
  const [options, setOptions] = useState(tool.defaultOptions);
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
      if (data.error) toast.error(`${tool.name}: ${data.error}`);
      else toast.success(`${tool.name} — ${data.findings_count} finding${data.findings_count !== 1 ? "s" : ""}`);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-3">
          <Shield className="h-4 w-4 shrink-0" style={{ color: "var(--brand-500)" }} />
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

export function AdInfraToolsPage() {
  const [activeTab, setActiveTab] = useState("crackmapexec");
  const activeTool = TOOLS.find((t) => t.id === activeTab) ?? TOOLS[0];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
          AD &amp; Infrastructure Tools
        </h1>
        <p className="text-sm mt-1" style={{ color: "var(--text-secondary)" }}>
          Active Directory, post-exploitation and network infrastructure tools — CME, Impacket, BloodHound, Certipy, Aircrack, OpenVAS, Burp.
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
          style={{ background: "rgba(245,158,11,0.1)", borderLeft: "3px solid var(--warning-500)" }}
        >
          <AlertTriangle className="h-3.5 w-3.5 shrink-0" style={{ color: "var(--warning-400)" }} />
          <span style={{ color: "var(--warning-300)" }}>
            Authorized use only. Some tools require root, CAP_NET_RAW, or domain credentials.
          </span>
        </div>
        <ToolPanel tool={activeTool} />
      </div>
    </div>
  );
}
