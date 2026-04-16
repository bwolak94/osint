import { useState, useMemo, useCallback, useRef, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import ReactFlow, { Background, MiniMap, ReactFlowProvider, useReactFlow, type NodeTypes, type EdgeTypes, type Node } from "reactflow";
import "reactflow/dist/style.css";
import { ArrowLeft } from "lucide-react";

import { PersonNode, CompanyNode, EmailNode, PhoneNode, UsernameNode, IPNode, DomainNode } from "./components/nodes";
import { RelationshipEdge } from "./components/edges/RelationshipEdge";
import { GraphToolbar } from "./components/GraphToolbar";
import { NodeDetailPanel } from "./components/NodeDetailPanel";
import { GraphStatusBar } from "./components/GraphStatusBar";
import { NodeContextMenu } from "./components/NodeContextMenu";
import { useGraphNodes, useNodeSelection, useNodeSearch, useNodeFilters, usePathFinding } from "./hooks";
import { useGraphLayout } from "./useGraphLayout";
import { Card, CardBody } from "@/shared/components/Card";
import { EmptyState } from "@/shared/components/EmptyState";
import type { OsintNodeData, LayoutType } from "./types";

const nodeTypes: NodeTypes = {
  person: PersonNode,
  company: CompanyNode,
  email: EmailNode,
  phone: PhoneNode,
  username: UsernameNode,
  ip: IPNode,
  domain: DomainNode,
};

const edgeTypes: EdgeTypes = {
  relationship: RelationshipEdge,
};

function GraphExplorer({ investigationId }: { investigationId: string }) {
  const navigate = useNavigate();
  const [currentLayout, setCurrentLayout] = useState<LayoutType>("force");
  const { applyLayout } = useGraphLayout();

  const { nodes, edges, setNodes, setEdges, onNodesChange, onEdgesChange, isLoading, meta } =
    useGraphNodes(investigationId);

  const { selectedNodeId, selectNode } = useNodeSelection();
  const { query: searchQuery, setQuery: setSearchQuery } = useNodeSearch(setNodes);
  const { visibleTypes, toggleType, minConfidence, setMinConfidence } = useNodeFilters();
  const pathFinding = usePathFinding(investigationId);

  // Context menu state for right-click on nodes
  const [contextMenu, setContextMenu] = useState<{x: number; y: number; nodeId: string; nodeLabel: string} | null>(null);

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
  const handleExport = useCallback(() => {
    const graphData = { nodes: filteredNodes, edges: filteredEdges };
    const blob = new Blob([JSON.stringify(graphData, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "graph-export.json";
    a.click();
    URL.revokeObjectURL(url);
  }, [filteredNodes, filteredEdges]);

  // Handle right-click context menu on nodes
  const onNodeContextMenu = useCallback(
    (e: React.MouseEvent, node: Node<OsintNodeData>) => {
      e.preventDefault();
      setContextMenu({ x: e.clientX, y: e.clientY, nodeId: node.id, nodeLabel: node.data.label });
    },
    [],
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

  // Keyboard shortcuts
  const { zoomIn, zoomOut, fitView } = useReactFlow();

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;

      switch (e.key) {
        case "Escape":
          selectNode(null);
          pathFinding.cancelPathFinding();
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
            // Focus search input
            document.querySelector<HTMLInputElement>('[placeholder*="Search"]')?.focus();
          } else {
            fitView({ padding: 0.2 });
          }
          break;
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [selectNode, pathFinding, zoomIn, zoomOut, fitView]);

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
        onExport={handleExport}
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
              nodeColor={(node) => {
                const colors: Record<string, string> = {
                  person: "#818cf8", company: "#22d3d0", email: "#34d399",
                  phone: "#fbbf24", username: "#a78bfa", ip: "#f87171", domain: "#60a5fa",
                };
                return colors[node.data?.type] ?? "#4e5566";
              }}
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
              onClose={() => setContextMenu(null)}
              onExpand={(id) => selectNode(id)}
              onStartPathFrom={(id) => pathFinding.startPathFinding()}
              onCopyValue={(value) => navigator.clipboard.writeText(value)}
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
      <GraphStatusBar nodeCount={filteredNodes.length} edgeCount={filteredEdges.length} />
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
