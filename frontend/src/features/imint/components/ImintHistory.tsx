import { useState } from 'react'
import { Trash2, ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useImintHistory, useDeleteImint } from '../hooks'
import type { ImintScan } from '../types'

interface ImintHistoryProps {
  onSelect: (scan: ImintScan) => void
}

const TARGET_TYPE_LABELS: Record<string, string> = {
  image_url: 'IMAGE',
  coordinates: 'COORDS',
  url: 'URL',
}

export function ImintHistory({ onSelect }: ImintHistoryProps) {
  const [page, setPage] = useState(1)
  const { data, isLoading } = useImintHistory(page, 10)
  const { mutate: deleteScan } = useDeleteImint()

  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-10 animate-pulse rounded" style={{ background: 'var(--bg-overlay)' }} />
        ))}
      </div>
    )
  }

  if (!data?.items.length) {
    return (
      <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>
        No scans yet.
      </p>
    )
  }

  return (
    <div className="space-y-2">
      {data.items.map((scan) => (
        <div
          key={scan.id}
          className="flex items-center gap-2 rounded-md border px-3 py-2 cursor-pointer transition-colors hover:bg-bg-overlay"
          style={{ borderColor: 'var(--border-subtle)' }}
          onClick={() => onSelect(scan)}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => e.key === 'Enter' && onSelect(scan)}
        >
          <span
            className="shrink-0 rounded px-1.5 py-0.5 font-mono text-xs"
            style={{ background: 'var(--bg-overlay)', color: 'var(--text-tertiary)' }}
          >
            {TARGET_TYPE_LABELS[scan.target_type] ?? scan.target_type}
          </span>
          <span className="flex-1 truncate font-mono text-sm" style={{ color: 'var(--text-primary)' }}>
            {scan.target}
          </span>
          <span className="shrink-0 text-xs" style={{ color: 'var(--text-tertiary)' }}>
            {new Date(scan.created_at).toLocaleDateString()}
          </span>
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6 shrink-0"
            onClick={(e) => {
              e.stopPropagation()
              deleteScan(scan.id)
            }}
            aria-label="Delete scan"
          >
            <Trash2 className="h-3.5 w-3.5" style={{ color: 'var(--text-tertiary)' }} />
          </Button>
        </div>
      ))}

      {data.total_pages > 1 && (
        <div className="flex items-center justify-end gap-2 pt-1">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
            {page} / {data.total_pages}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))}
            disabled={page === data.total_pages}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      )}
    </div>
  )
}
