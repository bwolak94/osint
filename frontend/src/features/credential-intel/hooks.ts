import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { credentialIntelApi } from './api'
import type { CredentialIntelRequest } from './types'

const KEYS = {
  list: (page: number, ps: number) => ['cred-intel', 'list', page, ps] as const,
}

export function useRunCredentialIntel() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (req: CredentialIntelRequest) => credentialIntelApi.run(req),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['cred-intel', 'list'] }),
  })
}

export function useCredentialIntelHistory(page: number, pageSize = 20) {
  return useQuery({
    queryKey: KEYS.list(page, pageSize),
    queryFn: () => credentialIntelApi.list(page, pageSize),
  })
}

export function useDeleteCredentialIntel() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => credentialIntelApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['cred-intel', 'list'] }),
  })
}
