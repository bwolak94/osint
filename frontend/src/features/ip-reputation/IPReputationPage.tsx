import { useState } from "react";
import { Shield, ShieldAlert, Globe, Wifi } from "lucide-react";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import apiClient from "@/shared/api/client";

interface IPReputationResult {
  ip: string;
  is_malicious: boolean;
  abuse_score: number | null;
  country: string | null;
  org: string | null;
  is_tor: boolean;
  is_vpn: boolean;
  open_ports: number[];
  cves: string[];
  sources: string[];
  overall_risk: string;
}

interface IPReputationResponse {
  results: IPReputationResult[];
  total_malicious: number;
  total_clean: number;
}

const RISK_COLOR: Record<string, string> = {
  critical: "text-red-500",
  high: "text-orange-400",
  medium: "text-yellow-400",
  low: "text-green-400",
};

const RISK_BADGE: Record<string, string> = {
  critical: "bg-red-900/50 text-red-300",
  high: "bg-orange-900/50 text-orange-300",
  medium: "bg-yellow-900/50 text-yellow-300",
  low: "bg-green-900/50 text-green-300",
};

export function IPReputationPage() {
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<IPReputationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleCheck = async () => {
    const ips = input.split(/[\n,\s]+/).map((s) => s.trim()).filter((s) => s.length > 0);
    if (!ips.length) return;
    setLoading(true);
    setError(null);
    try {
      const { data } = await apiClient.post<IPReputationResponse>("/api/v1/ip-reputation/check", { ips });
      setResult(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Check failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <Shield className="h-7 w-7 text-blue-400" />
        <div>
          <h1 className="text-2xl font-bold text-white">IP Reputation</h1>
          <p className="text-sm text-gray-400">Multi-source IP reputation check — Shodan, ip-api, AbuseIPDB</p>
        </div>
      </div>

      <Card className="bg-gray-900 border-gray-700">
        <CardContent className="pt-6 space-y-4">
          <div>
            <label className="text-sm text-gray-400 mb-1 block">IP Addresses (one per line or comma-separated, max 20)</label>
            <Textarea
              placeholder={"8.8.8.8\n1.1.1.1\n192.168.0.1"}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              className="bg-gray-800 border-gray-700 text-white font-mono h-28"
            />
          </div>
          <Button onClick={handleCheck} disabled={loading || !input.trim()} className="bg-blue-600 hover:bg-blue-700">
            {loading ? "Checking..." : "Check Reputation"}
          </Button>
          {error && <p className="text-red-400 text-sm">{error}</p>}
        </CardContent>
      </Card>

      {result && (
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-4">
            <Card className="bg-gray-900 border-gray-700">
              <CardContent className="pt-4">
                <p className="text-xs text-gray-400">Total Checked</p>
                <p className="text-2xl font-bold text-white">{result.results.length}</p>
              </CardContent>
            </Card>
            <Card className="bg-gray-900 border-red-900">
              <CardContent className="pt-4">
                <p className="text-xs text-gray-400">Malicious</p>
                <p className="text-2xl font-bold text-red-400">{result.total_malicious}</p>
              </CardContent>
            </Card>
            <Card className="bg-gray-900 border-green-900">
              <CardContent className="pt-4">
                <p className="text-xs text-gray-400">Clean</p>
                <p className="text-2xl font-bold text-green-400">{result.total_clean}</p>
              </CardContent>
            </Card>
          </div>

          <div className="space-y-3">
            {result.results.map((r) => (
              <Card key={r.ip} className={`bg-gray-900 ${r.is_malicious ? "border-red-800" : "border-gray-700"}`}>
                <CardContent className="pt-4">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                      {r.is_malicious ? (
                        <ShieldAlert className="h-5 w-5 text-red-400 flex-shrink-0" />
                      ) : (
                        <Shield className="h-5 w-5 text-green-400 flex-shrink-0" />
                      )}
                      <div>
                        <p className="text-white font-mono font-medium">{r.ip}</p>
                        <p className="text-xs text-gray-400">
                          {[r.org, r.country].filter(Boolean).join(" · ")}
                        </p>
                      </div>
                    </div>
                    <Badge className={RISK_BADGE[r.overall_risk] || "bg-gray-700 text-gray-300"}>
                      {r.overall_risk.toUpperCase()}
                    </Badge>
                  </div>

                  <div className="mt-3 flex flex-wrap gap-2">
                    {r.is_tor && <Badge className="bg-purple-900/50 text-purple-300 text-xs">TOR</Badge>}
                    {r.is_vpn && <Badge className="bg-blue-900/50 text-blue-300 text-xs">VPN/PROXY</Badge>}
                    {r.open_ports.length > 0 && (
                      <Badge className="bg-gray-700 text-gray-300 text-xs">
                        Ports: {r.open_ports.slice(0, 5).join(", ")}{r.open_ports.length > 5 ? "..." : ""}
                      </Badge>
                    )}
                    {r.cves.slice(0, 3).map((cve) => (
                      <Badge key={cve} variant="destructive" className="text-xs">{cve}</Badge>
                    ))}
                    {r.abuse_score != null && (
                      <Badge className={`text-xs ${r.abuse_score > 25 ? "bg-red-900/50 text-red-300" : "bg-gray-700 text-gray-300"}`}>
                        Abuse: {r.abuse_score}%
                      </Badge>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
