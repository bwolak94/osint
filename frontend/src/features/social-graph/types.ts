export interface GraphNode {
  id: string;
  label: string;
  type: "person" | "organization" | "location" | "email" | "username" | "phone";
  platform: string | null;
  connections: number;
  risk_score: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  relationship: string;
  weight: number;
  platforms: string[];
}

export interface SocialGraphResult {
  seed: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  total_connections: number;
  platforms_covered: string[];
  depth_reached: number;
}
