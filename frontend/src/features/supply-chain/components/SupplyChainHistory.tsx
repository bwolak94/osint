import { useState } from 'react'
import { Eye, Trash2, ChevronLeft, ChevronRight } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { Button } from '@/shared/components/Button'
import { Badge } from '@/shared/components/Badge'
import { Card, CardBody } from '@/shared/components/Card'
import { EmptyState } from '@/shared/components/EmptyState'
import { useSupplyChainHistory, useDeleteSupplyChainScan } from '../hooks'
import type { SupplyChainScan } from '../types'

interface Props { onSelect: (scan: SupplyChainScan) => void }

function relativeTime(iso: string): string {
  try { return formatDistanceToNow(new Date(iso), { addSuffix: true }) } catch { return iso }
}

export function SupplyChainHistory({ onSelect }: Props) {
  const [page, setPage] = useState(1)
  const [pendingDelete, setPendingDelete] = useState<SupplyChainScan | null>(null)
  const { data, isLoading } = useSupplyChainHistory(page, 10)
  const deleteMutation = useDeleteSupplyChainScan()
  const totalPages = data?.total_pages ?? 1

  return (
    <>
      <Card>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[500px]">
            <thead>
              <tr className="border-b text-left text-xs font-medium" style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-tertiary)' }}>
                <th className="px-4 py-3">Target</th>
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3">Packages</th>
                <th className="px-4 py-3">CVEs</th>
                <th className="px-4 py-3">Scanned</th>
                <th className="w-24 px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? Array.from({ length: 5 }).map((_, i) => (
                <tr key={i} className="border-b" style={{ borderColor: 'var(--border-subtle)' }}>
                  {Array.from({ length: 6 }).map((_, j) => <td key={j} className="px-4 py-3"><div className="h-4 animate-pulse rounded" style={{ background: 'var(--bg-elevated)', width: '75%' }} /></td>)}
                </tr>
              )) : data?.items.map((scan) => (
                <tr key={scan.id} className="border-b transition-colors hover:bg-bg-overlay" style={{ borderColor: 'var(--border-subtle)' }}>
                  <td className="px-4 py-3 font-medium" style={{ color: 'var(--text-primary)' }}>{scan.target}</td>
                  <td className="px-4 py-3"><Badge variant="neutral" size="sm">{scan.target_type.replace('_', ' ')}</Badge></td>
                  <td className="px-4 py-3 text-sm" style={{ color: 'var(--text-secondary)' }}>{scan.total_packages}</td>
                  <td className="px-4 py-3"><Badge variant={scan.total_cves > 0 ? 'danger' : 'success'} size="sm">{scan.total_cves}</Badge></td>
                  <td className="px-4 py-3 text-xs" style={{ color: 'var(--text-tertiary)' }}>{relativeTime(scan.created_at)}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-1">
                      <button onClick={() => onSelect(scan)} className="flex h-8 w-8 items-center justify-center rounded transition-colors hover:bg-bg-elevated"><Eye className="h-4 w-4" style={{ color: 'var(--brand-500)' }} /></button>
                      <button onClick={() => setPendingDelete(scan)} className="flex h-8 w-8 items-center justify-center rounded transition-colors hover:bg-danger-900"><Trash2 className="h-4 w-4" style={{ color: 'var(--danger-500)' }} /></button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!isLoading && (!data || data.items.length === 0) && <CardBody><EmptyState variant="no-data" title="No scan history" description="Scan a GitHub user, org, or domain for package intelligence" /></CardBody>}
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
            <h2 className="mb-2 text-base font-semibold" style={{ color: 'var(--text-primary)' }}>Delete scan</h2>
            <p className="mb-6 text-sm" style={{ color: 'var(--text-secondary)' }}>Delete scan for <span className="font-medium">{pendingDelete.target}</span>?</p>
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
