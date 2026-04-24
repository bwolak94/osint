import { apiClient } from '@/shared/api/client'
import type { DeepResearchRequest, DeepResearchResult } from './types'

export const deepResearchApi = {
  run: (body: DeepResearchRequest): Promise<DeepResearchResult> =>
    apiClient.post<DeepResearchResult>('/deep-research/run', body).then((r) => r.data),
}
