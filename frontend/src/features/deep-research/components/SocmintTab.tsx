import { CheckCircle2, XCircle, Users, Hash } from 'lucide-react'
import { Card, CardBody, CardHeader } from '@/shared/components/Card'
import { Badge } from '@/shared/components/Badge'
import type { SocmintResult } from '../types'

interface Props {
  data: SocmintResult
}

export function SocmintTab({ data }: Props) {
  const found = data.social_profiles.filter((p) => p.found)
  const notFound = data.social_profiles.filter((p) => !p.found)

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-3">
        <StatCard label="Profiles Found" value={data.profiles_found} accent="var(--brand-400)" />
        <StatCard label="Platforms Checked" value={data.platforms_checked} />
        <StatCard label="Username Variants" value={data.username_variations.length} />
      </div>

      {data.username_variations.length > 0 && (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Hash className="h-4 w-4" style={{ color: 'var(--brand-400)' }} />
              <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                Username Variations
              </span>
            </div>
          </CardHeader>
          <CardBody>
            <div className="flex flex-wrap gap-2">
              {data.username_variations.map((v) => (
                <code
                  key={v}
                  className="rounded border px-2 py-0.5 text-xs font-mono"
                  style={{ background: 'var(--bg-elevated)', borderColor: 'var(--border-subtle)', color: 'var(--text-primary)' }}
                >
                  {v}
                </code>
              ))}
            </div>
          </CardBody>
        </Card>
      )}

      {found.length > 0 && (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4" style={{ color: 'var(--success-500)' }} />
              <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                Active Profiles ({found.length})
              </span>
            </div>
          </CardHeader>
          <div className="divide-y" style={{ borderColor: 'var(--border-subtle)' }}>
            {found.map((p) => (
              <div key={p.platform} className="flex items-center justify-between gap-3 px-5 py-3">
                <div className="flex items-center gap-3">
                  <Users className="h-4 w-4 shrink-0" style={{ color: 'var(--brand-400)' }} />
                  <div>
                    <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                      {p.platform}
                    </p>
                    {p.url && (
                      <a
                        href={p.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs font-mono truncate max-w-[240px] block hover:underline"
                        style={{ color: 'var(--brand-400)' }}
                      >
                        {p.url}
                      </a>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {p.followers !== null && (
                    <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
                      {p.followers.toLocaleString()} followers
                    </span>
                  )}
                  <Badge variant="neutral" size="sm">Found</Badge>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {notFound.length > 0 && (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <XCircle className="h-4 w-4" style={{ color: 'var(--text-tertiary)' }} />
              <span className="text-sm font-semibold" style={{ color: 'var(--text-secondary)' }}>
                Not Found ({notFound.length})
              </span>
            </div>
          </CardHeader>
          <CardBody>
            <div className="flex flex-wrap gap-2">
              {notFound.map((p) => (
                <Badge key={p.platform} variant="neutral" size="sm">
                  {p.platform}
                </Badge>
              ))}
            </div>
          </CardBody>
        </Card>
      )}
    </div>
  )
}

function StatCard({ label, value, accent }: { label: string; value: number; accent?: string }) {
  return (
    <div
      className="rounded-xl border px-4 py-3 text-center"
      style={{ background: 'var(--bg-surface)', borderColor: 'var(--border-subtle)' }}
    >
      <p className="text-2xl font-bold" style={{ color: accent ?? 'var(--text-primary)' }}>
        {value}
      </p>
      <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>{label}</p>
    </div>
  )
}
