import { apiClient } from '@/shared/api/client'
import type {
  ReportSection,
  ReportTemplate,
  SaveTemplateRequest,
  BuildReportRequest,
  BuildReportResponse,
} from './types'

export const reportBuilderApi = {
  getSections: (): Promise<ReportSection[]> =>
    apiClient.get<ReportSection[]>('/report-builder/sections').then((r) => r.data),

  getTemplates: (): Promise<ReportTemplate[]> =>
    apiClient.get<ReportTemplate[]>('/report-builder/templates').then((r) => r.data),

  saveTemplate: (body: SaveTemplateRequest): Promise<ReportTemplate> =>
    apiClient.post<ReportTemplate>('/report-builder/templates', body).then((r) => r.data),

  deleteTemplate: (id: string): Promise<void> =>
    apiClient.delete(`/report-builder/templates/${id}`).then(() => undefined),

  buildReport: (body: BuildReportRequest): Promise<BuildReportResponse> =>
    apiClient.post<BuildReportResponse>('/report-builder/build', body).then((r) => r.data),
}
