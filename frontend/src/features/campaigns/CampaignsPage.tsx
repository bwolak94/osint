import { useState, useCallback, useMemo } from 'react'
import { Plus, Shield, Target, Flag } from 'lucide-react'
import { Badge } from '@/shared/components/Badge'
import { Card, CardBody } from '@/shared/components/Card'
import {
  useCampaigns,
  useCreateCampaign,
  useUpdateCampaign,
  useDeleteCampaign,
} from './hooks'
import { CampaignCard } from './components/CampaignCard'
import { CampaignForm } from './components/CampaignForm'
import { CampaignDetailPanel } from './components/CampaignDetailPanel'
import type {
  Campaign,
  CampaignFilters,
  CampaignStatus,
  TLP,
  CreateCampaignPayload,
  UpdateCampaignPayload,
} from './types'

// ─── Filter bar ───────────────────────────────────────────────────────────────

const STATUS_OPTIONS: Array<{ value: CampaignStatus | 'all'; label: string }> = [
  { value: 'all', label: 'All statuses' },
  { value: 'active', label: 'Active' },
  { value: 'completed', label: 'Completed' },
  { value: 'archived', label: 'Archived' },
]

const TLP_OPTIONS: Array<{ value: TLP | 'all'; label: string }> = [
  { value: 'all', label: 'All TLP' },
  { value: 'WHITE', label: 'TLP:WHITE' },
  { value: 'GREEN', label: 'TLP:GREEN' },
  { value: 'AMBER', label: 'TLP:AMBER' },
  { value: 'RED', label: 'TLP:RED' },
]

const selectClass =
  'rounded-lg border px-3 py-1.5 text-xs outline-none transition-colors focus:ring-2 focus:ring-brand-500'

const selectStyle = {
  background: 'var(--bg-overlay)',
  borderColor: 'var(--border-subtle)',
  color: 'var(--text-secondary)',
}

// ─── Stat card ────────────────────────────────────────────────────────────────

interface StatCardProps {
  icon: React.ElementType
  label: string
  value: number
  iconColor: string
}

function StatCard({ icon: Icon, label, value, iconColor }: StatCardProps) {
  return (
    <div
      className="flex items-center gap-3 rounded-lg border px-4 py-3"
      style={{ background: 'var(--bg-surface)', borderColor: 'var(--border-subtle)' }}
    >
      <div
        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
        style={{ background: 'var(--bg-overlay)' }}
        aria-hidden="true"
      >
        <Icon className="h-4 w-4" style={{ color: iconColor }} />
      </div>
      <div>
        <p className="text-lg font-bold leading-none" style={{ color: 'var(--text-primary)' }}>
          {value}
        </p>
        <p className="mt-0.5 text-xs" style={{ color: 'var(--text-tertiary)' }}>
          {label}
        </p>
      </div>
    </div>
  )
}

// ─── Modal states ─────────────────────────────────────────────────────────────

type ModalState =
  | { type: 'closed' }
  | { type: 'create' }
  | { type: 'edit'; campaign: Campaign }

// ─── Page ─────────────────────────────────────────────────────────────────────

