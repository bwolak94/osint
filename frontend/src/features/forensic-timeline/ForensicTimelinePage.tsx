import { useMemo, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Clock, Loader2, ZoomIn, ZoomOut } from "lucide-react";
import { Button } from "@/shared/components/Button";
import { Badge } from "@/shared/components/Badge";
import { apiClient } from "@/shared/api/client";
import { format, parseISO } from "date-fns";

interface TimelineEvent {
  event_id: string;
  timestamp: string;
  event_type: string;
  actor: string;
  summary: string;
  detail: Record<string, unknown>;
  entity_type: string | null;
  entity_value: string | null;
  confidence: number;
  source: string;
  tags: string[];
}

interface SwimLane {
  lane_id: string;
  label: string;
  events: TimelineEvent[];
  color: string;
}

interface ForensicTimelineResponse {
  investigation_id: string;
  total_events: number;
  time_range: { start: string | null; end: string | null };
  lanes: SwimLane[];
  generated_at: string;
}


function EventDot({ event, color }: { event: TimelineEvent; color: string }) {
  const [hovered, setHovered] = useState(false);
  return (
    <div className="relative flex flex-col items-center" style={{ flex: "0 0 auto" }}>
      <button
        className="h-3 w-3 rounded-full border-2 transition-transform hover:scale-150 focus:outline-none"
        style={{ background: color, borderColor: "var(--bg-base)", zIndex: 2 }}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        aria-label={event.summary}
      />
      {hovered && (
        <div
          className="absolute bottom-5 left-1/2 z-30 w-56 -translate-x-1/2 rounded-lg border p-3 shadow-xl text-xs"
          style={{ background: "var(--bg-surface)", borderColor: "var(--border-default)" }}
        >
          <p className="font-semibold mb-1" style={{ color: "var(--text-primary)" }}>{event.summary}</p>
          <p className="font-mono" style={{ color: "var(--text-tertiary)" }}>
            {format(parseISO(event.timestamp), "yyyy-MM-dd HH:mm:ss")}
          </p>
          {event.entity_value && (
            <p className="mt-1 font-mono truncate" style={{ color: color }}>{event.entity_value}</p>
          )}
          {event.tags.length > 0 && (
            <div className="mt-1 flex gap-1 flex-wrap">
              {event.tags.map((t) => <Badge key={t} variant="neutral" size="sm">{t}</Badge>)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function SwimLaneRow({ lane, minTime, maxTime, zoom }: {
  lane: SwimLane;
  minTime: number;
  maxTime: number;
  zoom: number;
}) {
  const totalMs = maxTime - minTime || 1;
  const canvasWidth = Math.max(600, 900 * zoom);

  const eventPositions = lane.events.map((evt) => {
    const t = parseISO(evt.timestamp).getTime();
    const x = ((t - minTime) / totalMs) * canvasWidth;
    return { ...evt, x };
  });

  return (
    <div className="flex items-center gap-3">
      {/* Lane label */}
      <div
        className="w-28 shrink-0 text-right text-xs font-medium truncate"
        style={{ color: "var(--text-secondary)" }}
        title={lane.label}
      >
        {lane.label}
      </div>

      {/* Lane track */}
      <div className="flex-1 relative h-8" style={{ minWidth: canvasWidth }}>
        {/* Track line */}
        <div
          className="absolute top-1/2 -translate-y-px w-full h-px"
          style={{ background: "var(--border-subtle)" }}
        />
        {/* Events */}
        {eventPositions.map((evt) => (
          <div
            key={evt.event_id}
            className="absolute top-1/2 -translate-y-1/2"
            style={{ left: evt.x }}
          >
            <EventDot event={evt} color={lane.color} />
          </div>
        ))}
      </div>

      {/* Count badge */}
      <div className="w-10 shrink-0 text-right">
        {lane.events.length > 0 && (
          <Badge variant="neutral" size="sm">{lane.events.length}</Badge>
        )}
      </div>
    </div>
  );
}

export function ForensicTimelinePage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [zoom, setZoom] = useState(1);

  const { data, isLoading } = useQuery({
    queryKey: ["forensic-timeline", id],
    queryFn: async () => {
      const res = await apiClient.get<ForensicTimelineResponse>(`/investigations/${id}/forensic-timeline`);
      return res.data;
    },
    enabled: !!id,
  });

  const { minTime, maxTime } = useMemo(() => {
    const start = data?.time_range.start;
    const end = data?.time_range.end;
    if (!start || !end) {
      const now = Date.now();
      return { minTime: now, maxTime: now + 1 };
    }
    return { minTime: parseISO(start).getTime(), maxTime: parseISO(end).getTime() };
  }, [data]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin" style={{ color: "var(--brand-500)" }} />
      </div>
    );
  }

  const nonEmptyLanes = data?.lanes.filter((l) => l.events.length > 0) ?? [];

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate(`/investigations/${id}`)}
          className="rounded-md p-1 transition-colors hover:bg-bg-overlay"
        >
          <ArrowLeft className="h-5 w-5" style={{ color: "var(--text-secondary)" }} />
        </button>
        <div className="flex-1">
          <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>Forensic Timeline</h1>
          <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
            {data?.total_events ?? 0} events across {nonEmptyLanes.length} categories
            {data?.time_range.start && (
              <> · {format(parseISO(data.time_range.start), "yyyy-MM-dd")} — {format(parseISO(data.time_range.end!), "yyyy-MM-dd")}</>
            )}
          </p>
        </div>
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="sm" onClick={() => setZoom((z) => Math.max(0.5, z - 0.25))}>
            <ZoomOut className="h-3.5 w-3.5" />
          </Button>
          <span className="w-12 text-center text-xs font-mono" style={{ color: "var(--text-secondary)" }}>
            {Math.round(zoom * 100)}%
          </span>
          <Button variant="ghost" size="sm" onClick={() => setZoom((z) => Math.min(4, z + 0.25))}>
            <ZoomIn className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-3">
        {nonEmptyLanes.map((lane) => (
          <div key={lane.lane_id} className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: lane.color }} />
            <span className="text-xs" style={{ color: "var(--text-secondary)" }}>
              {lane.label} ({lane.events.length})
            </span>
          </div>
        ))}
      </div>

      {/* Timeline */}
      {nonEmptyLanes.length === 0 ? (
        <div className="rounded-lg border py-16 text-center" style={{ borderColor: "var(--border-subtle)" }}>
          <Clock className="mx-auto h-8 w-8 mb-3" style={{ color: "var(--text-tertiary)" }} />
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>No events recorded yet</p>
          <p className="text-xs mt-1" style={{ color: "var(--text-tertiary)" }}>Run scans to populate the forensic timeline</p>
        </div>
      ) : (
        <div
          className="overflow-x-auto rounded-lg border"
          style={{ borderColor: "var(--border-subtle)", background: "var(--bg-surface)" }}
        >
          <div className="p-4 space-y-4" style={{ minWidth: Math.max(700, 900 * zoom + 200) }}>
            {/* Time axis */}
            <div className="flex items-center gap-3 text-[10px] font-mono" style={{ color: "var(--text-tertiary)" }}>
              <div className="w-28 shrink-0" />
              <div className="flex-1 flex justify-between">
                <span>{data?.time_range.start ? format(parseISO(data.time_range.start), "HH:mm:ss") : ""}</span>
                <span>{data?.time_range.end ? format(parseISO(data.time_range.end), "HH:mm:ss") : ""}</span>
              </div>
              <div className="w-10 shrink-0" />
            </div>

            {/* Swim lanes */}
            {nonEmptyLanes.map((lane) => (
              <SwimLaneRow
                key={lane.lane_id}
                lane={lane}
                minTime={minTime}
                maxTime={maxTime}
                zoom={zoom}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
