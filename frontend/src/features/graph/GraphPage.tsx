import { useState, useMemo, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import ReactFlow, { Background, MiniMap, ReactFlowProvider, type NodeTypes, type EdgeTypes, type Node } from "reactflow";
import "reactflow/dist/style.css";
import { ArrowLeft } from "lucide-react";

import { PersonNode, CompanyNode, EmailNode, PhoneNode, UsernameNode, IPNode, DomainNode } from "./components/nodes";
import { RelationshipEdge } from "./components/edges/RelationshipEdge";
import { GraphToolbar } from "./components/GraphToolbar";
import { NodeDetailPanel } from "./components/NodeDetailPanel";
import { GraphStatusBar } from "./components/GraphStatusBar";
import { useGraphNodes, useNodeSelection, useNodeSearch, useNodeFilters, usePathFinding } from "./hooks";
import { useGraphLayout } from "./useGraphLayout";
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
      />

      {/* Graph canvas */}
      <div className="relative mt-2 flex-1 overflow-hidden rounded-lg border" style={{ borderColor: "var(--border-subtle)" }}>
        <ReactFlow
          nodes={filteredNodes}
          edges={filteredEdges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          onNodeClick={onNodeClick}
          onPaneClick={() => { selectNode(null); pathFinding.cancelPathFinding(); }}
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

        {/* Node detail panel */}
        <NodeDetailPanel
          node={selectedNodeData}
          connectedNodes={connectedNodes}
          onClose={() => selectNode(null)}
          onExpandNode={(id) => { selectNode(id); }}
        />
      </div>

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
