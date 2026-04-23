import { X, ExternalLink, Shield, Globe, Target, AlertTriangle, Activity } from 'lucide-react'
import { Badge } from '@/shared/components/Badge'
import { Card, CardHeader, CardBody } from '@/shared/components/Card'
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
  onClose: () => void
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <p
      className="mb-2 text-[10px] font-semibold uppercase tracking-wider"
      style={{ color: 'var(--text-tertiary)' }}
    >
      {children}
    </p>
  )
}

export function ThreatActorDetail({ actor, onClose }: Props) {
  const flag = actor.origin_country ? (COUNTRY_FLAG[actor.origin_country] ?? '🌐') : '🌐'
  const confidencePct = Math.round(actor.confidence * 100)

  return (
    <Card className="flex h-full flex-col overflow-hidden">
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-xl">{flag}</span>
              <h2
                className="text-base font-bold"
                style={{ color: 'var(--text-primary)' }}
              >
                {actor.name}
              </h2>
            </div>
            <div className="mt-1 flex flex-wrap gap-1.5">
              <Badge variant={SOPHISTICATION_VARIANT[actor.sophistication]} size="sm">
                {actor.sophistication}
              </Badge>
              <Badge variant={MOTIVATION_VARIANT[actor.motivation]} size="sm">
                {actor.motivation}
              </Badge>
              <Badge variant="neutral" size="sm">
                {actor.source}
              </Badge>
            </div>
          </div>
          <button
            onClick={onClose}
            className="shrink-0 rounded p-1 transition-colors hover:bg-bg-overlay"
            aria-label="Close detail panel"
          >
            <X className="h-4 w-4" style={{ color: 'var(--text-tertiary)' }} />
          </button>
        </div>
      </CardHeader>

      <CardBody className="flex-1 space-y-5 overflow-y-auto">
        {/* Description */}
        <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
          {actor.description}
        </p>

        {/* Meta */}
        <div className="grid grid-cols-2 gap-3 text-xs">
          {actor.active_since && (
            <div>
              <p style={{ color: 'var(--text-tertiary)' }}>Active since</p>
              <p className="font-medium" style={{ color: 'var(--text-primary)' }}>
                {actor.active_since}
              </p>
            </div>
          )}
          {actor.last_seen && (
            <div>
              <p style={{ color: 'var(--text-tertiary)' }}>Last seen</p>
              <p className="font-medium" style={{ color: 'var(--text-primary)' }}>
                {actor.last_seen}
              </p>
            </div>
          )}
          <div>
            <p style={{ color: 'var(--text-tertiary)' }}>IOC count</p>
            <p className="font-medium" style={{ color: 'var(--text-primary)' }}>
              {actor.ioc_count.toLocaleString()}
            </p>
          </div>
          {actor.origin_country && (
            <div>
              <p style={{ color: 'var(--text-tertiary)' }}>Country</p>
              <p className="font-medium" style={{ color: 'var(--text-primary)' }}>
                {flag} {actor.origin_country}
              </p>
            </div>
          )}
        </div>

        {/* Confidence score */}
        <div>
          <SectionTitle>Confidence score</SectionTitle>
          <div className="flex items-center gap-3">
            <div
              className="h-2 flex-1 overflow-hidden rounded-full"
              style={{ background: 'var(--bg-overlay)' }}
              role="progressbar"
              aria-valuenow={confidencePct}
              aria-valuemin={0}
              aria-valuemax={100}
            >
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{
                  width: `${confidencePct}%`,
                  background:
                    confidencePct >= 90
                      ? 'var(--success-500)'
                      : confidencePct >= 70
                      ? 'var(--warning-500)'
                      : 'var(--danger-400)',
                }}
              />
            </div>
            <span
              className="w-10 shrink-0 text-right text-xs font-semibold tabular-nums"
              style={{ color: 'var(--text-primary)' }}
            >
              {confidencePct}%
            </span>
          </div>
        </div>

        {/* Aliases */}
        {actor.aliases.length > 0 && (
          <div>
            <SectionTitle>Known aliases</SectionTitle>
            <div className="flex flex-wrap gap-1.5">
              {actor.aliases.map((alias) => (
                <Badge key={alias} variant="neutral" size="md">
                  {alias}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {/* Targeted sectors */}
        {actor.targets.length > 0 && (
          <div>
            <SectionTitle>
              <Target className="mr-1 inline h-3 w-3" />
              Targeted sectors
            </SectionTitle>
            <div className="flex flex-wrap gap-1.5">
              {actor.targets.map((sector) => (
                <Badge key={sector} variant="info" size="sm">
                  {sector}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {/* MITRE ATT&CK TTPs */}
        {actor.ttps.length > 0 && (
          <div>
            <SectionTitle>
              <Shield className="mr-1 inline h-3 w-3" />
              MITRE ATT&CK TTPs
            </SectionTitle>
            <div className="flex flex-wrap gap-1.5">
              {actor.ttps.map((ttp) => {
                const techId = ttp.replace('/', '.')
                return (
                  <a
                    key={ttp}
                    href={`https://attack.mitre.org/techniques/${techId}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium transition-colors hover:border-brand-500/50"
                    style={{
                      background: 'var(--bg-overlay)',
                      borderColor: 'var(--border-subtle)',
                      color: 'var(--brand-400)',
                    }}
                  >
                    {ttp}
                    <ExternalLink className="h-2.5 w-2.5" />
                  </a>
                )
              })}
            </div>
          </div>
        )}

        {/* Malware families */}
        {actor.malware_families.length > 0 && (
          <div>
            <SectionTitle>
              <Activity className="mr-1 inline h-3 w-3" />
              Malware families
            </SectionTitle>
            <div className="flex flex-wrap gap-1.5">
              {actor.malware_families.map((mw) => (
                <Badge key={mw} variant="warning" size="sm">
                  {mw}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {/* CVE exploits */}
        {actor.cve_exploits.length > 0 && (
          <div>
            <SectionTitle>
              <AlertTriangle className="mr-1 inline h-3 w-3" />
              CVE exploits
            </SectionTitle>
            <div className="flex flex-wrap gap-1.5">
              {actor.cve_exploits.map((cve) => (
                <a
                  key={cve}
                  href={`https://nvd.nist.gov/vuln/detail/${cve}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium transition-colors hover:border-danger-500/50"
                  style={{
                    background: 'var(--bg-overlay)',
                    borderColor: 'var(--border-subtle)',
                    color: 'var(--danger-400)',
                  }}
                >
                  {cve}
                  <ExternalLink className="h-2.5 w-2.5" />
                </a>
              ))}
            </div>
          </div>
        )}

        {/* Infrastructure */}
        {actor.infrastructure.length > 0 && (
          <div>
            <SectionTitle>
              <Globe className="mr-1 inline h-3 w-3" />
              Known infrastructure
            </SectionTitle>
            <ul className="space-y-1">
              {actor.infrastructure.map((ioc) => (
                <li
                  key={ioc}
                  className="rounded px-2 py-1 font-mono text-xs"
                  style={{
                    background: 'var(--bg-overlay)',
                    color: 'var(--text-secondary)',
                  }}
                >
                  {ioc}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Source attribution */}
        <div
          className="rounded-md border px-3 py-2 text-xs"
          style={{
            background: 'var(--bg-overlay)',
            borderColor: 'var(--border-subtle)',
            color: 'var(--text-tertiary)',
          }}
        >
          Source attribution:{' '}
          <span className="font-semibold" style={{ color: 'var(--text-secondary)' }}>
            {actor.source}
          </span>{' '}
          &mdash; data may be incomplete or reflect historical state.
        </div>
      </CardBody>
    </Card>
  )
}
