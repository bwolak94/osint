import { useEffect, useRef, useState } from "react";
import { Card, CardBody, CardHeader } from "@/shared/components/Card";
import { Badge } from "@/shared/components/Badge";
import { ProgressBar } from "@/shared/components/ProgressBar";
import { ScannerBadge } from "@/shared/components/osint/ScannerBadge";
import { Radio, WifiOff, Clock } from "lucide-react";
import type { WSMessage } from "./useInvestigationWebSocket";

interface ScanProgressPanelProps {
  completed: number;
  total: number;
  percentage: number;
  currentScanner: string | null;
  nodesDiscovered: number;
  edgesDiscovered: number;
  events: WSMessage[];
  connected: boolean;
}

function EventIcon({ type }: { type: string }) {
  if (type === "scan_complete") return <span style={{ color: "var(--success-500)" }}>&#10003;</span>;
  if (type === "error") return <span style={{ color: "var(--danger-500)" }}>&#10007;</span>;
  if (type === "node_discovered") return <span style={{ color: "var(--brand-400)" }}>&#9679;</span>;
  return <span style={{ color: "var(--info-500)" }}>&#9889;</span>;
}

function useEtaEstimate(completed: number, total: number): string | null {
  const startTimeRef = useRef<number>(Date.now());
  const lastCompletedRef = useRef<number>(0);
  const [eta, setEta] = useState<string | null>(null);

  useEffect(() => {
    if (completed === 0 || total === 0 || completed >= total) {
      setEta(null);
      return;
    }
    // Only update when progress changes
    if (completed === lastCompletedRef.current) return;
    lastCompletedRef.current = completed;

    const elapsedMs = Date.now() - startTimeRef.current;
    const rate = completed / elapsedMs; // tasks per ms
    if (rate <= 0) return;

    const remaining = total - completed;
    const etaMs = remaining / rate;

    if (etaMs < 5000) {
      setEta("< 5s");
    } else if (etaMs < 60000) {
      setEta(`~${Math.round(etaMs / 1000)}s`);
    } else {
      setEta(`~${Math.round(etaMs / 60000)}m`);
    }
  }, [completed, total]);

  return eta;
}

export function ScanProgressPanel({
  completed, total, percentage: _percentage, currentScanner,
  nodesDiscovered, edgesDiscovered, events, connected,
}: ScanProgressPanelProps) {
  const eta = useEtaEstimate(completed, total);

  return (
    <>
      {!connected && (
        <div
          className="flex items-center gap-2 rounded-lg border px-3 py-2 text-xs"
          style={{ background: "var(--warning-950)", borderColor: "var(--warning-500)", color: "var(--warning-400)" }}
          role="status"
          aria-live="polite"
        >
          <WifiOff className="h-3.5 w-3.5 shrink-0" />
          Live feed disconnected — reconnecting automatically…
        </div>
      )}
    <Card>
      <CardHeader className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Radio className="h-4 w-4 animate-pulse" style={{ color: "var(--brand-500)" }} />
          <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
            Live Progress
          </h3>
        </div>
        <div className="flex items-center gap-2">
          {connected ? (
            <Badge variant="success" size="sm" dot>Connected</Badge>
          ) : (
            <Badge variant="danger" size="sm" dot>Reconnecting...</Badge>
          )}
        </div>
      </CardHeader>
      <CardBody className="space-y-4">
        {/* Overall progress */}
        <div className="space-y-1">
          <ProgressBar
            value={completed}
            max={total || 1}
            label={`${completed}/${total} tasks completed`}
          />
          {eta && (
            <div className="flex items-center gap-1 text-xs" style={{ color: "var(--text-tertiary)" }}>
              <Clock className="h-3 w-3" />
              ETA: {eta}
            </div>
          )}
        </div>

        {/* Current scanner */}
        {currentScanner && (
          <div className="flex items-center gap-2 text-sm" style={{ color: "var(--text-secondary)" }}>
            <span className="inline-block h-2 w-2 animate-pulse rounded-full" style={{ background: "var(--brand-500)" }} />
            Scanning with <ScannerBadge scanner={currentScanner} />
          </div>
        )}

        {/* Stats */}
        <div className="flex gap-4">
          <div className="text-center">
            <p className="text-lg font-bold font-mono" style={{ color: "var(--text-primary)" }}>{nodesDiscovered}</p>
            <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>Nodes</p>
          </div>
          <div className="text-center">
            <p className="text-lg font-bold font-mono" style={{ color: "var(--text-primary)" }}>{edgesDiscovered}</p>
            <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>Edges</p>
          </div>
        </div>

        {/* Event feed */}
        {events.length > 0 && (
          <div className="max-h-40 space-y-1 overflow-y-auto rounded-md p-2" style={{ background: "var(--bg-elevated)" }}>
            {events.slice(0, 20).map((evt, i) => (
              <div key={i} className="flex items-start gap-2 text-xs">
                <EventIcon type={evt.type} />
                <span className="font-mono" style={{ color: "var(--text-secondary)" }}>
                  {evt.type === "scan_complete"
                    ? `${evt.scanner}: found ${evt.findings_count} results`
                    : evt.type === "error"
                    ? `${evt.scanner}: ${evt.message}`
                    : evt.type === "node_discovered"
                    ? `New node: ${(evt.node as { label?: string })?.label ?? "unknown"}`
                    : evt.type === "progress"
                    ? `Progress: ${evt.percentage}%`
                    : evt.type}
                </span>
              </div>
            ))}
          </div>
        )}
      </CardBody>
    </Card>
    </>
  );
}
