import { Network, GitBranch, ZoomIn } from "lucide-react";
import { useViewport } from "reactflow";

interface GraphStatusBarProps {
  nodeCount: number;
  edgeCount: number;
  typeCounts?: Record<string, number>;
  nodeColors?: Record<string, string>;
}

export function GraphStatusBar({ nodeCount, edgeCount, typeCounts, nodeColors }: GraphStatusBarProps) {
  const { zoom } = useViewport();

  return (
    <div
      className="flex items-center gap-4 border-t px-4 py-1.5 text-xs"
      style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)", color: "var(--text-tertiary)" }}
    >
      <span className="flex items-center gap-1">
        <Network className="h-3 w-3" />
        {nodeCount} nodes
      </span>
      <span className="flex items-center gap-1">
        <GitBranch className="h-3 w-3" />
        {edgeCount} edges
      </span>
      <span className="flex items-center gap-1">
        <ZoomIn className="h-3 w-3" />
        {Math.round(zoom * 100)}%
      </span>

      {/* Node type breakdown */}
      {typeCounts && Object.keys(typeCounts).length > 0 && (
        <>
          <div className="h-3 w-px" style={{ background: "var(--border-default)" }} />
          <div className="flex items-center gap-2 overflow-x-auto">
            {Object.entries(typeCounts)
              .sort(([, a], [, b]) => b - a)
              .map(([type, count]) => (
                <span key={type} className="flex shrink-0 items-center gap-1 text-xs" style={{ color: "var(--text-tertiary)" }}>
                  <span
                    className="h-2 w-2 rounded-full"
                    style={{ background: nodeColors?.[type] ?? "#666" }}
                  />
                  <span className="capitalize">{type.replace(/_/g, " ")}</span>
                  <span className="font-mono">{count}</span>
                </span>
              ))}
          </div>
        </>
      )}
    </div>
  );
}
