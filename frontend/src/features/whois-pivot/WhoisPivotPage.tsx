import { useState } from "react";
import { Search, Globe, AlertTriangle } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import apiClient from "@/shared/api/client";

interface WhoisPivotResult {
  query: string;
  pivot_type: string;
  related_domains: string[];
  total_found: number;
  sources: string[];
  risk_indicators: string[];
}

export function WhoisPivotPage() {
  const [query, setQuery] = useState("");
  const [pivotType, setPivotType] = useState("email");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<WhoisPivotResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const { data } = await apiClient.post<WhoisPivotResult>("/api/v1/whois-pivot", {
        query,
        pivot_type: pivotType,
      });
      setResult(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Pivot failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <Search className="h-7 w-7 text-blue-400" />
        <div>
          <h1 className="text-2xl font-bold text-white">WHOIS Pivot</h1>
          <p className="text-sm text-gray-400">Find all domains registered by the same registrant email, org, or nameserver</p>
        </div>
      </div>

      <Card className="bg-gray-900 border-gray-700">
        <CardContent className="pt-6 space-y-4">
          <div className="flex gap-3">
            <div className="flex-1">
              <Input
                placeholder="registrant@example.com or org name"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                className="bg-gray-800 border-gray-700 text-white"
              />
            </div>
            <Select value={pivotType} onValueChange={setPivotType}>
              <SelectTrigger className="w-36 bg-gray-800 border-gray-700 text-white">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-gray-800 border-gray-700">
                <SelectItem value="email">Email</SelectItem>
                <SelectItem value="org">Organization</SelectItem>
                <SelectItem value="nameserver">Nameserver</SelectItem>
                <SelectItem value="registrar">Registrar</SelectItem>
              </SelectContent>
            </Select>
            <Button onClick={handleSearch} disabled={loading || !query.trim()} className="bg-blue-600 hover:bg-blue-700">
              {loading ? "Pivoting..." : "Pivot"}
            </Button>
          </div>
          {error && <p className="text-red-400 text-sm">{error}</p>}
        </CardContent>
      </Card>

      {result && (
        <div className="space-y-4">
          <div className="flex items-center gap-4">
            <Badge className="bg-blue-900/50 text-blue-300">{result.total_found} domains found</Badge>
            <span className="text-xs text-gray-400">Sources: {result.sources.join(", ") || "none"}</span>
          </div>

          {result.risk_indicators.length > 0 && (
            <Card className="bg-gray-900 border-red-900">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm text-red-400 flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4" />Risk Indicators
                </CardTitle>
              </CardHeader>
              <CardContent>
                {result.risk_indicators.map((r, i) => (
                  <p key={i} className="text-sm text-gray-300">• {r}</p>
                ))}
              </CardContent>
            </Card>
          )}

          <Card className="bg-gray-900 border-gray-700">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center gap-2">
                <Globe className="h-4 w-4 text-blue-400" />Related Domains
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-2 max-h-96 overflow-y-auto">
                {result.related_domains.map((d) => (
                  <span key={d} className="text-xs font-mono text-gray-300 bg-gray-800 rounded px-2 py-1 truncate">{d}</span>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