export function CampaignsPage() {
  const [modal, setModal] = useState<ModalState>({ type: 'closed' })
  const [selectedCampaign, setSelectedCampaign] = useState<Campaign | null>(null)
  const [filters, setFilters] = useState<CampaignFilters>({ status: 'all', tlp: 'all' })

  const { data, isLoading, isError } = useCampaigns()
  const createCampaign = useCreateCampaign()
  const updateCampaign = useUpdateCampaign()
  const deleteCampaign = useDeleteCampaign()

  // ── Derived stats ────────────────────────────────────────────────────────────

  const allCampaigns = data?.items ?? []
  const total = data?.total ?? 0
  const activeCount = allCampaigns.filter((c) => c.status === 'active').length
  const completedCount = allCampaigns.filter((c) => c.status === 'completed').length

  // ── Filtered campaigns ───────────────────────────────────────────────────────

  const filteredCampaigns = useMemo(() => {
    return allCampaigns.filter((c) => {
      const statusMatch = filters.status === 'all' || c.status === filters.status
      const tlpMatch = filters.tlp === 'all' || c.tlp === filters.tlp
      return statusMatch && tlpMatch
    })
  }, [allCampaigns, filters])

  // ── Handlers ─────────────────────────────────────────────────────────────────

  const handleCreate = useCallback(
    (payload: CreateCampaignPayload | UpdateCampaignPayload) => {
      createCampaign.mutate(payload as CreateCampaignPayload, {
        onSuccess: () => setModal({ type: 'closed' }),
      })
    },
    [createCampaign],
  )

  const handleUpdate = useCallback(
    (payload: CreateCampaignPayload | UpdateCampaignPayload) => {
      if (modal.type !== 'edit') return
      updateCampaign.mutate(
        { id: modal.campaign.id, payload: payload as UpdateCampaignPayload },
        { onSuccess: () => setModal({ type: 'closed' }) },
      )
    },
    [modal, updateCampaign],
  )

  const handleDelete = useCallback(
    (id: string) => {
      if (!confirm('Delete this campaign? This cannot be undone.')) return
      deleteCampaign.mutate(id, {
        onSuccess: () => {
          if (selectedCampaign?.id === id) setSelectedCampaign(null)
        },
      })
    },
    [deleteCampaign, selectedCampaign],
  )

  const handleSelect = useCallback((campaign: Campaign) => {
    setSelectedCampaign((prev) => (prev?.id === campaign.id ? null : campaign))
  }, [])

  const handleEdit = useCallback((campaign: Campaign) => {
    setModal({ type: 'edit', campaign })
  }, [])

  const handleFilterStatus = useCallback((value: string) => {
    setFilters((prev) => ({ ...prev, status: value as CampaignStatus | 'all' }))
  }, [])

  const handleFilterTlp = useCallback((value: string) => {
    setFilters((prev) => ({ ...prev, tlp: value as TLP | 'all' }))
  }, [])

  // ── Render ───────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>
            Campaigns
          </h1>
          <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)' }}>
            Manage and track Red Team campaign timelines, linked investigations, and threat intelligence.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setModal({ type: 'create' })}
          className="flex shrink-0 items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
          style={{ background: 'var(--brand-500)', color: '#fff' }}
          aria-label="Create new campaign"
        >
          <Plus className="h-4 w-4" aria-hidden="true" />
          New Campaign
        </button>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-3 gap-3 sm:grid-cols-3" aria-label="Campaign statistics">
        <StatCard icon={Shield} label="Total" value={total} iconColor="var(--brand-400)" />
        <StatCard icon={Target} label="Active" value={activeCount} iconColor="var(--success-500)" />
        <StatCard icon={Flag} label="Completed" value={completedCount} iconColor="var(--info-500)" />
      </div>

      {/* Filter bar */}
      <div
        className="flex flex-wrap items-center gap-3 rounded-lg border px-4 py-3"
        style={{ background: 'var(--bg-surface)', borderColor: 'var(--border-subtle)' }}
        role="search"
        aria-label="Filter campaigns"
      >
        <span className="text-xs font-medium" style={{ color: 'var(--text-tertiary)' }}>
          Filter:
        </span>

        <select
          value={filters.status}
          onChange={(e) => handleFilterStatus(e.target.value)}
          className={selectClass}
          style={selectStyle}
          aria-label="Filter by status"
        >
          {STATUS_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>

        <select
          value={filters.tlp}
          onChange={(e) => handleFilterTlp(e.target.value)}
          className={selectClass}
          style={selectStyle}
          aria-label="Filter by TLP"
        >
          {TLP_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>

        {(filters.status !== 'all' || filters.tlp !== 'all') && (
          <button
            type="button"
            onClick={() => setFilters({ status: 'all', tlp: 'all' })}
            className="rounded px-2 py-1 text-xs transition-colors hover:bg-bg-overlay focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
            style={{ color: 'var(--text-tertiary)' }}
          >
            Clear filters
          </button>
        )}

        <span className="ml-auto text-xs" style={{ color: 'var(--text-tertiary)' }}>
          {filteredCampaigns.length} of {total}
        </span>
      </div>

      {/* Main content: grid + detail panel */}
      <div className={`gap-6 ${selectedCampaign ? 'lg:grid lg:grid-cols-[1fr_360px]' : ''}`}>
        {/* Campaign grid */}
        <section aria-label="Campaign grid">
          {isLoading ? (
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {Array.from({ length: 6 }, (_, i) => (
                <div
                  key={i}
                  className="h-52 animate-pulse rounded-lg"
                  style={{ background: 'var(--bg-surface)' }}
                  aria-hidden="true"
                />
              ))}
            </div>
          ) : isError ? (
            <Card>
              <CardBody>
                <p className="text-center text-sm" style={{ color: 'var(--danger-400)' }}>
                  Failed to load campaigns. Please try again.
                </p>
              </CardBody>
            </Card>
          ) : filteredCampaigns.length === 0 ? (
            <Card>
              <CardBody>
                <div className="flex flex-col items-center gap-3 py-8">
                  <Shield className="h-8 w-8" style={{ color: 'var(--text-tertiary)' }} aria-hidden="true" />
                  <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>
                    {allCampaigns.length === 0
                      ? 'No campaigns yet. Create your first one.'
                      : 'No campaigns match the current filters.'}
                  </p>
                  {allCampaigns.length === 0 && (
                    <button
                      type="button"
                      onClick={() => setModal({ type: 'create' })}
                      className="flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-medium transition-colors hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                      style={{ background: 'var(--brand-500)', color: '#fff' }}
                    >
                      <Plus className="h-4 w-4" aria-hidden="true" />
                      New Campaign
                    </button>
                  )}
                </div>
              </CardBody>
            </Card>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {filteredCampaigns.map((campaign) => (
                <CampaignCard
                  key={campaign.id}
                  campaign={campaign}
                  isSelected={selectedCampaign?.id === campaign.id}
                  onSelect={handleSelect}
                  onEdit={handleEdit}
                  onDelete={handleDelete}
                />
              ))}
            </div>
          )}
        </section>

        {/* Detail panel */}
        {selectedCampaign && (
          <aside aria-label={`Campaign detail: ${selectedCampaign.title}`}>
            <div className="sticky top-4">
              {/* Panel header */}
              <div className="mb-3 flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--text-tertiary)' }}>
                  Campaign Details
                </span>
                <div className="flex items-center gap-2">
                  <Badge variant="brand" size="sm">Selected</Badge>
                  <button
                    type="button"
                    onClick={() => setSelectedCampaign(null)}
                    className="rounded px-2 py-0.5 text-[10px] transition-colors hover:bg-bg-overlay focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                    style={{ color: 'var(--text-tertiary)' }}
                    aria-label="Close detail panel"
                  >
                    Close
                  </button>
                </div>
              </div>
              <CampaignDetailPanel campaign={selectedCampaign} />
            </div>
          </aside>
        )}
      </div>

      {/* Create / Edit modal */}
      {modal.type !== 'closed' && (
        <CampaignForm
          initialData={modal.type === 'edit' ? modal.campaign : null}
          onSubmit={modal.type === 'edit' ? handleUpdate : handleCreate}
          onCancel={() => setModal({ type: 'closed' })}
          isSubmitting={createCampaign.isPending || updateCampaign.isPending}
        />
      )}
    </div>
  )
}
