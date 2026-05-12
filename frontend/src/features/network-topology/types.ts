export interface NetworkNode {
  id: string;
  ip: string;
  hostname: string | null;
  type: "router" | "switch" | "server" | "workstation" | "firewall" | "printer" | "unknown";
  os: string | null;
  open_ports: number[];
  services: string[];
  subnet: string;
  risk_score: number;
  vulnerabilities_count: number;
}

export interface NetworkEdge {
  source: string;
  target: string;
  relationship: string;
  protocol: string | null;
}

export interface NetworkTopologyResult {
  target_network: string;
  nodes: NetworkNode[];
  edges: NetworkEdge[];
  subnets: string[];
  total_hosts: number;
  live_hosts: number;
  services_found: Record<string, number>;
  scan_duration_ms: number;
}
