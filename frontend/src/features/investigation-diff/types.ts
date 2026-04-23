export type ChangeType = 'added' | 'removed' | 'modified';
export type MergeStrategy = 'union' | 'intersection';

export interface InvestigationVersion {
  version_id: string;
  created_at: string;
  node_count: number;
  edge_count: number;
  label: string;
}

export interface InvestigationVersionsResponse {
  versions: InvestigationVersion[];
}

export interface DiffEntry {
  entity_type: string;
  value: string;
  change_type: ChangeType;
  old_value?: string;
  new_value?: string;
}

export interface InvestigationDiffResponse {
  added: DiffEntry[];
  removed: DiffEntry[];
  modified: DiffEntry[];
}

export interface MergeCandidate {
  id: string;
  title: string;
  shared_entity_count: number;
  similarity_score: number;
}

export interface MergeRequest {
  source_id: string;
  target_id: string;
  strategy: MergeStrategy;
}

export interface MergeResponse {
  merged_id: string;
  merged_title: string;
  node_count: number;
  edge_count: number;
}
