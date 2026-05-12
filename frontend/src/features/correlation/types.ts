export interface CorrelationMatch {
  id: string;
  type: string;
  confidence: number;
  source_value: string;
  target_value: string;
  evidence: string[];
  source_types: string[];
}

export interface CorrelationResult {
  inputs: string[];
  total_matches: number;
  high_confidence_matches: number;
  matches: CorrelationMatch[];
  entity_clusters: Array<{ cluster_id: string; entities: string[]; confidence: number; label: string }>;
  timeline: Array<{ date: string; event: string; type: string }>;
}
