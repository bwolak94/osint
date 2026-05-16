import { useState } from "react";
import { Eye, EyeOff, AlertTriangle } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import apiClient from "@/shared/api/client";

interface DarkWebFinding {
  type: string;
  severity: string;
  source: string;
  query: string;
  result_count?: number;
  onion_services_found?: string[];
  sample_titles?: string[];
  description: string;
}

interface ScanResponse {
  findings: DarkWebFinding[];
  total_found: number;
  query: string;
}

export function DarkWebForumPage() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ScanResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const { data } = await apiClient.post<ScanResponse>("/api/v1/scanners/run", {
        scanner_name: "darkweb_forum",
        input_value: query.trim(),
        input_type: "domain",
      });
      setResult(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Search failed");
    } finally {
      setLoading(false);
    }
  };

  const mentionFindings = result?.findings.filter((f) => f.type !== "darkweb_summary") ?? [];

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <EyeOff className="h-7 w-7 text-purple-400" />
        <div>
          <h1 className="text-2xl font-bold text-white">Dark Web Forum Monitor</h1>
          <p className="text-sm text-gray-400">Search Ahmia, DarkSearch, and IntelX for mentions — clearnet indexes only</p>
        </div>
      </div>

      <div className="bg-yellow-900/20 border border-yellow-700 rounded-lg p-3 flex items-start gap-2">
        <AlertTriangle className="h-4 w-4 text-yellow-400 mt-0.5 flex-shrink-0" />
        <p className="text-xs text-yellow-200">Uses publicly accessible clearnet dark web search indexes. No Tor connection required.</p>
      </div>

      <Card className="bg-gray-900 border-gray-700">
        <CardContent className="pt-6 space-y-4">
          <Input
            placeholder="domain.com, email@example.com, or username"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            className="bg-gray-800 border-gray-700 text-white"
          />
          <Button onClick={handleSearch} disabled={loading || !query.trim()} className="bg-purple-600 hover:bg-purple-700">
            {loading ? "Searching..." : "Search Dark Web Indexes"}
          </Button>
          {error && <p className="text-red-400 text-sm">{error}</p>}
        </CardContent>
      </Card>

      {result && (
        <div className="space-y-3">
          {mentionFindings.length === 0 ? (
            <p className="text-center text-gray-400 py-8">No dark web mentions found</p>
          ) : (
            mentionFindings.map((f, i) => (
              <Card key={i} className="bg-gray-900 border-red-900">
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-sm flex items-center gap-2">
                      <Eye className="h-4 w-4 text-red-400" />
                      {f.source}
                    </CardTitle>
                    {f.result_count != null && (
                      <Badge variant="destructive">{f.result_count} results</Badge>
                    )}
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-gray-300">{f.description}</p>
                  {f.onion_services_found && f.onion_services_found.length > 0 && (
                    <div className="mt-2 space-y-1">
                      <p className="text-xs text-gray-500">Onion services:</p>
                      {f.onion_services_found.map((o) => (
                        <p key={o} className="text-xs font-mono text-purple-300">{o}</p>
                      ))}
                    </div>
                  )}
                  {f.sample_titles && f.sample_titles.length > 0 && (
                    <div className="mt-2 space-y-1">
                      {f.sample_titles.filter(Boolean).map((t, j) => (
                        <p key={j} className="text-xs text-gray-400">• {t}</p>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            ))
          )}
        </div>
      )}
    </div>
  );
}
