import { Cpu, Wifi, Info } from 'lucide-react'
import { Card, CardHeader, CardBody } from '@/shared/components/Card'
import { Badge } from '@/shared/components/Badge'
import type { MacLookup } from '../types'

interface Props {
  lookup: MacLookup
}

export function MacResultDisplay({ lookup }: Props) {
  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        {/* Manufacturer */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Cpu className="h-4 w-4" style={{ color: 'var(--brand-500)' }} />
              <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Manufacturer</h3>
            </div>
          </CardHeader>
          <CardBody>
            <dl className="space-y-2 text-sm">
              {[
                ['MAC Address', lookup.mac_address],
                ['OUI Prefix', lookup.oui_prefix],
                ['Manufacturer', lookup.manufacturer],
                ['Country', lookup.manufacturer_country],
                ['Device Type', lookup.device_type],
              ].map(([label, value]) => (
                <div key={label} className="flex justify-between gap-4">
                  <dt style={{ color: 'var(--text-tertiary)' }}>{label}</dt>
                  <dd className="font-medium" style={{ color: 'var(--text-primary)' }}>{value || '—'}</dd>
                </div>
              ))}
            </dl>
          </CardBody>
        </Card>

        {/* Flags */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Wifi className="h-4 w-4" style={{ color: 'var(--brand-500)' }} />
              <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>MAC Flags</h3>
            </div>
          </CardHeader>
          <CardBody>
            <dl className="space-y-3 text-sm">
              <div className="flex items-center justify-between gap-4">
                <dt style={{ color: 'var(--text-tertiary)' }}>Locally Administered</dt>
                <dd>
                  <Badge variant={lookup.is_private ? 'warning' : 'neutral'} size="sm">
                    {lookup.is_private == null ? 'Unknown' : lookup.is_private ? 'Yes (randomized)' : 'No'}
                  </Badge>
                </dd>
              </div>
              <div className="flex items-center justify-between gap-4">
                <dt style={{ color: 'var(--text-tertiary)' }}>Multicast</dt>
                <dd>
                  <Badge variant={lookup.is_multicast ? 'info' : 'neutral'} size="sm">
                    {lookup.is_multicast == null ? 'Unknown' : lookup.is_multicast ? 'Yes' : 'No'}
                  </Badge>
                </dd>
              </div>
            </dl>
            {lookup.is_private && (
              <p className="mt-3 text-xs" style={{ color: 'var(--text-tertiary)' }}>
                This MAC uses the locally administered bit, indicating it may be a randomized/spoofed address (common on modern mobile devices for privacy).
              </p>
            )}
          </CardBody>
        </Card>
      </div>

      {/* Raw data */}
      {Object.keys(lookup.raw_data).length > 0 && (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Info className="h-4 w-4" style={{ color: 'var(--brand-500)' }} />
              <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Raw Response</h3>
            </div>
          </CardHeader>
          <CardBody>
            <table className="w-full text-sm">
              <tbody>
                {Object.entries(lookup.raw_data).map(([k, v]) => (
                  <tr key={k} className="border-b last:border-0" style={{ borderColor: 'var(--border-subtle)' }}>
                    <td className="py-1.5 pr-4 font-mono text-xs" style={{ color: 'var(--text-tertiary)', width: '40%' }}>{k}</td>
                    <td className="py-1.5 font-medium" style={{ color: 'var(--text-primary)' }}>{v !== null && v !== undefined ? String(v) : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardBody>
        </Card>
      )}
    </div>
  )
}
