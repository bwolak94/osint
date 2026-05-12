import { Phone, Wifi } from 'lucide-react'
import { Card, CardBody, CardHeader } from '@/shared/components/Card'
import { Badge } from '@/shared/components/Badge'
import type { PhoneIntelResult } from '../types'

interface Props {
  data: PhoneIntelResult
}

export function PhoneTab({ data }: Props) {
  const spamColor = data.spam_score > 70
    ? 'var(--danger-400)'
    : data.spam_score > 40
      ? 'var(--warning-400)'
      : 'var(--success-400)'

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-4">
        {[
          { label: 'Country', value: data.country },
          { label: 'Carrier', value: data.carrier },
          { label: 'Line Type', value: data.line_type },
          { label: 'Valid', value: data.is_valid ? 'Yes' : 'No' },
        ].map(({ label, value }) => (
          <div
            key={label}
            className="rounded-xl border px-4 py-3 text-center"
            style={{ background: 'var(--bg-surface)', borderColor: 'var(--border-subtle)' }}
          >
            <p className="text-base font-bold" style={{ color: 'var(--text-primary)' }}>{value}</p>
            <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>{label}</p>
          </div>
        ))}
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Phone className="h-4 w-4" style={{ color: 'var(--brand-400)' }} />
              <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                Spam Score
              </span>
            </div>
          </CardHeader>
          <CardBody>
            <div className="flex items-center gap-3">
              <div
                className="text-4xl font-bold"
                style={{ color: spamColor }}
              >
                {data.spam_score}
              </div>
              <div>
                <div
                  className="h-3 w-32 rounded-full overflow-hidden"
                  style={{ background: 'var(--bg-elevated)' }}
                >
                  <div
                    className="h-full rounded-full transition-all"
                    style={{ width: `${data.spam_score}%`, background: spamColor }}
                  />
                </div>
                <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>
                  {data.breach_count} breach(es)
                </p>
              </div>
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Wifi className="h-4 w-4" style={{ color: 'var(--brand-400)' }} />
              <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                Associated Services
              </span>
            </div>
          </CardHeader>
          <CardBody>
            <div className="flex flex-wrap gap-2">
              {data.associated_services.map((s) => (
                <Badge key={s} variant="info" size="sm">{s}</Badge>
              ))}
              {data.associated_services.length === 0 && (
                <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>None found</p>
              )}
            </div>
          </CardBody>
        </Card>
      </div>
    </div>
  )
}
