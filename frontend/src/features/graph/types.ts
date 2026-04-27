export type NodeType =
  | "person" | "company" | "email" | "phone" | "username" | "ip" | "domain"
  | "service" | "location" | "vulnerability" | "breach" | "subdomain"
  | "port" | "certificate" | "asn" | "url" | "hash" | "address"
  | "bank_account" | "regon" | "nip" | "online_service" | "input";

export type RelationType =
  | "owns" | "uses" | "member_of" | "connected_to" | "registered_to"
  | "employed_by" | "alias_of" | "resolves_to" | "has_port" | "has_vulnerability"
  | "has_subdomain" | "hosts" | "located_in" | "exposed_in" | "has_certificate"
  | "belongs_to_asn" | "has_profile" | "registered_on" | "has_mx" | "has_ns"
  | "uses_nameserver" | "registered_with" | "runs_service" | "mentioned_on"
  | "found_in_paste" | "identifies" | "has_regon" | "has_address"
  | "has_bank_account" | "has_backup";

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
  /** Maltego-style: number of child entities discovered via transforms */
  childCount?: number;
  /** Weight/importance for sizing */
  weight?: number;
}

export interface OsintEdgeData {
  label: string;
  relationType: RelationType;
  confidence: number;
  validFrom?: string | null;
  validTo?: string | null;
  isOnPath: boolean;
  /** Number of edges bundled into this edge when more than 4 parallel edges exist. */
  bundleCount?: number;
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

export type LayoutType = "force" | "hierarchical" | "circular" | "radial" | "block" | "manual";
