import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { apiClient } from "@/shared/api/client";

interface AttackSurfaceScoreResponse {
  investigation_id: string;
  score: number;
  grade: string;
  risk_level: "critical" | "high" | "medium" | "low";
  breakdown: Record<string, number>;
  top_risks: string[];
  recommendations: string[];
  total_findings_analyzed: number;
}

const GRADE_COLORS: Record<string, string> = {
  A: "text-green-600 dark:text-green-400",
  B: "text-blue-600 dark:text-blue-400",
  C: "text-yellow-600 dark:text-yellow-400",
  D: "text-orange-600 dark:text-orange-400",
  F: "text-red-600 dark:text-red-400",
};

const RISK_LEVEL_COLORS: Record<string, string> = {
  low: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
  medium: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400",
  high: "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400",
  critical: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
};

const SCORE_BAR_COLOR: Record<string, string> = {
  A: "bg-green-500",
  B: "bg-blue-500",
  C: "bg-yellow-500",
  D: "bg-orange-500",
  F: "bg-red-500",
};

function formatCategory(key: string): string {
  return key
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export function AttackSurfaceScorePage() {
  const [investigationId, setInvestigationId] = useState("");
  const [result, setResult] = useState<AttackSurfaceScoreResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleScore() {
    const id = investigationId.trim();
    if (!id) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const response = await apiClient.get<AttackSurfaceScoreResponse>(
        `/api/v1/investigations/${encodeURIComponent(id)}/attack-surface-score`
      );
      setResult(response.data);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Failed to compute attack surface score.";
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      void handleScore();
    }
  }

  const gradeColor = result ? (GRADE_COLORS[result.grade] ?? "text-foreground") : "";
  const barColor = result ? (SCORE_BAR_COLOR[result.grade] ?? "bg-gray-400") : "";
  const riskBadgeClass = result
    ? (RISK_LEVEL_COLORS[result.risk_level] ?? "")
    : "";

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold">Attack Surface Score</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Quantify the attack surface of an investigation based on discovered ports, CVEs, exposed services, and misconfigurations.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Investigation</CardTitle>
          <CardDescription>Enter an investigation ID to compute its attack surface score.</CardDescription>
        </CardHeader>
        <CardContent className="flex gap-3">
          <Input
            placeholder="Investigation ID"
            value={investigationId}
            onChange={(e) => setInvestigationId(e.target.value)}
            onKeyDown={handleKeyDown}
            className="max-w-sm"
            aria-label="Investigation ID"
          />
          <Button onClick={() => void handleScore()} disabled={loading || !investigationId.trim()}>
            {loading ? "Scoring..." : "Compute Score"}
          </Button>
        </CardContent>
      </Card>

      {error && (
        <Card className="border-red-300 bg-red-50 dark:border-red-800 dark:bg-red-950/20">
          <CardContent className="pt-4 text-sm text-red-700 dark:text-red-400">{error}</CardContent>
        </Card>
      )}

      {result && (
        <>
          {/* Score hero */}
          <Card>
            <CardContent className="pt-6">
              <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-start sm:gap-8">
                {/* Big score number */}
                <div className="flex flex-col items-center">
                  <span className={`text-7xl font-black ${gradeColor}`}>{result.grade}</span>
                  <span className="text-sm text-muted-foreground">Grade</span>
                </div>

                <div className="flex-1 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-lg font-semibold">Score: {result.score} / 100</span>
                    <span
                      className={`rounded-full px-3 py-1 text-xs font-semibold uppercase ${riskBadgeClass}`}
                      aria-label={`Risk level: ${result.risk_level}`}
                    >
                      {result.risk_level} risk
                    </span>
                  </div>

                  {/* Score bar */}
                  <div
                    className="h-3 w-full overflow-hidden rounded-full bg-muted"
                    role="progressbar"
                    aria-valuenow={result.score}
                    aria-valuemin={0}
                    aria-valuemax={100}
                  >
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${barColor}`}
                      style={{ width: `${result.score}%` }}
                    />
                  </div>

                  <p className="text-sm text-muted-foreground">
                    Based on {result.total_findings_analyzed} scan result{result.total_findings_analyzed !== 1 ? "s" : ""} analysed.
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          <div className="grid gap-4 md:grid-cols-2">
            {/* Breakdown */}
            <Card>
              <CardHeader>
                <CardTitle>Score Breakdown</CardTitle>
                <CardDescription>Points contributed by each category.</CardDescription>
              </CardHeader>
              <CardContent>
                <table className="w-full text-sm" aria-label="Score breakdown by category">
                  <thead>
                    <tr className="border-b text-left text-muted-foreground">
                      <th className="pb-2 font-medium">Category</th>
                      <th className="pb-2 text-right font-medium">Points</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(result.breakdown).map(([key, value]) => (
                      <tr key={key} className="border-b last:border-0">
                        <td className="py-2">{formatCategory(key)}</td>
                        <td className={`py-2 text-right font-semibold ${value > 0 ? "text-red-500" : "text-muted-foreground"}`}>
                          {value > 0 ? `+${value}` : value}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </CardContent>
            </Card>

            {/* Top risks + Recommendations */}
            <div className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>Top Risks</CardTitle>
                </CardHeader>
                <CardContent>
                  {result.top_risks.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No significant risks identified.</p>
                  ) : (
                    <ol className="list-decimal space-y-1 pl-4 text-sm">
                      {result.top_risks.map((risk, i) => (
                        <li key={i}>{risk}</li>
                      ))}
                    </ol>
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Recommendations</CardTitle>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-2 text-sm">
                    {result.recommendations.map((rec, i) => (
                      <li key={i} className="flex gap-2">
                        <span className="mt-0.5 shrink-0 text-muted-foreground">•</span>
                        <span>{rec}</span>
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
