import { useState } from 'react'
import { ChevronDown, ChevronRight, CheckCircle2, XCircle, MinusCircle, AlertCircle } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { ModuleResultData } from '../types'
import { MODULE_LABELS } from '../types'

interface ModuleCardProps {
  moduleName: string
  result: ModuleResultData
}

function StatusBadge({ result }: { result: ModuleResultData }) {
  if (result.skipped) {
    return (
      <Badge variant="outline" className="gap-1 text-xs">
        <MinusCircle className="h-3 w-3" />
        Skipped
      </Badge>
    )
  }
  if (result.error) {
    return (
      <Badge variant="destructive" className="gap-1 text-xs">
        <XCircle className="h-3 w-3" />
        Error
      </Badge>
    )
  }
  if (result.found) {
    return (
      <Badge className="gap-1 bg-emerald-600 text-xs hover:bg-emerald-700">
        <CheckCircle2 className="h-3 w-3" />
        Found
      </Badge>
    )
  }
  return (
    <Badge variant="secondary" className="gap-1 text-xs">
      <AlertCircle className="h-3 w-3" />
      No results
    </Badge>
  )
}

function KeyFindings({ moduleName, data }: { moduleName: string; data: Record<string, unknown> }) {
  const lines: string[] = []

  if (moduleName === 'banner_grabber' && Array.isArray(data.open_ports)) {
    lines.push(`Open ports: ${(data.open_ports as number[]).join(', ') || 'none'}`)
  }
  if (moduleName === 'subdomain_takeover' && Array.isArray(data.vulnerable_subdomains)) {
    const count = (data.vulnerable_subdomains as unknown[]).length
    lines.push(`Vulnerable subdomains: ${count}`)
  }
  if (moduleName === 'common_files' && typeof data.accessible_count === 'number') {
    lines.push(`Accessible files: ${data.accessible_count}`)
    const sensitive = data.exposed_sensitive
    if (Array.isArray(sensitive) && sensitive.length > 0) {
      lines.push(`Sensitive exposed: ${sensitive.length}`)
    }
  }
  if (moduleName === 'mx_spf_dmarc') {
    if (typeof data.email_security_score === 'number') {
      lines.push(`Email security score: ${data.email_security_score}/100`)
    }
    if (typeof data.dmarc_policy === 'string') {
      lines.push(`DMARC policy: ${data.dmarc_policy}`)
    }
  }
  if (moduleName === 'shared_hosting' && typeof data.co_hosted_count === 'number') {
    lines.push(`Co-hosted domains: ${data.co_hosted_count} (${String(data.risk_level)} risk)`)
  }
  if (moduleName === 'ipv6_mapper') {
    lines.push(`Dual-stack: ${data.dual_stack ? 'Yes' : 'No'}`)
    if (Array.isArray(data.ipv6_addresses)) {
      lines.push(`IPv6 addresses: ${(data.ipv6_addresses as string[]).length}`)
    }
  }
  if (moduleName === 'traceroute' && typeof data.total_hops === 'number') {
    lines.push(`Hops: ${data.total_hops}`)
    lines.push(`Destination reached: ${data.destination_reached ? 'Yes' : 'No'}`)
  }

  if (lines.length === 0 && data.found) {
    lines.push('Results available — expand to view')
  }

  return lines.length > 0 ? (
    <ul className="mt-1 space-y-0.5">
      {lines.map((l) => (
        <li key={l} className="text-xs" style={{ color: 'var(--text-secondary)' }}>
          {l}
        </li>
      ))}
    </ul>
  ) : null
}

export function ModuleCard({ moduleName, result }: ModuleCardProps) {
  const [expanded, setExpanded] = useState(false)
  const label = MODULE_LABELS[moduleName] ?? moduleName

  return (
    <div
      className="rounded-lg border p-3"
      style={{ background: 'var(--bg-surface)', borderColor: 'var(--border-subtle)' }}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium truncate" style={{ color: 'var(--text-primary)' }}>
            {label}
          </p>
          {result.data && !result.skipped && (
            <KeyFindings moduleName={moduleName} data={result.data as Record<string, unknown>} />
          )}
          {result.error && (
            <p className="mt-1 text-xs text-danger-400 truncate">{result.error}</p>
          )}
          {result.skipped && result.reason && (
            <p className="mt-1 text-xs" style={{ color: 'var(--text-tertiary)' }}>
              {result.reason}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <StatusBadge result={result} />
          {result.data && !result.skipped && (
            <Button
              variant="ghost"
              size="sm"
              className="h-6 w-6 p-0"
              onClick={() => setExpanded((v) => !v)}
            >
              {expanded ? (
                <ChevronDown className="h-3.5 w-3.5" />
              ) : (
                <ChevronRight className="h-3.5 w-3.5" />
              )}
            </Button>
          )}
        </div>
      </div>

      {expanded && result.data && (
        <pre
          className="mt-3 max-h-64 overflow-auto rounded p-2 text-xs"
          style={{ background: 'var(--bg-overlay)', color: 'var(--text-secondary)' }}
        >
          {JSON.stringify(result.data, null, 2)}
        </pre>
      )}
    </div>
  )
}
