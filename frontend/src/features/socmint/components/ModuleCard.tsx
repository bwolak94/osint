import { useState } from 'react'
import { CheckCircle, XCircle, AlertCircle, SkipForward, ChevronDown, ChevronRight } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { SOCMINT_MODULE_LABELS, MODULE_DESCRIPTIONS } from '../types'
import type { ModuleResultData } from '../types'

interface ModuleCardProps {
  name: string
  result: ModuleResultData
}

function renderIcon(result: ModuleResultData): React.ReactNode {
  if (result.skipped) return <SkipForward className="h-4 w-4 shrink-0" style={{ color: 'var(--text-tertiary)' }} />
  if (result.error) return <AlertCircle className="h-4 w-4 shrink-0 text-warning-500" />
  if (result.found) return <CheckCircle className="h-4 w-4 shrink-0 text-success-500" />
  return <XCircle className="h-4 w-4 shrink-0" style={{ color: 'var(--text-tertiary)' }} />
}

function renderStatusBadge(result: ModuleResultData): React.ReactNode {
  if (result.skipped)
    return <Badge variant="outline" className="text-[10px]">Skipped</Badge>
  if (result.error)
    return (
      <Badge variant="outline" className="text-[10px] text-warning-500 border-warning-500">
        Error
      </Badge>
    )
  if (result.found)
    return (
      <Badge variant="outline" className="text-[10px] text-success-500 border-success-500">
        Found
      </Badge>
    )
  return <Badge variant="outline" className="text-[10px]">No Data</Badge>
}

function KeyFindings({ name, data }: { name: string; data: Record<string, unknown> }): React.ReactNode {
  if (name === 'activity_heatmap' && data.peak_hour_utc !== undefined) {
    return (
      <div className="space-y-0.5 text-xs" style={{ color: 'var(--text-secondary)' }}>
        <p>
          Peak hour (UTC):{' '}
          <span className="font-mono text-brand-400">{String(data.peak_hour_utc)}:00</span>
        </p>
        <p>
          Peak day:{' '}
          <span className="font-mono text-brand-400">{String(data.peak_day_of_week ?? '—')}</span>
        </p>
        <p>
          Est. timezone:{' '}
          <span className="font-mono text-brand-400">{String(data.estimated_timezone ?? '?')}</span>
        </p>
        <p>Data points: {String(data.total_data_points ?? 0)}</p>
      </div>
    )
  }

  if (name === 'profile_credibility' && data.credibility_score !== undefined) {
    const score = Number(data.credibility_score)
    const scoreColor =
      score >= 80 ? 'text-success-400' : score >= 50 ? 'text-warning-400' : 'text-danger-400'
    return (
      <div className="space-y-0.5 text-xs" style={{ color: 'var(--text-secondary)' }}>
        <p>
          Score:{' '}
          <span className={`font-mono font-bold ${scoreColor}`}>{score}/100</span>
        </p>
        <p>
          Verdict:{' '}
          <span className="font-mono text-brand-400">{String(data.verdict ?? '—')}</span>
        </p>
        {Array.isArray(data.suspicious_flags) &&
          (data.suspicious_flags as string[]).length > 0 && (
            <p className="text-warning-400">
              Flags: {(data.suspicious_flags as string[]).join(', ')}
            </p>
          )}
      </div>
    )
  }

  if (name === 'language_stylometrics' && data.type_token_ratio !== undefined) {
    return (
      <div className="space-y-0.5 text-xs" style={{ color: 'var(--text-secondary)' }}>
        <p>
          Vocabulary richness:{' '}
          <span className="font-mono text-brand-400">{String(data.type_token_ratio)}</span>
        </p>
        <p>
          Avg word length:{' '}
          <span className="font-mono text-brand-400">{String(data.avg_word_length)}</span>
        </p>
        <p>
          Readability:{' '}
          <span className="font-mono text-brand-400">{String(data.readability_level ?? '—')}</span>
        </p>
        <p>Sample size: {String(data.sample_size ?? 0)} texts</p>
      </div>
    )
  }

  if (name === 'bio_link_extractor' && data.discovered_links !== undefined) {
    const links = data.discovered_links as Array<{ source: string; url: string }>
    return (
      <div className="space-y-0.5 text-xs" style={{ color: 'var(--text-secondary)' }}>
        <p>
          Links found:{' '}
          <span className="font-mono text-brand-400">{String(data.total_links ?? 0)}</span>
        </p>
        {links.slice(0, 3).map((l, i) => (
          <p key={i} className="truncate font-mono text-brand-400" title={l.url}>
            {l.url}
          </p>
        ))}
        {links.length > 3 && <p>+{links.length - 3} more…</p>}
      </div>
    )
  }

  if (
    (name === 'username_crosscheck' || name === 'username_maigret') &&
    data.total_found !== undefined
  ) {
    return (
      <div className="space-y-0.5 text-xs" style={{ color: 'var(--text-secondary)' }}>
        <p>
          Found on:{' '}
          <span className="font-mono text-brand-400">{String(data.total_found)}</span> platforms
        </p>
        <p>Checked: {String(data.total_checked ?? 0)} sites</p>
        {Array.isArray(data.found_on) && (data.found_on as string[]).length > 0 && (
          <p className="truncate">
            Platforms:{' '}
            {(data.found_on as string[]).slice(0, 5).join(', ')}
            {(data.found_on as string[]).length > 5 ? '…' : ''}
          </p>
        )}
      </div>
    )
  }

  if (name === 'deleted_post_finder') {
    return (
      <div className="space-y-0.5 text-xs" style={{ color: 'var(--text-secondary)' }}>
        <p>
          Wayback snapshots:{' '}
          <span className="font-mono text-brand-400">
            {String(data.total_wayback_snapshots ?? 0)}
          </span>
        </p>
        <p>
          Deleted posts:{' '}
          <span className="font-mono text-brand-400">
            {String(data.total_deleted_posts ?? 0)}
          </span>
        </p>
      </div>
    )
  }

  if (name === 'reddit_karma' && data.data) {
    const rd = data.data as Record<string, unknown>
    return (
      <div className="space-y-0.5 text-xs" style={{ color: 'var(--text-secondary)' }}>
        <p>
          Post karma:{' '}
          <span className="font-mono text-brand-400">{String(rd.link_karma ?? '—')}</span>
        </p>
        <p>
          Comment karma:{' '}
          <span className="font-mono text-brand-400">{String(rd.comment_karma ?? '—')}</span>
        </p>
      </div>
    )
  }

  const keyCount = Object.keys(data).length
  return (
    <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
      {keyCount} data fields returned
    </p>
  )
}

