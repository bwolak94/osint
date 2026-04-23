import { ExternalLink, Users } from 'lucide-react'
import { Card, CardHeader, CardBody } from '@/shared/components/Card'
import { Badge } from '@/shared/components/Badge'
import { EmptyState } from '@/shared/components/EmptyState'
import type { FediverseScan, FediverseProfile } from '../types'

interface Props {
  scan: FediverseScan
}

function platformBadgeVariant(platform: string): 'info' | 'neutral' {
  if (platform === 'bluesky') return 'info'
  return 'neutral'
}

function ProfileCard({ profile }: { profile: FediverseProfile }) {
  const bio = profile.bio
    ? profile.bio.length > 100
      ? `${profile.bio.slice(0, 100)}…`
      : profile.bio
    : null

  return (
    <div
      className="flex gap-4 rounded-lg border p-4"
      style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-surface)' }}
    >
      {profile.avatar_url ? (
        <img
          src={profile.avatar_url}
          alt={`Avatar for ${profile.handle}`}
          className="h-12 w-12 shrink-0 rounded-full object-cover"
        />
      ) : (
        <div
          className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full"
          style={{ background: 'var(--bg-elevated)' }}
          aria-hidden="true"
        >
          <Users className="h-5 w-5" style={{ color: 'var(--text-tertiary)' }} />
        </div>
      )}

      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-medium" style={{ color: 'var(--text-primary)' }}>
            {profile.display_name || profile.handle}
          </span>
          <Badge variant={platformBadgeVariant(profile.platform)} size="sm">
            {profile.platform}
          </Badge>
          {profile.instance && (
            <Badge variant="neutral" size="sm">
              {profile.instance}
            </Badge>
          )}
        </div>

        <p className="mt-0.5 font-mono text-xs" style={{ color: 'var(--text-tertiary)' }}>
          @{profile.handle}
        </p>

        {bio && (
          <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)' }}>
            {bio}
          </p>
        )}

        <div className="mt-2 flex flex-wrap gap-4 text-xs" style={{ color: 'var(--text-tertiary)' }}>
          {profile.followers != null && (
            <span>
              <strong style={{ color: 'var(--text-primary)' }}>{profile.followers.toLocaleString()}</strong>{' '}
              followers
            </span>
          )}
          {profile.following != null && (
            <span>
              <strong style={{ color: 'var(--text-primary)' }}>{profile.following.toLocaleString()}</strong>{' '}
              following
            </span>
          )}
          {profile.posts != null && (
            <span>
              <strong style={{ color: 'var(--text-primary)' }}>{profile.posts.toLocaleString()}</strong> posts
            </span>
          )}
        </div>

        {profile.did && (
          <p
            className="mt-1 truncate font-mono text-xs"
            style={{ color: 'var(--brand-400)' }}
            title={profile.did}
          >
            {profile.did}
          </p>
        )}
      </div>

      {profile.profile_url && (
        <a
          href={profile.profile_url}
          target="_blank"
          rel="noopener noreferrer"
          className="shrink-0 rounded p-1 transition-colors hover:bg-bg-overlay"
          aria-label={`Open ${profile.handle} profile in new tab`}
        >
          <ExternalLink className="h-4 w-4" style={{ color: 'var(--brand-500)' }} />
        </a>
      )}
    </div>
  )
}

export function FediverseResults({ scan }: Props) {
  return (
    <div className="space-y-4">
      <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
        <strong style={{ color: 'var(--text-primary)' }}>{scan.total_results}</strong> profiles found across{' '}
        <strong style={{ color: 'var(--text-primary)' }}>{(scan.platforms_searched ?? []).length}</strong> platforms
      </p>

      {(scan.results ?? []).length > 0 ? (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Users className="h-4 w-4" style={{ color: 'var(--brand-500)' }} />
              <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                Profiles Found
              </h3>
            </div>
          </CardHeader>
          <CardBody>
            <div className="grid gap-3 sm:grid-cols-2">
              {(scan.results ?? []).map((profile, i) => (
                <ProfileCard key={i} profile={profile} />
              ))}
            </div>
          </CardBody>
        </Card>
      ) : (
        <Card>
          <CardBody>
            <EmptyState
              variant="no-data"
              title="No profiles found"
              description="No matching accounts were found on the searched platforms."
            />
          </CardBody>
        </Card>
      )}
    </div>
  )
}
