import { Card, CardBody, CardHeader } from "@/shared/components/Card";
import { Badge } from "@/shared/components/Badge";
import { ProgressBar } from "@/shared/components/ProgressBar";
import { ScannerBadge } from "@/shared/components/osint/ScannerBadge";
import { Wifi, WifiOff, Radio } from "lucide-react";
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

export function ScanProgressPanel({
  completed, total, percentage, currentScanner,
  nodesDiscovered, edgesDiscovered, events, connected,
}: ScanProgressPanelProps) {
  return (
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
        <div>
          <ProgressBar
            value={completed}
            max={total || 1}
            label={`${completed}/${total} tasks completed`}
          />
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
  );
}