export function SocmintModuleCard({ name, result }: ModuleCardProps) {
  const [expanded, setExpanded] = useState(false)
  const label = SOCMINT_MODULE_LABELS[name] ?? name.replace(/_/g, ' ')
  const description = MODULE_DESCRIPTIONS[name]

  const borderColor = result.found
    ? 'var(--success-700)'
    : result.error
    ? 'var(--warning-700)'
    : 'var(--border-subtle)'

  return (
    <div
      className="rounded-lg border p-3 space-y-2"
      style={{ borderColor, background: 'var(--bg-overlay)' }}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          {renderIcon(result)}
          <span className="text-sm font-medium truncate" style={{ color: 'var(--text-primary)' }}>
            {label}
          </span>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          {renderStatusBadge(result)}
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

      {description && (
        <p className="text-[10px] leading-relaxed" style={{ color: 'var(--text-tertiary)' }}>
          {description}
        </p>
      )}

      {result.skipped && result.reason && (
        <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
          {result.reason}
        </p>
      )}

      {result.error && (
        <p className="text-xs text-warning-400 font-mono truncate">{result.error}</p>
      )}

      {result.found && result.data && !result.skipped && (
        <KeyFindings name={name} data={result.data} />
      )}

      {!result.found && !result.skipped && !result.error && (
        <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
          No results found
        </p>
      )}

      {expanded && result.data && (
        <pre
          className="mt-1 max-h-64 overflow-auto rounded p-2 text-xs"
          style={{ background: 'var(--bg-surface)', color: 'var(--text-secondary)' }}
        >
          {JSON.stringify(result.data, null, 2)}
        </pre>
      )}
    </div>
  )
}
