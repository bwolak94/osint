import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from '@/shared/components/Toast'
import { redTeamApi } from './api'
import type { ReportFinding } from './types'

const KEY = 'redteam'

// ─── Scan mutations ───────────────────────────────────────────────────────────

export function useJWTAudit() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ targetUrl, token }: { targetUrl: string; token?: string }) =>
      redTeamApi.runJWTAudit(targetUrl, token),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [KEY, 'history'] })
      toast.success('JWT audit completed')
    },
    onError: (e: Error) => toast.error(e.message ?? 'JWT audit failed'),
  })
}

export function useAWSIAMAudit() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (domain: string) => redTeamApi.runAWSIAMAudit(domain),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [KEY, 'history'] })
      toast.success('AWS IAM audit completed')
    },
    onError: (e: Error) => toast.error(e.message ?? 'AWS IAM audit failed'),
  })
}

export function useCloudHunt() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ domain, providers }: { domain: string; providers: string[] }) =>
      redTeamApi.runCloudHunt(domain, providers),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [KEY, 'history'] })
      toast.success('Cloud storage hunt completed')
    },
    onError: (e: Error) => toast.error(e.message ?? 'Cloud hunt failed'),
  })
}

export function useCICDScan() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (url: string) => redTeamApi.runCICDScan(url),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [KEY, 'history'] })
      toast.success('CI/CD scan completed')
    },
    onError: (e: Error) => toast.error(e.message ?? 'CI/CD scan failed'),
  })
}

export function useIaCLint() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ content, fileType }: { content: string; fileType: string }) =>
      redTeamApi.runIaCLint(content, fileType),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [KEY, 'history'] })
      toast.success('IaC lint completed')
    },
    onError: (e: Error) => toast.error(e.message ?? 'IaC lint failed'),
  })
}

export function useAPIScan() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (url: string) => redTeamApi.runAPIScan(url),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [KEY, 'history'] })
      toast.success('API scan completed')
    },
    onError: (e: Error) => toast.error(e.message ?? 'API scan failed'),
  })
}

export function useKerberoast() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (domain: string) => redTeamApi.runKerberoast(domain),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [KEY, 'history'] })
      toast.success('Kerberoast scan completed')
    },
    onError: (e: Error) => toast.error(e.message ?? 'Kerberoast scan failed'),
  })
}

export function useContainerEscape() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (target: string) => redTeamApi.runContainerEscape(target),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [KEY, 'history'] })
      toast.success('Container escape audit completed')
    },
    onError: (e: Error) => toast.error(e.message ?? 'Container escape audit failed'),
  })
}

export function useADCSAbuse() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (domain: string) => redTeamApi.runADCSAbuse(domain),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [KEY, 'history'] })
      toast.success('AD CS abuse check completed')
    },
    onError: (e: Error) => toast.error(e.message ?? 'AD CS abuse check failed'),
  })
}

export function useGraphQLAudit() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ url, maxDepth }: { url: string; maxDepth: number }) =>
      redTeamApi.runGraphQLAudit(url, maxDepth),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [KEY, 'history'] })
      toast.success('GraphQL audit completed')
    },
    onError: (e: Error) => toast.error(e.message ?? 'GraphQL audit failed'),
  })
}

export function useDanglingDNS() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (domain: string) => redTeamApi.runDanglingDNS(domain),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [KEY, 'history'] })
      toast.success('Dangling DNS scan completed')
    },
    onError: (e: Error) => toast.error(e.message ?? 'Dangling DNS scan failed'),
  })
}

export function useThreatIntel() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (target: string) => redTeamApi.runThreatIntel(target),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [KEY, 'history'] })
      toast.success('Threat intel aggregation completed')
    },
    onError: (e: Error) => toast.error(e.message ?? 'Threat intel aggregation failed'),
  })
}

export function useMitreTechniqueMapper() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (techniques: string[]) => redTeamApi.mapMitreTechniques(techniques),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [KEY, 'history'] })
      toast.success('MITRE mapping completed')
    },
    onError: (e: Error) => toast.error(e.message ?? 'MITRE mapping failed'),
  })
}

export function useGenerateOSCPReport() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      investigationId,
      findings,
    }: {
      investigationId: string
      findings: ReportFinding[]
    }) => redTeamApi.generateOSCPReport(investigationId, findings),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [KEY, 'history'] })
      toast.success('OSCP report generated')
    },
    onError: (e: Error) => toast.error(e.message ?? 'Report generation failed'),
  })
}

// Generic hook for any module by key
export function useRedTeamScan(module: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      import('@/shared/api/client').then(({ apiClient }) =>
        apiClient.post(`/redteam/${module}`, payload).then((r) => r.data),
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [KEY, 'history'] })
      toast.success(`${module} scan completed`)
    },
    onError: (e: Error) => toast.error(e.message ?? 'Scan failed'),
  })
}

// ─── History query ────────────────────────────────────────────────────────────

export function useModuleHistory(moduleId: number, page = 1, pageSize = 10) {
  return useQuery({
    queryKey: [KEY, 'history', moduleId, page, pageSize],
    queryFn: () => redTeamApi.listHistory(moduleId, page, pageSize),
  })
}
