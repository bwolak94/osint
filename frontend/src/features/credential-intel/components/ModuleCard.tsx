import { CheckCircle, XCircle, AlertCircle, SkipForward } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { MODULE_LABELS, MODULE_DESCRIPTIONS } from '../types'
import type { ModuleResultData, ComplexityRow } from '../types'
import { PasswordComplexityChart } from './PasswordComplexityChart'

interface ModuleCardProps {
  name: string
  result: ModuleResultData
}

export function CredentialIntelModuleCard({ name, result }: ModuleCardProps) {
  const label = MODULE_LABELS[name] ?? name.replace(/_/g, ' ')
  const description = MODULE_DESCRIPTIONS[name]
  const data = result.data as Record<string, unknown> | undefined

  function renderIcon() {
    if (result.skipped) return <SkipForward className="h-4 w-4 text-text-tertiary" />
    if (result.error) return <AlertCircle className="h-4 w-4 text-warning-500" />
    if (result.found) return <CheckCircle className="h-4 w-4 text-success-500" />
    return <XCircle className="h-4 w-4 text-text-tertiary" />
  }

  function renderStatusBadge() {
    if (result.skipped) return <Badge variant="outline" className="text-[10px]">Skipped</Badge>
    if (result.error) return <Badge variant="outline" className="text-[10px] text-warning-500 border-warning-500">Error</Badge>
    if (result.found) return <Badge variant="outline" className="text-[10px] text-success-500 border-success-500">Found</Badge>
    return <Badge variant="outline" className="text-[10px]">Clean</Badge>
  }

  function renderSummary() {
    if (result.skipped) return <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>{result.reason}</p>
    if (result.error) return <p className="text-xs font-mono truncate text-warning-400">{result.error}</p>
    if (!result.found || !data) return <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>No results found</p>

    // Breach modules
    if (name === 'breach_hibp' && data.total_breaches !== undefined) {
      return (
        <div className="text-xs space-y-0.5" style={{ color: 'var(--text-secondary)' }}>
          <p>Breaches found: <span className="font-mono text-danger-400 font-bold">{String(data.total_breaches)}</span></p>
          {Array.isArray(data.breaches) && (
            <p className="truncate">
              {(data.breaches as Array<{name: string}>).slice(0, 3).map((b) => b.name).join(', ')}
              {(data.breaches as unknown[]).length > 3 ? '...' : ''}
            </p>
          )}
        </div>
      )
    }

    // Hash analyzer
    if (name === 'hash_analyzer' && data.algorithm) {
      const complexityRows = (data.complexity_table as ComplexityRow[]) ?? []
      const ratingColor = data.security_rating === 'Broken' || data.security_rating === 'Weak'
        ? 'text-danger-400'
        : data.security_rating === 'Moderate'
        ? 'text-warning-400'
        : 'text-success-400'
      return (
        <div className="space-y-3">
          <div className="text-xs space-y-0.5" style={{ color: 'var(--text-secondary)' }}>
            <p>Algorithm: <span className="font-mono font-bold text-brand-400">{String(data.algorithm)}</span></p>
            <p>Security: <span className={`font-mono font-bold ${ratingColor}`}>{String(data.security_rating)}</span></p>
            <p className="text-[10px] italic" style={{ color: 'var(--text-tertiary)' }}>{String(data.educational_note)}</p>
          </div>
          {complexityRows.length > 0 && (
            <PasswordComplexityChart rows={complexityRows} />
          )}
        </div>
      )
    }

    // Exposed git
    if (name === 'exposed_git') {
      const severity = data.severity as string
      const count = Number(data.total_exposed ?? 0)
      const sevColor = severity === 'critical' ? 'text-danger-400' : severity === 'high' ? 'text-warning-400' : 'text-success-400'
      return (
        <div className="text-xs space-y-0.5" style={{ color: 'var(--text-secondary)' }}>
          <p>Severity: <span className={`font-mono font-bold ${sevColor}`}>{severity}</span></p>
          <p>Exposed paths: <span className="font-mono">{count}</span></p>
          {Boolean(data.is_git_confirmed) && <p className="text-danger-400 font-medium">Full git repo accessible!</p>}
        </div>
      )
    }

    // Env file miner
    if (name === 'env_file_miner') {
      const count = Number(data.total_exposed_files ?? 0)
      const secrets = Number(data.total_detected_secrets ?? 0)
      return (
        <div className="text-xs space-y-0.5" style={{ color: 'var(--text-secondary)' }}>
          <p>Exposed files: <span className="font-mono text-danger-400 font-bold">{count}</span></p>
          <p>Detected secrets: <span className="font-mono text-danger-400">{secrets}</span></p>
        </div>
      )
    }

    // Domain squatting
    if (name === 'domain_squatting') {
      return (
        <div className="text-xs space-y-0.5" style={{ color: 'var(--text-secondary)' }}>
          <p>Registered squatters: <span className="font-mono text-warning-400">{String(data.total_registered ?? 0)}</span></p>
          <p>Variants checked: {String(data.total_checked ?? 0)}</p>
          <p>Risk: <span className="font-mono">{String(data.risk_level ?? '-')}</span></p>
        </div>
      )
    }

    // Compromised IP
    if (name === 'compromised_ip') {
      const score = Number(data.abuse_confidence_score ?? 0)
      const reports = Number(data.total_reports ?? 0)
      const scoreColor = score >= 75 ? 'text-danger-400' : score >= 25 ? 'text-warning-400' : 'text-success-400'
      return (
        <div className="text-xs space-y-0.5" style={{ color: 'var(--text-secondary)' }}>
          <p>Abuse score: <span className={`font-mono font-bold ${scoreColor}`}>{score}/100</span></p>
          <p>Reports: <span className="font-mono">{reports}</span></p>
          {Boolean(data.isp) && <p>ISP: {String(data.isp)}</p>}
        </div>
      )
    }

    // Exploit DB
    if (name === 'exploit_db') {
      return (
        <div className="text-xs space-y-0.5" style={{ color: 'var(--text-secondary)' }}>
          <p>Total CVEs found: <span className="font-mono text-warning-400">{String(data.total_results ?? 0)}</span></p>
          <p>Critical: <span className="font-mono text-danger-400">{String(data.critical_count ?? 0)}</span></p>
          <p>High: <span className="font-mono text-warning-400">{String(data.high_count ?? 0)}</span></p>
        </div>
      )
    }

    // Ransomware intel
    if (name === 'ransomware_intel') {
      const matches = Number(data.total_matches ?? 0)
      return (
        <div className="text-xs space-y-0.5" style={{ color: 'var(--text-secondary)' }}>
          <p>Victim matches: <span className={`font-mono font-bold ${matches > 0 ? 'text-danger-400' : 'text-success-400'}`}>{matches}</span></p>
          {matches > 0 && Array.isArray(data.victim_matches) && (
            <p>Group: {(data.victim_matches as Array<{group: string}>)[0]?.group}</p>
          )}
        </div>
      )
    }

    // Generic fallback
    return <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>{Object.keys(data).length} data fields</p>
  }

  const borderColor = result.found
    ? name.includes('breach') || name === 'compromised_ip' || name === 'ransomware_intel'
      ? 'var(--danger-700)'
      : 'var(--warning-700)'
    : result.error
    ? 'var(--warning-700)'
    : 'var(--border-subtle)'

  return (
    <div
      className="rounded-lg border p-3 space-y-2"
      style={{ borderColor, background: 'var(--bg-overlay)' }}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          {renderIcon()}
          <span className="text-sm font-medium truncate" style={{ color: 'var(--text-primary)' }}>
            {label}
          </span>
        </div>
        {renderStatusBadge()}
      </div>
      {description && (
        <p className="text-[10px] leading-relaxed" style={{ color: 'var(--text-tertiary)' }}>
          {description}
        </p>
      )}
      {renderSummary()}
    </div>
  )
}
