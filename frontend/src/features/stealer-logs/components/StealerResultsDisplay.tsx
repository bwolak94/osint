import { AlertTriangle, Bug, Shield } from 'lucide-react'
import { Card, CardHeader, CardBody } from '@/shared/components/Card'
import { Badge } from '@/shared/components/Badge'
import type { StealerLogCheck, Infection } from '../types'

interface Props {
  check: StealerLogCheck
}

function riskVariant(level: string): 'danger' | 'warning' | 'info' | 'neutral' {
  if (level === 'critical') return 'danger'
  if (level === 'high') return 'danger'
  if (level === 'medium') return 'warning'
  if (level === 'low') return 'info'
  return 'neutral'
}

function InfectionCard({ infection }: { infection: Infection }) {
  if (infection.error) {
    return (
      <div className="rounded-lg border px-4 py-3" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-elevated)' }}>
        <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>{infection.error}</p>
      </div>
    )
  }

  return (
    <div className="rounded-lg border px-4 py-4" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-surface)' }}>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Badge variant={riskVariant(infection.risk_level)} size="sm">{infection.risk_level.toUpperCase()} RISK</Badge>
        {infection.stealer_family && <Badge variant="neutral" size="sm">{infection.stealer_family}</Badge>}
        {infection.has_crypto_wallet && <Badge variant="warning" size="sm">Crypto Wallet</Badge>}
      </div>
      <dl className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-3">
        {[
          ['Date Compromised', infection.date_compromised],
          ['Computer', infection.computer_name],
          ['OS', infection.operating_system],
          ['Country', infection.country],
          ['IP', infection.ip],
          ['Credentials', infection.credentials_count?.toString()],
          ['Session Cookies', infection.cookies_count?.toString()],
          ['Autofill Records', infection.autofill_count?.toString()],
        ].map(([label, value]) => value ? (
          <div key={label}>
            <dt style={{ color: 'var(--text-tertiary)' }}>{label}</dt>
            <dd className="font-medium mt-0.5" style={{ color: 'var(--text-primary)' }}>{value}</dd>
          </div>
        ) : null)}
      </dl>
    </div>
  )
}

export function StealerResultsDisplay({ check }: Props) {
  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="grid gap-4 sm:grid-cols-3">
        {[
          { label: 'Infections Found', value: check.total_infections },
          { label: 'Sources Checked', value: (check.sources_checked ?? []).length },
          { label: 'Query Type', value: check.query_type.toUpperCase() },
        ].map(({ label, value }) => (
          <div key={label} className="rounded-xl border px-4 py-3 text-center" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border-subtle)' }}>
            <p className="text-2xl font-bold" style={{ color: typeof value === 'number' && value > 0 ? 'var(--danger-400)' : 'var(--text-primary)' }}>{value}</p>
            <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>{label}</p>
          </div>
        ))}
      </div>

      {check.total_infections > 0 && (
        <div className="flex items-center gap-2 rounded-lg border px-4 py-3" style={{ background: 'var(--danger-900)', borderColor: 'var(--danger-500)' }}>
          <AlertTriangle className="h-4 w-4 shrink-0" style={{ color: 'var(--danger-500)' }} />
          <span className="text-sm font-medium" style={{ color: 'var(--danger-500)' }}>
            {check.total_infections} infostealer infection{check.total_infections !== 1 ? 's' : ''} found for this target
          </span>
        </div>
      )}

      {check.total_infections === 0 && (
        <div className="flex items-center gap-2 rounded-lg border px-4 py-3" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border-subtle)' }}>
          <Shield className="h-4 w-4 shrink-0" style={{ color: 'var(--success-500)' }} />
          <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>No infostealer records found for this target</span>
        </div>
      )}

      {/* Infections list */}
      {(check.infections ?? []).length > 0 && (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Bug className="h-4 w-4" style={{ color: 'var(--brand-500)' }} />
              <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Infection Records</h3>
            </div>
          </CardHeader>
          <CardBody>
            <div className="space-y-3">
              {(check.infections ?? []).map((infection, i) => (
                <InfectionCard key={i} infection={infection} />
              ))}
            </div>
          </CardBody>
        </Card>
      )}
    </div>
  )
}
