import { useState } from 'react'
import { Globe, AlertTriangle } from 'lucide-react'
import { Card, CardHeader, CardBody } from '@/shared/components/Card'
import { Badge } from '@/shared/components/Badge'
import type { DomainPermutationScan, PermutationItem } from '../types'

interface Props {
  scan: DomainPermutationScan
}

const FUZZER_LABELS: Record<string, string> = {
  omission: 'Char Omission',
  repetition: 'Char Repeat',
  transposition: 'Transposition',
  homoglyph: 'Homoglyph',
  hyphenation: 'Hyphen',
  'tld-swap': 'TLD Swap',
  subdomain: 'Subdomain',
  addition: 'Addition',
}

export function PermutationResultsDisplay({ scan }: Props) {
  const [showAll, setShowAll] = useState(false)
  const [filterRegistered, setFilterRegistered] = useState(true)

  const filtered = scan.permutations.filter((p) => !filterRegistered || p.registered)
  const displayed = showAll ? filtered : filtered.slice(0, 50)

  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="grid gap-4 sm:grid-cols-3">
        {[
          { label: 'Total Generated', value: scan.total_permutations, variant: 'neutral' as const },
          { label: 'Registered', value: scan.registered_count, variant: scan.registered_count > 0 ? 'warning' as const : 'success' as const },
          { label: 'Safe', value: scan.total_permutations - scan.registered_count, variant: 'neutral' as const },
        ].map(({ label, value, variant }) => (
          <div key={label} className="rounded-xl border px-4 py-3 text-center" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border-subtle)' }}>
            <p className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>{value}</p>
            <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>{label}</p>
          </div>
        ))}
      </div>

      {scan.registered_count > 0 && (
        <div className="flex items-center gap-2 rounded-lg border px-4 py-3" style={{ background: 'var(--warning-900)', borderColor: 'var(--warning-500)' }}>
          <AlertTriangle className="h-4 w-4 shrink-0" style={{ color: 'var(--warning-500)' }} />
          <span className="text-sm" style={{ color: 'var(--warning-500)' }}>
            {scan.registered_count} lookalike domain{scan.registered_count !== 1 ? 's are' : ' is'} registered — potential typosquatting/phishing risk
          </span>
        </div>
      )}

      {/* Filter toggle */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => setFilterRegistered(true)}
          className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${filterRegistered ? 'bg-brand-900 text-brand-400' : 'text-text-secondary hover:bg-bg-overlay'}`}
        >
          Registered only ({scan.registered_count})
        </button>
        <button
          onClick={() => setFilterRegistered(false)}
          className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${!filterRegistered ? 'bg-brand-900 text-brand-400' : 'text-text-secondary hover:bg-bg-overlay'}`}
        >
          All ({scan.total_permutations})
        </button>
      </div>

      {/* Results table */}
      <Card>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[500px]">
            <thead>
              <tr className="border-b text-left text-xs font-medium" style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-tertiary)' }}>
                <th className="px-4 py-3">Domain</th>
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">DNS A</th>
              </tr>
            </thead>
            <tbody>
              {displayed.map((p) => (
                <tr key={p.domain} className="border-b transition-colors hover:bg-bg-overlay" style={{ borderColor: 'var(--border-subtle)' }}>
                  <td className="px-4 py-3 font-mono text-sm" style={{ color: 'var(--text-primary)' }}>
                    <a href={`https://${p.domain}`} target="_blank" rel="noopener noreferrer" className="hover:underline" style={{ color: p.registered ? 'var(--danger-400)' : 'var(--text-secondary)' }}>
                      {p.domain}
                    </a>
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant="neutral" size="sm">{FUZZER_LABELS[p.fuzzer] ?? p.fuzzer}</Badge>
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant={p.registered ? 'danger' : 'neutral'} size="sm">{p.registered ? 'Registered' : 'Free'}</Badge>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs" style={{ color: 'var(--text-tertiary)' }}>
                    {p.dns_a.slice(0, 2).join(', ') || '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {filtered.length === 0 && (
          <CardBody>
            <p className="text-center text-sm" style={{ color: 'var(--text-tertiary)' }}>
              {filterRegistered ? 'No registered lookalike domains found.' : 'No permutations generated.'}
            </p>
          </CardBody>
        )}

        {filtered.length > 50 && !showAll && (
          <div className="border-t px-4 py-3 text-center" style={{ borderColor: 'var(--border-subtle)' }}>
            <button onClick={() => setShowAll(true)} className="text-xs font-medium hover:underline" style={{ color: 'var(--brand-400)' }}>
              Show all {filtered.length} results
            </button>
          </div>
        )}
      </Card>
    </div>
  )
}
