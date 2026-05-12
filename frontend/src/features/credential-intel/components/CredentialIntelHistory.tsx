import { useState } from 'react'
import { Trash2, ChevronLeft, ChevronRight, Clock } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { useCredentialIntelHistory, useDeleteCredentialIntel } from '../hooks'
import type { CredentialIntelScan } from '../types'

interface CredentialIntelHistoryProps {
  onSelect: (scan: CredentialIntelScan) => void
}

export function CredentialIntelHistory({ onSelect }: CredentialIntelHistoryProps) {
  const [page, setPage] = useState(1)
  const { data, isLoading } = useCredentialIntelHistory(page)
  const { mutate: deleteScan } = useDeleteCredentialIntel()

  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-12 animate-pulse rounded-md" style={{ background: 'var(--bg-overlay)' }} />
        ))}
      </div>
    )
  }

  if (!data || data.items.length === 0) {
    return <p className="text-sm text-center py-6" style={{ color: 'var(--text-tertiary)' }}>No scans yet.</p>
  }

  return (
    <div className="space-y-2">
      {data.items.map((scan) => {
        const foundCount = Object.values(scan.results).filter((r) => r.found).length
        return (
          <div
            key={scan.id}
            className="flex items-center gap-3 rounded-md border px-3 py-2 cursor-pointer hover:bg-bg-overlay transition-colors"
            style={{ borderColor: 'var(--border-subtle)' }}
            onClick={() => onSelect(scan)}
          >
            <Clock className="h-3.5 w-3.5 shrink-0" style={{ color: 'var(--text-tertiary)' }} />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-mono font-medium truncate" style={{ color: 'var(--text-primary)' }}>
                {scan.target}
              </p>
              <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
                {new Date(scan.created_at).toLocaleString()} &bull; {scan.target_type}
              </p>
            </div>
            <Badge
              variant="outline"
              className={`text-[10px] shrink-0 ${foundCount > 0 ? 'text-danger-400 border-danger-400' : ''}`}
            >
              {foundCount > 0 ? `${foundCount} findings` : 'clean'}
            </Badge>
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6 shrink-0 text-text-tertiary hover:text-danger-500"
              onClick={(e) => { e.stopPropagation(); deleteScan(scan.id) }}
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </div>
        )
      })}
      {data.total_pages > 1 && (
        <div className="flex items-center justify-between pt-2">
          <Button variant="outline" size="sm" disabled={page === 1} onClick={() => setPage((p) => p - 1)}>
            <ChevronLeft className="h-3.5 w-3.5" />
          </Button>
          <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
            {page} / {data.total_pages}
          </span>
          <Button variant="outline" size="sm" disabled={page === data.total_pages} onClick={() => setPage((p) => p + 1)}>
            <ChevronRight className="h-3.5 w-3.5" />
          </Button>
        </div>
      )}
    </div>
  )
}
