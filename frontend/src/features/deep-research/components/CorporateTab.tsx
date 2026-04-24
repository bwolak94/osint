import { Building2, Users, Hash, CheckCircle2, XCircle } from 'lucide-react'
import { Card, CardBody, CardHeader } from '@/shared/components/Card'
import { Badge } from '@/shared/components/Badge'
import type { CorporateResult } from '../types'

interface Props {
  data: CorporateResult
}

export function CorporateTab({ data }: Props) {
  return (
    <div className="space-y-4">
      {/* KRS Records */}
      {data.krs_records.length > 0 ? (
        data.krs_records.map((rec, i) => (
          <Card key={i}>
            <CardHeader>
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <Building2 className="h-4 w-4" style={{ color: 'var(--brand-400)' }} />
                  <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                    {rec.company_name}
                  </span>
                </div>
                <Badge
                  variant={rec.status === 'ACTIVE' ? 'neutral' : 'danger'}
                  size="sm"
                >
                  {rec.status}
                </Badge>
              </div>
            </CardHeader>
            <CardBody className="space-y-3">
              <div className="grid gap-2 sm:grid-cols-3 text-sm">
                <InfoRow label="KRS" value={rec.krs_number ?? '—'} mono />
                <InfoRow label="NIP" value={rec.nip ?? '—'} mono />
                <InfoRow label="REGON" value={rec.regon ?? '—'} mono />
                <InfoRow label="Registration Date" value={rec.registration_date ?? '—'} />
                <InfoRow label="Share Capital" value={rec.share_capital ?? '—'} />
                {rec.address && <InfoRow label="Address" value={rec.address} className="sm:col-span-3" />}
              </div>

              {rec.board_members.length > 0 && (
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: 'var(--text-tertiary)' }}>
                    Board Members
                  </p>
                  <ul className="space-y-1">
                    {rec.board_members.map((m, j) => (
                      <li key={j} className="flex items-center gap-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
                        <Users className="h-3.5 w-3.5 shrink-0" style={{ color: 'var(--brand-400)' }} />
                        {m}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </CardBody>
          </Card>
        ))
      ) : (
        <div
          className="rounded-xl border py-10 text-center"
          style={{ borderColor: 'var(--border-subtle)' }}
        >
          <Building2 className="mx-auto h-8 w-8 mb-2" style={{ color: 'var(--text-tertiary)' }} />
          <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>
            No KRS records found. Provide a NIP or company name to search Polish business registries.
          </p>
        </div>
      )}

      {/* REGON / CEIDG */}
      <div className="grid gap-3 sm:grid-cols-2">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Hash className="h-4 w-4" style={{ color: 'var(--brand-400)' }} />
              <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>CEIDG</span>
            </div>
          </CardHeader>
          <CardBody>
            <div className="flex items-center gap-2">
              {data.ceidg_found ? (
                <CheckCircle2 className="h-5 w-5" style={{ color: 'var(--success-500)' }} />
              ) : (
                <XCircle className="h-5 w-5" style={{ color: 'var(--text-tertiary)' }} />
              )}
              <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                {data.ceidg_found ? 'Found in CEIDG (sole trader registry)' : 'Not found in CEIDG'}
              </span>
            </div>
          </CardBody>
        </Card>

        {data.regon_data && (
          <Card>
            <CardHeader>
              <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>REGON Data</span>
            </CardHeader>
            <CardBody>
              <dl className="space-y-1 text-sm">
                {Object.entries(data.regon_data).map(([k, v]) => (
                  <div key={k} className="flex justify-between gap-3">
                    <dt style={{ color: 'var(--text-tertiary)' }}>{k}</dt>
                    <dd className="font-mono" style={{ color: 'var(--text-primary)' }}>{String(v)}</dd>
                  </div>
                ))}
              </dl>
            </CardBody>
          </Card>
        )}
      </div>

      {/* Related entities */}
      {data.related_entities.length > 0 && (
        <Card>
          <CardHeader>
            <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              Related Entities
            </span>
          </CardHeader>
          <CardBody>
            <div className="flex flex-wrap gap-2">
              {data.related_entities.map((e) => (
                <Badge key={e} variant="info" size="sm">{e}</Badge>
              ))}
            </div>
          </CardBody>
        </Card>
      )}
    </div>
  )
}

function InfoRow({
  label, value, mono, className = '',
}: {
  label: string
  value: string
  mono?: boolean
  className?: string
}) {
  return (
    <div className={className}>
      <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>{label}</p>
      <p
        className={`text-sm ${mono ? 'font-mono' : ''}`}
        style={{ color: 'var(--text-primary)' }}
      >
        {value}
      </p>
    </div>
  )
}
