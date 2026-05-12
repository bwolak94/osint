import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { reportBuilderApi } from './api'
import { toast } from '@/shared/components/Toast'
import type { SaveTemplateRequest, BuildReportRequest } from './types'

const SECTIONS_KEY = 'report-builder-sections'
const TEMPLATES_KEY = 'report-builder-templates'

export function useReportSections() {
  return useQuery({
    queryKey: [SECTIONS_KEY],
    queryFn: () => reportBuilderApi.getSections(),
    staleTime: 5 * 60 * 1000,
  })
}

export function useReportTemplates() {
  return useQuery({
    queryKey: [TEMPLATES_KEY],
    queryFn: () => reportBuilderApi.getTemplates(),
  })
}

export function useSaveTemplate() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: SaveTemplateRequest) => reportBuilderApi.saveTemplate(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [TEMPLATES_KEY] })
      toast.success('Template saved')
    },
    onError: (e: Error) => toast.error(e.message ?? 'Failed to save template'),
  })
}

export function useDeleteTemplate() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => reportBuilderApi.deleteTemplate(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [TEMPLATES_KEY] })
      toast.success('Template deleted')
    },
    onError: (e: Error) => toast.error(e.message ?? 'Failed to delete template'),
  })
}

export function useBuildReport() {
  return useMutation({
    mutationFn: (body: BuildReportRequest) => reportBuilderApi.buildReport(body),
    onSuccess: () => {
      toast.success('Report queued successfully')
    },
    onError: (e: Error) => toast.error(e.message ?? 'Failed to build report'),
  })
}
