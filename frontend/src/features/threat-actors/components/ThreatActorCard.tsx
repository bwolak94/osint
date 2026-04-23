import { Shield, Target, Globe, Activity } from 'lucide-react'
import { Card, CardHeader, CardBody } from '@/shared/components/Card'
import { Badge } from '@/shared/components/Badge'
import type { ThreatActor, ThreatActorMotivation, ThreatActorSophistication } from '../types'

const COUNTRY_FLAG: Record<string, string> = {
  RU: '🇷🇺',
  KP: '🇰🇵',
  CN: '🇨🇳',
  IR: '🇮🇷',
  GB: '🇬🇧',
  US: '🇺🇸',
  UA: '🇺🇦',
  KR: '🇰🇷',
  IN: '🇮🇳',
  PK: '🇵🇰',
}

const SOPHISTICATION_VARIANT: Record<
  ThreatActorSophistication,
  'danger' | 'warning' | 'info' | 'neutral'
> = {
  'nation-state': 'danger',
  high: 'warning',
  medium: 'info',
  low: 'neutral',
}

const MOTIVATION_VARIANT: Record<
  ThreatActorMotivation,
  'warning' | 'brand' | 'info' | 'danger'
> = {
  financial: 'warning',
  espionage: 'brand',
  hacktivism: 'info',
  sabotage: 'danger',
}

interface Props {
  actor: ThreatActor
  selected: boolean
  onSelect: (actor: ThreatActor) => void
}

export function ThreatActorCard({ actor, selected, onSelect }: Props) {
  const flag = actor.origin_country ? (COUNTRY_FLAG[actor.origin_country] ?? '🌐') : '🌐'
  const topMalware = actor.malware_families.slice(0, 3)
  const topTtps = actor.ttps.slice(0, 4)

  return (
    <Card
      hover
      onClick={() => onSelect(actor)}
      className={`transition-all ${selected ? 'ring-2 ring-brand-500/60' : ''}`}
    >
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-base">{flag}</span>
              <h3
                className="truncate text-sm font-semibold"
                style={{ color: 'var(--text-primary)' }}
              >
                {actor.name}
              </h3>
            </div>
            {actor.aliases.length > 0 && (
              <p
                className="mt-0.5 truncate text-xs"
                style={{ color: 'var(--text-tertiary)' }}
                title={actor.aliases.join(', ')}
              >
                {actor.aliases.slice(0, 2).join(', ')}
                {actor.aliases.length > 2 && ` +${actor.aliases.length - 2}`}
              </p>
            )}
          </div>
          <div className="flex shrink-0 flex-col items-end gap-1">
            <Badge variant={SOPHISTICATION_VARIANT[actor.sophistication]} size="sm">
              {actor.sophistication}
            </Badge>
            <Badge variant={MOTIVATION_VARIANT[actor.motivation]} size="sm">
              {actor.motivation}
            </Badge>
          </div>
        </div>
      </CardHeader>

      <CardBody className="space-y-3">
        <p
          className="line-clamp-2 text-xs leading-relaxed"
          style={{ color: 'var(--text-secondary)' }}
        >
          {actor.description}
        </p>

        {/* Stats row */}
        <div className="flex items-center gap-4 text-xs" style={{ color: 'var(--text-tertiary)' }}>
          <span className="flex items-center gap-1">
            <Shield className="h-3 w-3" />
            {actor.ioc_count.toLocaleString()} IOCs
          </span>
          {actor.last_seen && (
            <span className="flex items-center gap-1">
              <Activity className="h-3 w-3" />
              Last seen {actor.last_seen}
            </span>
          )}
          {actor.active_since && (
            <span className="flex items-center gap-1">
              <Globe className="h-3 w-3" />
              Since {actor.active_since}
            </span>
          )}
        </div>

        {/* Malware families */}
        {topMalware.length > 0 && (
          <div>
            <p
              className="mb-1 text-[10px] font-medium uppercase tracking-wider"
              style={{ color: 'var(--text-tertiary)' }}
            >
              Malware
            </p>
            <div className="flex flex-wrap gap-1">
              {topMalware.map((mw) => (
                <Badge key={mw} variant="neutral" size="sm">
                  {mw}
                </Badge>
              ))}
              {actor.malware_families.length > 3 && (
                <Badge variant="neutral" size="sm">
                  +{actor.malware_families.length - 3}
                </Badge>
              )}
            </div>
          </div>
        )}

        {/* MITRE TTPs */}
        {topTtps.length > 0 && (
          <div>
            <p
              className="mb-1 text-[10px] font-medium uppercase tracking-wider"
              style={{ color: 'var(--text-tertiary)' }}
            >
              TTPs
            </p>
            <div className="flex flex-wrap gap-1">
              {topTtps.map((ttp) => (
                <Badge key={ttp} variant="brand" size="sm">
                  {ttp}
                </Badge>
              ))}
              {actor.ttps.length > 4 && (
                <Badge variant="brand" size="sm">
                  +{actor.ttps.length - 4}
                </Badge>
              )}
            </div>
          </div>
        )}

        {/* Targets */}
        <div className="flex items-start gap-1">
          <Target className="mt-0.5 h-3 w-3 shrink-0" style={{ color: 'var(--text-tertiary)' }} />
          <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
            {actor.targets.slice(0, 3).join(', ')}
            {actor.targets.length > 3 && ` +${actor.targets.length - 3} more`}
          </p>
        </div>

        {/* Confidence */}
        <div className="flex items-center justify-between text-xs">
          <span style={{ color: 'var(--text-tertiary)' }}>
            Confidence
          </span>
          <span
            className="font-semibold tabular-nums"
            style={{ color: 'var(--success-500)' }}
          >
            {Math.round(actor.confidence * 100)}%
          </span>
        </div>
      </CardBody>
    </Card>
  )
}
