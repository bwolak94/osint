import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Network, Key, ShieldAlert, Lock, Award, ChevronDown, ChevronRight, Download, AlertTriangle } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import apiClient from "@/shared/api/client";

// ─── Shared types ─────────────────────────────────────────────────────────────
interface Finding {
  title: string;
  severity: string;
  description: string;
  cwe?: number;
  cve?: string;
  evidence?: Record<string, unknown>;
  mitre_techniques?: { id: string; name: string }[];
}

interface ToolResult {
  tool: string;
  exit_code: number;
  duration_seconds: number;
  findings: Finding[];
  error?: string;
  metadata?: Record<string, unknown>;
}

// ─── Shared UI ────────────────────────────────────────────────────────────────
const severityColor: Record<string, string> = {
  critical: "bg-red-900/60 text-red-300 border-red-700",
  high: "bg-orange-900/60 text-orange-300 border-orange-700",
  medium: "bg-yellow-900/60 text-yellow-300 border-yellow-700",
  low: "bg-blue-900/60 text-blue-300 border-blue-700",
  info: "bg-gray-700 text-gray-300 border-gray-600",
};

function FindingRow({ f }: { f: Finding }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border border-gray-700 rounded-md mb-2 bg-gray-900/40">
      <button
        className="w-full flex items-center gap-3 p-3 text-left hover:bg-gray-800/50 transition-colors"
        onClick={() => setOpen((o) => !o)}
      >
        {open ? <ChevronDown className="h-4 w-4 text-gray-400 shrink-0" /> : <ChevronRight className="h-4 w-4 text-gray-400 shrink-0" />}
        <Badge className={`text-xs border ${severityColor[f.severity] ?? severityColor.info}`}>{f.severity}</Badge>
        <span className="text-sm text-gray-200 flex-1">{f.title}</span>
        {f.cwe && <span className="text-xs text-gray-500">CWE-{f.cwe}</span>}
      </button>
      {open && (
        <div className="px-4 pb-3 space-y-2 text-sm text-gray-400">
          <p>{f.description}</p>
          {f.mitre_techniques && f.mitre_techniques.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-1">
              {f.mitre_techniques.map((t) => (
                <Badge key={t.id} variant="outline" className="text-xs text-purple-400 border-purple-700">
                  {t.id} — {t.name}
                </Badge>
              ))}
            </div>
          )}
          {f.evidence && (
            <pre className="bg-gray-950 rounded p-2 text-xs overflow-x-auto text-green-400">
              {JSON.stringify(f.evidence, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

function ResultPanel({ result }: { result: ToolResult }) {
  const exportJson = () => {
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${result.tool}-result.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const commands = result.metadata?.commands as string[] | undefined;
  const setupSteps = result.metadata?.setup_steps as string[] | undefined;

  return (
    <div className="mt-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex gap-4 text-xs text-gray-500">
          <span>Duration: {result.duration_seconds}s</span>
          <span>Findings: {result.findings.length}</span>
          <span>Exit: {result.exit_code}</span>
        </div>
        <Button variant="outline" size="sm" onClick={exportJson} className="text-xs">
          <Download className="h-3 w-3 mr-1" /> Export
        </Button>
      </div>
      {result.error && (
        <div className="p-3 bg-red-900/30 border border-red-700 rounded text-sm text-red-300">{result.error}</div>
      )}
      {commands && commands.length > 0 && (
        <div className="p-3 bg-yellow-900/20 border border-yellow-700 rounded space-y-2">
          <p className="text-xs text-yellow-400 font-semibold">Generated Commands:</p>
          {commands.map((cmd, i) => (
            <pre key={i} className="text-xs text-green-300 bg-gray-950 rounded p-2 overflow-x-auto">{cmd}</pre>
          ))}
          {setupSteps && (
            <>
              <p className="text-xs text-yellow-400 font-semibold mt-2">Setup Steps:</p>
              {setupSteps.map((s, i) => <p key={i} className="text-xs text-gray-400">{s}</p>)}
            </>
          )}
        </div>
      )}
      {result.findings.length > 0 && (
        <div>
          <p className="text-xs text-gray-500 mb-2">Findings:</p>
          {result.findings.map((f, i) => <FindingRow key={i} f={f} />)}
        </div>
      )}
      {result.findings.length === 0 && !result.error && !commands?.length && (
        <p className="text-sm text-gray-500 italic">No findings detected.</p>
      )}
    </div>
  );
}

// ─── LDAP Recon ───────────────────────────────────────────────────────────────
function LdapReconPanel() {
  const [target, setTarget] = useState("");
  const [domain, setDomain] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const { mutate, data, isPending } = useMutation<ToolResult>({
    mutationFn: () =>
      apiClient.post("/api/v1/ad-attack/ldap-recon", {
        target,
        options: {
          domain: domain || undefined,
          username: username || undefined,
          password: password || undefined,
        },
      }).then((r) => r.data),
  });

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <Label className="text-gray-300">DC IP / Hostname</Label>
          <Input value={target} onChange={(e) => setTarget(e.target.value)} placeholder="192.168.1.10" className="bg-gray-900 border-gray-700 text-gray-200" />
        </div>
        <div>
          <Label className="text-gray-300">Domain (FQDN)</Label>
          <Input value={domain} onChange={(e) => setDomain(e.target.value)} placeholder="corp.example.com" className="bg-gray-900 border-gray-700 text-gray-200" />
        </div>
        <div>
          <Label className="text-gray-300">Username</Label>
          <Input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="CORP\\user" className="bg-gray-900 border-gray-700 text-gray-200" />
        </div>
        <div>
          <Label className="text-gray-300">Password</Label>
          <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="P@ssw0rd" className="bg-gray-900 border-gray-700 text-gray-200" />
        </div>
      </div>
      <Button onClick={() => mutate()} disabled={isPending || !target} className="bg-red-700 hover:bg-red-800">
        {isPending ? "Dumping LDAP..." : "Run LDAP Domain Dump"}
      </Button>
      {data && <ResultPanel result={data} />}
    </div>
  );
}

// ─── Ligolo-ng ────────────────────────────────────────────────────────────────
function LigoloPanel() {
  const [proxyHost, setProxyHost] = useState("");
  const [proxyPort, setProxyPort] = useState("11601");
  const [tunnelType, setTunnelType] = useState("tcp");
  const [agentPlatform, setAgentPlatform] = useState("linux");

  const { mutate, data, isPending } = useMutation<ToolResult>({
    mutationFn: () =>
      apiClient.post("/api/v1/ad-attack/ligolo", {
        target: proxyHost || "attacker-ip",
        options: {
          proxy_port: parseInt(proxyPort, 10),
          tunnel_type: tunnelType,
          agent_platform: agentPlatform,
        },
      }).then((r) => r.data),
  });

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <Label className="text-gray-300">Attacker IP / Proxy Host</Label>
          <Input value={proxyHost} onChange={(e) => setProxyHost(e.target.value)} placeholder="10.10.14.1" className="bg-gray-900 border-gray-700 text-gray-200" />
        </div>
        <div>
          <Label className="text-gray-300">Proxy Port</Label>
          <Input value={proxyPort} onChange={(e) => setProxyPort(e.target.value)} placeholder="11601" className="bg-gray-900 border-gray-700 text-gray-200" />
        </div>
        <div>
          <Label className="text-gray-300">Tunnel Type</Label>
          <Select value={tunnelType} onValueChange={setTunnelType}>
            <SelectTrigger className="bg-gray-900 border-gray-700 text-gray-200"><SelectValue /></SelectTrigger>
            <SelectContent className="bg-gray-900 border-gray-700">
              <SelectItem value="tcp" className="text-gray-200">TCP</SelectItem>
              <SelectItem value="tls" className="text-gray-200">TLS</SelectItem>
              <SelectItem value="tls-mutual" className="text-gray-200">Mutual TLS</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label className="text-gray-300">Agent Platform</Label>
          <Select value={agentPlatform} onValueChange={setAgentPlatform}>
            <SelectTrigger className="bg-gray-900 border-gray-700 text-gray-200"><SelectValue /></SelectTrigger>
            <SelectContent className="bg-gray-900 border-gray-700">
              <SelectItem value="linux" className="text-gray-200">Linux</SelectItem>
              <SelectItem value="windows" className="text-gray-200">Windows</SelectItem>
              <SelectItem value="darwin" className="text-gray-200">macOS</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>
      <Button onClick={() => mutate()} disabled={isPending} className="bg-red-700 hover:bg-red-800">
        {isPending ? "Generating..." : "Generate Ligolo-ng Commands"}
      </Button>
      {data && <ResultPanel result={data} />}
    </div>
  );
}

// ─── ACL Abuse ────────────────────────────────────────────────────────────────
function AclAbusePanel() {
  const [target, setTarget] = useState("");
  const [domain, setDomain] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [action, setAction] = useState("enumerate");
  const [targetObject, setTargetObject] = useState("");
  const [right, setRight] = useState("GenericAll");

  const { mutate, data, isPending } = useMutation<ToolResult>({
    mutationFn: () =>
      apiClient.post("/api/v1/ad-attack/acl-abuse", {
        target,
        options: {
          domain: domain || undefined,
          username: username || undefined,
          password: password || undefined,
          action,
          target_object: targetObject || undefined,
          right,
        },
      }).then((r) => r.data),
  });

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <Label className="text-gray-300">DC IP</Label>
          <Input value={target} onChange={(e) => setTarget(e.target.value)} placeholder="192.168.1.10" className="bg-gray-900 border-gray-700 text-gray-200" />
        </div>
        <div>
          <Label className="text-gray-300">Domain</Label>
          <Input value={domain} onChange={(e) => setDomain(e.target.value)} placeholder="corp.example.com" className="bg-gray-900 border-gray-700 text-gray-200" />
        </div>
        <div>
          <Label className="text-gray-300">Username</Label>
          <Input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="attacker-user" className="bg-gray-900 border-gray-700 text-gray-200" />
        </div>
        <div>
          <Label className="text-gray-300">Password</Label>
          <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="password" className="bg-gray-900 border-gray-700 text-gray-200" />
        </div>
        <div>
          <Label className="text-gray-300">Action</Label>
          <Select value={action} onValueChange={setAction}>
            <SelectTrigger className="bg-gray-900 border-gray-700 text-gray-200"><SelectValue /></SelectTrigger>
            <SelectContent className="bg-gray-900 border-gray-700">
              <SelectItem value="enumerate" className="text-gray-200">Enumerate ACLs</SelectItem>
              <SelectItem value="exploit" className="text-gray-200">Exploit ACL</SelectItem>
              <SelectItem value="shadow_cred" className="text-gray-200">Shadow Credentials</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label className="text-gray-300">Dangerous Right</Label>
          <Select value={right} onValueChange={setRight}>
            <SelectTrigger className="bg-gray-900 border-gray-700 text-gray-200"><SelectValue /></SelectTrigger>
            <SelectContent className="bg-gray-900 border-gray-700">
              {["GenericAll", "GenericWrite", "WriteDacl", "WriteOwner", "AllExtendedRights", "ForceChangePassword", "AddMember"].map((r) => (
                <SelectItem key={r} value={r} className="text-gray-200">{r}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
      {action !== "enumerate" && (
        <div>
          <Label className="text-gray-300">Target Object (sAMAccountName)</Label>
          <Input value={targetObject} onChange={(e) => setTargetObject(e.target.value)} placeholder="target-user or DA-group" className="bg-gray-900 border-gray-700 text-gray-200" />
        </div>
      )}
      <Button onClick={() => mutate()} disabled={isPending || !target} className="bg-red-700 hover:bg-red-800">
        {isPending ? "Running..." : action === "enumerate" ? "Enumerate ACLs" : "Exploit ACL Misconfiguration"}
      </Button>
      {data && <ResultPanel result={data} />}
    </div>
  );
}

// ─── Pass-the-Hash / Ticket ───────────────────────────────────────────────────
function PthPanel() {
  const [target, setTarget] = useState("");
  const [username, setUsername] = useState("");
  const [hash, setHash] = useState("");
  const [domain, setDomain] = useState("");
  const [method, setMethod] = useState("wmiexec");
  const [attackType, setAttackType] = useState("pth");
  const [command, setCommand] = useState("whoami");

  const { mutate, data, isPending } = useMutation<ToolResult>({
    mutationFn: () =>
      apiClient.post("/api/v1/ad-attack/pth", {
        target,
        options: {
          username: username || undefined,
          hash: hash || undefined,
          domain: domain || undefined,
          method,
          attack_type: attackType,
          command: command || undefined,
        },
      }).then((r) => r.data),
  });

  return (
    <div className="space-y-4">
      <div className="flex gap-4">
        <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
          <input type="radio" name="attack-type" value="pth" checked={attackType === "pth"} onChange={() => setAttackType("pth")} className="accent-red-500" />
          Pass-the-Hash (NT Hash)
        </label>
        <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
          <input type="radio" name="attack-type" value="ptt" checked={attackType === "ptt"} onChange={() => setAttackType("ptt")} className="accent-red-500" />
          Pass-the-Ticket (KRB5CCNAME)
        </label>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <Label className="text-gray-300">Target IP</Label>
          <Input value={target} onChange={(e) => setTarget(e.target.value)} placeholder="192.168.1.20" className="bg-gray-900 border-gray-700 text-gray-200" />
        </div>
        <div>
          <Label className="text-gray-300">Domain</Label>
          <Input value={domain} onChange={(e) => setDomain(e.target.value)} placeholder="CORP" className="bg-gray-900 border-gray-700 text-gray-200" />
        </div>
        <div>
          <Label className="text-gray-300">Username</Label>
          <Input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="Administrator" className="bg-gray-900 border-gray-700 text-gray-200" />
        </div>
        <div>
          <Label className="text-gray-300">{attackType === "pth" ? "NT Hash" : "Ticket Path (KRB5CCNAME)"}</Label>
          <Input
            value={hash}
            onChange={(e) => setHash(e.target.value)}
            placeholder={attackType === "pth" ? "aad3b435b51404eeaad3b435b51404ee:ntlm-hash" : "/tmp/ticket.ccache"}
            className="bg-gray-900 border-gray-700 text-gray-200"
          />
        </div>
        <div>
          <Label className="text-gray-300">Execution Method</Label>
          <Select value={method} onValueChange={setMethod}>
            <SelectTrigger className="bg-gray-900 border-gray-700 text-gray-200"><SelectValue /></SelectTrigger>
            <SelectContent className="bg-gray-900 border-gray-700">
              <SelectItem value="wmiexec" className="text-gray-200">wmiexec (impacket)</SelectItem>
              <SelectItem value="psexec" className="text-gray-200">psexec (impacket)</SelectItem>
              <SelectItem value="smbexec" className="text-gray-200">smbexec (impacket)</SelectItem>
              <SelectItem value="atexec" className="text-gray-200">atexec (impacket)</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label className="text-gray-300">Command to Execute</Label>
          <Input value={command} onChange={(e) => setCommand(e.target.value)} placeholder="whoami /all" className="bg-gray-900 border-gray-700 text-gray-200" />
        </div>
      </div>
      <Button onClick={() => mutate()} disabled={isPending || !target} className="bg-red-700 hover:bg-red-800">
        {isPending ? "Generating..." : `Generate ${attackType === "pth" ? "PtH" : "PtT"} Commands`}
      </Button>
      {data && <ResultPanel result={data} />}
    </div>
  );
}

// ─── ADCS Exploitation ────────────────────────────────────────────────────────
function AdcsPanel() {
  const [target, setTarget] = useState("");
  const [domain, setDomain] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [action, setAction] = useState("find");
  const [escTemplate, setEscTemplate] = useState("ESC1");
  const [targetUser, setTargetUser] = useState("");

  const { mutate, data, isPending } = useMutation<ToolResult>({
    mutationFn: () =>
      apiClient.post("/api/v1/ad-attack/adcs", {
        target,
        options: {
          domain: domain || undefined,
          username: username || undefined,
          password: password || undefined,
          action,
          esc_template: escTemplate,
          target_user: targetUser || undefined,
        },
      }).then((r) => r.data),
  });

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <Label className="text-gray-300">CA / DC IP</Label>
          <Input value={target} onChange={(e) => setTarget(e.target.value)} placeholder="192.168.1.10" className="bg-gray-900 border-gray-700 text-gray-200" />
        </div>
        <div>
          <Label className="text-gray-300">Domain</Label>
          <Input value={domain} onChange={(e) => setDomain(e.target.value)} placeholder="corp.example.com" className="bg-gray-900 border-gray-700 text-gray-200" />
        </div>
        <div>
          <Label className="text-gray-300">Username</Label>
          <Input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="CORP\\user" className="bg-gray-900 border-gray-700 text-gray-200" />
        </div>
        <div>
          <Label className="text-gray-300">Password</Label>
          <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="password" className="bg-gray-900 border-gray-700 text-gray-200" />
        </div>
        <div>
          <Label className="text-gray-300">Action</Label>
          <Select value={action} onValueChange={setAction}>
            <SelectTrigger className="bg-gray-900 border-gray-700 text-gray-200"><SelectValue /></SelectTrigger>
            <SelectContent className="bg-gray-900 border-gray-700">
              <SelectItem value="find" className="text-gray-200">Find Vulnerable Templates</SelectItem>
              <SelectItem value="request" className="text-gray-200">Request Certificate (ESC1)</SelectItem>
              <SelectItem value="auth" className="text-gray-200">Authenticate with Certificate</SelectItem>
              <SelectItem value="shadow" className="text-gray-200">Shadow Credentials (ESC8)</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label className="text-gray-300">ESC Template</Label>
          <Select value={escTemplate} onValueChange={setEscTemplate}>
            <SelectTrigger className="bg-gray-900 border-gray-700 text-gray-200"><SelectValue /></SelectTrigger>
            <SelectContent className="bg-gray-900 border-gray-700">
              {["ESC1", "ESC2", "ESC3", "ESC4", "ESC5", "ESC6", "ESC7", "ESC8"].map((e) => (
                <SelectItem key={e} value={e} className="text-gray-200">{e}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
      {action !== "find" && (
        <div>
          <Label className="text-gray-300">Target User (for impersonation)</Label>
          <Input value={targetUser} onChange={(e) => setTargetUser(e.target.value)} placeholder="Administrator" className="bg-gray-900 border-gray-700 text-gray-200" />
        </div>
      )}
      <Button onClick={() => mutate()} disabled={isPending || !target} className="bg-red-700 hover:bg-red-800">
        {isPending ? "Running..." : action === "find" ? "Find ADCS Vulnerabilities" : "Generate certipy Commands"}
      </Button>
      {data && <ResultPanel result={data} />}
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────
export function AdAttackPage() {
  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-100">Active Directory Attack Tools</h1>
        <p className="text-gray-400 text-sm mt-1">
          LDAP recon, tunneling with Ligolo-ng, ACL abuse, Pass-the-Hash/Ticket, and ADCS certificate exploitation.
        </p>
      </div>

      <div className="p-3 rounded-lg border flex items-center gap-3" style={{ background: "rgba(239,68,68,0.1)", borderColor: "rgba(239,68,68,0.45)" }}>
        <AlertTriangle className="h-5 w-5 text-red-400 shrink-0" />
        <p className="text-xs text-red-300">
          <strong>Authorized internal network use only.</strong> These tools target Active Directory infrastructure.
          Only operate against environments you own or have written authorization to test.
        </p>
      </div>

      <Tabs defaultValue="ldap">
        <TabsList className="bg-gray-900 border border-gray-700 flex flex-wrap h-auto gap-1 p-1">
          <TabsTrigger value="ldap" className="data-[state=active]:bg-gray-700">
            <Network className="h-4 w-4 mr-1" /> LDAP Recon
          </TabsTrigger>
          <TabsTrigger value="ligolo" className="data-[state=active]:bg-gray-700">
            <Lock className="h-4 w-4 mr-1" /> Ligolo-ng
          </TabsTrigger>
          <TabsTrigger value="acl" className="data-[state=active]:bg-gray-700">
            <ShieldAlert className="h-4 w-4 mr-1" /> ACL Abuse
          </TabsTrigger>
          <TabsTrigger value="pth" className="data-[state=active]:bg-gray-700">
            <Key className="h-4 w-4 mr-1" /> PtH / PtT
          </TabsTrigger>
          <TabsTrigger value="adcs" className="data-[state=active]:bg-gray-700">
            <Award className="h-4 w-4 mr-1" /> ADCS
          </TabsTrigger>
        </TabsList>

        <TabsContent value="ldap">
          <Card className="bg-gray-900/60 border-gray-700">
            <CardHeader>
              <CardTitle className="text-gray-100">LDAP Domain Dump</CardTitle>
              <CardDescription className="text-gray-400">
                Dumps users, groups, computers, GPOs, and policies using ldapdomaindump. Detects Kerberoastable accounts and weak password policies.
              </CardDescription>
            </CardHeader>
            <CardContent><LdapReconPanel /></CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="ligolo">
          <Card className="bg-gray-900/60 border-gray-700">
            <CardHeader>
              <CardTitle className="text-gray-100">Ligolo-ng Tunnel Setup</CardTitle>
              <CardDescription className="text-gray-400">
                Generates proxy and agent commands for setting up reverse tunnels into internal networks via Ligolo-ng.
              </CardDescription>
            </CardHeader>
            <CardContent><LigoloPanel /></CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="acl">
          <Card className="bg-gray-900/60 border-gray-700">
            <CardHeader>
              <CardTitle className="text-gray-100">Active Directory ACL Abuse</CardTitle>
              <CardDescription className="text-gray-400">
                Enumerate and exploit dangerous AD ACL rights (GenericAll, WriteDacl, etc.) using dacledit and pywhisker.
              </CardDescription>
            </CardHeader>
            <CardContent><AclAbusePanel /></CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="pth">
          <Card className="bg-gray-900/60 border-gray-700">
            <CardHeader>
              <CardTitle className="text-gray-100">Pass-the-Hash / Pass-the-Ticket</CardTitle>
              <CardDescription className="text-gray-400">
                Execute commands using captured NT hashes (PtH) or Kerberos tickets (PtT) via impacket suite.
              </CardDescription>
            </CardHeader>
            <CardContent><PthPanel /></CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="adcs">
          <Card className="bg-gray-900/60 border-gray-700">
            <CardHeader>
              <CardTitle className="text-gray-100">ADCS Certificate Exploitation</CardTitle>
              <CardDescription className="text-gray-400">
                Find and exploit AD Certificate Services misconfigurations (ESC1-ESC8) using certipy.
              </CardDescription>
            </CardHeader>
            <CardContent><AdcsPanel /></CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
