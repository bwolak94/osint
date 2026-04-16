import { memo } from "react";
import { getBezierPath, EdgeLabelRenderer, type EdgeProps } from "reactflow";
import type { OsintEdgeData } from "../../types";

function getStrokeWidth(confidence: number): number {
  if (confidence >= 0.9) return 3;
  if (confidence >= 0.6) return 2;
  return 1;
}

function getStrokeDash(confidence: number): string | undefined {
  if (confidence >= 0.6) return undefined; // solid
  if (confidence >= 0.3) return "6 3"; // dashed
  return "2 2"; // dotted
}

function getStrokeColor(confidence: number, isHistorical: boolean): string {
  if (isHistorical) return "var(--text-tertiary)";
  if (confidence >= 0.8) return "var(--brand-500)";
  if (confidence >= 0.5) return "var(--text-secondary)";
  return "var(--text-tertiary)";
}

export const RelationshipEdge = memo(function RelationshipEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  selected,
}: EdgeProps<OsintEdgeData>) {
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
  });

  const confidence = data?.confidence ?? 0.5;
  const isHistorical = !!(data?.validTo && new Date(data.validTo) < new Date());
  const isOnPath = data?.isOnPath ?? false;

  return (
    <>
      <path
        id={id}
        d={edgePath}
        stroke={isOnPath ? "var(--brand-400)" : getStrokeColor(confidence, isHistorical)}
        strokeWidth={isOnPath ? 3 : getStrokeWidth(confidence)}
        strokeDasharray={isHistorical ? "4 4" : getStrokeDash(confidence)}
        fill="none"
        className={`transition-all ${selected ? "!stroke-brand-400" : ""}`}
        style={{ opacity: isHistorical ? 0.5 : 1 }}
      />
      {data?.label && (
        <EdgeLabelRenderer>
          <div
            className="nodrag nopan pointer-events-none rounded px-1.5 py-0.5 text-[10px] font-medium"
            style={{
              position: "absolute",
              transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
              background: "var(--bg-elevated)",
              color: selected || isOnPath ? "var(--brand-400)" : "var(--text-tertiary)",
              border: "1px solid var(--border-subtle)",
            }}
          >
            {data.label}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
});
