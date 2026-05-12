import { useState } from 'react'
import { Eye, Trash2, ChevronLeft, ChevronRight } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { Button } from '@/shared/components/Button'
import { Card, CardBody } from '@/shared/components/Card'
import { EmptyState } from '@/shared/components/EmptyState'
import { useInstagramIntelHistory, useDeleteInstagramIntelScan } from '../hooks'
import type { InstagramIntelScan } from '../types'

interface Props {
  onSelect: (scan: InstagramIntelScan) => void
}

const PAGE_SIZE_OPTIONS = [10, 20, 50] as const
type PageSizeOption = (typeof PAGE_SIZE_OPTIONS)[number]

function SkeletonRow() {
  return (
    <tr className="border-b" style={{ borderColor: 'var(--border-subtle)' }}>
      {Array.from({ length: 5 }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <div
            className="h-4 animate-pulse rounded"
            style={{ background: 'var(--bg-elevated)', width: i === 0 ? '60%' : '80%' }}
          />
        </td>
      ))}
    </tr>
  )
}

function ConfirmDeleteDialog({
  query,
  onConfirm,
  onCancel,
  isLoading,
}: {
  query: string
  onConfirm: () => void
  onCancel: () => void
  isLoading: boolean
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="ig-delete-dialog-title"
    >
      <div
        className="absolute inset-0"
        style={{ background: 'rgba(0,0,0,0.5)' }}
        onClick={onCancel}
      />
      <div
        className="relative z-10 w-full max-w-md rounded-xl border p-6 shadow-xl"
        style={{ background: 'var(--bg-surface)', borderColor: 'var(--border-subtle)' }}
      >
        <h2
          id="ig-delete-dialog-title"
          className="mb-2 text-base font-semibold"
          style={{ color: 'var(--text-primary)' }}
        >
          Delete record
        </h2>
        <p className="mb-6 text-sm" style={{ color: 'var(--text-secondary)' }}>
          Delete the scan for{' '}
          <span className="font-medium" style={{ color: 'var(--text-primary)' }}>
            {query}
          </span>
          ? This cannot be undone.
        </p>
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onCancel} disabled={isLoading}>
            Cancel
          </Button>
          <Button variant="danger" onClick={onConfirm} loading={isLoading}>
            Delete
          </Button>
        </div>
      </div>
    </div>
  )
}

function relativeTime(iso: string): string {
  try {
    return formatDistanceToNow(new Date(iso), { addSuffix: true })
  } catch {
    return iso
  }
}

function formatDate(iso: string): string {
  return new Intl.DateTimeFormat(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(iso))
}

export function InstagramHistory({ onSelect }: Props) {
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState<PageSizeOption>(10)
  const [pendingDelete, setPendingDelete] = useState<InstagramIntelScan | null>(null)

  const { data, isLoading } = useInstagramIntelHistory(page, pageSize)
  const deleteMutation = useDeleteInstagramIntelScan()

  const handleDelete = () => {
    if (!pendingDelete) return
    deleteMutation.mutate(pendingDelete.id, {
      onSuccess: () => {
        setPendingDelete(null)
        if (data && data.items.length === 1 && page > 1) {
          setPage((p) => p - 1)
        }
      },
    })
  }

  const totalPages = data?.total_pages ?? 1

  return (
    <>
      <Card>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px]">
            <thead>
              <tr
                className="border-b text-left text-xs font-medium"
                style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-tertiary)' }}
              >
                <th className="px-4 py-3">Query</th>
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3">Results</th>
                <th className="px-4 py-3">Date</th>
                <th className="w-24 px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {isLoading
                ? Array.from({ length: 5 }).map((_, i) => <SkeletonRow key={i} />)
                : data?.items.map((scan) => (
                    <tr
                      key={scan.id}
                      className="border-b transition-colors hover:bg-bg-overlay"
                      style={{ borderColor: 'var(--border-subtle)' }}
                    >
                      <td className="px-4 py-3">
                        <span
                          className="block max-w-[200px] truncate text-sm font-medium"
                          style={{ color: 'var(--text-primary)' }}
                          title={scan.query}
                        >
                          {scan.query}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs capitalize" style={{ color: 'var(--text-secondary)' }}>
                        {scan.query_type}
                      </td>
                      <td className="px-4 py-3 text-sm" style={{ color: 'var(--text-secondary)' }}>
                        {scan.total_results}
                      </td>
                      <td
                        className="px-4 py-3 text-xs"
                        style={{ color: 'var(--text-tertiary)' }}
                        title={formatDate(scan.created_at)}
                      >
                        {relativeTime(scan.created_at)}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            onClick={() => onSelect(scan)}
                            aria-label={`View results for ${scan.query}`}
                            className="flex h-8 w-8 items-center justify-center rounded transition-colors hover:bg-bg-elevated"
                            title="View"
                          >
                            <Eye className="h-4 w-4" style={{ color: 'var(--brand-500)' }} />
                          </button>
                          <button
                            onClick={() => setPendingDelete(scan)}
                            aria-label={`Delete scan for ${scan.query}`}
                            className="flex h-8 w-8 items-center justify-center rounded transition-colors hover:bg-danger-900"
                            title="Delete"
                          >
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
            <EmptyState
              variant="no-data"
              title="No scan history"
              description="Search for Instagram profiles to see them here"
            />
          </CardBody>
        )}

        {data && data.total > 0 && (
          <div
            className="flex flex-wrap items-center justify-between gap-3 border-t px-4 py-3"
            style={{ borderColor: 'var(--border-subtle)' }}
          >
            <div className="flex items-center gap-2">
              <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
                Rows per page:
              </span>
              <select
                value={pageSize}
                onChange={(e) => {
                  setPageSize(Number(e.target.value) as PageSizeOption)
                  setPage(1)
                }}
                aria-label="Select page size"
                className="rounded border px-2 py-1 text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                style={{
                  background: 'var(--bg-elevated)',
                  borderColor: 'var(--border-default)',
                  color: 'var(--text-primary)',
                }}
              >
                {PAGE_SIZE_OPTIONS.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                Page {page} of {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                aria-label="Previous page"
              >
                <ChevronLeft className="h-4 w-4" />
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                aria-label="Next page"
              >
                Next
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        )}
      </Card>

      {pendingDelete && (
        <ConfirmDeleteDialog
          query={pendingDelete.query}
          onConfirm={handleDelete}
          onCancel={() => setPendingDelete(null)}
          isLoading={deleteMutation.isPending}
        />
      )}
    </>
  )
}
