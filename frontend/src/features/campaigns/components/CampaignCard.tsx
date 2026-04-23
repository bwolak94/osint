import { useCallback } from 'react'
import { Shield, Flag, Edit2, Trash2, ChevronRight } from 'lucide-react'
import { Card, CardBody, CardFooter } from '@/shared/components/Card'
import { Badge } from '@/shared/components/Badge'
import type { Campaign, TLP, CampaignStatus } from '../types'

// ─── TLP helpers ──────────────────────────────────────────────────────────────

const tlpColor: Record<TLP, string> = {
  WHITE: 'var(--text-tertiary)',
  GREEN: 'var(--success-500)',
  AMBER: 'var(--warning-500)',
  RED: 'var(--danger-400)',
}

const tlpBorderColor: Record<TLP, string> = {
  WHITE: 'var(--border-subtle)',
  GREEN: 'var(--success-500)',
  AMBER: 'var(--warning-500)',
  RED: 'var(--danger-400)',
}

type BadgeVariant = 'success' | 'warning' | 'danger' | 'info' | 'neutral' | 'brand'

const statusVariant: Record<CampaignStatus, BadgeVariant> = {
  active: 'success',
  completed: 'info',
  archived: 'neutral',
}

const statusLabel: Record<CampaignStatus, string> = {
  active: 'Active',
  completed: 'Completed',
  archived: 'Archived',
}

// ─── Date formatter ───────────────────────────────────────────────────────────

function formatDate(iso: string | null): string | null {
  if (!iso) return null
  return new Date(iso).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}

// ─── Props ────────────────────────────────────────────────────────────────────

interface CampaignCardProps {
  campaign: Campaign
  isSelected: boolean
  onSelect: (campaign: Campaign) => void
  onEdit: (campaign: Campaign) => void
  onDelete: (id: string) => void
}

// ─── Component ────────────────────────────────────────────────────────────────

