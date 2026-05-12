export type TLP = 'WHITE' | 'GREEN' | 'AMBER' | 'RED'
export type CampaignStatus = 'active' | 'completed' | 'archived'

export interface Campaign {
  id: string
  title: string
  description: string
  tlp: TLP
  tags: string[]
  status: CampaignStatus
  start_date: string | null
  end_date: string | null
  investigation_count: number
  created_at: string
  updated_at: string
}

export interface CampaignsListResponse {
  items: Campaign[]
  total: number
}

export interface CreateCampaignPayload {
  title: string
  description: string
  tlp: TLP
  tags: string[]
  start_date?: string | null
  end_date?: string | null
}

export interface UpdateCampaignPayload {
  title?: string
  description?: string
  tlp?: TLP
  tags?: string[]
  status?: CampaignStatus
  start_date?: string | null
  end_date?: string | null
}

export interface AddInvestigationPayload {
  investigation_id: string
}

export interface CampaignGraphResponse {
  nodes: unknown[]
  edges: unknown[]
  merged_investigation_id?: string
}

export interface SimilarCampaign {
  id: string
  title: string
  similarity_score: number
}

export interface CampaignFilters {
  status?: CampaignStatus | 'all'
  tlp?: TLP | 'all'
}
