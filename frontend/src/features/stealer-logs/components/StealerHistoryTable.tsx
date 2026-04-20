import { useState } from 'react'
import { Eye, Trash2, ChevronLeft, ChevronRight } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { Button } from '@/shared/components/Button'
import { Badge } from '@/shared/components/Badge'
import { Card, CardBody } from '@/shared/components/Card'
import { EmptyState } from '@/shared/components/EmptyState'
import { useStealerLogHistory, useDeleteStealerCheck } from '../hooks'
import type { StealerLogCheck } from '../types'

interface Props {
  onSelect: (check: StealerLogCheck) => void
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

export function StealerHistoryTable({ onSelect }: Props) {
  const [page, setPage] = useState(1)
  const [pageSize] = useState(10)
  const [pendingDelete, setPendingDelete] = useState<StealerLogCheck | null>(null)

  const { data, isLoading } = useStealerLogHistory(page, pageSize)
  const deleteMutation = useDeleteStealerCheck()
  const totalPages = data?.total_pages ?? 1

  return (
    <>
      <Card>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[500px]">
            <thead>
              <tr className="border-b text-left text-xs font-medium" style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-tertiary)' }}>
                <th className="px-4 py-3">Query</th>
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3">Infections</th>
                <th className="px-4 py-3">Checked</th>
                <th className="w-24 px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {isLoading
                ? Array.from({ length: 5 }).map((_, i) => <SkeletonRow key={i} />)
                : data?.items.map((check) => (
                    <tr key={check.id} className="border-b transition-colors hover:bg-bg-overlay" style={{ borderColor: 'var(--border-subtle)' }}>
                      <td className="px-4 py-3 font-medium" style={{ color: 'var(--text-primary)' }}>{check.query}</td>
                      <td className="px-4 py-3">
                        <Badge variant="neutral" size="sm">{check.query_type}</Badge>
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant={check.total_infections > 0 ? 'danger' : 'success'} size="sm">
                          {check.total_infections}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-xs" style={{ color: 'var(--text-tertiary)' }}>{relativeTime(check.created_at)}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-end gap-1">
                          <button onClick={() => onSelect(check)} className="flex h-8 w-8 items-center justify-center rounded transition-colors hover:bg-bg-elevated">
                            <Eye className="h-4 w-4" style={{ color: 'var(--brand-500)' }} />
                          </button>
                          <button onClick={() => setPendingDelete(check)} className="flex h-8 w-8 items-center justify-center rounded transition-colors hover:bg-danger-900">
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
            <EmptyState variant="no-data" title="No query history" description="Enter an email, domain, or IP to check stealer logs" />
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
            <p className="mb-6 text-sm" style={{ color: 'var(--text-secondary)' }}>Delete stealer log check for <span className="font-medium">{pendingDelete.query}</span>?</p>
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
