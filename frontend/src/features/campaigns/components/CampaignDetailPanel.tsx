import { useState, useCallback, useId } from 'react'
import { Link, Trash2, ChevronRight, Flag, Shield, Target } from 'lucide-react'
import { Card, CardHeader, CardBody } from '@/shared/components/Card'
import { Badge } from '@/shared/components/Badge'
import { useCampaignGraph, useSimilarCampaigns, useAddInvestigation, useRemoveInvestigation } from '../hooks'
import type { Campaign, TLP, CampaignStatus } from '../types'

// ─── TLP / status helpers ─────────────────────────────────────────────────────

const tlpColor: Record<TLP, string> = {
  WHITE: 'var(--text-tertiary)',
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

// ─── Formatting ───────────────────────────────────────────────────────────────

function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}

// ─── Section heading ──────────────────────────────────────────────────────────

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <h4 className="mb-3 text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--text-tertiary)' }}>
      {children}
    </h4>
  )
}

// ─── Detail row ───────────────────────────────────────────────────────────────

function DetailRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-2 py-1.5">
      <span className="shrink-0 text-xs" style={{ color: 'var(--text-tertiary)' }}>{label}</span>
      <span className="text-right text-xs" style={{ color: 'var(--text-secondary)' }}>{children}</span>
    </div>
  )
}

// ─── Props ────────────────────────────────────────────────────────────────────

interface CampaignDetailPanelProps {
  campaign: Campaign
  onClose?: () => void
}

// ─── Component ────────────────────────────────────────────────────────────────

