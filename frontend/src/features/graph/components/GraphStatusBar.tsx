import { Network, GitBranch, ZoomIn } from "lucide-react";
import { useReactFlow, useViewport } from "reactflow";

interface GraphStatusBarProps {
  nodeCount: number;
  edgeCount: number;
}

export function GraphStatusBar({ nodeCount, edgeCount }: GraphStatusBarProps) {
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
    </div>
  );
}
