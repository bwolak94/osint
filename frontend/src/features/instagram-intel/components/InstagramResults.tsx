import {
  ExternalLink,
  Users,
  Image,
  CheckCircle,
  Lock,
  Tag,
  Link,
} from 'lucide-react'
import { Card, CardBody } from '@/shared/components/Card'
import type { InstagramIntelScan, InstagramProfile } from '../types'

interface Props {
  scan: InstagramIntelScan
}

function ProfileCard({ profile }: { profile: InstagramProfile }) {
  return (
    <Card>
      <CardBody>
        <div className="flex items-start gap-4">
          {/* Avatar */}
          <div
            className="flex h-14 w-14 shrink-0 items-center justify-center overflow-hidden rounded-full border text-xl font-bold"
            style={{ background: 'var(--bg-elevated)', borderColor: 'var(--border-subtle)', color: 'var(--brand-400)' }}
          >
            {profile.profile_pic_url ? (
              <img
                src={profile.profile_pic_url}
                alt={profile.username ?? 'profile'}
                className="h-full w-full object-cover"
                onError={(e) => {
                  ;(e.currentTarget as HTMLImageElement).style.display = 'none'
                }}
              />
            ) : (
              (profile.username?.[0] ?? '?').toUpperCase()
            )}
          </div>

          {/* Main info */}
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                {profile.full_name ?? profile.username ?? 'Unknown'}
              </h3>
              {profile.is_verified && (
                <CheckCircle className="h-4 w-4 shrink-0" style={{ color: 'var(--brand-400)' }} aria-label="Verified" />
              )}
              {profile.is_private && (
                <span
                  className="flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs"
                  style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-tertiary)' }}
                >
                  <Lock className="h-3 w-3" /> Private
                </span>
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
              <p className="mt-0.5 font-mono text-xs" style={{ color: 'var(--text-tertiary)' }}>
                @{profile.username}
              </p>
            )}
            {profile.user_id && (
              <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
                ID: {profile.user_id}
              </p>
            )}

            {profile.biography && (
              <p className="mt-2 line-clamp-3 text-xs" style={{ color: 'var(--text-secondary)' }}>
                {profile.biography}
              </p>
            )}

            {profile.external_url && (
              <a
                href={profile.external_url}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-1 flex items-center gap-1 text-xs hover:underline"
                style={{ color: 'var(--brand-400)' }}
              >
                <Link className="h-3 w-3" />
                {profile.external_url.replace(/^https?:\/\//, '').replace(/\/$/, '')}
              </a>
            )}

            {/* Stats */}
            <div className="mt-3 flex flex-wrap gap-3 text-xs" style={{ color: 'var(--text-secondary)' }}>
              {profile.follower_count !== null && (
                <span className="flex items-center gap-1">
                  <Users className="h-3 w-3 shrink-0" />
                  {profile.follower_count.toLocaleString()} followers
                </span>
              )}
              {profile.following_count !== null && (
                <span className="flex items-center gap-1">
                  <Users className="h-3 w-3 shrink-0" style={{ color: 'var(--text-tertiary)' }} />
                  {profile.following_count.toLocaleString()} following
                </span>
              )}
              {profile.media_count !== null && (
                <span className="flex items-center gap-1">
                  <Image className="h-3 w-3 shrink-0" />
                  {profile.media_count.toLocaleString()} posts
                </span>
              )}
            </div>
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
                aria-label={`Open Instagram profile for ${profile.username}`}
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
              {profile.source.replace(/_/g, ' ')}
            </span>
          </div>
        </div>
      </CardBody>
    </Card>
  )
}

export function InstagramResults({ scan }: Props) {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
          {scan.total_results} profile{scan.total_results !== 1 ? 's' : ''} found
        </p>
      </div>
      {scan.results.map((profile, idx) => (
        <ProfileCard key={profile.user_id ?? profile.username ?? idx} profile={profile} />
      ))}
    </div>
  )
}
