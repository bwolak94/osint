import { Shield, AlertTriangle, Network, Info } from 'lucide-react'
import { Card, CardHeader, CardBody } from '@/shared/components/Card'
import { Badge } from '@/shared/components/Badge'
import type { EmailHeaderCheck } from '../types'

interface Props {
  check: EmailHeaderCheck
}

function authVariant(result: string | null): 'success' | 'danger' | 'warning' | 'neutral' {
  if (!result) return 'neutral'
  if (['pass', 'valid'].includes(result)) return 'success'
  if (['fail', 'reject'].includes(result)) return 'danger'
  return 'warning'
}

export function HeaderResultsDisplay({ check }: Props) {
  return (
    <div className="space-y-4">
      {check.is_spoofed && (
        <div className="flex items-center gap-2 rounded-lg border px-4 py-3" style={{ background: 'var(--danger-900)', borderColor: 'var(--danger-500)' }}>
          <AlertTriangle className="h-4 w-4 shrink-0" style={{ color: 'var(--danger-500)' }} />
          <span className="text-sm font-medium" style={{ color: 'var(--danger-500)' }}>Spoofing detected — SPF and DKIM both failed</span>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        {/* Sender info */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Info className="h-4 w-4" style={{ color: 'var(--brand-500)' }} />
              <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Sender Information</h3>
            </div>
          </CardHeader>
          <CardBody>
            <dl className="space-y-2 text-sm">
              {[
                ['From', check.sender_from],
                ['Reply-To', check.sender_reply_to],
                ['Subject', check.subject],
                ['Originating IP', check.originating_ip],
                ['Location', [check.originating_city, check.originating_country].filter(Boolean).join(', ')],
              ].map(([label, value]) => (
                <div key={label} className="flex justify-between gap-4">
                  <dt style={{ color: 'var(--text-tertiary)' }}>{label}</dt>
                  <dd className="truncate font-medium text-right" style={{ color: 'var(--text-primary)' }}>{value || '—'}</dd>
                </div>
              ))}
            </dl>
          </CardBody>
        </Card>

        {/* Auth results */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Shield className="h-4 w-4" style={{ color: 'var(--brand-500)' }} />
              <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Authentication Results</h3>
            </div>
          </CardHeader>
          <CardBody>
            <dl className="space-y-3 text-sm">
              {[
                ['SPF', check.spf_result],
                ['DKIM', check.dkim_result],
                ['DMARC', check.dmarc_result],
              ].map(([label, result]) => (
                <div key={label} className="flex items-center justify-between gap-4">
                  <dt className="font-mono" style={{ color: 'var(--text-tertiary)' }}>{label}</dt>
                  <dd><Badge variant={authVariant(result ?? null)} size="sm">{result ?? 'not checked'}</Badge></dd>
                </div>
              ))}
            </dl>
          </CardBody>
        </Card>
      </div>

      {/* Routing hops */}
      {check.hops.length > 0 && (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Network className="h-4 w-4" style={{ color: 'var(--brand-500)' }} />
              <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Email Routing Path ({check.hops.length} hops)</h3>
            </div>
          </CardHeader>
          <CardBody>
            <ol className="space-y-3">
              {check.hops.map((hop) => (
                <li key={hop.index} className="flex gap-4 rounded-lg border px-4 py-3" style={{ borderColor: 'var(--border-subtle)' }}>
                  <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold" style={{ background: 'var(--brand-900)', color: 'var(--brand-400)' }}>
                    {hop.index + 1}
                  </div>
                  <div className="min-w-0 flex-1 space-y-0.5 text-xs">
                    {hop.from_host && <p style={{ color: 'var(--text-secondary)' }}>From: <span className="font-mono" style={{ color: 'var(--text-primary)' }}>{hop.from_host}</span></p>}
                    {hop.by_host && <p style={{ color: 'var(--text-secondary)' }}>By: <span className="font-mono" style={{ color: 'var(--text-primary)' }}>{hop.by_host}</span></p>}
                    {hop.ip && <p style={{ color: 'var(--text-secondary)' }}>IP: <span className="font-mono font-medium" style={{ color: 'var(--brand-400)' }}>{hop.ip}</span></p>}
                    {hop.protocol && <p style={{ color: 'var(--text-tertiary)' }}>{hop.protocol}</p>}
                  </div>
                </li>
              ))}
            </ol>
          </CardBody>
        </Card>
      )}
    </div>
  )
}
