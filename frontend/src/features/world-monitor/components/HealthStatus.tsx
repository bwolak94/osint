import { Activity, AlertTriangle, CheckCircle, XCircle } from 'lucide-react'
import { useWorldMonitorHealth } from '../hooks'

const STATUS_ICON = {
  OK: CheckCircle,
  WARN: AlertTriangle,
  STALE: XCircle,
  EMPTY: XCircle,
}

const STATUS_COLOR = {
  OK: 'var(--success-500, #10b981)',
  WARN: 'var(--warning-500, #f59e0b)',
  STALE: 'var(--danger-500, #ef4444)',
  EMPTY: 'var(--text-tertiary)',
}

export function HealthStatus() {
  const { data, isLoading } = useWorldMonitorHealth()

  if (isLoading) {
    return (
      <div className="flex items-center gap-1.5 text-xs" style={{ color: 'var(--text-tertiary)' }}>
        <Activity className="h-3.5 w-3.5 animate-pulse" />
        <span>Checking...</span>
      </div>
    )
  }

  if (!data) return null

  const Icon = STATUS_ICON[data.status === 'OK' ? 'OK' : 'WARN']
  const color = data.status === 'OK' ? STATUS_COLOR.OK : STATUS_COLOR.WARN

  const lastRun = data.last_aggregation
    ? new Date(data.last_aggregation).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : null

  return (
    <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--text-tertiary)' }}>
      <Icon className="h-3.5 w-3.5" style={{ color }} aria-hidden="true" />
      <span style={{ color }}>
        {data.status}
      </span>
      {lastRun && (
        <>
          <span>·</span>
          <span>Last sync {lastRun}</span>
        </>
      )}
      {data.items_fetched_last_run != null && (
        <>
          <span>·</span>
          <span>{data.items_fetched_last_run} items</span>
        </>
      )}
    </div>
  )
}
