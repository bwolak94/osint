import { apiClient } from '@/shared/api/client'
import type { TransformConfig, ItdsConfig, MaltegoTransformRequest, MaltegoTransformResponse } from './types'

export const maltegoApi = {
  listTransforms: (): Promise<TransformConfig[]> =>
    apiClient.get<TransformConfig[]>('/maltego/transforms').then((r) => r.data),

  getItdsConfig: (): Promise<ItdsConfig> =>
    apiClient.get<ItdsConfig>('/maltego/transforms/itds').then((r) => r.data),

  runTransform: (req: MaltegoTransformRequest): Promise<MaltegoTransformResponse> =>
    apiClient
      .post<MaltegoTransformResponse>('/maltego/transform', req)
      .then((r) => r.data),
}
