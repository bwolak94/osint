export type RedTeamCategory =
  | 'CLOUD'
  | 'ACTIVE_DIRECTORY'
  | 'NETWORK'
  | 'EVASION'
  | 'FORENSICS'
  | 'REPORTING'

export type RiskLevel = 'Low' | 'Medium' | 'High' | 'Critical'

export interface RedTeamModule {
  id: number
  name: string
  description: string
  category: RedTeamCategory
  mitreAttackIds: string[]
  riskLevel: RiskLevel
  requiresAuth: boolean
}

// ─── JWT Audit ────────────────────────────────────────────────────────────────

export interface JWTVuln {
  type: string
  severity: 'Low' | 'Medium' | 'High' | 'Critical'
  description: string
}

export interface JWTAuditResult {
  token: string
  algorithm: string
  header: Record<string, unknown>
  payload: Record<string, unknown>
  vulnerabilities: JWTVuln[]
  noneAlgorithmVulnerable: boolean
  algorithmConfusionRisk: boolean
}

// ─── AWS IAM Audit ────────────────────────────────────────────────────────────

export interface IAMFinding {
  resourceArn: string
  issue: string
  severity: 'Low' | 'Medium' | 'High' | 'Critical'
  remediation: string
}

export interface AWSIAMAuditResult {
  domain: string
  findings: IAMFinding[]
  totalFindings: number
  criticalCount: number
}

// ─── Cloud Hunt ───────────────────────────────────────────────────────────────

export interface BucketResult {
  name: string
  url: string
  provider: 'AWS' | 'Azure' | 'GCP'
  accessible: boolean
  permissions: string
  sensitiveFiles: string[]
}

export interface CloudHuntResult {
  domain: string
  provider: string
  buckets: BucketResult[]
  totalBuckets: number
  accessibleBuckets: number
}

// ─── CI/CD Secret Scanner ─────────────────────────────────────────────────────

export interface SecretFinding {
  file: string
  line: number
  type: string
  value: string
  severity: 'Low' | 'Medium' | 'High' | 'Critical'
}

export interface CICDScanResult {
  url: string
  secrets: SecretFinding[]
  totalSecrets: number
}

// ─── IaC Linter ───────────────────────────────────────────────────────────────

export interface IaCViolation {
  rule: string
  severity: 'Low' | 'Medium' | 'High' | 'Critical'
  line: number
  description: string
  remediation: string
}

export interface IaCLintResult {
  fileType: string
  violations: IaCViolation[]
  passed: number
  failed: number
}

// ─── API Security Scanner ─────────────────────────────────────────────────────

export interface APIEndpoint {
  method: string
  path: string
  statusCode: number
  issues: string[]
}

export interface APIScanResult {
  url: string
  endpoints: APIEndpoint[]
  totalIssues: number
  authBypassRisk: boolean
}

// ─── Kerberoast ───────────────────────────────────────────────────────────────

export interface KerberoastTarget {
  username: string
  spn: string
  encryptionType: string
  crackable: boolean
}

export interface KerberoastResult {
  domain: string
  targets: KerberoastTarget[]
  totalTargets: number
}

// ─── Container Escape ─────────────────────────────────────────────────────────

export interface ContainerEscapeVector {
  vector: string
  description: string
  severity: 'Low' | 'Medium' | 'High' | 'Critical'
  exploitable: boolean
}

export interface ContainerEscapeResult {
  target: string
  vectors: ContainerEscapeVector[]
  escapePossible: boolean
}

// ─── AD CS Abuse ─────────────────────────────────────────────────────────────

export interface ADCSTemplate {
  name: string
  vulnerable: boolean
  issueType: string
  severity: 'Low' | 'Medium' | 'High' | 'Critical'
}

export interface ADCSAbuseResult {
  domain: string
  templates: ADCSTemplate[]
  totalVulnerable: number
}

// ─── GraphQL Audit ────────────────────────────────────────────────────────────

export interface GraphQLFinding {
  type: 'IntrospectionEnabled' | 'DepthVulnerable' | 'BatchingAbuse' | 'FieldSuggestions'
  description: string
  severity: 'Low' | 'Medium' | 'High' | 'Critical'
}

export interface GraphQLAuditResult {
  url: string
  maxDepth: number
  introspectionEnabled: boolean
  findings: GraphQLFinding[]
}

// ─── Dangling DNS ─────────────────────────────────────────────────────────────

export interface DanglingRecord {
  name: string
  type: string
  value: string
  dangling: boolean
  takeoverPossible: boolean
  provider: string
}

export interface DanglingDNSResult {
  domain: string
  records: DanglingRecord[]
  totalDangling: number
  takeoverCount: number
}

// ─── Threat Intel ─────────────────────────────────────────────────────────────

export interface ThreatIntelEntry {
  source: string
  type: string
  indicator: string
  confidence: number
  firstSeen: string
  lastSeen: string
  tags: string[]
}

export interface ThreatIntelResult {
  target: string
  entries: ThreatIntelEntry[]
  totalHits: number
  maliciousScore: number
}

// ─── MITRE Mapping ────────────────────────────────────────────────────────────

export interface MitreMapping {
  techniqueId: string
  tacticId: string
  techniqueName: string
  tacticName: string
  executed: boolean
  description: string
}

export interface MitreMappingResult {
  techniques: MitreMapping[]
  totalTechniques: number
  coveredTactics: string[]
}

// ─── OSCP Report ──────────────────────────────────────────────────────────────

export interface ReportFinding {
  id: string
  title: string
  severity: 'Low' | 'Medium' | 'High' | 'Critical'
  description: string
  proofOfConcept: string
  remediation: string
  cvssScore?: number
  cveIds?: string[]
}

export interface OSCPReportResult {
  investigationId: string
  reportMarkdown: string
  findings: ReportFinding[]
  generatedAt: string
}

// ─── Generic scan result envelope ─────────────────────────────────────────────

export interface RedTeamScanRecord<T = unknown> {
  id: string
  moduleId: number
  moduleName: string
  result: T
  createdAt: string
}

export interface RedTeamHistoryResponse {
  items: RedTeamScanRecord[]
  total: number
  page: number
  pageSize: number
  totalPages: number
}
