import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { apiClient } from "@/shared/api/client";

interface TimelineAnomaly {
  anomaly_type: string;
  timestamp: string;
  description: string;
  severity: "high" | "medium" | "low";
}

interface TimelineAnomalyResponse {
  investigation_id: string;
  total_events: number;
  anomalies: TimelineAnomaly[];
  first_event: string | null;
  last_event: string | null;
  timeline_span_days: number;
}

const SEVERITY_CLASSES: Record<string, string> = {
  high: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
  medium: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400",
  low: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
};

const ANOMALY_TYPE_LABELS: Record<string, string> = {
  temporal_gap: "Temporal Gap",
  activity_burst: "Activity Burst",
  off_hours_activity: "Off-Hours Activity",
  future_date: "Future Date",
};

function formatDate(iso: string | null): string {
  if (!iso) return "N/A";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export function TimelineAnomalyPage() {
  const [investigationId, setInvestigationId] = useState("");
  const [result, setResult] = useState<TimelineAnomalyResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleDetect() {
    const id = investigationId.trim();
    if (!id) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const response = await apiClient.get<TimelineAnomalyResponse>(
        `/api/v1/investigations/${encodeURIComponent(id)}/timeline-anomalies`
      );
      setResult(response.data);
    } catch (err: unknown) {
      const message =
        err instanceof Error
          ? err.message
          : "Failed to fetch timeline anomalies.";
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      void handleDetect();
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold">Timeline Anomaly Detection</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Detect temporal anomalies in investigation scan result timestamps — gaps, bursts, off-hours activity, and future-dated events.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Investigation</CardTitle>
          <CardDescription>Enter an investigation ID to analyse its timeline.</CardDescription>
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
          <Button onClick={() => void handleDetect()} disabled={loading || !investigationId.trim()}>
            {loading ? "Analysing..." : "Detect Anomalies"}
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
          {/* Summary */}
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Card>
              <CardContent className="pt-4">
                <p className="text-xs text-muted-foreground">Total Events</p>
                <p className="text-2xl font-bold">{result.total_events}</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4">
                <p className="text-xs text-muted-foreground">Anomalies Found</p>
                <p className="text-2xl font-bold text-red-600">{result.anomalies.length}</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4">
                <p className="text-xs text-muted-foreground">Timeline Span</p>
                <p className="text-2xl font-bold">{result.timeline_span_days}d</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4">
                <p className="text-xs text-muted-foreground">First Event</p>
                <p className="text-sm font-medium">{formatDate(result.first_event)}</p>
              </CardContent>
            </Card>
          </div>

          {/* Anomaly list */}
          <Card>
            <CardHeader>
              <CardTitle>Detected Anomalies</CardTitle>
              <CardDescription>
                {result.anomalies.length === 0
                  ? "No anomalies detected in this investigation's timeline."
                  : `${result.anomalies.length} anomal${result.anomalies.length === 1 ? "y" : "ies"} detected.`}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {result.anomalies.length === 0 ? (
                <p className="text-sm text-muted-foreground">Timeline appears normal.</p>
              ) : (
                <ul className="space-y-3" aria-label="Timeline anomalies">
                  {result.anomalies.map((anomaly, idx) => (
                    <li
                      key={idx}
                      className="flex flex-col gap-1 rounded-md border p-3 sm:flex-row sm:items-start sm:justify-between"
                    >
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-semibold">
                            {ANOMALY_TYPE_LABELS[anomaly.anomaly_type] ?? anomaly.anomaly_type}
                          </span>
                          <Badge
                            className={SEVERITY_CLASSES[anomaly.severity] ?? ""}
                            aria-label={`Severity: ${anomaly.severity}`}
                          >
                            {anomaly.severity}
                          </Badge>
                        </div>
                        <p className="text-sm text-muted-foreground">{anomaly.description}</p>
                        <p className="text-xs text-muted-foreground">{formatDate(anomaly.timestamp)}</p>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
