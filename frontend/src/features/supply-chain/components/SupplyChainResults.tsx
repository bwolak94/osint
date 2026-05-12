import { Package } from 'lucide-react'
import { Card, CardHeader } from '@/shared/components/Card'
import { Badge } from '@/shared/components/Badge'
import type { SupplyChainScan } from '../types'

interface Props {
  scan: SupplyChainScan
}

function riskVariant(score: string): 'danger' | 'warning' | 'info' | 'neutral' {
  if (score === 'critical') return 'danger'
  if (score === 'high') return 'danger'
  if (score === 'medium') return 'warning'
  return 'neutral'
}

export function SupplyChainResults({ scan }: Props) {
  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-3">
        {[
          { label: 'Packages Found', value: scan.total_packages },
          { label: 'Total CVEs', value: scan.total_cves },
          { label: 'Target Type', value: scan.target_type.replace('_', ' ').toUpperCase() },
        ].map(({ label, value }) => (
          <div key={label} className="rounded-xl border px-4 py-3 text-center" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border-subtle)' }}>
            <p className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>{value}</p>
            <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>{label}</p>
          </div>
        ))}
      </div>

      {scan.packages.length > 0 && (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Package className="h-4 w-4" style={{ color: 'var(--brand-500)' }} />
              <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Packages ({scan.total_packages})</h3>
            </div>
          </CardHeader>
          <div className="divide-y" style={{ borderColor: 'var(--border-subtle)' }}>
            {scan.packages.map((pkg, i) => (
              <div key={i} className="px-4 py-3">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono font-medium" style={{ color: 'var(--text-primary)' }}>{pkg.name}</span>
                      <Badge variant="neutral" size="sm">{pkg.registry}</Badge>
                      {pkg.cve_count > 0 && <Badge variant={riskVariant(pkg.risk_score)} size="sm">{pkg.cve_count} CVE{pkg.cve_count !== 1 ? 's' : ''}</Badge>}
                    </div>
                    {(pkg.cves?.length ?? 0) > 0 && (
                      <ul className="mt-2 space-y-1">
                        {(pkg.cves ?? []).slice(0, 3).map((cve) => (
                          <li key={cve.id} className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
                            <span className="font-mono" style={{ color: 'var(--danger-400)' }}>{cve.id}</span>
                            {cve.summary && ` — ${cve.summary.slice(0, 80)}…`}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}
