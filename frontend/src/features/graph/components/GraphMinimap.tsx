import { useState, useRef, useCallback, useMemo, type MouseEvent } from "react";
import { Map } from "lucide-react";
import type { NodeType } from "../types";

interface MinimapNode {
  id: string;
  position: { x: number; y: number };
  type?: string;
}

interface ReactFlowViewport {
  x: number;
  y: number;
  zoom: number;
}

interface GraphMinimapProps {
  nodes: MinimapNode[];
  viewport: ReactFlowViewport;
  onViewportChange: (viewport: ReactFlowViewport) => void;
}

const MINIMAP_WIDTH = 160;
const MINIMAP_HEIGHT = 120;
const PADDING = 8;

const NODE_TYPE_COLORS: Record<string, string> = {
  person: "#a78bfa",
  company: "#60a5fa",
  email: "#34d399",
  phone: "#fbbf24",
  username: "#f472b6",
  ip: "#38bdf8",
  domain: "#4ade80",
  service: "#fb923c",
  location: "#e879f9",
  vulnerability: "#f87171",
  breach: "#ef4444",
  subdomain: "#86efac",
  port: "#93c5fd",
  certificate: "#fde68a",
  asn: "#c4b5fd",
  url: "#6ee7b7",
  hash: "#d1d5db",
  address: "#fdba74",
  bank_account: "#fca5a5",
  regon: "#a5b4fc",
  nip: "#a5b4fc",
  online_service: "#67e8f9",
  input: "#cbd5e1",
};

function getNodeColor(type: string | undefined): string {
  return NODE_TYPE_COLORS[type ?? ""] ?? "#64748b";
}

function computeBounds(nodes: MinimapNode[]): {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
} {
  if (nodes.length === 0) return { minX: 0, minY: 0, maxX: 1, maxY: 1 };

  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;

  for (const n of nodes) {
    minX = Math.min(minX, n.position.x);
    minY = Math.min(minY, n.position.y);
    maxX = Math.max(maxX, n.position.x);
    maxY = Math.max(maxY, n.position.y);
  }

  return { minX, minY, maxX, maxY };
}

