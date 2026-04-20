import { useState, useRef, useEffect } from "react";
import {
  Search, ZoomIn, ZoomOut, Maximize2, LayoutGrid, GitBranch, Circle,
  Route, Download, Filter, X, Target, FileJson, FileImage, FileSpreadsheet,
  Disc, SquareStack,
} from "lucide-react";
import { useReactFlow } from "reactflow";
import { Button } from "@/shared/components/Button";
import { Input } from "@/shared/components/Input";
import { Badge } from "@/shared/components/Badge";
import type { LayoutType, NodeType } from "../types";

const ALL_NODE_TYPES: NodeType[] = [
  "person", "company", "email", "phone", "username", "ip", "domain",
  "service", "location", "vulnerability", "breach", "subdomain",
  "port", "certificate", "asn", "url", "hash", "address",
  "bank_account", "regon", "nip", "online_service", "input",
];

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
  onExportJSON?: () => void;
  onExportCSV?: () => void;
  onExportPNG?: () => void;
  onSelectByType?: (type: NodeType) => void;
  onClearSelection?: () => void;
  availableTypes?: NodeType[];
  /** @deprecated Use onExportJSON instead */
  onExport?: () => void;
}

export function GraphToolbar({
  searchQuery, onSearchChange, layout, onLayoutChange,
  visibleTypes, onToggleType, minConfidence, onConfidenceChange,
  pathFindingActive, onStartPathFinding, onCancelPathFinding,
  pathSourceId, pathTargetId, onExportJSON, onExportCSV, onExportPNG,
  onSelectByType, onClearSelection, availableTypes = [],
  onExport,
}: GraphToolbarProps) {
  const { zoomIn, zoomOut, fitView } = useReactFlow();
  const [showFilters, setShowFilters] = useState(false);
  const [showExportMenu, setShowExportMenu] = useState(false);
  const [showSelectByType, setShowSelectByType] = useState(false);
  const exportRef = useRef<HTMLDivElement>(null);
  const selectRef = useRef<HTMLDivElement>(null);

  // Close dropdowns on outside click
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (exportRef.current && !exportRef.current.contains(e.target as HTMLElement)) {
        setShowExportMenu(false);
      }
      if (selectRef.current && !selectRef.current.contains(e.target as HTMLElement)) {
        setShowSelectByType(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const layouts: { value: LayoutType; label: string; icon: typeof LayoutGrid }[] = [
    { value: "force", label: "Force", icon: LayoutGrid },
    { value: "hierarchical", label: "Hierarchy", icon: GitBranch },
    { value: "circular", label: "Circular", icon: Circle },
    { value: "radial", label: "Radial", icon: Disc },
    { value: "block", label: "Block", icon: SquareStack },
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

        {/* Select by Type dropdown */}
        <div className="relative" ref={selectRef}>
          <Button
            variant={showSelectByType ? "secondary" : "ghost"}
            size="sm"
            onClick={() => setShowSelectByType(!showSelectByType)}
            leftIcon={<Target className="h-3.5 w-3.5" />}
          >
            Select by Type
          </Button>
          {showSelectByType && (
            <div
              className="absolute left-0 top-full z-50 mt-1 rounded-lg border py-1 shadow-lg"
              style={{ background: "var(--bg-surface)", borderColor: "var(--border-default)", minWidth: 160 }}
            >
              <button
                onClick={() => { onClearSelection?.(); setShowSelectByType(false); }}
                className="flex w-full items-center gap-2 px-3 py-1.5 text-xs transition-colors hover:bg-bg-overlay"
                style={{ color: "var(--text-secondary)" }}
              >
                Clear Selection
              </button>
              <div className="my-1 h-px" style={{ background: "var(--border-subtle)" }} />
              {(availableTypes.length > 0 ? availableTypes : ALL_NODE_TYPES).map((t) => (
                <button
                  key={t}
                  onClick={() => { onSelectByType?.(t); setShowSelectByType(false); }}
                  className="flex w-full items-center gap-2 px-3 py-1.5 text-xs capitalize transition-colors hover:bg-bg-overlay"
                  style={{ color: "var(--text-primary)" }}
                >
                  {t.replace(/_/g, " ")}
                </button>
              ))}
            </div>
          )}
        </div>

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

        {/* Export dropdown */}
        <div className="relative" ref={exportRef}>
          <Button
            variant="ghost"
            size="sm"
            leftIcon={<Download className="h-3.5 w-3.5" />}
            onClick={() => setShowExportMenu(!showExportMenu)}
          >
            Export
          </Button>
          {showExportMenu && (
            <div
              className="absolute right-0 top-full z-50 mt-1 rounded-lg border py-1 shadow-lg"
              style={{ background: "var(--bg-surface)", borderColor: "var(--border-default)", minWidth: 160 }}
            >
              <button
                onClick={() => { (onExportJSON ?? onExport)?.(); setShowExportMenu(false); }}
                className="flex w-full items-center gap-2.5 px-3 py-2 text-sm transition-colors hover:bg-bg-overlay"
                style={{ color: "var(--text-primary)" }}
              >
                <FileJson className="h-3.5 w-3.5" style={{ color: "var(--text-tertiary)" }} />
                Export JSON
              </button>
              <button
                onClick={() => { onExportCSV?.(); setShowExportMenu(false); }}
                className="flex w-full items-center gap-2.5 px-3 py-2 text-sm transition-colors hover:bg-bg-overlay"
                style={{ color: "var(--text-primary)" }}
              >
                <FileSpreadsheet className="h-3.5 w-3.5" style={{ color: "var(--text-tertiary)" }} />
                Export CSV
              </button>
              <button
                onClick={() => { onExportPNG?.(); setShowExportMenu(false); }}
                className="flex w-full items-center gap-2.5 px-3 py-2 text-sm transition-colors hover:bg-bg-overlay"
                style={{ color: "var(--text-primary)" }}
              >
                <FileImage className="h-3.5 w-3.5" style={{ color: "var(--text-tertiary)" }} />
                Export PNG
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Filter panel */}
      {showFilters && (
        <div
          className="flex flex-wrap items-center gap-4 rounded-md border px-4 py-2"
          style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}
        >
          {/* Node type toggles */}
          <div className="flex flex-wrap items-center gap-1">
            <span className="mr-1 text-xs font-medium" style={{ color: "var(--text-tertiary)" }}>Types:</span>
            {ALL_NODE_TYPES.map((t) => (
              <button
                key={t}
                onClick={() => onToggleType(t)}
                className={`rounded px-2 py-0.5 text-xs capitalize transition-colors ${
                  visibleTypes.has(t)
                    ? "bg-bg-overlay text-text-primary"
                    : "text-text-tertiary line-through opacity-50"
                }`}
              >
                {t.replace(/_/g, " ")}
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
