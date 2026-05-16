import { useState } from "react";
import { TrendingUp, FileText, DollarSign } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import apiClient from "@/shared/api/client";

interface SECFinding {
  type: string;
  severity: string;
  source: string;
  company: string;
  total_filings?: number;
  total_events?: number;
  total_disclosures?: number;
  sample_filings?: Array<{ filed: string; company: string; form: string; description: string }>;
  recent_events?: string[];
  description: string;
}

interface ScanResponse {
  findings: SECFinding[];
  company: string;
  total_found: number;
}

export function SECEdgarPage() {
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
        scanner_name: "sec_edgar",
        input_value: query.trim(),
        input_type: "domain",
      });
      setResult(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Scan failed");
    } finally {
      setLoading(false);
    }
  };

  const typeIcon = (type: string) => {
    if (type === "insider_trading_filings") return <DollarSign className="h-4 w-4 text-yellow-400" />;
    if (type === "sec_material_events") return <TrendingUp className="h-4 w-4 text-blue-400" />;
    return <FileText className="h-4 w-4 text-gray-400" />;
  };

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <TrendingUp className="h-7 w-7 text-green-400" />
        <div>
          <h1 className="text-2xl font-bold text-white">SEC EDGAR Intelligence</h1>
          <p className="text-sm text-gray-400">Insider trading (Form 4), material events (8-K), ownership disclosures (13D/G)</p>
        </div>
      </div>

      <Card className="bg-gray-900 border-gray-700">
        <CardContent className="pt-6 space-y-4">
          <Input
            placeholder="company.com or company name"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleScan()}
            className="bg-gray-800 border-gray-700 text-white"
          />
          <Button onClick={handleScan} disabled={loading || !query.trim()} className="bg-green-700 hover:bg-green-800">
            {loading ? "Searching EDGAR..." : "Search SEC EDGAR"}
          </Button>
          {error && <p className="text-red-400 text-sm">{error}</p>}
        </CardContent>
      </Card>

      {result && (
        <div className="space-y-3">
          {result.findings.length === 0 ? (
            <p className="text-center text-gray-400 py-8">No SEC filings found for "{result.company}"</p>
          ) : (
            result.findings.map((f, i) => (
              <Card key={i} className="bg-gray-900 border-gray-700">
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-sm flex items-center gap-2">
                      {typeIcon(f.type)}
                      {f.source}
                    </CardTitle>
                    <Badge className="bg-blue-900/50 text-blue-300">
                      {f.total_filings ?? f.total_events ?? f.total_disclosures ?? 0} filings
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-gray-300">{f.description}</p>
                  {f.sample_filings && f.sample_filings.length > 0 && (
                    <div className="mt-3 space-y-1">
                      {f.sample_filings.map((sf, j) => (
                        <div key={j} className="text-xs flex gap-2">
                          <span className="text-gray-500 w-24 flex-shrink-0">{sf.filed}</span>
                          <span className="text-white">{sf.company}</span>
                          <Badge className="text-xs bg-gray-800 text-gray-300 ml-auto">{sf.form}</Badge>
                        </div>
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
