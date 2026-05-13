import { useState } from "react";
import { UserSearch, Search, ExternalLink, CheckCircle, XCircle, AlertCircle } from "lucide-react";
import { useUsernameScanner } from "./hooks";
import type { PlatformResult, UsernameScanResult } from "./types";
import { Button } from "@/shared/components/Button";
import { Input } from "@/shared/components/Input";
import { Card, CardBody } from "@/shared/components/Card";
import { Badge } from "@/shared/components/Badge";

function PlatformRow({ result }: { result: PlatformResult }) {
  return (
    <div
      className="flex items-center gap-3 rounded-lg border px-4 py-3"
      style={{
        background: "var(--bg-surface)",
        borderColor: result.found ? "var(--brand-500, #6366f1)" : "var(--border-subtle)",
      }}
    >
      {result.error ? (
        <AlertCircle className="h-4 w-4 shrink-0" style={{ color: "var(--text-tertiary)" }} />
      ) : result.found ? (
        <CheckCircle className="h-4 w-4 shrink-0" style={{ color: "var(--success-400, #4ade80)" }} />
      ) : (
        <XCircle className="h-4 w-4 shrink-0" style={{ color: "var(--text-tertiary)" }} />
      )}
      <span className="flex-1 text-sm font-medium" style={{ color: "var(--text-primary)" }}>{result.platform}</span>
      {result.status_code && (
        <Badge variant="neutral" size="sm">{result.status_code}</Badge>
      )}
      {result.found && (
        <a href={result.url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 text-xs hover:underline shrink-0" style={{ color: "var(--brand-400)" }}>
          <ExternalLink className="h-3 w-3" /> Visit
        </a>
      )}
    </div>
  );
}

function ScanResults({ data }: { data: UsernameScanResult }) {
  const [showNotFound, setShowNotFound] = useState(false);

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-3">
        {[
          { label: "Found", value: data.found.length, color: data.found.length > 0 ? "var(--success-400, #4ade80)" : "var(--text-tertiary)" },
          { label: "Not Found", value: data.not_found.length, color: "var(--text-tertiary)" },
          { label: "Checked", value: data.total_checked, color: "var(--text-primary)" },
        ].map(({ label, value, color }) => (
          <div key={label} className="rounded-xl border p-4 text-center" style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}>
            <p className="text-3xl font-bold" style={{ color }}>{value}</p>
            <p className="text-xs mt-1" style={{ color: "var(--text-tertiary)" }}>{label}</p>
          </div>
        ))}
      </div>

      {data.found.length > 0 && (
        <div className="space-y-2">
          <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Found on {data.found.length} platform{data.found.length !== 1 ? "s" : ""}</p>
          {data.found.map((r) => <PlatformRow key={r.platform} result={r} />)}
        </div>
      )}

      {data.not_found.length > 0 && (
        <div>
          <button
            onClick={() => setShowNotFound((v) => !v)}
            className="text-sm mb-2 hover:underline"
            style={{ color: "var(--text-tertiary)" }}
          >
            {showNotFound ? "Hide" : "Show"} {data.not_found.length} platforms where not found
          </button>
          {showNotFound && (
            <div className="space-y-1">
              {data.not_found.map((r) => <PlatformRow key={r.platform} result={r} />)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function UsernameScannerPage() {
  const [username, setUsername] = useState("");
  const scan = useUsernameScanner();

  const handleScan = () => {
    if (username.trim()) scan.mutate(username.trim());
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <UserSearch className="h-6 w-6" style={{ color: "var(--brand-400)" }} />
        <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Username Scanner</h1>
      </div>

      <Card>
        <CardBody>
          <div className="flex gap-3">
            <div className="flex-1">
              <Input
                placeholder="Username to investigate..."
                prefixIcon={<Search className="h-4 w-4" />}
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleScan()}
              />
            </div>
            <Button onClick={handleScan} disabled={!username.trim() || scan.isPending} leftIcon={<UserSearch className="h-4 w-4" />}>
              {scan.isPending ? "Scanning 30+ platforms..." : "Scan Username"}
            </Button>
          </div>
          <p className="mt-2 text-xs" style={{ color: "var(--text-tertiary)" }}>
            Checks 30+ platforms including GitHub, Reddit, Twitter, Instagram, TikTok, and more.
          </p>
        </CardBody>
      </Card>

      {scan.data && <ScanResults data={scan.data} />}

      {!scan.data && !scan.isPending && (
        <div className="rounded-xl border py-16 text-center" style={{ borderColor: "var(--border-subtle)" }}>
          <UserSearch className="mx-auto h-10 w-10 mb-3" style={{ color: "var(--text-tertiary)" }} />
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Enter a username to find profiles across 30+ platforms</p>
        </div>
      )}
    </div>
  );
}
