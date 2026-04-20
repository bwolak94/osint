import { useState } from 'react'
import { Eye, Trash2, ChevronLeft, ChevronRight, MapPin } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { Button } from '@/shared/components/Button'
import { Badge } from '@/shared/components/Badge'
import { Card, CardBody } from '@/shared/components/Card'
import { EmptyState } from '@/shared/components/EmptyState'
import { useImageHistory, useDeleteImageCheck } from '../hooks'
import type { ImageCheck } from '../types'

interface Props {
  onSelect: (check: ImageCheck) => void
}

const PAGE_SIZE_OPTIONS = [10, 20, 50] as const
type PageSizeOption = typeof PAGE_SIZE_OPTIONS[number]

function SkeletonRow() {
  return (
    <tr className="border-b" style={{ borderColor: 'var(--border-subtle)' }}>
      {Array.from({ length: 6 }).map((_, i) => (
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
  filename,
  onConfirm,
  onCancel,
  isLoading,
}: {
  filename: string
  onConfirm: () => void
  onCancel: () => void
  isLoading: boolean
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="delete-dialog-title"
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
          id="delete-dialog-title"
          className="mb-2 text-base font-semibold"
          style={{ color: 'var(--text-primary)' }}
        >
          Delete record
        </h2>
        <p className="mb-6 text-sm" style={{ color: 'var(--text-secondary)' }}>
          Are you sure you want to delete the record for{' '}
          <span className="font-medium" style={{ color: 'var(--text-primary)' }}>
            {filename}
          </span>
          ? This action cannot be undone.
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

function formatDate(iso: string): string {
  return new Intl.DateTimeFormat(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(iso))
}

function relativeTime(iso: string): string {
  try {
    return formatDistanceToNow(new Date(iso), { addSuffix: true })
  } catch {
    return iso
  }
}

export function HistoryTable({ onSelect }: Props) {
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState<PageSizeOption>(10)
  const [pendingDelete, setPendingDelete] = useState<ImageCheck | null>(null)

  const { data, isLoading } = useImageHistory(page, pageSize)
  const deleteMutation = useDeleteImageCheck()

  const handleDelete = () => {
    if (!pendingDelete) return
    deleteMutation.mutate(pendingDelete.id, {
      onSuccess: () => {
        setPendingDelete(null)
        // If we deleted the last item on a page beyond page 1, go back
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
          <table className="w-full min-w-[700px]">
            <thead>
              <tr
                className="border-b text-left text-xs font-medium"
                style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-tertiary)' }}
              >
                <th className="px-4 py-3">Filename</th>
                <th className="px-4 py-3">Camera</th>
                <th className="px-4 py-3">GPS</th>
                <th className="px-4 py-3">Taken At</th>
                <th className="px-4 py-3">Uploaded</th>
                <th className="w-24 px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {isLoading
                ? Array.from({ length: 5 }).map((_, i) => <SkeletonRow key={i} />)
                : data?.items.map((check) => {
                    const camera =
                      [check.camera_make, check.camera_model].filter(Boolean).join(' ') ||
                      'Unknown'
                    return (
                      <tr
                        key={check.id}
                        className="border-b transition-colors hover:bg-bg-overlay"
                        style={{ borderColor: 'var(--border-subtle)' }}
                      >
                        <td className="px-4 py-3">
                          <span
                            className="block max-w-[180px] truncate text-sm font-medium"
                            style={{ color: 'var(--text-primary)' }}
                            title={check.filename}
                          >
                            {check.filename}
                          </span>
                        </td>
                        <td
                          className="px-4 py-3 text-sm"
                          style={{ color: 'var(--text-secondary)' }}
                        >
                          {camera}
                        </td>
                        <td className="px-4 py-3">
                          {check.gps_data ? (
                            <Badge variant="success" size="sm">
                              <MapPin className="h-2.5 w-2.5" />
                              Has GPS
                            </Badge>
                          ) : (
                            <Badge variant="neutral" size="sm">
                              No GPS
                            </Badge>
                          )}
                        </td>
                        <td
                          className="px-4 py-3 text-sm"
                          style={{ color: 'var(--text-secondary)' }}
                        >
                          {check.taken_at ? formatDate(check.taken_at) : '—'}
                        </td>
                        <td
                          className="px-4 py-3 text-xs"
                          style={{ color: 'var(--text-tertiary)' }}
                          title={formatDate(check.created_at)}
                        >
                          {relativeTime(check.created_at)}
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center justify-end gap-1">
                            <button
                              onClick={() => onSelect(check)}
                              aria-label={`View metadata for ${check.filename}`}
                              className="flex h-8 w-8 items-center justify-center rounded transition-colors hover:bg-bg-elevated"
                              title="View"
                            >
                              <Eye
                                className="h-4 w-4"
                                style={{ color: 'var(--brand-500)' }}
                              />
                            </button>
                            <button
                              onClick={() => setPendingDelete(check)}
                              aria-label={`Delete record for ${check.filename}`}
                              className="flex h-8 w-8 items-center justify-center rounded transition-colors hover:bg-danger-900"
                              title="Delete"
                            >
                              <Trash2
                                className="h-4 w-4"
                                style={{ color: 'var(--danger-500)' }}
                              />
                            </button>
                          </div>
                        </td>
                      </tr>
                    )
                  })}
            </tbody>
          </table>
        </div>

        {!isLoading && (!data || data.items.length === 0) && (
          <CardBody>
            <EmptyState
              variant="no-data"
              title="No analysis history"
              description="Upload and analyze images to see them here"
            />
          </CardBody>
        )}

        {/* Pagination */}
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
          filename={pendingDelete.filename}
          onConfirm={handleDelete}
          onCancel={() => setPendingDelete(null)}
          isLoading={deleteMutation.isPending}
        />
      )}
    </>
  )
}
