import { useState, useCallback, useMemo } from 'react'
import { Eye, Plus, Bell, Activity, PauseCircle } from 'lucide-react'
import {
  useWatchlist,
  useCreateWatchItem,
  useUpdateWatchItem,
  useDeleteWatchItem,
  useTriggerWatchItem,
} from './hooks'
import { WatchItemCard } from './components/WatchItemCard'
import { WatchItemForm } from './components/WatchItemForm'
import type { WatchItem, CreateWatchItemRequest, WatchlistStats } from './types'

function StatCard({ label, value, icon: Icon }: { label: string; value: number; icon: React.ElementType }) {
  return (
    <div
      className="flex items-center gap-3 rounded-lg border px-4 py-3"
      style={{ background: 'var(--bg-surface)', borderColor: 'var(--border-subtle)' }}
    >
      <div
        className="flex h-9 w-9 items-center justify-center rounded-lg shrink-0"
        style={{ background: 'var(--bg-elevated)' }}
      >
        <Icon className="h-4 w-4" style={{ color: 'var(--brand-500)' }} />
      </div>
      <div>
        <p className="text-xl font-bold leading-none" style={{ color: 'var(--text-primary)' }}>
          {value}
        </p>
        <p className="mt-0.5 text-xs" style={{ color: 'var(--text-tertiary)' }}>
          {label}
        </p>
      </div>
    </div>
  )
}

export function WatchlistPage() {
  const [showForm, setShowForm] = useState(false)

  const { data: items = [], isLoading } = useWatchlist()
  const createMutation = useCreateWatchItem()
  const updateMutation = useUpdateWatchItem()
  const deleteMutation = useDeleteWatchItem()
  const triggerMutation = useTriggerWatchItem()

  const stats = useMemo<WatchlistStats>(() => {
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    return {
      total: items.length,
      active: items.filter((i) => i.status === 'active').length,
      paused: items.filter((i) => i.status === 'paused').length,
      triggered_today: items.filter((i) => {
        if (!i.last_checked) return false
        return new Date(i.last_checked) >= today
      }).length,
    }
  }, [items])

  const handleCreate = useCallback(
    (data: CreateWatchItemRequest) => {
      createMutation.mutate(data, {
        onSuccess: () => setShowForm(false),
      })
    },
    [createMutation],
  )

  const handleTogglePause = useCallback(
    (item: WatchItem) => {
      const newStatus = item.status === 'paused' ? 'active' : 'paused'
      updateMutation.mutate({ id: item.id, body: { status: newStatus } })
    },
    [updateMutation],
  )

  const handleDelete = useCallback(
    (id: string) => {
      deleteMutation.mutate(id)
    },
    [deleteMutation],
  )

  const handleTrigger = useCallback(
    (id: string) => {
      triggerMutation.mutate(id)
    },
    [triggerMutation],
  )

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Eye className="h-5 w-5" style={{ color: 'var(--brand-500)' }} />
            <h1 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>
              Watchlist
            </h1>
          </div>
          <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)' }}>
            Monitor targets continuously and receive alerts when results change
          </p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors"
          style={{ background: 'var(--brand-500)', color: 'white' }}
        >
          <Plus className="h-4 w-4" />
          Add Watch Item
        </button>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="Total" value={stats.total} icon={Eye} />
        <StatCard label="Active" value={stats.active} icon={Activity} />
        <StatCard label="Paused" value={stats.paused} icon={PauseCircle} />
        <StatCard label="Triggered Today" value={stats.triggered_today} icon={Bell} />
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className="h-48 animate-pulse rounded-lg border"
              style={{ background: 'var(--bg-surface)', borderColor: 'var(--border-subtle)' }}
            />
          ))}
        </div>
      ) : items.length === 0 ? (
        <div
          className="flex flex-col items-center justify-center rounded-xl border py-16 text-center"
          style={{ background: 'var(--bg-surface)', borderColor: 'var(--border-subtle)' }}
        >
          <Eye className="h-10 w-10 mb-3" style={{ color: 'var(--text-tertiary)' }} />
          <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
            No watch items yet
          </p>
          <p className="mt-1 text-xs" style={{ color: 'var(--text-tertiary)' }}>
            Add a target to start monitoring it for changes
          </p>
          <button
            onClick={() => setShowForm(true)}
            className="mt-4 flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium"
            style={{ background: 'var(--brand-500)', color: 'white' }}
          >
            <Plus className="h-4 w-4" />
            Add Watch Item
          </button>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((item) => (
            <WatchItemCard
              key={item.id}
              item={item}
              onTrigger={handleTrigger}
              onTogglePause={handleTogglePause}
              onDelete={handleDelete}
              isTriggerPending={triggerMutation.isPending}
              isUpdatePending={updateMutation.isPending}
              isDeletePending={deleteMutation.isPending}
            />
          ))}
        </div>
      )}

      {/* Add form modal */}
      {showForm && (
        <WatchItemForm
          onClose={() => setShowForm(false)}
          onSubmit={handleCreate}
          isPending={createMutation.isPending}
        />
      )}
    </div>
  )
}
