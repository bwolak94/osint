import { useState, useRef, useMemo, useCallback, type MouseEvent } from "react";
import { ZoomIn, ZoomOut, X } from "lucide-react";
import { Button } from "@/shared/components/Button";
import { Badge } from "@/shared/components/Badge";
import { format, parseISO } from "date-fns";

export interface TimelineEvent {
  id: string;
  scanner: string;
  input: string;
  status: "success" | "failed" | "rate_limited";
  duration_ms: number;
  findings_count: number;
  created_at: string;
}

interface InvestigationTimelineProps {
  events: TimelineEvent[];
  investigationId: string;
}

const STATUS_COLORS: Record<TimelineEvent["status"], string> = {
  success: "var(--success-500, #22c55e)",
  failed: "var(--danger-500, #ef4444)",
  rate_limited: "var(--warning-500, #f59e0b)",
};

const STATUS_BG: Record<TimelineEvent["status"], string> = {
  success: "rgba(34,197,94,0.15)",
  failed: "rgba(239,68,68,0.15)",
  rate_limited: "rgba(245,158,11,0.15)",
};

const STATUS_LABELS: Record<TimelineEvent["status"], string> = {
  success: "Success",
  failed: "Failed",
  rate_limited: "Rate Limited",
};

const ROW_HEIGHT = 36;
const ROW_GAP = 4;
const LABEL_WIDTH = 120;
const MIN_BAR_WIDTH = 6;

