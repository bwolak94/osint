import { useCallback, useMemo } from "react";
import { useParams } from "react-router-dom";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
} from "reactflow";
import "reactflow/dist/style.css";
import { useGraphData } from "./hooks";
import { LoadingSpinner } from "@/shared/components/LoadingSpinner";

export function GraphPage() {
  const { id } = useParams<{ id: string }>();
  const { data: graphData, isLoading } = useGraphData(id!);

  // Convert API graph data to ReactFlow nodes and edges
  const initialNodes: Node[] = useMemo(
    () =>
      graphData?.nodes.map((node) => ({
        id: node.id,
        type: "default",
        position: node.position,
        data: { label: node.label },
        style: {
          background: "#1e1e2e",
          color: "#e5e5e5",
          border: "1px solid #374151",
          borderRadius: "8px",
          padding: "10px",
        },
      })) ?? [],
    [graphData],
  );

  const initialEdges: Edge[] = useMemo(
    () =>
      graphData?.edges.map((edge) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        label: edge.label,
        style: { stroke: "#6366f1" },
        labelStyle: { fill: "#a1a1aa", fontSize: 12 },
      })) ?? [],
    [graphData],
  );

  const [nodes, , onNodesChange] = useNodesState(initialNodes);
  const [edges, , onEdgesChange] = useEdgesState(initialEdges);

  const onInit = useCallback(() => {
    // Graph initialized
  }, []);

  if (isLoading) return <LoadingSpinner />;

  return (
    <div className="h-[calc(100vh-4rem)] w-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onInit={onInit}
        fitView
        attributionPosition="bottom-left"
      >
        <Background color="#374151" gap={16} />
        <Controls />
        <MiniMap
          nodeStrokeColor="#6366f1"
          nodeColor="#1e1e2e"
          maskColor="rgba(0, 0, 0, 0.7)"
        />
      </ReactFlow>
    </div>
  );
}
