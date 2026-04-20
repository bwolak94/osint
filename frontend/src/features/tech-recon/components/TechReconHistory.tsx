import { useState } from 'react'
import { Trash2, ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useTechReconHistory, useDeleteTechRecon } from '../hooks'
import type { TechReconScan } from '../types'

interface TechReconHistoryProps {
  onSelect: (scan: TechReconScan) => void
}

export function TechReconHistory({ onSelect }: TechReconHistoryProps) {
  const [page, setPage] = useState(1)
  const PAGE_SIZE = 10
  const { data, isLoading } = useTechReconHistory(page, PAGE_SIZE)
  const { mutate: deleteScan } = useDeleteTechRecon()

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
      <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>
        No previous scans. Run a scan above to see history here.
      </p>
    )
  }

  return (
    <div className="space-y-3">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
              <th className="pb-2 text-left font-medium" style={{ color: 'var(--text-tertiary)' }}>
                Target
              </th>
              <th className="pb-2 text-left font-medium" style={{ color: 'var(--text-tertiary)' }}>
                Type
              </th>
              <th className="pb-2 text-left font-medium" style={{ color: 'var(--text-tertiary)' }}>
                Modules
              </th>
              <th className="pb-2 text-left font-medium" style={{ color: 'var(--text-tertiary)' }}>
                Date
              </th>
              <th className="pb-2" />
            </tr>
          </thead>
          <tbody className="space-y-1">
            {data.items.map((scan) => (
              <tr
                key={scan.id}
                className="cursor-pointer transition-colors hover:bg-bg-overlay"
                onClick={() => onSelect(scan)}
              >
                <td className="py-2 pr-4 font-mono text-xs" style={{ color: 'var(--text-primary)' }}>
                  {scan.target}
                </td>
                <td className="py-2 pr-4 uppercase text-xs" style={{ color: 'var(--text-tertiary)' }}>
                  {scan.target_type}
                </td>
                <td className="py-2 pr-4 text-xs" style={{ color: 'var(--text-secondary)' }}>
                  {scan.modules_run.length} modules
                </td>
                <td className="py-2 pr-4 text-xs" style={{ color: 'var(--text-tertiary)' }}>
                  {new Date(scan.created_at).toLocaleString()}
                </td>
                <td className="py-2 text-right">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 w-6 p-0 hover:text-danger-500"
                    onClick={(e) => {
                      e.stopPropagation()
                      deleteScan(scan.id)
                    }}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {data.total_pages > 1 && (
        <div className="flex items-center justify-between">
          <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
            Page {page} of {data.total_pages}
          </span>
          <div className="flex gap-1">
            <Button
              variant="outline"
              size="sm"
              disabled={page === 1}
              onClick={() => setPage((p) => p - 1)}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={page === data.total_pages}
              onClick={() => setPage((p) => p + 1)}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