export function CampaignDetailPanel({ campaign }: CampaignDetailPanelProps) {
  const inputId = useId()
  const [invInput, setInvInput] = useState('')
  const [graphEnabled, setGraphEnabled] = useState(false)

  const { data: graph, isLoading: graphLoading } = useCampaignGraph(campaign.id, graphEnabled)
  const { data: similar, isLoading: similarLoading } = useSimilarCampaigns(campaign.id, true)

  const addInvestigation = useAddInvestigation()
  const removeInvestigation = useRemoveInvestigation()

  const handleAddInvestigation = useCallback(() => {
    const id = invInput.trim()
    if (!id) return
    addInvestigation.mutate(
      { id: campaign.id, payload: { investigation_id: id } },
      { onSuccess: () => setInvInput('') },
    )
  }, [invInput, campaign.id, addInvestigation])

  const handleRemoveInvestigation = useCallback(
    (invId: string) => {
      removeInvestigation.mutate({ id: campaign.id, invId })
    },
    [campaign.id, removeInvestigation],
  )

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter') handleAddInvestigation()
    },
    [handleAddInvestigation],
  )

  return (
    <div className="space-y-4">
      {/* ── Campaign Details ─────────────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Shield className="h-4 w-4" style={{ color: tlpColor[campaign.tlp] }} aria-hidden="true" />
              <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                {campaign.title}
              </h3>
            </div>
            <div className="flex items-center gap-1.5">
              <span
                className="inline-flex items-center gap-1 rounded-full border px-1.5 py-0.5 text-[10px] font-semibold font-mono"
                style={{ color: tlpColor[campaign.tlp], borderColor: tlpColor[campaign.tlp] }}
              >
                <Flag className="h-2.5 w-2.5" aria-hidden="true" />
                TLP:{campaign.tlp}
              </span>
              <Badge variant={statusVariant[campaign.status]} size="sm">
                {campaign.status}
              </Badge>
            </div>
          </div>
        </CardHeader>

        <CardBody className="space-y-1 divide-y" style={{ '--tw-divide-opacity': '1' } as React.CSSProperties}>
          {campaign.description && (
            <p className="pb-3 text-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              {campaign.description}
            </p>
          )}

          <div className="divide-y" style={{ borderColor: 'var(--border-subtle)' }}>
            <DetailRow label="Investigations">{campaign.investigation_count}</DetailRow>
            <DetailRow label="Start date">{formatDate(campaign.start_date)}</DetailRow>
            <DetailRow label="End date">{formatDate(campaign.end_date)}</DetailRow>
            <DetailRow label="Created">{formatDate(campaign.created_at)}</DetailRow>
            <DetailRow label="Updated">{formatDate(campaign.updated_at)}</DetailRow>
          </div>

          {campaign.tags.length > 0 && (
            <div className="flex flex-wrap gap-1 pt-3" aria-label="Tags">
              {campaign.tags.map((tag) => (
                <span
                  key={tag}
                  className="rounded px-1.5 py-0.5 font-mono text-[10px]"
                  style={{ background: 'var(--bg-overlay)', color: 'var(--text-tertiary)' }}
                >
                  {tag}
                </span>
              ))}
            </div>
          )}
        </CardBody>
      </Card>

      {/* ── Linked Investigations ─────────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <SectionHeading>Linked Investigations</SectionHeading>
        </CardHeader>
        <CardBody>
          {/* Add investigation input */}
          <div className="mb-3 flex gap-2">
            <input
              id={inputId}
              type="text"
              value={invInput}
              onChange={(e) => setInvInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Investigation ID…"
              className="flex-1 rounded-lg border px-3 py-1.5 text-xs outline-none focus:ring-2 focus:ring-brand-500"
              style={{
                background: 'var(--bg-overlay)',
                borderColor: 'var(--border-subtle)',
                color: 'var(--text-primary)',
              }}
              aria-label="Add investigation by ID"
            />
            <button
              type="button"
              onClick={handleAddInvestigation}
              disabled={!invInput.trim() || addInvestigation.isPending}
              className="flex items-center gap-1 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 disabled:opacity-50"
              style={{ background: 'var(--brand-500)', color: '#fff' }}
              aria-label="Add investigation"
            >
              <Link className="h-3 w-3" aria-hidden="true" />
              Link
            </button>
          </div>

          {/* Investigation count indicator */}
          {campaign.investigation_count === 0 ? (
            <p className="text-center text-xs py-4" style={{ color: 'var(--text-tertiary)' }}>
              No investigations linked yet
            </p>
          ) : (
            <div className="space-y-1" aria-label="Linked investigations">
              {/* We show placeholder rows based on count since we don't have a dedicated list endpoint */}
              {Array.from({ length: Math.min(campaign.investigation_count, 10) }, (_, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between rounded-lg px-3 py-2"
                  style={{ background: 'var(--bg-overlay)' }}
                >
                  <span className="font-mono text-xs" style={{ color: 'var(--text-secondary)' }}>
                    Investigation #{i + 1}
                  </span>
                  <button
                    type="button"
                    onClick={() => handleRemoveInvestigation(`inv-${i}`)}
                    className="rounded p-1 transition-colors hover:bg-danger-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-danger-500"
                    style={{ color: 'var(--danger-400)' }}
                    aria-label={`Remove investigation ${i + 1}`}
                    disabled={removeInvestigation.isPending}
                  >
                    <Trash2 className="h-3 w-3" aria-hidden="true" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </CardBody>
      </Card>

      {/* ── Merged Graph ──────────────────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <SectionHeading>Merged Graph</SectionHeading>
        </CardHeader>
        <CardBody>
          {!graphEnabled ? (
            <button
              type="button"
              onClick={() => setGraphEnabled(true)}
              className="w-full rounded-lg border border-dashed py-4 text-xs font-medium transition-colors hover:bg-bg-overlay focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
              style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-tertiary)' }}
            >
              Load merged graph
            </button>
          ) : graphLoading ? (
            <p className="text-center text-xs py-4" style={{ color: 'var(--text-tertiary)' }}>
              Loading graph…
            </p>
          ) : graph?.merged_investigation_id ? (
            <a
              href={`/investigations/${graph.merged_investigation_id}/graph`}
              className="flex w-full items-center justify-center gap-2 rounded-lg py-3 text-xs font-medium transition-colors hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
              style={{ background: 'var(--brand-500)', color: '#fff' }}
              aria-label="Open merged graph"
            >
              <Target className="h-3.5 w-3.5" aria-hidden="true" />
              View Merged Graph
              <ChevronRight className="h-3.5 w-3.5" aria-hidden="true" />
            </a>
          ) : (
            <p className="text-center text-xs py-4" style={{ color: 'var(--text-tertiary)' }}>
              No merged graph available
            </p>
          )}
        </CardBody>
      </Card>

      {/* ── Similar Campaigns ─────────────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <SectionHeading>Similar Campaigns</SectionHeading>
        </CardHeader>
        <CardBody>
          {similarLoading ? (
            <p className="text-center text-xs py-4" style={{ color: 'var(--text-tertiary)' }}>
              Loading…
            </p>
          ) : !similar || similar.length === 0 ? (
            <p className="text-center text-xs py-4" style={{ color: 'var(--text-tertiary)' }}>
              No similar campaigns found
            </p>
          ) : (
            <div className="space-y-1" aria-label="Similar campaigns">
              {similar.map((s) => (
                <div
                  key={s.id}
                  className="flex items-center justify-between rounded-lg px-3 py-2"
                  style={{ background: 'var(--bg-overlay)' }}
                >
                  <span className="truncate text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>
                    {s.title}
                  </span>
                  <span
                    className="ml-2 shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold"
                    style={{
                      background: 'var(--brand-900)',
                      color: 'var(--brand-400)',
                    }}
                    aria-label={`Similarity score: ${Math.round(s.similarity_score * 100)}%`}
                  >
                    {Math.round(s.similarity_score * 100)}%
                  </span>
                </div>
              ))}
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  )
}
