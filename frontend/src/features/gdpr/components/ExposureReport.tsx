import { useState, useCallback } from 'react'
import {
  ShieldAlert,
  FileText,
  Users,
  Download,
  CheckCircle2,
  AlertTriangle,
  Shield,
  Database,
} from 'lucide-react'
import { Card, CardHeader, CardBody } from '@/shared/components/Card'
import { Badge } from '@/shared/components/Badge'
import { toast } from '@/shared/components/Toast'
import type { ExposureSource, GdprReport, RiskScore, Severity, SourceType } from '../types'

interface Props {
  report: GdprReport
}

const riskBadgeVariant: Record<RiskScore, 'danger' | 'warning' | 'info' | 'success'> = {
  critical: 'danger',
  high: 'warning',
  medium: 'info',
  low: 'success',
}

const severityBadgeVariant: Record<Severity, 'danger' | 'warning' | 'info' | 'success'> = {
  critical: 'danger',
  high: 'warning',
  medium: 'info',
  low: 'success',
}

function SourceIcon({ type }: { type: SourceType }) {
  const cls = 'h-4 w-4 shrink-0 mt-0.5'
  switch (type) {
    case 'breach':
      return <ShieldAlert className={cls} style={{ color: 'var(--warning-500)' }} />
    case 'paste':
      return <FileText className={cls} style={{ color: 'var(--danger-500)' }} />
    case 'social':
      return <Users className={cls} style={{ color: 'var(--info-500)' }} />
    case 'stealer':
      return <AlertTriangle className={cls} style={{ color: 'var(--danger-500)' }} />
    case 'public_record':
      return <Database className={cls} style={{ color: 'var(--text-tertiary)' }} />
    default:
      return <Shield className={cls} style={{ color: 'var(--text-tertiary)' }} />
  }
}

function ExposureSourceCard({ source }: { source: ExposureSource }) {
  return (
    <div
      className="rounded-lg border p-3 space-y-2"
      style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-elevated)' }}
    >
      <div className="flex items-start gap-2">
        <SourceIcon type={source.source_type} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
              {source.source_name}
            </span>
            <Badge variant={severityBadgeVariant[source.severity]} size="sm" dot>
              {source.severity}
            </Badge>
            <span className="text-xs uppercase tracking-wide" style={{ color: 'var(--text-tertiary)' }}>
              {source.source_type}
            </span>
          </div>
          {source.date_found && (
            <p className="mt-0.5 text-xs" style={{ color: 'var(--text-tertiary)' }}>
              Detected: {source.date_found}
            </p>
          )}
        </div>
      </div>

      {/* Data fields as tags */}
      <div className="flex flex-wrap gap-1.5 pl-6">
        {source.found_data.map((field) => (
          <span
            key={field}
            className="rounded px-1.5 py-0.5 text-[10px] font-mono font-medium"
            style={{
              background: 'var(--bg-overlay)',
              color: 'var(--text-secondary)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            {field}
          </span>
        ))}
      </div>
    </div>
  )
}

export function ExposureReport({ report }: Props) {
  const [checkedActions, setCheckedActions] = useState<Set<number>>(new Set())

  const toggleAction = useCallback((index: number) => {
    setCheckedActions((prev) => {
      const next = new Set(prev)
      if (next.has(index)) {
        next.delete(index)
      } else {
        next.add(index)
      }
      return next
    })
  }, [])

  const handleExportPdf = useCallback(() => {
    toast.info('PDF export would be triggered here')
  }, [])

  const formattedDate = new Date(report.created_at).toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })

  return (
    <div className="space-y-4">
      {/* Header card */}
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div className="space-y-1">
              <h2 className="text-base font-semibold" style={{ color: 'var(--text-primary)' }}>
                {report.subject_name}
              </h2>
              <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                {report.subject_email}
              </p>
              <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
                Generated {formattedDate}
                {report.requester_reference && (
                  <> &middot; Ref: {report.requester_reference}</>
                )}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <div className="text-right">
                <p className="text-xs font-medium mb-1" style={{ color: 'var(--text-tertiary)' }}>
                  Risk Score
                </p>
                <Badge variant={riskBadgeVariant[report.risk_score]} size="md" dot>
                  {report.risk_score.toUpperCase()}
                </Badge>
              </div>
              <div className="text-right">
                <p className="text-xs font-medium mb-1" style={{ color: 'var(--text-tertiary)' }}>
                  Exposures
                </p>
                <span className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>
                  {report.total_exposures}
                </span>
              </div>
            </div>
          </div>
        </CardHeader>
        <CardBody>
          <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
            {report.summary}
          </p>
        </CardBody>
      </Card>

      {/* Exposure sources */}
      {report.exposure_sources.length > 0 && (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <ShieldAlert className="h-4 w-4" style={{ color: 'var(--brand-500)' }} />
              <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                Exposure Sources
              </h3>
              <span
                className="ml-auto text-xs font-medium"
                style={{ color: 'var(--text-tertiary)' }}
              >
                {report.exposure_sources.length} found
              </span>
            </div>
          </CardHeader>
          <CardBody className="space-y-2">
            {report.exposure_sources.map((source, i) => (
              <ExposureSourceCard key={i} source={source} />
            ))}
          </CardBody>
        </Card>
      )}

      {/* Recommended actions */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4" style={{ color: 'var(--brand-500)' }} />
            <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              Recommended Actions
            </h3>
            <span
              className="ml-auto text-xs"
              style={{ color: 'var(--text-tertiary)' }}
            >
              {checkedActions.size}/{report.recommended_actions.length} completed
            </span>
          </div>
        </CardHeader>
        <CardBody className="space-y-2">
          {report.recommended_actions.map((action, i) => {
            const isChecked = checkedActions.has(i)
            return (
              <label
                key={i}
                className="flex cursor-pointer items-start gap-3 rounded-lg p-2 transition-colors hover:bg-bg-overlay"
              >
                <input
                  type="checkbox"
                  checked={isChecked}
                  onChange={() => toggleAction(i)}
                  className="mt-0.5 h-4 w-4 rounded accent-brand-500"
                  aria-label={action}
                />
                <span
                  className={`text-sm transition-all ${isChecked ? 'line-through opacity-50' : ''}`}
                  style={{ color: 'var(--text-secondary)' }}
                >
                  {action}
                </span>
              </label>
            )
          })}
        </CardBody>
      </Card>

      {/* Export button */}
      <button
        onClick={handleExportPdf}
        className="flex w-full items-center justify-center gap-2 rounded-lg border py-2.5 text-sm font-medium transition-colors hover:bg-bg-overlay"
        style={{ borderColor: 'var(--border-default)', color: 'var(--text-secondary)' }}
        aria-label="Export report as PDF"
      >
        <Download className="h-4 w-4" />
        Export as PDF
      </button>
    </div>
  )
}
