import { apiClient } from '@/shared/api/client'
import type {
  JWTAuditResult,
  AWSIAMAuditResult,
  CloudHuntResult,
  CICDScanResult,
  IaCLintResult,
  APIScanResult,
  KerberoastResult,
  ContainerEscapeResult,
  ADCSAbuseResult,
  GraphQLAuditResult,
  DanglingDNSResult,
  ThreatIntelResult,
  MitreMappingResult,
  OSCPReportResult,
  RedTeamHistoryResponse,
  ReportFinding,
} from './types'

export const redTeamApi = {
  // Module 101
  runJWTAudit: (targetUrl: string, token?: string): Promise<JWTAuditResult> =>
    apiClient
      .post<JWTAuditResult>('/redteam/jwt-audit', { target_url: targetUrl, token })
      .then((r) => r.data),

  // Module 102
  runAWSIAMAudit: (domain: string): Promise<AWSIAMAuditResult> =>
    apiClient
      .post<AWSIAMAuditResult>('/redteam/aws-iam-audit', { domain })
      .then((r) => r.data),

  // Module 103
  runCloudHunt: (domain: string, providers: string[]): Promise<CloudHuntResult> =>
    apiClient
      .post<CloudHuntResult>('/redteam/cloud-hunt', { domain, providers })
      .then((r) => r.data),

  // Module 104
  runCICDScan: (url: string): Promise<CICDScanResult> =>
    apiClient
      .post<CICDScanResult>('/redteam/cicd-scan', { url })
      .then((r) => r.data),

  // Module 105
  runIaCLint: (content: string, fileType: string): Promise<IaCLintResult> =>
    apiClient
      .post<IaCLintResult>('/redteam/iac-lint', { content, file_type: fileType })
      .then((r) => r.data),

  // Module 107
  runAPIScan: (url: string): Promise<APIScanResult> =>
    apiClient
      .post<APIScanResult>('/redteam/api-scan', { url })
      .then((r) => r.data),

  // Module 111
  runKerberoast: (domain: string): Promise<KerberoastResult> =>
    apiClient
      .post<KerberoastResult>('/redteam/kerberoast', { domain })
      .then((r) => r.data),

  // Module 115
  runContainerEscape: (target: string): Promise<ContainerEscapeResult> =>
    apiClient
      .post<ContainerEscapeResult>('/redteam/container-escape', { target })
      .then((r) => r.data),

  // Module 121
  runADCSAbuse: (domain: string): Promise<ADCSAbuseResult> =>
    apiClient
      .post<ADCSAbuseResult>('/redteam/adcs-abuse', { domain })
      .then((r) => r.data),

  // Module 122
  runGraphQLAudit: (url: string, maxDepth: number): Promise<GraphQLAuditResult> =>
    apiClient
      .post<GraphQLAuditResult>('/redteam/graphql-audit', { url, max_depth: maxDepth })
      .then((r) => r.data),

  // Module 125
  runDanglingDNS: (domain: string): Promise<DanglingDNSResult> =>
    apiClient
      .post<DanglingDNSResult>('/redteam/dangling-dns', { domain })
      .then((r) => r.data),

  // Module 127
  runThreatIntel: (target: string): Promise<ThreatIntelResult> =>
    apiClient
      .post<ThreatIntelResult>('/redteam/threat-intel', { target })
      .then((r) => r.data),

  // Module 126
  mapMitreTechniques: (techniques: string[]): Promise<MitreMappingResult> =>
    apiClient
      .post<MitreMappingResult>('/redteam/mitre-map', { techniques })
      .then((r) => r.data),

  // Module 130
  generateOSCPReport: (investigationId: string, findings: ReportFinding[]): Promise<OSCPReportResult> =>
    apiClient
      .post<OSCPReportResult>('/redteam/oscp-report', { investigation_id: investigationId, findings })
      .then((r) => r.data),

  // History
  listHistory: (moduleId: number, page: number, pageSize: number): Promise<RedTeamHistoryResponse> =>
    apiClient
      .get<RedTeamHistoryResponse>('/redteam/history', {
        params: { module_id: moduleId, page, page_size: pageSize },
      })
      .then((r) => r.data),
}
