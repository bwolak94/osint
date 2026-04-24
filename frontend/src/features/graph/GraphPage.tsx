import { useState, useMemo, useCallback, useEffect, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import ReactFlow, { Background, MiniMap, ReactFlowProvider, useReactFlow, type NodeTypes, type EdgeTypes, type Node } from "reactflow";
import "reactflow/dist/style.css";
import { ArrowLeft, Search, X } from "lucide-react";

import {
  PersonNode, CompanyNode, EmailNode, PhoneNode, UsernameNode, IPNode, DomainNode,
  ServiceNode, LocationNode, VulnerabilityNode, BreachNode, SubdomainNode,
  PortNode, CertificateNode, ASNNode, URLNode, HashNode, AddressNode,
  BankAccountNode, GenericNode,
} from "./components/nodes";
import { RelationshipEdge } from "./components/edges/RelationshipEdge";
import { GraphToolbar } from "./components/GraphToolbar";
import { NodeDetailPanel } from "./components/NodeDetailPanel";
import { GraphStatusBar } from "./components/GraphStatusBar";
import { NodeContextMenu } from "./components/NodeContextMenu";
import { useGraphNodes, useNodeSelection, useNodeSearch, useNodeFilters, usePathFinding } from "./hooks";
import { useGraphLayout } from "./useGraphLayout";
import { Card, CardBody } from "@/shared/components/Card";
import { EmptyState } from "@/shared/components/EmptyState";
import type { OsintNodeData, LayoutType, NodeType } from "./types";

const nodeTypes: NodeTypes = {
  person: PersonNode,
  company: CompanyNode,
  email: EmailNode,
  phone: PhoneNode,
  username: UsernameNode,
  ip: IPNode,
  domain: DomainNode,
  service: ServiceNode,
  location: LocationNode,
  vulnerability: VulnerabilityNode,
  breach: BreachNode,
  subdomain: SubdomainNode,
  port: PortNode,
  certificate: CertificateNode,
  asn: ASNNode,
  url: URLNode,
  hash: HashNode,
  address: AddressNode,
  bank_account: BankAccountNode,
  // Fallback types map to GenericNode
  regon: GenericNode,
  nip: GenericNode,
  online_service: GenericNode,
  input: GenericNode,
};

const edgeTypes: EdgeTypes = {
  relationship: RelationshipEdge,
};

/** Color map for minimap and status bar */
const NODE_COLOR_MAP: Record<string, string> = {
  person: "#818cf8", company: "#22d3d0", email: "#34d399",
  phone: "#fbbf24", username: "#a78bfa", ip: "#f87171", domain: "#60a5fa",
  service: "#f472b6", location: "#fb923c", vulnerability: "#ef4444",
  breach: "#dc2626", subdomain: "#38bdf8", port: "#94a3b8",
  certificate: "#a78bfa", asn: "#64748b", url: "#2dd4bf",
  hash: "#a3a3a3", address: "#fb923c", bank_account: "#eab308",
  regon: "#78716c", nip: "#78716c", online_service: "#c084fc", input: "#6366f1",
};

function GraphExplorer({ investigationId }: { investigationId: string }) {
  const navigate = useNavigate();
  const [currentLayout, setCurrentLayout] = useState<LayoutType>("force");
  const { applyLayout } = useGraphLayout();

  const { nodes, edges, setNodes, setEdges, onNodesChange, onEdgesChange, isLoading } =
    useGraphNodes(investigationId);

  const { selectedNodeId, selectNode } = useNodeSelection();
  const { query: searchQuery, setQuery: setSearchQuery } = useNodeSearch(setNodes);
  const { visibleTypes, toggleType, minConfidence, setMinConfidence } = useNodeFilters();
  const pathFinding = usePathFinding(investigationId);

  const canvasSearchRef = useRef<HTMLInputElement>(null);

  // Context menu state for right-click on nodes
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    nodeId: string;
    nodeLabel: string;
    nodeType: string;
  } | null>(null);

  // Apply layout
  const handleLayoutChange = useCallback(
    (layout: LayoutType) => {
      setCurrentLayout(layout);
      setNodes((prev) => applyLayout(prev, edges, layout));
    },
    [applyLayout, edges, setNodes],
  );

  // Filter nodes
  const filteredNodes = useMemo(
    () =>
      nodes.filter(
        (n) =>
          visibleTypes.has(n.data.type) &&
          n.data.confidence >= minConfidence,
      ),
    [nodes, visibleTypes, minConfidence],
  );

  const filteredNodeIds = useMemo(() => new Set(filteredNodes.map((n) => n.id)), [filteredNodes]);
  const filteredEdges = useMemo(
    () => edges.filter((e) => filteredNodeIds.has(e.source) && filteredNodeIds.has(e.target)),
    [edges, filteredNodeIds],
  );

  // Selected node data
  const selectedNodeData = useMemo(
    () => (selectedNodeId ? nodes.find((n) => n.id === selectedNodeId)?.data ?? null : null),
    [selectedNodeId, nodes],
  );

  const connectedNodes = useMemo(() => {
    if (!selectedNodeId) return [];
    return edges
      .filter((e) => e.source === selectedNodeId || e.target === selectedNodeId)
      .map((e) => {
        const otherId = e.source === selectedNodeId ? e.target : e.source;
        const other = nodes.find((n) => n.id === otherId);
        return {
          id: otherId,
          type: other?.data.type ?? "person",
          label: other?.data.label ?? otherId,
          relation: e.data?.label ?? "connected",
        };
      });
  }, [selectedNodeId, edges, nodes]);

  // Export graph data as JSON
  const handleExportJSON = useCallback(() => {
    const graphData = { nodes: filteredNodes, edges: filteredEdges };
    const blob = new Blob([JSON.stringify(graphData, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "graph-export.json";
    a.click();
    URL.revokeObjectURL(url);
  }, [filteredNodes, filteredEdges]);

  // Export graph data as CSV
  const handleExportCSV = useCallback(() => {
    const headers = ["id", "type", "label", "confidence", "sources"];
    const rows = filteredNodes.map((n) => [
      n.data.id, n.data.type, `"${n.data.label}"`, String(n.data.confidence), `"${n.data.sources.join(";")}"`,
    ]);
    const csv = [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "graph-export.csv";
    a.click();
    URL.revokeObjectURL(url);
  }, [filteredNodes]);

  // Export as PNG using canvas
  const handleExportPNG = useCallback(() => {
    const svgEl = document.querySelector<SVGElement>(".react-flow__viewport");
    if (!svgEl) return;
    // Use html2canvas-style approach: serialize the viewport to an image
    // For simplicity, download JSON as fallback; a full PNG export requires html-to-image library
    handleExportJSON();
  }, [handleExportJSON]);

  // Select all nodes by type
  const handleSelectByType = useCallback(
    (type: NodeType) => {
      setNodes((prev) =>
        prev.map((n) => ({
          ...n,
          data: { ...n.data, isSelected: n.data.type === type, isDimmed: n.data.type !== type },
        })),
      );
    },
    [setNodes],
  );

  // Clear type selection
  const handleClearSelection = useCallback(() => {
    setNodes((prev) =>
      prev.map((n) => ({
        ...n,
        data: { ...n.data, isSelected: false, isDimmed: false },
      })),
    );
  }, [setNodes]);

  // Hide a specific node
  const handleHideNode = useCallback(
    (nodeId: string) => {
      setNodes((prev) => prev.filter((n) => n.id !== nodeId));
      setEdges((prev) => prev.filter((e) => e.source !== nodeId && e.target !== nodeId));
    },
    [setNodes, setEdges],
  );

  // Remove a specific node
  const handleRemoveNode = useCallback(
    (nodeId: string) => {
      setNodes((prev) => prev.filter((n) => n.id !== nodeId));
      setEdges((prev) => prev.filter((e) => e.source !== nodeId && e.target !== nodeId));
      if (selectedNodeId === nodeId) selectNode(null);
    },
    [setNodes, setEdges, selectedNodeId, selectNode],
  );

  // Handle right-click context menu on nodes
  const onNodeContextMenu = useCallback(
    (e: React.MouseEvent, node: Node<OsintNodeData>) => {
      e.preventDefault();
      setContextMenu({
        x: e.clientX,
        y: e.clientY,
        nodeId: node.id,
        nodeLabel: node.data.label,
        nodeType: node.data.type,
      });
    },
    [],
  );

  const handlePentestThisTarget = useCallback(
    (_nodeId: string, nodeLabel: string, nodeType: string) => {
      navigate("/pentest/engagements/new", {
        state: {
          prefilled_target: { type: nodeType, value: nodeLabel },
          osint_investigation_id: investigationId,
        },
      });
    },
    [navigate, investigationId],
  );

  // Handle node click
  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node<OsintNodeData>) => {
      if (pathFinding.isActive) {
        pathFinding.selectPathNode(node.id);
      } else {
        selectNode(node.id);
      }
    },
    [pathFinding, selectNode],
  );

  // Node type counts for status bar
  const typeCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    filteredNodes.forEach((n) => {
      counts[n.data.type] = (counts[n.data.type] || 0) + 1;
    });
    return counts;
  }, [filteredNodes]);

  // Match count for the canvas search overlay
  const matchCount = useMemo(() => {
    if (!searchQuery) return filteredNodes.length;
    return filteredNodes.filter((n) => !n.data.isDimmed).length;
  }, [filteredNodes, searchQuery]);

  // Keyboard shortcuts
  const { zoomIn, zoomOut, fitView } = useReactFlow();

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;

      switch (e.key) {
        case "Escape":
          if (searchQuery) {
            setSearchQuery("");
          } else {
            selectNode(null);
            pathFinding.cancelPathFinding();
            handleClearSelection();
          }
          break;
        case "+":
        case "=":
          zoomIn();
          break;
        case "-":
          zoomOut();
          break;
        case "f":
          if (e.ctrlKey || e.metaKey) {
            e.preventDefault();
            canvasSearchRef.current?.focus();
          } else {
            fitView({ padding: 0.2 });
          }
          break;
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [selectNode, pathFinding, zoomIn, zoomOut, fitView, handleClearSelection, searchQuery, setSearchQuery]);

  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col">
      {/* Header */}
      <div className="mb-2 flex items-center gap-3">
        <button
          onClick={() => navigate(`/investigations/${investigationId}`)}
          className="rounded-md p-1 transition-colors hover:bg-bg-overlay"
        >
          <ArrowLeft className="h-5 w-5" style={{ color: "var(--text-secondary)" }} />
        </button>
        <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>
          Knowledge Graph
        </h1>
      </div>

      {/* Toolbar */}
      <GraphToolbar
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        layout={currentLayout}
        onLayoutChange={handleLayoutChange}
        visibleTypes={visibleTypes}
        onToggleType={toggleType}
        minConfidence={minConfidence}
        onConfidenceChange={setMinConfidence}
        pathFindingActive={pathFinding.isActive}
        onStartPathFinding={pathFinding.startPathFinding}
        onCancelPathFinding={pathFinding.cancelPathFinding}
        pathSourceId={pathFinding.sourceId}
        pathTargetId={pathFinding.targetId}
        onExportJSON={handleExportJSON}
        onExportCSV={handleExportCSV}
        onExportPNG={handleExportPNG}
        onSelectByType={handleSelectByType}
        onClearSelection={handleClearSelection}
        availableTypes={Object.keys(typeCounts) as NodeType[]}
      />

      {/* Graph canvas */}
      {filteredNodes.length === 0 && !isLoading ? (
        <Card className="flex-1">
          <CardBody className="flex h-full items-center justify-center">
            <EmptyState
              variant="no-data"
              title="No graph data yet"
              description="Run a scan on this investigation to see the knowledge graph populate with discovered entities and relationships."
            />
          </CardBody>
        </Card>
      ) : (
        <div className="relative mt-2 flex-1 overflow-hidden rounded-lg border" style={{ borderColor: "var(--border-subtle)" }}>
          {/* Floating canvas search bar */}
          <div
            style={{
              position: "absolute",
              top: 12,
              left: "50%",
              transform: "translateX(-50%)",
              zIndex: 10,
            }}
          >
            <div
              className="flex items-center gap-2 rounded-lg px-3 py-1.5 shadow-lg"
              style={{
                background: "var(--bg-surface)",
                border: "1px solid var(--border-default)",
                minWidth: 260,
              }}
            >
              <Search className="h-3.5 w-3.5 shrink-0" style={{ color: "var(--text-tertiary)" }} />
              <input
                ref={canvasSearchRef}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Filter nodes by label or type..."
                className="flex-1 bg-transparent text-xs outline-none"
                style={{ color: "var(--text-primary)" }}
              />
              {searchQuery && (
                <>
                  <span
                    className="shrink-0 text-xs font-medium tabular-nums"
                    style={{ color: "var(--text-tertiary)" }}
                  >
                    {matchCount} / {filteredNodes.length}
                  </span>
                  <button
                    onClick={() => setSearchQuery("")}
                    className="shrink-0 rounded p-0.5 transition-colors hover:bg-bg-overlay"
                    aria-label="Clear search"
                  >
                    <X className="h-3 w-3" style={{ color: "var(--text-tertiary)" }} />
                  </button>
                </>
              )}
            </div>
          </div>

          <ReactFlow
            nodes={filteredNodes}
            edges={filteredEdges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            onNodeClick={onNodeClick}
            onNodeContextMenu={onNodeContextMenu}
            onPaneClick={() => { selectNode(null); pathFinding.cancelPathFinding(); setContextMenu(null); }}
            fitView
            fitViewOptions={{ padding: 0.2 }}
            minZoom={0.1}
            maxZoom={3}
            defaultEdgeOptions={{ type: "relationship" }}
            proOptions={{ hideAttribution: true }}
          >
            <Background
              gap={24}
              color="var(--border-subtle)"
              style={{ background: "var(--bg-base)" }}
            />
            <MiniMap
              nodeColor={(node) => NODE_COLOR_MAP[node.data?.type] ?? "#4e5566"}
              maskColor="rgba(10, 11, 13, 0.8)"
              style={{ background: "var(--bg-elevated)" }}
            />
          </ReactFlow>

          {/* Node right-click context menu */}
          {contextMenu && (
            <NodeContextMenu
              x={contextMenu.x}
              y={contextMenu.y}
              nodeId={contextMenu.nodeId}
              nodeLabel={contextMenu.nodeLabel}
              nodeType={contextMenu.nodeType}
              onClose={() => setContextMenu(null)}
              onExpand={(id) => selectNode(id)}
              onStartPathFrom={(_id) => pathFinding.startPathFinding()}
              onCopyValue={(value) => navigator.clipboard.writeText(value)}
              onHideNode={handleHideNode}
              onRemoveNode={handleRemoveNode}
              onPentestThis={handlePentestThisTarget}
            />
          )}

          {/* Node detail panel */}
          <NodeDetailPanel
            node={selectedNodeData}
            connectedNodes={connectedNodes}
            onClose={() => selectNode(null)}
            onExpandNode={(id) => { selectNode(id); }}
          />
        </div>
      )}

      {/* Status bar */}
      <GraphStatusBar
        nodeCount={filteredNodes.length}
        edgeCount={filteredEdges.length}
        typeCounts={typeCounts}
        nodeColors={NODE_COLOR_MAP}
      />
    </div>
  );
}

export function GraphPage() {
  const { id } = useParams();
  if (!id) return null;

  return (
    <ReactFlowProvider>
      <GraphExplorer investigationId={id} />
    </ReactFlowProvider>
  );
}
