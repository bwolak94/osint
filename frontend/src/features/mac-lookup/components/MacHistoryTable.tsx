import { useState } from 'react'
import { Eye, Trash2, ChevronLeft, ChevronRight } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { Button } from '@/shared/components/Button'
import { Badge } from '@/shared/components/Badge'
import { Card, CardBody } from '@/shared/components/Card'
import { EmptyState } from '@/shared/components/EmptyState'
import { useMacLookupHistory, useDeleteMacLookup } from '../hooks'
import type { MacLookup } from '../types'

interface Props {
  onSelect: (lookup: MacLookup) => void
}

function SkeletonRow() {
  return (
    <tr className="border-b" style={{ borderColor: 'var(--border-subtle)' }}>
      {Array.from({ length: 5 }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <div className="h-4 animate-pulse rounded" style={{ background: 'var(--bg-elevated)', width: '75%' }} />
        </td>
      ))}
    </tr>
  )
}

function relativeTime(iso: string): string {
  try { return formatDistanceToNow(new Date(iso), { addSuffix: true }) } catch { return iso }
}

export function MacHistoryTable({ onSelect }: Props) {
  const [page, setPage] = useState(1)
  const [pageSize] = useState(10)
  const [pendingDelete, setPendingDelete] = useState<MacLookup | null>(null)

  const { data, isLoading } = useMacLookupHistory(page, pageSize)
  const deleteMutation = useDeleteMacLookup()
  const totalPages = data?.total_pages ?? 1

  return (
    <>
      <Card>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[500px]">
            <thead>
              <tr className="border-b text-left text-xs font-medium" style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-tertiary)' }}>
                <th className="px-4 py-3">MAC Address</th>
                <th className="px-4 py-3">Manufacturer</th>
                <th className="px-4 py-3">Device Type</th>
                <th className="px-4 py-3">Flags</th>
                <th className="px-4 py-3">Looked Up</th>
                <th className="w-24 px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {isLoading
                ? Array.from({ length: 5 }).map((_, i) => <SkeletonRow key={i} />)
                : data?.items.map((lookup) => (
                    <tr key={lookup.id} className="border-b transition-colors hover:bg-bg-overlay" style={{ borderColor: 'var(--border-subtle)' }}>
                      <td className="px-4 py-3 font-mono text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{lookup.mac_address}</td>
                      <td className="px-4 py-3 text-sm" style={{ color: 'var(--text-secondary)' }}>{lookup.manufacturer || '—'}</td>
                      <td className="px-4 py-3 text-sm" style={{ color: 'var(--text-secondary)' }}>{lookup.device_type || '—'}</td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-1">
                          {lookup.is_private && <Badge variant="warning" size="sm">Randomized</Badge>}
                          {lookup.is_multicast && <Badge variant="info" size="sm">Multicast</Badge>}
                          {!lookup.is_private && !lookup.is_multicast && <Badge variant="success" size="sm">Global</Badge>}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-xs" style={{ color: 'var(--text-tertiary)' }}>{relativeTime(lookup.created_at)}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-end gap-1">
                          <button onClick={() => onSelect(lookup)} className="flex h-8 w-8 items-center justify-center rounded transition-colors hover:bg-bg-elevated">
                            <Eye className="h-4 w-4" style={{ color: 'var(--brand-500)' }} />
                          </button>
                          <button onClick={() => setPendingDelete(lookup)} className="flex h-8 w-8 items-center justify-center rounded transition-colors hover:bg-danger-900">
                            <Trash2 className="h-4 w-4" style={{ color: 'var(--danger-500)' }} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
            </tbody>
          </table>
        </div>

        {!isLoading && (!data || data.items.length === 0) && (
          <CardBody>
            <EmptyState variant="no-data" title="No lookup history" description="Enter a MAC address to identify the vendor" />
          </CardBody>
        )}

        {data && data.total > 0 && (
          <div className="flex items-center justify-between gap-3 border-t px-4 py-3" style={{ borderColor: 'var(--border-subtle)' }}>
            <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>Page {page} of {totalPages}</span>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1}><ChevronLeft className="h-4 w-4" />Previous</Button>
              <Button variant="outline" size="sm" onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page >= totalPages}>Next<ChevronRight className="h-4 w-4" /></Button>
            </div>
          </div>
        )}
      </Card>

      {pendingDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" role="dialog" aria-modal="true">
          <div className="absolute inset-0" style={{ background: 'rgba(0,0,0,0.5)' }} onClick={() => setPendingDelete(null)} />
          <div className="relative z-10 w-full max-w-md rounded-xl border p-6 shadow-xl" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border-subtle)' }}>
            <h2 className="mb-2 text-base font-semibold" style={{ color: 'var(--text-primary)' }}>Delete record</h2>
            <p className="mb-6 text-sm" style={{ color: 'var(--text-secondary)' }}>Delete lookup for <span className="font-mono font-medium" style={{ color: 'var(--text-primary)' }}>{pendingDelete.mac_address}</span>? Cannot be undone.</p>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setPendingDelete(null)}>Cancel</Button>
              <Button variant="danger" onClick={() => deleteMutation.mutate(pendingDelete.id, { onSuccess: () => setPendingDelete(null) })} loading={deleteMutation.isPending}>Delete</Button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