export function GraphMinimap({ nodes, viewport, onViewportChange }: GraphMinimapProps) {
  const [visible, setVisible] = useState(true);
  const [isDragging, setIsDragging] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const drawArea = useMemo(
    () => ({
      width: MINIMAP_WIDTH - PADDING * 2,
      height: MINIMAP_HEIGHT - PADDING * 2,
    }),
    [],
  );

  const bounds = useMemo(() => computeBounds(nodes), [nodes]);

  const graphToMinimap = useCallback(
    (gx: number, gy: number): { x: number; y: number } => {
      const rangeX = bounds.maxX - bounds.minX || 1;
      const rangeY = bounds.maxY - bounds.minY || 1;
      return {
        x: PADDING + ((gx - bounds.minX) / rangeX) * drawArea.width,
        y: PADDING + ((gy - bounds.minY) / rangeY) * drawArea.height,
      };
    },
    [bounds, drawArea],
  );

  const minimapToGraph = useCallback(
    (mx: number, my: number): { x: number; y: number } => {
      const rangeX = bounds.maxX - bounds.minX || 1;
      const rangeY = bounds.maxY - bounds.minY || 1;
      const nx = ((mx - PADDING) / drawArea.width) * rangeX + bounds.minX;
      const ny = ((my - PADDING) / drawArea.height) * rangeY + bounds.minY;
      return { x: nx, y: ny };
    },
    [bounds, drawArea],
  );

  // Viewport rect in minimap coords
  const viewportRect = useMemo(() => {
    // ReactFlow viewport: x,y are offsets in px, zoom is scale
    // The visible area in graph coords:
    const vWidth = window.innerWidth / viewport.zoom;
    const vHeight = window.innerHeight / viewport.zoom;
    const vLeft = -viewport.x / viewport.zoom;
    const vTop = -viewport.y / viewport.zoom;

    const topLeft = graphToMinimap(vLeft, vTop);
    const bottomRight = graphToMinimap(vLeft + vWidth, vTop + vHeight);

    return {
      x: Math.max(PADDING, topLeft.x),
      y: Math.max(PADDING, topLeft.y),
      width: Math.max(4, bottomRight.x - topLeft.x),
      height: Math.max(4, bottomRight.y - topLeft.y),
    };
  }, [viewport, graphToMinimap]);

  const handlePointerDown = useCallback(
    (e: MouseEvent<HTMLDivElement>) => {
      if (!containerRef.current) return;
      e.preventDefault();
      setIsDragging(true);
      const rect = containerRef.current.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;
      const { x: gx, y: gy } = minimapToGraph(mx, my);

      const vWidth = window.innerWidth / viewport.zoom;
      const vHeight = window.innerHeight / viewport.zoom;

      onViewportChange({
        x: -(gx - vWidth / 2) * viewport.zoom,
        y: -(gy - vHeight / 2) * viewport.zoom,
        zoom: viewport.zoom,
      });
    },
    [minimapToGraph, viewport, onViewportChange],
  );

  const handlePointerMove = useCallback(
    (e: MouseEvent<HTMLDivElement>) => {
      if (!isDragging || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;
      const { x: gx, y: gy } = minimapToGraph(mx, my);

      const vWidth = window.innerWidth / viewport.zoom;
      const vHeight = window.innerHeight / viewport.zoom;

      onViewportChange({
        x: -(gx - vWidth / 2) * viewport.zoom,
        y: -(gy - vHeight / 2) * viewport.zoom,
        zoom: viewport.zoom,
      });
    },
    [isDragging, minimapToGraph, viewport, onViewportChange],
  );

  const handlePointerUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  return (
    <div className="absolute bottom-4 right-4 z-20 flex flex-col items-end gap-1">
      {/* Toggle button */}
      <button
        onClick={() => setVisible((v) => !v)}
        aria-label={visible ? "Hide minimap" : "Show minimap"}
        className="flex h-7 w-7 items-center justify-center rounded-md border transition-colors hover:bg-bg-overlay"
        style={{
          background: "var(--bg-surface)",
          borderColor: "var(--border-default)",
          color: "var(--text-secondary)",
        }}
      >
        <Map className="h-3.5 w-3.5" />
      </button>

      {/* Minimap panel */}
      {visible && (
        <div
          ref={containerRef}
          onMouseDown={handlePointerDown}
          onMouseMove={handlePointerMove}
          onMouseUp={handlePointerUp}
          onMouseLeave={handlePointerUp}
          role="img"
          aria-label="Graph minimap"
          className="relative overflow-hidden rounded-lg border"
          style={{
            width: MINIMAP_WIDTH,
            height: MINIMAP_HEIGHT,
            background: "rgba(0,0,0,0.65)",
            borderColor: "var(--border-default)",
            cursor: isDragging ? "grabbing" : "crosshair",
            backdropFilter: "blur(4px)",
          }}
        >
          {/* Node dots */}
          <svg
            width={MINIMAP_WIDTH}
            height={MINIMAP_HEIGHT}
            className="pointer-events-none absolute inset-0"
          >
            {nodes.map((node) => {
              const { x, y } = graphToMinimap(node.position.x, node.position.y);
              const inBounds =
                x >= PADDING - 2 &&
                x <= MINIMAP_WIDTH - PADDING + 2 &&
                y >= PADDING - 2 &&
                y <= MINIMAP_HEIGHT - PADDING + 2;
              if (!inBounds) return null;
              return (
                <circle
                  key={node.id}
                  cx={x}
                  cy={y}
                  r={2.5}
                  fill={getNodeColor(node.type)}
                  opacity={0.85}
                />
              );
            })}

            {/* Viewport rect */}
            <rect
              x={viewportRect.x}
              y={viewportRect.y}
              width={viewportRect.width}
              height={viewportRect.height}
              fill="rgba(255,255,255,0.06)"
              stroke="rgba(255,255,255,0.4)"
              strokeWidth={1}
              strokeDasharray="3 2"
              rx={1}
            />
          </svg>

          {/* Label */}
          <div
            className="pointer-events-none absolute bottom-1 left-2 text-[9px] font-medium uppercase tracking-widest"
            style={{ color: "rgba(255,255,255,0.3)" }}
          >
            Minimap
          </div>
        </div>
      )}
    </div>
  );
}

export type { NodeType, ReactFlowViewport };