export function InvestigationTimeline({
  events,
}: InvestigationTimelineProps) {
  const [zoomLevel, setZoomLevel] = useState(1);
  const [selectedEvent, setSelectedEvent] = useState<TimelineEvent | null>(null);
  const [popoverPos, setPopoverPos] = useState({ x: 0, y: 0 });
  const scrollRef = useRef<HTMLDivElement>(null);

  const scanners = useMemo(() => {
    const order = new Map<string, number>();
    for (const e of events) {
      if (!order.has(e.scanner)) order.set(e.scanner, order.size);
    }
    return Array.from(order.keys());
  }, [events]);

  const { minTime, maxTime } = useMemo(() => {
    if (events.length === 0) {
      const now = Date.now();
      return { minTime: now, maxTime: now + 1 };
    }
    let min = Infinity;
    let max = -Infinity;
    for (const e of events) {
      const t = parseISO(e.created_at).getTime();
      min = Math.min(min, t);
      max = Math.max(max, t + e.duration_ms);
    }
    return { minTime: min, maxTime: max };
  }, [events]);

  const totalTimeMs = maxTime - minTime || 1;
  const canvasWidth = Math.max(600, 800 * zoomLevel);

  const timeToX = useCallback(
    (t: number): number => ((t - minTime) / totalTimeMs) * canvasWidth,
    [minTime, totalTimeMs, canvasWidth],
  );

  const durationToWidth = useCallback(
    (ms: number): number => Math.max(MIN_BAR_WIDTH, (ms / totalTimeMs) * canvasWidth),
    [totalTimeMs, canvasWidth],
  );

  const handleBarClick = useCallback(
    (e: MouseEvent<HTMLButtonElement>, event: TimelineEvent) => {
      const rect = e.currentTarget.getBoundingClientRect();
      setPopoverPos({ x: rect.left, y: rect.bottom + 8 });
      setSelectedEvent((prev) => (prev?.id === event.id ? null : event));
    },
    [],
  );

  const totalHeight =
    scanners.length * (ROW_HEIGHT + ROW_GAP) + 32;

  return (
    <div className="flex flex-col gap-2">
      {/* Controls */}
      <div className="flex items-center gap-2">
        <span
          className="text-xs font-medium"
          style={{ color: "var(--text-tertiary)" }}
        >
          Timeline
        </span>
        <div className="ml-auto flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setZoomLevel((z) => Math.max(0.5, z - 0.25))}
            aria-label="Zoom out timeline"
          >
            <ZoomOut className="h-3.5 w-3.5" />
          </Button>
          <span
            className="w-10 text-center text-xs font-mono"
            style={{ color: "var(--text-secondary)" }}
          >
            {Math.round(zoomLevel * 100)}%
          </span>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setZoomLevel((z) => Math.min(4, z + 0.25))}
            aria-label="Zoom in timeline"
          >
            <ZoomIn className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      {/* Timeline scroll area */}
      <div
        ref={scrollRef}
        className="overflow-x-auto rounded-lg border"
        style={{ borderColor: "var(--border-subtle)" }}
        role="region"
        aria-label="Investigation timeline"
      >
        <div
          style={{
            width: LABEL_WIDTH + canvasWidth + 16,
            height: totalHeight,
            position: "relative",
            background: "var(--bg-surface)",
          }}
        >
          {/* Scanner rows */}
          {scanners.map((scanner, rowIdx) => {
            const y = 16 + rowIdx * (ROW_HEIGHT + ROW_GAP);
            const rowEvents = events.filter((e) => e.scanner === scanner);

            return (
              <div key={scanner}>
                {/* Row label */}
                <div
                  className="absolute flex items-center"
                  style={{
                    left: 0,
                    top: y,
                    width: LABEL_WIDTH,
                    height: ROW_HEIGHT,
                    paddingLeft: 12,
                    paddingRight: 8,
                  }}
                >
                  <span
                    className="truncate text-xs font-medium"
                    style={{ color: "var(--text-secondary)" }}
                    title={scanner}
                  >
                    {scanner}
                  </span>
                </div>

                {/* Row background */}
                <div
                  className="absolute"
                  style={{
                    left: LABEL_WIDTH,
                    top: y,
                    width: canvasWidth,
                    height: ROW_HEIGHT,
                    background: rowIdx % 2 === 0 ? "var(--bg-elevated)" : "transparent",
                    borderRadius: 4,
                  }}
                />

                {/* Event bars */}
                {rowEvents.map((event) => {
                  const x = timeToX(parseISO(event.created_at).getTime());
                  const w = durationToWidth(event.duration_ms);
                  return (
                    <button
                      key={event.id}
                      onClick={(e) => handleBarClick(e, event)}
                      aria-label={`${scanner} scan: ${event.status}, ${event.findings_count} findings`}
                      className="absolute flex items-center justify-center rounded transition-opacity hover:opacity-80"
                      style={{
                        left: LABEL_WIDTH + x,
                        top: y + 6,
                        width: w,
                        height: ROW_HEIGHT - 12,
                        background: STATUS_BG[event.status],
                        border: `1px solid ${STATUS_COLORS[event.status]}`,
                        minWidth: MIN_BAR_WIDTH,
                      }}
                    >
                      {w > 24 && (
                        <span
                          className="truncate px-1 text-[10px] font-medium"
                          style={{ color: STATUS_COLORS[event.status] }}
                        >
                          {event.findings_count}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            );
          })}

          {events.length === 0 && (
            <div
              className="absolute inset-0 flex items-center justify-center text-sm"
              style={{ color: "var(--text-tertiary)" }}
            >
              No scan events recorded
            </div>
          )}
        </div>
      </div>

      {/* Popover detail */}
      {selectedEvent && (
        <div
          className="fixed z-50 w-64 rounded-lg border p-4 shadow-xl"
          style={{
            left: Math.min(popoverPos.x, window.innerWidth - 280),
            top: popoverPos.y,
            background: "var(--bg-surface)",
            borderColor: "var(--border-default)",
          }}
          role="tooltip"
        >
          <div className="mb-3 flex items-center justify-between">
            <span
              className="text-sm font-semibold"
              style={{ color: "var(--text-primary)" }}
            >
              {selectedEvent.scanner}
            </span>
            <button
              onClick={() => setSelectedEvent(null)}
              aria-label="Close detail"
              className="rounded p-0.5 hover:bg-bg-overlay"
            >
              <X className="h-3.5 w-3.5" style={{ color: "var(--text-tertiary)" }} />
            </button>
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                Status
              </span>
              <Badge
                variant={
                  selectedEvent.status === "success"
                    ? "success"
                    : selectedEvent.status === "failed"
                    ? "danger"
                    : "warning"
                }
                size="sm"
              >
                {STATUS_LABELS[selectedEvent.status]}
              </Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                Input
              </span>
              <span
                className="max-w-[120px] truncate text-xs font-mono"
                style={{ color: "var(--text-primary)" }}
                title={selectedEvent.input}
              >
                {selectedEvent.input}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                Findings
              </span>
              <span
                className="text-xs font-semibold"
                style={{ color: "var(--text-primary)" }}
              >
                {selectedEvent.findings_count}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                Duration
              </span>
              <span
                className="text-xs font-mono"
                style={{ color: "var(--text-secondary)" }}
              >
                {selectedEvent.duration_ms < 1000
                  ? `${selectedEvent.duration_ms}ms`
                  : `${(selectedEvent.duration_ms / 1000).toFixed(1)}s`}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                Time
              </span>
              <span
                className="text-xs"
                style={{ color: "var(--text-secondary)" }}
              >
                {format(parseISO(selectedEvent.created_at), "HH:mm:ss")}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
