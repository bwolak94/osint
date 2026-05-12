export type SourceType = 'breach' | 'social' | 'paste' | 'stealer' | 'public_record'

export type Severity = 'low' | 'medium' | 'high' | 'critical'

export type RiskScore = 'low' | 'medium' | 'high' | 'critical'

export type ReportStatus = 'queued' | 'running' | 'completed' | 'failed'

export interface GdprSubjectRequest {
  full_name: string
  email: string
  phone?: string
  include_breach_check: boolean
  include_social_scan: boolean
  include_paste_check: boolean
  include_stealer_logs: boolean
  requester_reference?: string
}

export interface ExposureSource {
  source_type: SourceType
  source_name: string
  found_data: string[]
  severity: Severity
  date_found: string | null
}

export interface GdprReport {
  report_id: string
  status: ReportStatus
  subject_name: string
  subject_email: string
  created_at: string
  completed_at: string | null
  exposure_sources: ExposureSource[]
  total_exposures: number
  risk_score: RiskScore
  summary: string
  recommended_actions: string[]
  requester_reference: string | null
}
