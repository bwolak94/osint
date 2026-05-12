import {
  ExternalLink,
  MapPin,
  Briefcase,
  GraduationCap,
  Users,
  CheckCircle,
  Tag,
} from 'lucide-react'
import { Card, CardBody } from '@/shared/components/Card'
import type { FacebookIntelScan, FacebookProfile } from '../types'

interface Props {
  scan: FacebookIntelScan
}

function ProfileCard({ profile }: { profile: FacebookProfile }) {
  return (
    <Card>
      <CardBody>
        <div className="flex items-start gap-4">
          {/* Avatar */}
          <div
            className="flex h-14 w-14 shrink-0 items-center justify-center overflow-hidden rounded-full border text-xl font-bold"
            style={{ background: 'var(--bg-elevated)', borderColor: 'var(--border-subtle)', color: 'var(--brand-400)' }}
          >
            {profile.avatar_url ? (
              <img
                src={profile.avatar_url}
                alt={profile.name ?? 'profile'}
                className="h-full w-full object-cover"
                onError={(e) => {
                  ;(e.currentTarget as HTMLImageElement).style.display = 'none'
                }}
              />
            ) : (
              (profile.name?.[0] ?? '?').toUpperCase()
            )}
          </div>

          {/* Main info */}
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                {profile.name ?? 'Unknown'}
              </h3>
              {profile.verified && (
                <CheckCircle className="h-4 w-4 shrink-0" style={{ color: 'var(--brand-400)' }} aria-label="Verified" />
              )}
              {profile.category && (
                <span
                  className="rounded-full border px-2 py-0.5 text-xs"
                  style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-tertiary)' }}
                >
                  {profile.category}
                </span>
              )}
            </div>

            {profile.username && (
              <p className="mt-0.5 text-xs font-mono" style={{ color: 'var(--text-tertiary)' }}>
                @{profile.username}
              </p>
            )}
            {profile.uid && (
              <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
                ID: {profile.uid}
              </p>
            )}

            {profile.bio && (
              <p className="mt-2 text-xs line-clamp-3" style={{ color: 'var(--text-secondary)' }}>
                {profile.bio}
              </p>
            )}

            {/* Meta */}
            <div className="mt-3 flex flex-wrap gap-3 text-xs" style={{ color: 'var(--text-secondary)' }}>
              {profile.location && (
                <span className="flex items-center gap-1">
                  <MapPin className="h-3 w-3 shrink-0" />
                  {profile.location}
                </span>
              )}
              {profile.hometown && profile.hometown !== profile.location && (
                <span className="flex items-center gap-1">
                  <MapPin className="h-3 w-3 shrink-0" style={{ color: 'var(--text-tertiary)' }} />
                  {profile.hometown}
                </span>
              )}
              {profile.followers !== null && (
                <span className="flex items-center gap-1">
                  <Users className="h-3 w-3 shrink-0" />
                  {profile.followers.toLocaleString()} followers
                </span>
              )}
              {profile.friends !== null && (
                <span className="flex items-center gap-1">
                  <Users className="h-3 w-3 shrink-0" style={{ color: 'var(--text-tertiary)' }} />
                  {profile.friends.toLocaleString()} friends
                </span>
              )}
            </div>

            {profile.work.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {profile.work.map((w, i) => (
                  <span
                    key={i}
                    className="flex items-center gap-1 rounded border px-2 py-0.5 text-xs"
                    style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-secondary)' }}
                  >
                    <Briefcase className="h-3 w-3 shrink-0" />
                    {w}
                  </span>
                ))}
              </div>
            )}

            {profile.education.length > 0 && (
              <div className="mt-1.5 flex flex-wrap gap-1.5">
                {profile.education.map((e, i) => (
                  <span
                    key={i}
                    className="flex items-center gap-1 rounded border px-2 py-0.5 text-xs"
                    style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-secondary)' }}
                  >
                    <GraduationCap className="h-3 w-3 shrink-0" />
                    {e}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="flex shrink-0 flex-col items-end gap-2">
            {profile.profile_url && (
              <a
                href={profile.profile_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 rounded border px-2 py-1 text-xs transition-colors hover:bg-brand-900"
                style={{ borderColor: 'var(--border-subtle)', color: 'var(--brand-400)' }}
                aria-label={`Open profile for ${profile.name}`}
              >
                <ExternalLink className="h-3 w-3" />
                Profile
              </a>
            )}
            <span
              className="flex items-center gap-1 rounded px-2 py-0.5 text-xs"
              style={{ background: 'var(--bg-elevated)', color: 'var(--text-tertiary)' }}
              title="Data source"
            >
              <Tag className="h-3 w-3" />
              {profile.source.replace('_', ' ')}
            </span>
          </div>
        </div>
      </CardBody>
    </Card>
  )
}

export function FacebookResults({ scan }: Props) {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
          {scan.total_results} profile{scan.total_results !== 1 ? 's' : ''} found
        </p>
      </div>
      {scan.results.map((profile, idx) => (
        <ProfileCard key={profile.uid ?? idx} profile={profile} />
      ))}
    </div>
  )
}
