export interface MitreTactic {
  id: string
  name: string
  shortName: string
}

export interface MitreTechnique {
  id: string
  name: string
  tacticIds: string[]
  description: string
  platforms: string[]
  isSubtechnique: boolean
  parentId?: string
}

export interface MatrixCell {
  technique: MitreTechnique
  tactic: MitreTactic
  executed: boolean
  score: number // 0–3 for colour intensity
}

export interface TechniqueDetails extends MitreTechnique {
  url: string
}
