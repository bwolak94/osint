import { useCallback } from 'react'
import { Play, Pause, Trash2, Zap, Clock, AlertCircle } from 'lucide-react'
import { Card, CardBody } from '@/shared/components/Card'
import { Badge } from '@/shared/components/Badge'
import type { WatchItem, WatchItemStatus } from '../types'

interface Props {
  item: WatchItem
  onTrigger: (id: string) => void
  onTogglePause: (item: WatchItem) => void
  onDelete: (id: string) => void
  isTriggerPending: boolean
  isUpdatePending: boolean
  isDeletePending: boolean
}

const STATUS_BADGE_VARIANT: Record<WatchItemStatus, 'success' | 'warning' | 'danger'> = {
  active: 'success',
  paused: 'warning',
  error: 'danger',
}

const STATUS_LABEL: Record<WatchItemStatus, string> = {
  active: 'Active',
  paused: 'Paused',
  error: 'Error',
}

const TYPE_LABELS: Record<string, string> = {
  email: 'Email',
  phone: 'Phone',
  username: 'Username',
  nip: 'NIP',
  url: 'URL',
  ip: 'IP',
  domain: 'Domain',
}

const SCHEDULE_LABELS: Record<string, string> = {
  '@hourly': 'Hourly',
  '@daily': 'Daily',
  '@weekly': 'Weekly',
}

function formatLastChecked(iso: string | null): string {
  if (!iso) return 'Never'
  const date = new Date(iso)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMin = Math.floor(diffMs / 60_000)
  if (diffMin < 1) return 'Just now'
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr}h ago`
  const diffDay = Math.floor(diffHr / 24)
  return `${diffDay}d ago`
}

export function WatchItemCard({
  item,
  onTrigger,
  onTogglePause,
  onDelete,
  isTriggerPending,
  isUpdatePending,
  isDeletePending,
}: Props) {
  const handleTrigger = useCallback(() => onTrigger(item.id), [item.id, onTrigger])
  const handleToggle = useCallback(() => onTogglePause(item), [item, onTogglePause])
  const handleDelete = useCallback(() => onDelete(item.id), [item.id, onDelete])

  return (
    <Card>
      <CardBody className="space-y-3">
        {/* Top row: label + status badge */}
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <p
              className="text-sm font-semibold truncate"
              style={{ color: 'var(--text-primary)' }}
            >
              {item.label}
            </p>
          </div>
          <Badge variant={STATUS_BADGE_VARIANT[item.status]} dot size="sm">
            {STATUS_LABEL[item.status]}
          </Badge>
        </div>

        {/* Type + schedule badges */}
        <div className="flex items-center gap-2 flex-wrap">
          <Badge variant="brand" size="sm">
            {TYPE_LABELS[item.input_type] ?? item.input_type}
          </Badge>
          <Badge variant="neutral" size="sm">
            <Clock className="h-3 w-3" />
            {SCHEDULE_LABELS[item.cron_schedule] ?? item.cron_schedule}
          </Badge>
        </div>

        {/* Monitored value */}
        <p
          className="text-xs rounded px-2 py-1.5 break-all"
          style={{
            fontFamily: 'monospace',
            background: 'var(--bg-elevated)',
            color: 'var(--text-secondary)',
            borderColor: 'var(--border-subtle)',
          }}
        >
          {item.value}
        </p>

        {/* Last checked */}
        <div className="flex items-center gap-1.5">
          {item.status === 'error' ? (
            <AlertCircle className="h-3.5 w-3.5 shrink-0" style={{ color: 'var(--danger-500)' }} />
          ) : (
            <Clock className="h-3.5 w-3.5 shrink-0" style={{ color: 'var(--text-tertiary)' }} />
          )}
          <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
            Last checked: {formatLastChecked(item.last_checked)}
          </p>
        </div>

        {/* Actions */}
        <div
          className="flex items-center gap-2 pt-1 border-t"
          style={{ borderColor: 'var(--border-subtle)' }}
        >
          <button
            onClick={handleTrigger}
            disabled={isTriggerPending || isUpdatePending}
            className="flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors disabled:opacity-50"
            style={{
              background: 'var(--bg-elevated)',
              color: 'var(--text-secondary)',
            }}
            title="Trigger scan now"
          >
            <Zap className="h-3.5 w-3.5" />
            Trigger Now
          </button>

          <button
            onClick={handleToggle}
            disabled={isUpdatePending || isTriggerPending}
            className="flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors disabled:opacity-50"
            style={{
              background: 'var(--bg-elevated)',
              color: 'var(--text-secondary)',
            }}
            title={item.status === 'paused' ? 'Resume monitoring' : 'Pause monitoring'}
          >
            {item.status === 'paused' ? (
              <>
                <Play className="h-3.5 w-3.5" />
                Resume
              </>
            ) : (
              <>
                <Pause className="h-3.5 w-3.5" />
                Pause
              </>
            )}
          </button>

          <button
            onClick={handleDelete}
            disabled={isDeletePending}
            className="ml-auto flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors disabled:opacity-50 hover:bg-danger-900"
            style={{
              color: 'var(--danger-500)',
            }}
            title="Delete watch item"
          >
            <Trash2 className="h-3.5 w-3.5" />
            Delete
          </button>
        </div>
      </CardBody>
    </Card>
  )
}
