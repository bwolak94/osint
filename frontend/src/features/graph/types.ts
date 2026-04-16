export type NodeType = "person" | "company" | "email" | "phone" | "username" | "ip" | "domain";

export type RelationType = "owns" | "uses" | "member_of" | "connected_to" | "registered_to" | "employed_by" | "alias_of";

export interface OsintNodeData {
  id: string;
  type: NodeType;
  label: string;
  confidence: number;
  sources: string[];
  properties: Record<string, unknown>;
  isSelected: boolean;
  isDimmed: boolean;
  isOnPath: boolean;
}

export interface OsintEdgeData {
  label: string;
  relationType: RelationType;
  confidence: number;
  validFrom?: string | null;
  validTo?: string | null;
  isOnPath: boolean;
}

export interface GraphApiNode {
  id: string;
  type: string;
  label: string;
  properties: Record<string, unknown>;
  confidence: number;
  sources: string[];
  x?: number | null;
  y?: number | null;
}

export interface GraphApiEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  label: string;
  confidence: number;
  valid_from?: string | null;
  valid_to?: string | null;
}

export interface GraphApiResponse {
  nodes: GraphApiNode[];
  edges: GraphApiEdge[];
  meta: { node_count: number; edge_count: number; density: number };
}

export interface PathApiResponse {
  paths: GraphApiNode[][];
  path_count: number;
}

export type LayoutType = "force" | "hierarchical" | "circular" | "manual";
