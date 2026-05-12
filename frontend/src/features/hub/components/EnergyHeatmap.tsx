import { memo, useCallback } from "react";

export interface EnergyHeatmapProps {
  /** [7][24] matrix — row = day (Mon=0 … Sun=6), col = hour (0–23). Values 0–1. */
  data: number[][];
  onCellClick?: (day: number, hour: number, score: number) => void;
}

const DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] as const;

const HOUR_LABEL_SET = new Set([0, 6, 12, 18]);

/**
 * Interpolate between three oklch waypoints based on a score in [0, 1].
 *
 * low  (0.0) = oklch(75% 0.15 140)  — green  (good for work)
 * mid  (0.5) = oklch(75% 0.15  50)  — amber
 * high (1.0) = oklch(65% 0.20  25)  — red    (high load)
 */
function scoreToColor(score: number): string {
  const s = Math.max(0, Math.min(1, score));

  if (s <= 0.5) {
    // green → amber
    const t = s / 0.5;
    const l = 75;
    const c = 0.15;
    const h = 140 + (50 - 140) * t; // 140 → 50
    return `oklch(${l}% ${c} ${h.toFixed(1)})`;
  }

  // amber → red
  const t = (s - 0.5) / 0.5;
  const l = 75 + (65 - 75) * t;  // 75 → 65
  const c = 0.15 + (0.20 - 0.15) * t; // 0.15 → 0.20
  const h = 50 + (25 - 50) * t;  // 50 → 25
  return `oklch(${l.toFixed(1)}% ${c.toFixed(3)} ${h.toFixed(1)})`;
}

export const EnergyHeatmap = memo(function EnergyHeatmap({
  data,
  onCellClick,
}: EnergyHeatmapProps) {
  const handleCellClick = useCallback(
    (day: number, hour: number, score: number) => {
      onCellClick?.(day, hour, score);
    },
    [onCellClick]
  );

  return (
    <div
      role="grid"
      aria-label="Energy heatmap — cognitive load by day and hour"
      className="select-none overflow-auto"
    >
      {/* Day headers */}
      <div
        className="grid mb-1"
        style={{ gridTemplateColumns: "2rem repeat(7, 1fr)" }}
      >
        {/* Empty corner above hour labels */}
        <div aria-hidden="true" />
        {DAY_LABELS.map((day) => (
          <div
            key={day}
            className="text-center text-xs font-medium"
            style={{ color: "var(--text-secondary)" }}
            aria-hidden="true"
          >
            {day}
          </div>
        ))}
      </div>

      {/* Grid body: 24 rows (hours) × 7 columns (days) */}
      {Array.from({ length: 24 }, (_, hour) => (
        <div
          key={hour}
          role="row"
          className="grid mb-0.5"
          style={{ gridTemplateColumns: "2rem repeat(7, 1fr)" }}
        >
          {/* Hour label — only show at 0, 6, 12, 18 */}
          <div
            className="flex items-center justify-end pr-1 text-xs"
            style={{
              color: "var(--text-tertiary)",
              minWidth: "2rem",
              lineHeight: 1,
            }}
            aria-hidden="true"
          >
            {HOUR_LABEL_SET.has(hour) ? String(hour).padStart(2, "0") : ""}
          </div>

          {Array.from({ length: 7 }, (_, day) => {
            const score = data[day]?.[hour] ?? 0;
            const pct = Math.round(score * 100);
            const dayLabel = DAY_LABELS[day];

            return (
              <button
                key={day}
                role="gridcell"
                type="button"
                aria-label={`${dayLabel} ${String(hour).padStart(2, "0")}:00 — score ${pct}%`}
                onClick={() => handleCellClick(day, hour, score)}
                className="h-4 w-full rounded-sm transition-opacity hover:opacity-80 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1"
                style={{
                  backgroundColor: scoreToColor(score),
                  outlineColor: "var(--brand-500)",
                  cursor: onCellClick ? "pointer" : "default",
                }}
              />
            );
          })}
        </div>
      ))}
    </div>
  );
});
