import { useState, useCallback } from 'react'
import { Shield, FileText, AlertTriangle } from 'lucide-react'
import { Card, CardHeader, CardBody } from '@/shared/components/Card'
import { Badge } from '@/shared/components/Badge'
import { SubjectRequestForm } from './components/SubjectRequestForm'
import { ExposureReport } from './components/ExposureReport'
import { useGdprReports } from './hooks'
import type { GdprReport, RiskScore } from './types'

const riskBadgeVariant: Record<RiskScore, 'danger' | 'warning' | 'info' | 'success'> = {
  critical: 'danger',
  high: 'warning',
  medium: 'info',
  low: 'success',
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div
        className="mb-4 flex h-14 w-14 items-center justify-center rounded-full"
        style={{ background: 'var(--bg-elevated)' }}
      >
        <FileText className="h-6 w-6" style={{ color: 'var(--text-tertiary)' }} />
      </div>
      <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
        No report selected
      </p>
      <p className="mt-1 max-w-xs text-xs" style={{ color: 'var(--text-tertiary)' }}>
        Fill in the subject details on the left and run an exposure check, or select a
        previous report from the history list.
      </p>
    </div>
  )
}

export function GdprPage() {
  const [selectedReport, setSelectedReport] = useState<GdprReport | null>(null)
  const { data: reports = [], isLoading: reportsLoading } = useGdprReports()

  const handleSuccess = useCallback((report: GdprReport) => {
    setSelectedReport(report)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [])

  const handleSelectReport = useCallback((report: GdprReport) => {
    setSelectedReport(report)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [])

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>
          GDPR Data Subject Request
        </h1>
        <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)' }}>
          Automate Article 15 exposure checks — scan breach databases, paste sites, social
          profiles, and stealer logs for a given subject.
        </p>
      </div>

      {/* Split layout */}
      <div className="flex gap-6 items-start">
        {/* Left panel — form + history */}
        <div className="w-1/3 shrink-0 space-y-4">
          {/* Request form */}
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Shield className="h-4 w-4" style={{ color: 'var(--brand-500)' }} />
                <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                  Subject Details
                </h2>
              </div>
            </CardHeader>
            <CardBody>
              <SubjectRequestForm onSuccess={handleSuccess} />
            </CardBody>
          </Card>

          {/* Recent reports */}
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <FileText className="h-4 w-4" style={{ color: 'var(--text-tertiary)' }} />
                <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                  Recent Reports
                </h2>
                {reports.length > 0 && (
                  <span
                    className="ml-auto text-xs"
                    style={{ color: 'var(--text-tertiary)' }}
                  >
                    {reports.length}
                  </span>
                )}
              </div>
            </CardHeader>
            <CardBody className="p-0">
              {reportsLoading ? (
                <div className="px-5 py-6 text-center text-sm" style={{ color: 'var(--text-tertiary)' }}>
                  Loading...
                </div>
              ) : reports.length === 0 ? (
                <div className="px-5 py-6 text-center text-sm" style={{ color: 'var(--text-tertiary)' }}>
                  No reports yet
                </div>
              ) : (
                <ul>
                  {reports.map((report) => {
                    const isSelected = selectedReport?.report_id === report.report_id
                    return (
                      <li key={report.report_id}>
                        <button
                          onClick={() => handleSelectReport(report)}
                          className={`w-full text-left px-5 py-3 transition-colors border-b last:border-b-0 ${
                            isSelected ? 'bg-brand-900' : 'hover:bg-bg-overlay'
                          }`}
                          style={{ borderColor: 'var(--border-subtle)' }}
                          aria-pressed={isSelected}
                        >
                          <div className="flex items-center gap-2 min-w-0">
                            <span
                              className="flex-1 truncate text-sm font-medium"
                              style={{ color: isSelected ? 'var(--brand-400)' : 'var(--text-primary)' }}
                            >
                              {report.subject_name}
                            </span>
                            <Badge
                              variant={riskBadgeVariant[report.risk_score]}
                              size="sm"
                              dot
                            >
                              {report.risk_score}
                            </Badge>
                          </div>
                          <p
                            className="mt-0.5 truncate text-xs"
                            style={{ color: 'var(--text-tertiary)' }}
                          >
                            {report.subject_email}
                          </p>
                          <p
                            className="mt-0.5 text-xs"
                            style={{ color: 'var(--text-tertiary)' }}
                          >
                            {report.total_exposures} exposure{report.total_exposures !== 1 ? 's' : ''} &middot;{' '}
                            {new Date(report.created_at).toLocaleDateString()}
                          </p>
                        </button>
                      </li>
                    )
                  })}
                </ul>
              )}
            </CardBody>
          </Card>
        </div>

        {/* Right panel — report view */}
        <div className="flex-1 min-w-0">
          {selectedReport !== null ? (
            <div className="animate-in fade-in slide-in-from-top-2 duration-300">
              <div className="mb-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4" style={{ color: 'var(--warning-500)' }} />
                  <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                    Exposure Report —{' '}
                    <span className="font-normal" style={{ color: 'var(--text-tertiary)' }}>
                      {selectedReport.subject_name}
                    </span>
                  </h2>
                </div>
                <button
                  onClick={() => setSelectedReport(null)}
                  className="text-xs transition-colors hover:underline"
                  style={{ color: 'var(--text-tertiary)' }}
                >
                  Dismiss
                </button>
              </div>
              <ExposureReport report={selectedReport} />
            </div>
          ) : (
            <Card>
              <EmptyState />
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
