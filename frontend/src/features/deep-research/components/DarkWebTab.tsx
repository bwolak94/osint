import { Eye, AlertTriangle, FileSearch, Globe } from 'lucide-react'
import { Card, CardBody, CardHeader } from '@/shared/components/Card'
import { Badge } from '@/shared/components/Badge'
import type { DarkWebResult } from '../types'

interface Props {
  data: DarkWebResult
}

export function DarkWebTab({ data }: Props) {
  const totalHits = data.leaks_found + data.paste_hits + data.forum_mentions

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-3">
        {[
          { label: 'Data Leaks', value: data.leaks_found, danger: data.leaks_found > 0 },
          { label: 'Paste Sites', value: data.paste_hits, danger: data.paste_hits > 0 },
          { label: 'Forum Mentions', value: data.forum_mentions, danger: false },
        ].map(({ label, value, danger }) => (
          <div
            key={label}
            className="rounded-xl border px-4 py-3 text-center"
            style={{ background: 'var(--bg-surface)', borderColor: 'var(--border-subtle)' }}
          >
            <p
              className="text-2xl font-bold"
              style={{ color: danger ? 'var(--danger-400)' : 'var(--text-primary)' }}
            >
              {value}
            </p>
            <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>{label}</p>
          </div>
        ))}
      </div>

      {totalHits === 0 ? (
        <div
          className="rounded-xl border py-12 text-center"
          style={{ borderColor: 'var(--border-subtle)' }}
        >
          <Eye className="mx-auto h-8 w-8 mb-2" style={{ color: 'var(--text-tertiary)' }} />
          <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>
            No dark web exposure detected
          </p>
        </div>
      ) : (
        <>
          {data.marketplaces_seen.length > 0 && (
            <Card>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <Globe className="h-4 w-4" style={{ color: 'var(--danger-400)' }} />
                  <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                    Seen On Marketplaces / Channels
                  </span>
                </div>
              </CardHeader>
              <CardBody>
                <div className="flex flex-wrap gap-2">
                  {data.marketplaces_seen.map((m) => (
                    <Badge key={m} variant="danger" size="sm">{m}</Badge>
                  ))}
                </div>
              </CardBody>
            </Card>
          )}

          {data.sample_records.length > 0 && (
            <Card>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <FileSearch className="h-4 w-4" style={{ color: 'var(--warning-400)' }} />
                  <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                    Sample Records
                  </span>
                </div>
              </CardHeader>
              <div className="divide-y" style={{ borderColor: 'var(--border-subtle)' }}>
                {data.sample_records.map((rec, i) => (
                  <div key={i} className="flex flex-wrap gap-3 px-5 py-3">
                    {Object.entries(rec).map(([k, v]) => (
                      <div key={k} className="text-xs">
                        <span style={{ color: 'var(--text-tertiary)' }}>{k}: </span>
                        <span className="font-mono" style={{ color: 'var(--text-secondary)' }}>{String(v)}</span>
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            </Card>
          )}

          <div
            className="rounded-lg border px-4 py-3 flex items-start gap-2"
            style={{ background: 'var(--danger-900)', borderColor: 'var(--danger-700)' }}
          >
            <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" style={{ color: 'var(--danger-400)' }} />
            <p className="text-xs" style={{ color: 'var(--danger-300)' }}>
              Data retrieved from dark web intelligence sources. Handle with care and in accordance
              with applicable legal requirements.
            </p>
          </div>
        </>
      )}
    </div>
  )
}
