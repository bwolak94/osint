import { useState } from 'react'
import { Trash2, ChevronLeft, ChevronRight, Clock } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { useSocmintHistory, useDeleteSocmint } from '../hooks'
import type { SocmintScan } from '../types'

interface SocmintHistoryProps {
  onSelect: (scan: SocmintScan) => void
}

const PAGE_SIZE = 10

export function SocmintHistory({ onSelect }: SocmintHistoryProps) {
  const [page, setPage] = useState(1)
  const { data, isLoading } = useSocmintHistory(page, PAGE_SIZE)
  const { mutate: deleteScan } = useDeleteSocmint()

  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <div
            key={i}
            className="h-12 animate-pulse rounded-md"
            style={{ background: 'var(--bg-overlay)' }}
          />
        ))}
      </div>
    )
  }

  if (!data || data.items.length === 0) {
    return (
      <p className="py-6 text-center text-sm" style={{ color: 'var(--text-tertiary)' }}>
        No SOCMINT scans yet. Run a scan above to see history here.
      </p>
    )
  }

  return (
    <div className="space-y-3">
      <div className="space-y-1.5">
        {data.items.map((scan) => {
          const foundCount = Object.values(scan.results).filter((r) => r.found).length
          return (
            <div
              key={scan.id}
              className="flex cursor-pointer items-center gap-3 rounded-md border px-3 py-2 transition-colors hover:bg-bg-overlay"
              style={{ borderColor: 'var(--border-subtle)' }}
              onClick={() => onSelect(scan)}
            >
              <Clock
                className="h-3.5 w-3.5 shrink-0"
                style={{ color: 'var(--text-tertiary)' }}
              />
              <div className="min-w-0 flex-1">
                <p
                  className="truncate font-mono text-sm font-medium"
                  style={{ color: 'var(--text-primary)' }}
                >
                  {scan.target}
                </p>
                <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
                  {new Date(scan.created_at).toLocaleString()} &bull;{' '}
                  <span className="uppercase">{scan.target_type}</span> &bull;{' '}
                  {scan.modules_run.length} modules
                </p>
              </div>
              <Badge variant="outline" className="shrink-0 text-[10px]">
                {foundCount} hits
              </Badge>
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6 shrink-0 hover:text-danger-500"
                style={{ color: 'var(--text-tertiary)' }}
                onClick={(e) => {
                  e.stopPropagation()
                  deleteScan(scan.id)
                }}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </div>
          )
        })}
      </div>

      {/* Pagination */}
      {data.total_pages > 1 && (
        <div className="flex items-center justify-between pt-1">
          <Button
            variant="outline"
            size="sm"
            disabled={page === 1}
            onClick={() => setPage((p) => p - 1)}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
            Page {page} of {data.total_pages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page === data.total_pages}
            onClick={() => setPage((p) => p + 1)}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      )}
    </div>
  )
}
