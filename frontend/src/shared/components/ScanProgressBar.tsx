import { useScanProgress } from '@/shared/hooks/useScanProgress'

interface Props {
  scanId: string | null
  onComplete?: () => void
}

export function ScanProgressBar({ scanId, onComplete }: Props) {
  const { progress } = useScanProgress({ scanId, onComplete })

  if (!scanId || !progress) return null

  const isRunning = progress.status === 'running' || progress.status === 'queued'
  const isFailed = progress.status === 'failed'

  return (
    <div
      className="rounded-lg border p-3"
      style={{ background: 'var(--bg-surface)', borderColor: 'var(--border-subtle)' }}
      role="status"
      aria-live="polite"
      aria-label={`Scan progress: ${progress.progress}%`}
    >
      <div className="mb-1 flex items-center justify-between">
        <span className="text-xs font-medium" style={{ color: 'var(--text-primary)' }}>
          {progress.scanner ? `${progress.scanner}: ` : ''}{progress.message}
        </span>
        <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
          {progress.progress}%
        </span>
      </div>
      <div
        className="h-1.5 w-full overflow-hidden rounded-full"
        style={{ background: 'var(--bg-elevated)' }}
      >
        <div
          className="h-full rounded-full transition-all duration-300"
          style={{
            width: `${progress.progress}%`,
            background: isFailed
              ? 'var(--danger-400)'
              : isRunning
                ? 'var(--brand-500)'
                : 'var(--success-500)',
          }}
        />
      </div>
    </div>
  )
}
