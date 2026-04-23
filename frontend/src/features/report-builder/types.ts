export interface ReportSection {
  id: string
  name: string
  description: string
  required: boolean
  order: number
}

export interface ReportTemplate {
  id: string
  name: string
  sections: string[]
  created_at: string
}

export interface SaveTemplateRequest {
  name: string
  sections: string[]
}

export type ReportFormat = 'pdf' | 'html' | 'docx'

export type ReportClassification = 'UNCLASSIFIED' | 'CONFIDENTIAL' | 'SECRET'

export interface BuildReportRequest {
  investigation_id: string
  sections: string[]
  format: ReportFormat
  template_id?: string
  title?: string
  classification?: ReportClassification
}

export interface BuildReportResponse {
  report_id: string
  status: 'queued'
}
