import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { FileText, ShieldCheck, Plus, Trash2, Download, Copy, Check } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import apiClient from "@/shared/api/client";

interface ToolResult {
  tool: string;
  exit_code: number;
  duration_seconds: number;
  findings: Array<{ title: string; severity: string; description: string; cwe?: number; evidence?: Record<string, unknown> }>;
  error?: string;
  metadata?: Record<string, unknown>;
}

// ─── OSCP Report Generator ────────────────────────────────────────────────────
interface ReportFinding {
  title: string;
  severity: string;
  description: string;
  cwe: string;
  cve: string;
  cvss_v3: string;
  evidence: string;
}

const EMPTY_FINDING: ReportFinding = { title: "", severity: "high", description: "", cwe: "", cve: "", cvss_v3: "", evidence: "" };

function OscpReportPanel() {
  const [target, setTarget] = useState("");
  const [author, setAuthor] = useState("");
  const [date, setDate] = useState(new Date().toISOString().split("T")[0]);
  const [testPeriod, setTestPeriod] = useState("");
  const [classification, setClassification] = useState("CONFIDENTIAL");
  const [execSummary, setExecSummary] = useState("");
  const [findings, setFindings] = useState<ReportFinding[]>([{ ...EMPTY_FINDING }]);
  const [copied, setCopied] = useState(false);

  const addFinding = () => setFindings((f) => [...f, { ...EMPTY_FINDING }]);
  const removeFinding = (i: number) => setFindings((f) => f.filter((_, idx) => idx !== i));
  const updateFinding = (i: number, key: keyof ReportFinding, value: string) =>
    setFindings((f) => f.map((row, idx) => idx === i ? { ...row, [key]: value } : row));

  const { mutate, data, isPending } = useMutation<ToolResult>({
    mutationFn: () =>
      apiClient.post("/api/v1/reporting-tools/oscp-report", {
        target,
        options: {
          author: author || "Security Researcher",
          date,
          test_period: testPeriod || date,
          classification,
          executive_summary: execSummary || "A penetration test was conducted against the target environment.",
          findings: findings.filter((f) => f.title).map((f) => ({
            title: f.title,
            severity: f.severity,
            description: f.description,
            cwe: f.cwe ? parseInt(f.cwe, 10) : undefined,
            cve: f.cve || undefined,
            cvss_v3: f.cvss_v3 || undefined,
            evidence: f.evidence ? { notes: f.evidence } : {},
          })),
        },
      }).then((r) => r.data),
  });

  const reportMd = data?.metadata?.report_markdown as string | undefined;

  const copyToClipboard = () => {
    if (reportMd) {
      navigator.clipboard.writeText(reportMd);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const downloadMd = () => {
    if (!reportMd) return;
    const blob = new Blob([reportMd], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `pentest-report-${target || "target"}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const severityColor: Record<string, string> = {
    critical: "bg-red-900/60 text-red-300 border-red-700",
    high: "bg-orange-900/60 text-orange-300 border-orange-700",
    medium: "bg-yellow-900/60 text-yellow-300 border-yellow-700",
    low: "bg-blue-900/60 text-blue-300 border-blue-700",
  };

  return (
    <div className="space-y-6">
      {/* Header info */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <Label className="text-gray-300">Target / Client Name</Label>
          <Input value={target} onChange={(e) => setTarget(e.target.value)} placeholder="Example Corp" className="bg-gray-900 border-gray-700 text-gray-200" />
        </div>
        <div>
          <Label className="text-gray-300">Author / Tester</Label>
          <Input value={author} onChange={(e) => setAuthor(e.target.value)} placeholder="John Doe" className="bg-gray-900 border-gray-700 text-gray-200" />
        </div>
        <div>
          <Label className="text-gray-300">Report Date</Label>
          <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="bg-gray-900 border-gray-700 text-gray-200" />
        </div>
        <div>
          <Label className="text-gray-300">Test Period</Label>
          <Input value={testPeriod} onChange={(e) => setTestPeriod(e.target.value)} placeholder="2026-01-01 to 2026-01-07" className="bg-gray-900 border-gray-700 text-gray-200" />
        </div>
        <div>
          <Label className="text-gray-300">Classification</Label>
          <Select value={classification} onValueChange={setClassification}>
            <SelectTrigger className="bg-gray-900 border-gray-700 text-gray-200"><SelectValue /></SelectTrigger>
            <SelectContent className="bg-gray-900 border-gray-700">
              <SelectItem value="CONFIDENTIAL" className="text-gray-200">CONFIDENTIAL</SelectItem>
              <SelectItem value="RESTRICTED" className="text-gray-200">RESTRICTED</SelectItem>
              <SelectItem value="INTERNAL" className="text-gray-200">INTERNAL</SelectItem>
              <SelectItem value="PUBLIC" className="text-gray-200">PUBLIC</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>
      <div>
        <Label className="text-gray-300">Executive Summary</Label>
        <Textarea
          value={execSummary}
          onChange={(e) => setExecSummary(e.target.value)}
          placeholder="A penetration test was conducted against the target environment from [date]. The assessment identified X critical findings..."
          className="bg-gray-900 border-gray-700 text-gray-200 min-h-[80px]"
        />
      </div>

      {/* Findings */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-200">Findings ({findings.filter((f) => f.title).length})</h3>
          <Button variant="outline" size="sm" onClick={addFinding} className="text-xs border-gray-700 text-gray-300">
            <Plus className="h-3 w-3 mr-1" /> Add Finding
          </Button>
        </div>
        {findings.map((f, i) => (
          <div key={i} className="border border-gray-700 rounded-lg p-3 space-y-2 bg-gray-900/40">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-gray-400">Finding #{i + 1}</span>
              {findings.length > 1 && (
                <button onClick={() => removeFinding(i)} className="text-gray-600 hover:text-red-400 transition-colors">
                  <Trash2 className="h-3 w-3" />
                </button>
              )}
            </div>
            <div className="grid grid-cols-3 gap-2">
              <div className="col-span-2">
                <Input value={f.title} onChange={(e) => updateFinding(i, "title", e.target.value)} placeholder="Finding title" className="bg-gray-950 border-gray-700 text-gray-200 text-sm" />
              </div>
              <Select value={f.severity} onValueChange={(v) => updateFinding(i, "severity", v)}>
                <SelectTrigger className={`border text-xs ${severityColor[f.severity] ?? "bg-gray-700 text-gray-300 border-gray-600"}`}><SelectValue /></SelectTrigger>
                <SelectContent className="bg-gray-900 border-gray-700">
                  {["critical", "high", "medium", "low", "info"].map((s) => <SelectItem key={s} value={s} className="text-gray-200 text-xs">{s.toUpperCase()}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <Textarea value={f.description} onChange={(e) => updateFinding(i, "description", e.target.value)} placeholder="Description of the vulnerability..." className="bg-gray-950 border-gray-700 text-gray-200 text-xs min-h-[60px]" />
            <div className="grid grid-cols-3 gap-2">
              <Input value={f.cwe} onChange={(e) => updateFinding(i, "cwe", e.target.value)} placeholder="CWE (e.g. 79)" className="bg-gray-950 border-gray-700 text-gray-200 text-xs" />
              <Input value={f.cve} onChange={(e) => updateFinding(i, "cve", e.target.value)} placeholder="CVE (e.g. CVE-2021-44228)" className="bg-gray-950 border-gray-700 text-gray-200 text-xs" />
              <Input value={f.cvss_v3} onChange={(e) => updateFinding(i, "cvss_v3", e.target.value)} placeholder="CVSS v3 (e.g. 9.8)" className="bg-gray-950 border-gray-700 text-gray-200 text-xs" />
            </div>
          </div>
        ))}
      </div>

      <Button onClick={() => mutate()} disabled={isPending || !target} className="bg-emerald-700 hover:bg-emerald-800">
        {isPending ? "Generating Report..." : "Generate OSCP-Style Report"}
      </Button>

      {/* Report output */}
      {reportMd && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-300 font-semibold">Generated Report (Markdown)</p>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={copyToClipboard} className="text-xs border-gray-700 text-gray-300">
                {copied ? <Check className="h-3 w-3 mr-1 text-green-400" /> : <Copy className="h-3 w-3 mr-1" />}
                {copied ? "Copied!" : "Copy"}
              </Button>
              <Button variant="outline" size="sm" onClick={downloadMd} className="text-xs border-gray-700 text-gray-300">
                <Download className="h-3 w-3 mr-1" /> Download .md
              </Button>
            </div>
          </div>
          <pre className="bg-gray-950 border border-gray-700 rounded-lg p-4 text-xs text-gray-300 overflow-x-auto max-h-96 overflow-y-auto whitespace-pre-wrap">
            {reportMd}
          </pre>
        </div>
      )}
    </div>
  );
}

// ─── Password Policy Auditor ──────────────────────────────────────────────────
function PasswordPolicyPanel() {
  const [target, setTarget] = useState("");
  const [mode, setMode] = useState("manual");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [domain, setDomain] = useState("");
  // Manual policy fields
  const [minLength, setMinLength] = useState("8");
  const [lockoutThreshold, setLockoutThreshold] = useState("0");
  const [maxAgeDays, setMaxAgeDays] = useState("0");
  const [complexityEnabled, setComplexityEnabled] = useState("true");
  const [historyCount, setHistoryCount] = useState("3");
  const [lockoutDuration, setLockoutDuration] = useState("30");

  const { mutate, data, isPending } = useMutation<ToolResult>({
    mutationFn: () =>
      apiClient.post("/api/v1/reporting-tools/password-policy", {
        target: target || domain || "localhost",
        options: {
          mode: mode === "manual" ? "analyze" : mode,
          domain: domain || undefined,
          username: username || undefined,
          password: password || undefined,
          policy: mode === "manual" ? {
            min_length: minLength,
            lockout_threshold: lockoutThreshold,
            max_age_days: maxAgeDays,
            complexity_enabled: complexityEnabled,
            history_count: historyCount,
            lockout_duration_mins: lockoutDuration,
          } : {},
        },
      }).then((r) => r.data),
  });

  const severityColor: Record<string, string> = {
    critical: "bg-red-900/60 text-red-300 border-red-700",
    high: "bg-orange-900/60 text-orange-300 border-orange-700",
    medium: "bg-yellow-900/60 text-yellow-300 border-yellow-700",
    low: "bg-blue-900/60 text-blue-300 border-blue-700",
    info: "bg-gray-700 text-gray-300 border-gray-600",
  };

  return (
    <div className="space-y-4">
      <div className="flex gap-4">
        {["manual", "generate"].map((m) => (
          <label key={m} className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
            <input type="radio" name="policy-mode" value={m} checked={mode === m} onChange={() => setMode(m)} className="accent-emerald-500" />
            {m === "manual" ? "Analyze manual policy values" : "Generate audit commands"}
          </label>
        ))}
      </div>

      {mode === "generate" && (
        <div className="grid grid-cols-2 gap-3">
          <div>
            <Label className="text-gray-300">Target DC IP</Label>
            <Input value={target} onChange={(e) => setTarget(e.target.value)} placeholder="192.168.1.10" className="bg-gray-900 border-gray-700 text-gray-200" />
          </div>
          <div>
            <Label className="text-gray-300">Domain</Label>
            <Input value={domain} onChange={(e) => setDomain(e.target.value)} placeholder="corp.example.com" className="bg-gray-900 border-gray-700 text-gray-200" />
          </div>
          <div>
            <Label className="text-gray-300">Username</Label>
            <Input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="user" className="bg-gray-900 border-gray-700 text-gray-200" />
          </div>
          <div>
            <Label className="text-gray-300">Password</Label>
            <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="password" className="bg-gray-900 border-gray-700 text-gray-200" />
          </div>
        </div>
      )}

      {mode === "manual" && (
        <div className="grid grid-cols-2 gap-3">
          <div>
            <Label className="text-gray-300">Min Password Length</Label>
            <Input value={minLength} onChange={(e) => setMinLength(e.target.value)} placeholder="8" className="bg-gray-900 border-gray-700 text-gray-200" />
          </div>
          <div>
            <Label className="text-gray-300">Lockout Threshold (0=disabled)</Label>
            <Input value={lockoutThreshold} onChange={(e) => setLockoutThreshold(e.target.value)} placeholder="0" className="bg-gray-900 border-gray-700 text-gray-200" />
          </div>
          <div>
            <Label className="text-gray-300">Max Password Age (days, 0=never)</Label>
            <Input value={maxAgeDays} onChange={(e) => setMaxAgeDays(e.target.value)} placeholder="0" className="bg-gray-900 border-gray-700 text-gray-200" />
          </div>
          <div>
            <Label className="text-gray-300">Complexity Enabled</Label>
            <Select value={complexityEnabled} onValueChange={setComplexityEnabled}>
              <SelectTrigger className="bg-gray-900 border-gray-700 text-gray-200"><SelectValue /></SelectTrigger>
              <SelectContent className="bg-gray-900 border-gray-700">
                <SelectItem value="true" className="text-gray-200">Enabled</SelectItem>
                <SelectItem value="false" className="text-gray-200">Disabled</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-gray-300">Password History Count</Label>
            <Input value={historyCount} onChange={(e) => setHistoryCount(e.target.value)} placeholder="3" className="bg-gray-900 border-gray-700 text-gray-200" />
          </div>
          <div>
            <Label className="text-gray-300">Lockout Duration (minutes)</Label>
            <Input value={lockoutDuration} onChange={(e) => setLockoutDuration(e.target.value)} placeholder="30" className="bg-gray-900 border-gray-700 text-gray-200" />
          </div>
        </div>
      )}

      <Button onClick={() => mutate()} disabled={isPending} className="bg-emerald-700 hover:bg-emerald-800">
        {isPending ? "Auditing..." : mode === "manual" ? "Analyze Policy" : "Get Audit Commands"}
      </Button>

      {data && (
        <div className="mt-4 space-y-3">
          <div className="flex gap-4 text-xs text-gray-500">
            <span>Duration: {data.duration_seconds}s</span>
            <span>Issues: {data.findings.length}</span>
          </div>
          {data.metadata?.commands && (
            <div className="p-3 bg-yellow-900/20 border border-yellow-700 rounded space-y-2">
              <p className="text-xs text-yellow-400 font-semibold">Audit Commands:</p>
              {(data.metadata.commands as string[]).filter(Boolean).map((cmd, i) => (
                <pre key={i} className="text-xs text-green-300 bg-gray-950 rounded p-2 overflow-x-auto">{cmd}</pre>
              ))}
            </div>
          )}
          {data.findings.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs text-gray-500">Policy Issues:</p>
              {data.findings.map((f, i) => (
                <div key={i} className="border border-gray-700 rounded-md p-3 bg-gray-900/40 space-y-1">
                  <div className="flex items-center gap-2">
                    <Badge className={`text-xs border ${severityColor[f.severity] ?? severityColor.info}`}>{f.severity}</Badge>
                    <span className="text-sm text-gray-200">{f.title}</span>
                  </div>
                  <p className="text-xs text-gray-400">{f.description}</p>
                  {f.evidence && (
                    <div className="flex gap-3 text-xs text-gray-500">
                      {Object.entries(f.evidence).map(([k, v]) => (
                        <span key={k}><span className="text-gray-400">{k}:</span> {String(v)}</span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────
export function ReportingToolsPage() {
  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-100">Reporting & Automation Tools</h1>
        <p className="text-gray-400 text-sm mt-1">
          Generate OSCP-style penetration test reports in Markdown and audit Active Directory password policies for compliance gaps.
        </p>
      </div>
      <Tabs defaultValue="oscp-report">
        <TabsList className="bg-gray-900 border border-gray-700">
          <TabsTrigger value="oscp-report" className="data-[state=active]:bg-gray-700">
            <FileText className="h-4 w-4 mr-1" /> OSCP Report Generator
          </TabsTrigger>
          <TabsTrigger value="password-policy" className="data-[state=active]:bg-gray-700">
            <ShieldCheck className="h-4 w-4 mr-1" /> Password Policy Auditor
          </TabsTrigger>
        </TabsList>

        <TabsContent value="oscp-report">
          <Card className="bg-gray-900/60 border-gray-700">
            <CardHeader>
              <CardTitle className="text-gray-100">OSCP-Style Pentest Report</CardTitle>
              <CardDescription className="text-gray-400">
                Build a structured penetration test report with executive summary, findings table, and remediation recommendations. Export as Markdown.
              </CardDescription>
            </CardHeader>
            <CardContent><OscpReportPanel /></CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="password-policy">
          <Card className="bg-gray-900/60 border-gray-700">
            <CardHeader>
              <CardTitle className="text-gray-100">Password Policy Auditor</CardTitle>
              <CardDescription className="text-gray-400">
                Analyze AD/LDAP password policies for CIS/NIST compliance — checks minimum length, lockout, complexity, history, and expiry settings.
              </CardDescription>
            </CardHeader>
            <CardContent><PasswordPolicyPanel /></CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
