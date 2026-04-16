import { useState } from "react";
import {
  Search, ZoomIn, ZoomOut, Maximize2, LayoutGrid, GitBranch, Circle,
  Route, Download, Filter, X,
} from "lucide-react";
import { useReactFlow } from "reactflow";
import { Button } from "@/shared/components/Button";
import { Input } from "@/shared/components/Input";
import { Badge } from "@/shared/components/Badge";
import type { LayoutType, NodeType } from "../types";

const nodeTypes: NodeType[] = ["person", "company", "email", "phone", "username", "ip", "domain"];

interface GraphToolbarProps {
  searchQuery: string;
  onSearchChange: (query: string) => void;
  layout: LayoutType;
  onLayoutChange: (layout: LayoutType) => void;
  visibleTypes: Set<NodeType>;
  onToggleType: (type: NodeType) => void;
  minConfidence: number;
  onConfidenceChange: (value: number) => void;
  pathFindingActive: boolean;
  onStartPathFinding: () => void;
  onCancelPathFinding: () => void;
  pathSourceId: string | null;
  pathTargetId: string | null;
}

export function GraphToolbar({
  searchQuery, onSearchChange, layout, onLayoutChange,
  visibleTypes, onToggleType, minConfidence, onConfidenceChange,
  pathFindingActive, onStartPathFinding, onCancelPathFinding,
  pathSourceId, pathTargetId,
}: GraphToolbarProps) {
  const { zoomIn, zoomOut, fitView } = useReactFlow();
  const [showFilters, setShowFilters] = useState(false);

  const layouts: { value: LayoutType; label: string; icon: typeof LayoutGrid }[] = [
    { value: "force", label: "Force", icon: LayoutGrid },
    { value: "hierarchical", label: "Hierarchy", icon: GitBranch },
    { value: "circular", label: "Circular", icon: Circle },
  ];

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        {/* Layout buttons */}
        <div className="flex gap-0.5 rounded-md border p-0.5" style={{ borderColor: "var(--border-default)" }}>
          {layouts.map((l) => (
            <button
              key={l.value}
              onClick={() => onLayoutChange(l.value)}
              title={l.label}
              className={`rounded px-2 py-1 text-xs font-medium transition-colors ${
                layout === l.value
                  ? "bg-bg-overlay text-text-primary"
                  : "text-text-tertiary hover:text-text-secondary"
              }`}
            >
              <l.icon className="inline h-3.5 w-3.5 mr-1" />
              {l.label}
            </button>
          ))}
        </div>

        {/* Zoom controls */}
        <div className="flex gap-0.5">
          <Button variant="ghost" size="sm" onClick={() => zoomIn()}><ZoomIn className="h-4 w-4" /></Button>
          <Button variant="ghost" size="sm" onClick={() => zoomOut()}><ZoomOut className="h-4 w-4" /></Button>
          <Button variant="ghost" size="sm" onClick={() => fitView({ padding: 0.2 })}><Maximize2 className="h-4 w-4" /></Button>
        </div>

        <div className="h-6 w-px" style={{ background: "var(--border-default)" }} />

        {/* Search */}
        <div className="w-52">
          <Input
            placeholder="Search nodes..."
            prefixIcon={<Search className="h-3.5 w-3.5" />}
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            suffixIcon={searchQuery ? (
              <button onClick={() => onSearchChange("")} className="cursor-pointer">
                <X className="h-3.5 w-3.5" />
              </button>
            ) : undefined}
          />
        </div>

        {/* Filters toggle */}
        <Button
          variant={showFilters ? "secondary" : "ghost"}
          size="sm"
          onClick={() => setShowFilters(!showFilters)}
          leftIcon={<Filter className="h-3.5 w-3.5" />}
        >
          Filters
        </Button>

        <div className="flex-1" />

        {/* Path finding */}
        {pathFindingActive ? (
          <div className="flex items-center gap-2">
            <Badge variant="info" size="sm" dot>
              {!pathSourceId
                ? "Click source node..."
                : !pathTargetId
                ? "Click target node..."
                : "Path found"}
            </Badge>
            <Button variant="ghost" size="sm" onClick={onCancelPathFinding}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        ) : (
          <Button variant="ghost" size="sm" onClick={onStartPathFinding} leftIcon={<Route className="h-3.5 w-3.5" />}>
            Find Path
          </Button>
        )}

        <Button variant="ghost" size="sm" leftIcon={<Download className="h-3.5 w-3.5" />}>
          Export
        </Button>
      </div>

      {/* Filter panel */}
      {showFilters && (
        <div
          className="flex items-center gap-4 rounded-md border px-4 py-2"
          style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}
        >
          {/* Node type toggles */}
          <div className="flex items-center gap-1">
            <span className="mr-1 text-xs font-medium" style={{ color: "var(--text-tertiary)" }}>Types:</span>
            {nodeTypes.map((t) => (
              <button
                key={t}
                onClick={() => onToggleType(t)}
                className={`rounded px-2 py-0.5 text-xs capitalize transition-colors ${
                  visibleTypes.has(t)
                    ? "bg-bg-overlay text-text-primary"
                    : "text-text-tertiary line-through opacity-50"
                }`}
              >
                {t}
              </button>
            ))}
          </div>

          <div className="h-4 w-px" style={{ background: "var(--border-default)" }} />

          {/* Confidence slider */}
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium" style={{ color: "var(--text-tertiary)" }}>
              Min confidence:
            </span>
            <input
              type="range"
              min={0}
              max={100}
              value={minConfidence * 100}
              onChange={(e) => onConfidenceChange(parseInt(e.target.value) / 100)}
              className="w-24 accent-[var(--brand-500)]"
            />
            <span className="text-xs font-mono" style={{ color: "var(--text-secondary)" }}>
              {Math.round(minConfidence * 100)}%
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
