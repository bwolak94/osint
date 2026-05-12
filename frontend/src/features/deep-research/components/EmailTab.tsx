import { ShieldAlert, CheckCircle2, XCircle, Server } from 'lucide-react'
import { Card, CardBody, CardHeader } from '@/shared/components/Card'
import { Badge } from '@/shared/components/Badge'
import type { EmailIntelResult } from '../types'

interface Props {
  data: EmailIntelResult
}

export function EmailTab({ data }: Props) {
  return (
    <div className="space-y-4">
      {/* Summary row */}
      <div className="grid gap-3 sm:grid-cols-4">
        <MetaCard
          label="Valid"
          icon={data.is_valid ? <CheckCircle2 className="h-5 w-5" style={{ color: 'var(--success-500)' }} /> : <XCircle className="h-5 w-5" style={{ color: 'var(--danger-500)' }} />}
          value={data.is_valid ? 'Yes' : 'No'}
        />
        <MetaCard label="Disposable" value={data.is_disposable ? 'Yes' : 'No'} danger={data.is_disposable} />
        <MetaCard label="Breaches" value={String(data.breach_count)} danger={data.breach_count > 0} />
        <MetaCard label="Registered On" value={String(data.registered_services.length) + ' services'} />
      </div>

      {/* Breaches */}
      {data.breach_count > 0 && (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <ShieldAlert className="h-4 w-4" style={{ color: 'var(--danger-400)' }} />
              <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                Data Breaches ({data.breach_count})
              </span>
            </div>
          </CardHeader>
          <CardBody>
            <div className="flex flex-wrap gap-2">
              {data.breach_sources.map((b) => (
                <Badge key={b} variant="danger" size="sm">{b}</Badge>
              ))}
            </div>
          </CardBody>
        </Card>
      )}

      {/* Holehe / registered services */}
      {data.registered_services.length > 0 && (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Server className="h-4 w-4" style={{ color: 'var(--brand-400)' }} />
              <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                Registered Services — Holehe Hits
              </span>
            </div>
          </CardHeader>
          <CardBody>
            <div className="flex flex-wrap gap-2">
              {data.registered_services.map((s) => (
                <Badge
                  key={s}
                  variant={data.holehe_hits.includes(s) ? 'brand' : 'neutral'}
                  size="sm"
                >
                  {s}
                  {data.holehe_hits.includes(s) && ' ✓'}
                </Badge>
              ))}
            </div>
            <p className="mt-3 text-xs" style={{ color: 'var(--text-tertiary)' }}>
              Highlighted services confirmed via Holehe without triggering notifications.
            </p>
          </CardBody>
        </Card>
      )}
    </div>
  )
}

function MetaCard({
  label, value, icon, danger,
}: {
  label: string
  value: string
  icon?: React.ReactNode
  danger?: boolean
}) {
  return (
    <div
      className="rounded-xl border px-4 py-3 text-center"
      style={{ background: 'var(--bg-surface)', borderColor: 'var(--border-subtle)' }}
    >
      {icon && <div className="flex justify-center mb-1">{icon}</div>}
      <p
        className="text-lg font-bold"
        style={{ color: danger ? 'var(--danger-400)' : 'var(--text-primary)' }}
      >
        {value}
      </p>
      <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>{label}</p>
    </div>
  )
}
