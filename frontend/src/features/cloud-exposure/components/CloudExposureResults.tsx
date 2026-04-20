import { Cloud, AlertTriangle, ExternalLink } from 'lucide-react'
import { Card, CardHeader, CardBody } from '@/shared/components/Card'
import { Badge } from '@/shared/components/Badge'
import type { CloudExposureScan } from '../types'

interface Props {
  scan: CloudExposureScan
}

const PROVIDER_COLORS: Record<string, string> = {
  'AWS S3': 'var(--warning-500)',
  'Azure Blob': 'var(--brand-500)',
  'GCP Storage': 'var(--success-500)',
}

export function CloudExposureResults({ scan }: Props) {
  return (
    <div className="space-y-4">
      {/* Summary stats */}
      <div className="grid gap-4 sm:grid-cols-3">
        {[
          { label: 'Total Buckets', value: scan.total_buckets },
          { label: 'Public', value: scan.public_buckets },
          { label: 'Sensitive Files', value: scan.sensitive_findings },
        ].map(({ label, value }) => (
          <div key={label} className="rounded-xl border px-4 py-3 text-center" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border-subtle)' }}>
            <p className="text-2xl font-bold" style={{ color: value > 0 && label !== 'Total Buckets' ? 'var(--danger-400)' : 'var(--text-primary)' }}>{value}</p>
            <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>{label}</p>
          </div>
        ))}
      </div>

      {scan.sensitive_findings > 0 && (
        <div className="flex items-center gap-2 rounded-lg border px-4 py-3" style={{ background: 'var(--danger-900)', borderColor: 'var(--danger-500)' }}>
          <AlertTriangle className="h-4 w-4 shrink-0" style={{ color: 'var(--danger-500)' }} />
          <span className="text-sm font-medium" style={{ color: 'var(--danger-500)' }}>
            {scan.sensitive_findings} bucket{scan.sensitive_findings !== 1 ? 's contain' : ' contains'} potentially sensitive files
          </span>
        </div>
      )}

      {/* Bucket list */}
      {scan.buckets.length > 0 && (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Cloud className="h-4 w-4" style={{ color: 'var(--brand-500)' }} />
              <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Discovered Buckets</h3>
            </div>
          </CardHeader>
          <div className="divide-y" style={{ borderColor: 'var(--border-subtle)' }}>
            {scan.buckets.map((bucket, i) => (
              <div key={i} className="px-4 py-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{bucket.name}</span>
                      <Badge variant="neutral" size="sm" style={{ color: PROVIDER_COLORS[bucket.provider] }}>{bucket.provider}</Badge>
                      {bucket.is_public && <Badge variant="danger" size="sm">Public</Badge>}
                      {bucket.has_sensitive_files && <Badge variant="danger" size="sm">Sensitive Files</Badge>}
                    </div>
                    <p className="mt-1 text-xs" style={{ color: 'var(--text-tertiary)' }}>
                      {bucket.file_count} files indexed
                      {bucket.sensitive_file_count > 0 && ` · ${bucket.sensitive_file_count} sensitive`}
                    </p>
                    {bucket.sample_files.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {bucket.sample_files.slice(0, 5).map((f, j) => (
                          <span key={j} className="rounded px-1.5 py-0.5 font-mono text-xs" style={{ background: 'var(--bg-elevated)', color: 'var(--text-tertiary)' }}>{f}</span>
                        ))}
                      </div>
                    )}
                  </div>
                  {bucket.url && (
                    <a href={bucket.url} target="_blank" rel="noopener noreferrer" className="shrink-0 rounded p-1 hover:bg-bg-overlay" title="Open bucket URL">
                      <ExternalLink className="h-4 w-4" style={{ color: 'var(--brand-500)' }} />
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {scan.total_buckets === 0 && (
        <Card>
          <CardBody>
            <p className="text-center text-sm" style={{ color: 'var(--text-tertiary)' }}>No exposed buckets found for this target.</p>
          </CardBody>
        </Card>
      )}
    </div>
  )
}