export function CampaignCard({ campaign, isSelected, onSelect, onEdit, onDelete }: CampaignCardProps) {
  const handleSelect = useCallback(() => onSelect(campaign), [campaign, onSelect])
  const handleEdit = useCallback(
    (e: React.MouseEvent) => { e.stopPropagation(); onEdit(campaign) },
    [campaign, onEdit],
  )
  const handleDelete = useCallback(
    (e: React.MouseEvent) => { e.stopPropagation(); onDelete(campaign.id) },
    [campaign.id, onDelete],
  )

  const startDate = formatDate(campaign.start_date)
  const endDate = formatDate(campaign.end_date)

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={handleSelect}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleSelect() }}
      aria-pressed={isSelected}
      aria-label={`Campaign: ${campaign.title}`}
      className="focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 rounded-lg"
    >
      <Card
        className="h-full transition-all"
        style={{
          borderColor: isSelected ? 'var(--brand-500)' : tlpBorderColor[campaign.tlp],
          borderLeftWidth: '3px',
        } as React.CSSProperties}
      >
        {/* Header row */}
        <CardBody className="pb-3">
          <div className="mb-2 flex items-start justify-between gap-2">
            <div
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
              style={{ background: isSelected ? 'var(--brand-500)' : 'var(--bg-overlay)' }}
              aria-hidden="true"
            >
              <Shield
                className="h-4 w-4"
                style={{ color: isSelected ? '#fff' : tlpColor[campaign.tlp] }}
              />
            </div>

            <div className="flex items-center gap-1.5">
              {/* TLP badge */}
              <span
                className="inline-flex items-center gap-1 rounded-full border px-1.5 py-0.5 text-[10px] font-semibold font-mono"
                style={{
                  color: tlpColor[campaign.tlp],
                  borderColor: tlpColor[campaign.tlp],
                  background: 'transparent',
                }}
                aria-label={`TLP: ${campaign.tlp}`}
              >
                <Flag className="h-2.5 w-2.5" aria-hidden="true" />
                TLP:{campaign.tlp}
              </span>

              {/* Status badge */}
              <Badge variant={statusVariant[campaign.status]} size="sm">
                {statusLabel[campaign.status]}
              </Badge>
            </div>
          </div>

          {/* Title */}
          <h3
            className="mt-1 text-sm font-semibold leading-tight"
            style={{ color: 'var(--text-primary)' }}
          >
            {campaign.title}
          </h3>

          {/* Description */}
          {campaign.description && (
            <p
              className="mt-1 line-clamp-2 text-xs leading-relaxed"
              style={{ color: 'var(--text-secondary)' }}
            >
              {campaign.description}
            </p>
          )}

          {/* Investigation count */}
          <div className="mt-2.5 flex items-center gap-1.5">
            <Shield className="h-3.5 w-3.5" style={{ color: 'var(--text-tertiary)' }} aria-hidden="true" />
            <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
              {campaign.investigation_count} investigation{campaign.investigation_count !== 1 ? 's' : ''}
            </span>
          </div>

          {/* Tags */}
          {campaign.tags.length > 0 && (
            <div
              className="mt-2.5 flex flex-wrap gap-1"
              aria-label="Campaign tags"
            >
              {campaign.tags.slice(0, 4).map((tag) => (
                <span
                  key={tag}
                  className="rounded px-1.5 py-0.5 text-[10px] font-mono"
                  style={{ background: 'var(--bg-overlay)', color: 'var(--text-tertiary)' }}
                >
                  {tag}
                </span>
              ))}
              {campaign.tags.length > 4 && (
                <span
                  className="rounded px-1.5 py-0.5 text-[10px] font-mono"
                  style={{ background: 'var(--bg-overlay)', color: 'var(--text-tertiary)' }}
                >
                  +{campaign.tags.length - 4}
                </span>
              )}
            </div>
          )}

          {/* Dates */}
          {(startDate ?? endDate) && (
            <div className="mt-2.5 flex flex-wrap gap-3">
              {startDate && (
                <div className="flex items-center gap-1">
                  <span className="text-[10px]" style={{ color: 'var(--text-tertiary)' }}>
                    Start: <span style={{ color: 'var(--text-secondary)' }}>{startDate}</span>
                  </span>
                </div>
              )}
              {endDate && (
                <div className="flex items-center gap-1">
                  <span className="text-[10px]" style={{ color: 'var(--text-tertiary)' }}>
                    End: <span style={{ color: 'var(--text-secondary)' }}>{endDate}</span>
                  </span>
                </div>
              )}
            </div>
          )}
        </CardBody>

        {/* Action footer */}
        <CardFooter className="flex items-center justify-between py-2">
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={handleEdit}
              className="flex items-center gap-1 rounded px-2 py-1 text-xs transition-colors hover:bg-bg-overlay focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
              style={{ color: 'var(--text-tertiary)' }}
              aria-label={`Edit campaign: ${campaign.title}`}
            >
              <Edit2 className="h-3 w-3" aria-hidden="true" />
              Edit
            </button>
            <button
              type="button"
              onClick={handleDelete}
              className="flex items-center gap-1 rounded px-2 py-1 text-xs transition-colors hover:bg-danger-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-danger-500"
              style={{ color: 'var(--danger-400)' }}
              aria-label={`Delete campaign: ${campaign.title}`}
            >
              <Trash2 className="h-3 w-3" aria-hidden="true" />
              Delete
            </button>
          </div>

          <button
            type="button"
            onClick={handleSelect}
            className="flex items-center gap-1 rounded px-2 py-1 text-xs font-medium transition-colors hover:bg-brand-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
            style={{ color: 'var(--brand-400)' }}
            aria-label={`View campaign: ${campaign.title}`}
          >
            View
            <ChevronRight className="h-3 w-3" aria-hidden="true" />
          </button>
        </CardFooter>
      </Card>
    </div>
  )
}
