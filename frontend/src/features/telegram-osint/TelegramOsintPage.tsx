import { useState } from "react";
import { Send, Users, MessageSquare, BarChart2 } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import apiClient from "@/shared/api/client";

interface TelegramFinding {
  type: string;
  severity: string;
  source: string;
  username?: string;
  title?: string;
  description_text?: string;
  subscribers?: number;
  total_posts?: number;
  url?: string;
  description: string;
}

interface ScanResponse {
  findings: TelegramFinding[];
  username: string;
  total_found: number;
}

export function TelegramOsintPage() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ScanResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleScan = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const { data } = await apiClient.post<ScanResponse>("/api/v1/scanners/run", {
        scanner_name: "telegram_osint",
        input_value: query.trim(),
        input_type: "username",
      });
      setResult(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Scan failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <Send className="h-7 w-7 text-blue-400" />
        <div>
          <h1 className="text-2xl font-bold text-white">Telegram OSINT</h1>
          <p className="text-sm text-gray-400">Public channel and username intelligence — t.me, TGStat, Telemetr</p>
        </div>
      </div>

      <Card className="bg-gray-900 border-gray-700">
        <CardContent className="pt-6 space-y-4">
          <Input
            placeholder="@username or channel name"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleScan()}
            className="bg-gray-800 border-gray-700 text-white"
          />
          <Button onClick={handleScan} disabled={loading || !query.trim()} className="bg-blue-600 hover:bg-blue-700">
            {loading ? "Scanning..." : "Scan Telegram"}
          </Button>
          {error && <p className="text-red-400 text-sm">{error}</p>}
        </CardContent>
      </Card>

      {result && result.total_found > 0 && (
        <div className="space-y-3">
          {result.findings.map((f, i) => (
            <Card key={i} className="bg-gray-900 border-gray-700">
              <CardContent className="pt-4">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2">
                    {f.type === "telegram_profile" ? <MessageSquare className="h-5 w-5 text-blue-400" /> : <BarChart2 className="h-5 w-5 text-green-400" />}
                    <div>
                      <p className="text-white font-medium">{f.title || `@${f.username}`}</p>
                      <p className="text-xs text-gray-400">{f.source}</p>
                    </div>
                  </div>
                  {f.subscribers && (
                    <Badge className="bg-blue-900/50 text-blue-300">
                      <Users className="h-3 w-3 mr-1" />{f.subscribers.toLocaleString()}
                    </Badge>
                  )}
                </div>
                {f.description_text && (
                  <p className="mt-2 text-sm text-gray-300 line-clamp-2">{f.description_text}</p>
                )}
                {f.url && (
                  <a href={f.url} target="_blank" rel="noopener noreferrer"
                     className="mt-1 text-xs text-blue-400 hover:underline block">{f.url}</a>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {result && result.total_found === 0 && (
        <p className="text-center text-gray-400 py-8">No Telegram presence found for this username</p>
      )}
    </div>
  );
}
