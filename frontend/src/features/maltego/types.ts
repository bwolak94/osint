export interface MaltegoEntity {
  type: string
  value: string
  properties: Record<string, unknown>
}

export interface MaltegoTransformRequest {
  entity: MaltegoEntity
  transform_name: string
  limit?: number
}

export interface MaltegoTransformResponse {
  entities: MaltegoEntity[]
  messages: string[]
  error: string | null
}

export interface TransformConfig {
  transform_name: string
  display_name: string
  entity_type: string
  description: string
  scanner_type: string
}

export interface ItdsTransform {
  name: string
  displayName: string
  abstract: string
  template: boolean
  visibility: string
  description: string
  author: string
  requireDisplayInfo: boolean
  entityType: string
  uiTemplate: string
  jasperPrint: string
  url: string
  inputConstraint: string
  outputEntities: unknown[]
  defaultSets: string[]
  oauth: null
}

export interface ItdsSet {
  name: string
  description: string
}

export interface ItdsConfig {
  transforms: ItdsTransform[]
  sets: ItdsSet[]
}
