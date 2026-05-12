import { useMemo, useState } from "react";
import { Badge } from "@/shared/components/Badge";
import { ScannerBadge } from "@/shared/components/osint/ScannerBadge";
import { Clock, CheckCircle2, AlertCircle, Search, Filter, X } from "lucide-react";

interface TimelineEvent {
  id: string;
  timestamp: string;
  type: "scan_started" | "scan_completed" | "scan_failed" | "investigation_created" | "investigation_completed";
  scanner?: string;
  input?: string;
  findings?: number;
  message?: string;
}

interface TimelineTabProps {
  investigation: any;
  scanResults: any[];
}

export function TimelineTab({ investigation, scanResults }: TimelineTabProps) {
  const [scannerFilter, setScannerFilter] = useState<string>("all");
  const [typeFilter, setTypeFilter] = useState<string>("all");

  // Build timeline events from investigation and scan results
  const events: TimelineEvent[] = [];

  // Investigation created
  events.push({
    id: "created",
    timestamp: investigation.created_at,
    type: "investigation_created",
    message: `Investigation "${investigation.title}" created`,
  });

  // Scan results
  for (const r of scanResults) {
    events.push({
      id: r.id,
      timestamp: r.created_at,
      type: r.status === "success" ? "scan_completed" : "scan_failed",
      scanner: r.scanner_name,
      input: r.input_value,
      findings: r.findings_count,
    });
  }

  // Investigation completed
  if (investigation.status === "completed" && investigation.completed_at) {
    events.push({
      id: "completed",
      timestamp: investigation.completed_at || investigation.updated_at,
      type: "investigation_completed",
      message: "Investigation completed",
    });
  }

  // Sort by timestamp
  events.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());

  // Unique scanners for filter
  const availableScanners = useMemo(
    () => [...new Set(scanResults.map((r) => r.scanner_name).filter(Boolean))],
    [scanResults],
  );

  const filteredEvents = useMemo(() => {
    return events.filter((e) => {
      if (scannerFilter !== "all" && e.scanner !== scannerFilter) return false;
      if (typeFilter !== "all" && e.type !== typeFilter) return false;
      return true;
    });
  }, [events, scannerFilter, typeFilter]);

  const hasActiveFilters = scannerFilter !== "all" || typeFilter !== "all";

  const iconMap = {
    investigation_created: Search,
    scan_completed: CheckCircle2,
    scan_failed: AlertCircle,
    investigation_completed: CheckCircle2,
    scan_started: Clock,
  };

  const colorMap: Record<string, string> = {
    investigation_created: "var(--info-500)",
    scan_completed: "var(--success-500)",
    scan_failed: "var(--danger-500)",
    investigation_completed: "var(--brand-500)",
    scan_started: "var(--warning-500)",
  };

  return (
    <div className="space-y-4">
      {/* Filter bar */}
      <div className="flex flex-wrap items-center gap-2">
        <Filter className="h-3.5 w-3.5 shrink-0" style={{ color: "var(--text-tertiary)" }} />
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="rounded-md border px-2 py-1 text-xs"
          style={{ background: "var(--bg-elevated)", borderColor: "var(--border-default)", color: "var(--text-primary)" }}
        >
          <option value="all">All events</option>
          <option value="scan_completed">Completed scans</option>
          <option value="scan_failed">Failed scans</option>
          <option value="investigation_created">Created</option>
          <option value="investigation_completed">Completed</option>
        </select>

        {availableScanners.length > 0 && (
          <select
            value={scannerFilter}
            onChange={(e) => setScannerFilter(e.target.value)}
            className="rounded-md border px-2 py-1 text-xs"
            style={{ background: "var(--bg-elevated)", borderColor: "var(--border-default)", color: "var(--text-primary)" }}
          >
            <option value="all">All scanners</option>
            {availableScanners.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        )}

        {hasActiveFilters && (
          <button
            onClick={() => { setScannerFilter("all"); setTypeFilter("all"); }}
            className="flex items-center gap-1 text-xs transition-colors hover:underline"
            style={{ color: "var(--text-tertiary)" }}
          >
            <X className="h-3 w-3" /> Clear
          </button>
        )}

        <span className="ml-auto text-xs" style={{ color: "var(--text-tertiary)" }}>
          {filteredEvents.length} event{filteredEvents.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Timeline */}
      <div className="space-y-0">
      {filteredEvents.map((event, i) => {
        const Icon = iconMap[event.type] ?? Clock;
        const color = colorMap[event.type] ?? "var(--text-tertiary)";
        const isLast = i === filteredEvents.length - 1;

        return (
          <div key={event.id} className="flex gap-4">
            {/* Timeline line */}
            <div className="flex flex-col items-center">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full" style={{ background: `${color}15` }}>
                <Icon className="h-4 w-4" style={{ color }} />
              </div>
              {!isLast && <div className="w-px flex-1 min-h-[24px]" style={{ background: "var(--border-subtle)" }} />}
            </div>

            {/* Content */}
            <div className="pb-6 pt-1">
              <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                {event.message ?? (
                  <>
                    {event.scanner && <ScannerBadge scanner={event.scanner} />}
                    {" "}
                    {event.type === "scan_completed" ? "completed" : "failed"}
                    {event.input && <span className="ml-1 font-mono text-xs" style={{ color: "var(--text-secondary)" }}>({event.input})</span>}
                    {event.findings !== undefined && event.findings > 0 && (
                      <Badge variant="success" size="sm" className="ml-2">{event.findings} findings</Badge>
                    )}
                  </>
                )}
              </p>
              <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                {new Date(event.timestamp).toLocaleString()}
              </p>
            </div>
          </div>
        );
      })}
      </div>
    </div>
  );
}
