import { Shield, AlertTriangle, Clock, User, Building2, MapPin, FileText } from 'lucide-react'
import { Card, CardHeader, CardBody } from '@/shared/components/Card'
import { Badge } from '@/shared/components/Badge'
import type { DocMetadata } from '../types'

interface Props {
  doc: DocMetadata
}

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(iso))
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function DocMetadataDisplay({ doc }: Props) {
  const riskFlags = [
    doc.has_macros && { label: 'Macros Detected', variant: 'danger' as const },
    doc.has_hidden_content && { label: 'Hidden Content', variant: 'warning' as const },
    doc.has_tracked_changes && { label: 'Tracked Changes', variant: 'warning' as const },
    (doc.gps_lat !== null) && { label: 'GPS Coordinates', variant: 'info' as const },
  ].filter(Boolean) as Array<{ label: string; variant: 'danger' | 'warning' | 'info' }>

  return (
    <div className="space-y-4">
      {/* Risk flags */}
      {riskFlags.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 rounded-lg border px-4 py-3" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border-subtle)' }}>
          <AlertTriangle className="h-4 w-4 shrink-0" style={{ color: 'var(--warning-500)' }} />
          <span className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Risk flags:</span>
          {riskFlags.map((f) => (
            <Badge key={f.label} variant={f.variant} size="sm">{f.label}</Badge>
          ))}
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        {/* Identity */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <User className="h-4 w-4" style={{ color: 'var(--brand-500)' }} />
              <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Identity</h3>
            </div>
          </CardHeader>
          <CardBody>
            <dl className="space-y-2 text-sm">
              {[
                ['Author', doc.author],
                ['Last Modified By', doc.last_modified_by],
                ['Creator Tool', doc.creator_tool],
              ].map(([label, value]) => (
                <div key={label} className="flex justify-between gap-4">
                  <dt style={{ color: 'var(--text-tertiary)' }}>{label}</dt>
                  <dd className="truncate font-medium" style={{ color: 'var(--text-primary)' }}>{value || '—'}</dd>
                </div>
              ))}
            </dl>
          </CardBody>
        </Card>

        {/* Organization */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Building2 className="h-4 w-4" style={{ color: 'var(--brand-500)' }} />
              <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Organization & File</h3>
            </div>
          </CardHeader>
          <CardBody>
            <dl className="space-y-2 text-sm">
              {[
                ['Company', doc.company],
                ['Format', doc.doc_format?.toUpperCase()],
                ['File Size', formatFileSize(doc.file_size)],
                ['Revisions', doc.revision_count?.toString()],
              ].map(([label, value]) => (
                <div key={label} className="flex justify-between gap-4">
                  <dt style={{ color: 'var(--text-tertiary)' }}>{label}</dt>
                  <dd className="font-medium" style={{ color: 'var(--text-primary)' }}>{value || '—'}</dd>
                </div>
              ))}
            </dl>
          </CardBody>
        </Card>

        {/* Timestamps */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4" style={{ color: 'var(--brand-500)' }} />
              <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Timestamps</h3>
            </div>
          </CardHeader>
          <CardBody>
            <dl className="space-y-2 text-sm">
              {[
                ['Created', formatDate(doc.created_at_doc)],
                ['Modified', formatDate(doc.modified_at_doc)],
                ['Analyzed', formatDate(doc.created_at)],
              ].map(([label, value]) => (
                <div key={label} className="flex justify-between gap-4">
                  <dt style={{ color: 'var(--text-tertiary)' }}>{label}</dt>
                  <dd className="font-medium" style={{ color: 'var(--text-primary)' }}>{value}</dd>
                </div>
              ))}
            </dl>
          </CardBody>
        </Card>

        {/* GPS / Security */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Shield className="h-4 w-4" style={{ color: 'var(--brand-500)' }} />
              <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Security & Location</h3>
            </div>
          </CardHeader>
          <CardBody>
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between gap-4">
                <dt style={{ color: 'var(--text-tertiary)' }}>Macros</dt>
                <dd><Badge variant={doc.has_macros ? 'danger' : 'neutral'} size="sm">{doc.has_macros ? 'Yes' : 'No'}</Badge></dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt style={{ color: 'var(--text-tertiary)' }}>Hidden Content</dt>
                <dd><Badge variant={doc.has_hidden_content ? 'warning' : 'neutral'} size="sm">{doc.has_hidden_content ? 'Yes' : 'No'}</Badge></dd>
              </div>
              {doc.gps_lat !== null && (
                <div className="flex justify-between gap-4">
                  <dt style={{ color: 'var(--text-tertiary)' }}>GPS</dt>
                  <dd className="font-medium" style={{ color: 'var(--text-primary)' }}>
                    <a href={`https://maps.google.com/maps?q=${doc.gps_lat},${doc.gps_lon}`} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 underline" style={{ color: 'var(--brand-500)' }}>
                      <MapPin className="h-3 w-3" />{doc.gps_lat?.toFixed(5)}, {doc.gps_lon?.toFixed(5)}
                    </a>
                  </dd>
                </div>
              )}
            </dl>
          </CardBody>
        </Card>
      </div>

      {/* Raw metadata */}
      {Object.keys(doc.raw_metadata).length > 0 && (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <FileText className="h-4 w-4" style={{ color: 'var(--brand-500)' }} />
              <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>All Metadata</h3>
            </div>
          </CardHeader>
          <CardBody>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <tbody>
                  {Object.entries(doc.raw_metadata).map(([k, v]) => (
                    <tr key={k} className="border-b last:border-0" style={{ borderColor: 'var(--border-subtle)' }}>
                      <td className="py-1.5 pr-4 font-mono text-xs" style={{ color: 'var(--text-tertiary)', width: '40%' }}>{k}</td>
                      <td className="py-1.5 font-medium break-all" style={{ color: 'var(--text-primary)' }}>{v !== null ? String(v) : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardBody>
        </Card>
      )}
    </div>
  )
}
