import { useState, useCallback, useMemo, useDeferredValue, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNodesState, useEdgesState, useReactFlow, type Node, type Edge } from "reactflow";
import { apiClient } from "@/shared/api/client";
import type {
  GraphApiResponse, GraphApiNode, GraphApiEdge, OsintNodeData, OsintEdgeData,
  NodeType, LayoutType, PathApiResponse,
} from "./types";

// Transform API data to ReactFlow format
function apiNodeToReactFlow(n: GraphApiNode, index: number): Node<OsintNodeData> {
  const angle = (index / 20) * 2 * Math.PI;
  const radius = 300;
  return {
    id: n.id,
    type: n.type as NodeType,
    position: { x: n.x ?? Math.cos(angle) * radius, y: n.y ?? Math.sin(angle) * radius },
    data: {
      id: n.id,
      type: n.type as NodeType,
      label: n.label,
      confidence: n.confidence,
      sources: n.sources,
      properties: n.properties,
      isSelected: false,
      isDimmed: false,
      isOnPath: false,
    },
  };
}

function apiEdgeToReactFlow(e: GraphApiEdge): Edge<OsintEdgeData> {
  return {
    id: e.id,
    source: e.source,
    target: e.target,
    type: "relationship",
    data: {
      label: e.label || e.type,
      relationType: e.type as any,
      confidence: e.confidence,
      validFrom: e.valid_from,
      validTo: e.valid_to,
      isOnPath: false,
    },
  };
}

export function useGraphData(investigationId: string) {
  return useQuery({
    queryKey: ["graph", investigationId],
    queryFn: async () => {
      const res = await apiClient.get<GraphApiResponse>(
        `/investigations/${investigationId}/graph`,
      );
      return res.data;
    },
    enabled: !!investigationId,
  });
}

export function useGraphNodes(investigationId: string) {
  const { data, isLoading } = useGraphData(investigationId);

  const initialNodes = useMemo(
    () => (data?.nodes ?? []).map((n, i) => apiNodeToReactFlow(n, i)),
    [data?.nodes],
  );

  const initialEdges = useMemo(
    () => (data?.edges ?? []).map(apiEdgeToReactFlow),
    [data?.edges],
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // Sync when data changes
  useEffect(() => {
    if (initialNodes.length > 0) setNodes(initialNodes);
  }, [initialNodes, setNodes]);

  useEffect(() => {
    if (initialEdges.length > 0) setEdges(initialEdges);
  }, [initialEdges, setEdges]);

  return { nodes, edges, setNodes, setEdges, onNodesChange, onEdgesChange, isLoading, meta: data?.meta };
}

export function useNodeSelection() {
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  const selectNode = useCallback((nodeId: string | null) => {
    setSelectedNodeId(nodeId);
  }, []);

  return { selectedNodeId, selectNode };
}

export function useNodeSearch(setNodes: (updater: (nodes: Node<OsintNodeData>[]) => Node<OsintNodeData>[]) => void) {
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query);

  useEffect(() => {
    setNodes((nodes) =>
      nodes.map((n) => ({
        ...n,
        data: {
          ...n.data,
          isDimmed: deferredQuery
            ? !n.data.label.toLowerCase().includes(deferredQuery.toLowerCase())
            : false,
        },
      })),
    );
  }, [deferredQuery, setNodes]);

  return { query, setQuery };
}

export function useNodeFilters() {
  const [visibleTypes, setVisibleTypes] = useState<Set<NodeType>>(
    new Set(["person", "company", "email", "phone", "username", "ip", "domain"]),
  );
  const [minConfidence, setMinConfidence] = useState(0);

  const toggleType = useCallback((type: NodeType) => {
    setVisibleTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  }, []);

  return { visibleTypes, toggleType, minConfidence, setMinConfidence };
}

export function usePathFinding(investigationId: string) {
  const [isActive, setIsActive] = useState(false);
  const [sourceId, setSourceId] = useState<string | null>(null);
  const [targetId, setTargetId] = useState<string | null>(null);

  const { data: pathData } = useQuery({
    queryKey: ["paths", investigationId, sourceId, targetId],
    queryFn: async () => {
      const res = await apiClient.get<PathApiResponse>(
        `/investigations/${investigationId}/graph/paths`,
        { params: { from: sourceId, to: targetId } },
      );
      return res.data;
    },
    enabled: !!(isActive && sourceId && targetId),
  });

  const startPathFinding = useCallback(() => {
    setIsActive(true);
    setSourceId(null);
    setTargetId(null);
  }, []);

  const selectPathNode = useCallback(
    (nodeId: string) => {
      if (!isActive) return;
      if (!sourceId) setSourceId(nodeId);
      else if (!targetId) setTargetId(nodeId);
    },
    [isActive, sourceId, targetId],
  );

  const cancelPathFinding = useCallback(() => {
    setIsActive(false);
    setSourceId(null);
    setTargetId(null);
  }, []);

  return {
    isActive, sourceId, targetId, paths: pathData?.paths ?? [],
    startPathFinding, selectPathNode, cancelPathFinding,
  };
}
