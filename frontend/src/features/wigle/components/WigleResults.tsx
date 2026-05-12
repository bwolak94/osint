import { ExternalLink } from 'lucide-react'
import { Badge } from '@/shared/components/Badge'
import { Card } from '@/shared/components/Card'
import type { WigleScan } from '../types'

interface Props {
  scan: WigleScan
}

function formatLocation(city: string | null, region: string | null, country: string | null): string {
  return [city, region, country].filter(Boolean).join(', ') || '—'
}

function formatDate(value: string | null): string {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return new Intl.DateTimeFormat(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  }).format(d)
}

export function WigleResults({ scan }: Props) {
  if (scan.total_results === 0) {
    return (
      <div
        className="rounded-xl border px-6 py-8 text-center"
        style={{ background: 'var(--bg-surface)', borderColor: 'var(--border-subtle)' }}
      >
        <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
          No networks found
        </p>
        <p className="mt-1 text-xs" style={{ color: 'var(--text-tertiary)' }}>
          Note: WiGLE API requires a valid API key.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
        <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>
          {scan.total_results}
        </span>{' '}
        {scan.total_results === 1 ? 'network' : 'networks'} found for{' '}
        <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>
          {scan.query_type.toUpperCase()}
        </span>
        :{' '}
        <span className="font-mono" style={{ color: 'var(--text-primary)' }}>
          {scan.query}
        </span>
      </p>

      <Card>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[700px]">
            <thead>
              <tr
                className="border-b text-left text-xs font-medium"
                style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-tertiary)' }}
              >
                <th className="px-4 py-3">BSSID</th>
                <th className="px-4 py-3">SSID</th>
                <th className="px-4 py-3">Encryption</th>
                <th className="px-4 py-3">Channel</th>
                <th className="px-4 py-3">Location</th>
                <th className="px-4 py-3">First Seen</th>
                <th className="px-4 py-3">Last Seen</th>
                <th className="px-4 py-3">Map</th>
              </tr>
            </thead>
            <tbody>
              {(scan.results ?? []).map((net, i) => (
                <tr
                  key={i}
                  className="border-b transition-colors hover:bg-bg-overlay"
                  style={{ borderColor: 'var(--border-subtle)' }}
                >
                  <td
                    className="px-4 py-3 font-mono text-sm"
                    style={{ color: 'var(--text-primary)' }}
                  >
                    {net.netid || '—'}
                  </td>
                  <td
                    className="px-4 py-3 text-sm"
                    style={{ color: 'var(--text-secondary)' }}
                  >
                    {net.ssid || <span style={{ color: 'var(--text-tertiary)' }}>Hidden</span>}
                  </td>
                  <td className="px-4 py-3">
                    {net.encryption ? (
                      <Badge variant="neutral" size="sm">
                        {net.encryption}
                      </Badge>
                    ) : (
                      <span style={{ color: 'var(--text-tertiary)' }}>—</span>
                    )}
                  </td>
                  <td
                    className="px-4 py-3 text-sm"
                    style={{ color: 'var(--text-secondary)' }}
                  >
                    {net.channel != null ? `CH ${net.channel}` : '—'}
                  </td>
                  <td
                    className="px-4 py-3 text-sm"
                    style={{ color: 'var(--text-secondary)' }}
                  >
                    {formatLocation(net.city, net.region, net.country)}
                  </td>
                  <td
                    className="px-4 py-3 text-sm"
                    style={{ color: 'var(--text-secondary)' }}
                  >
                    {formatDate(net.first_seen)}
                  </td>
                  <td
                    className="px-4 py-3 text-sm"
                    style={{ color: 'var(--text-secondary)' }}
                  >
                    {formatDate(net.last_seen)}
                  </td>
                  <td className="px-4 py-3">
                    {net.maps_url ? (
                      <a
                        href={net.maps_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        aria-label={`Open map for ${net.netid}`}
                        className="inline-flex items-center gap-1 text-xs hover:underline"
                        style={{ color: 'var(--brand-500)' }}
                      >
                        <ExternalLink className="h-3 w-3" aria-hidden="true" />
                        Map
                      </a>
                    ) : (
                      <span style={{ color: 'var(--text-tertiary)' }}>—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}
