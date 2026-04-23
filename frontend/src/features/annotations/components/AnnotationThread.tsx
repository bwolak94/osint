import { useState, useCallback, useMemo } from 'react'
import { Info, AlertTriangle, AlertOctagon, Send, Edit2, Trash2 } from 'lucide-react'
import { Card, CardBody } from '@/shared/components/Card'
import {
  useAnnotations,
  useCreateAnnotation,
  useUpdateAnnotation,
  useDeleteAnnotation,
} from '../hooks'
import type { Annotation, AnnotationSeverity } from '../types'

interface AnnotationThreadProps {
  investigationId: string
  targetId: string
  targetType: string
}

const SEVERITY_CONFIG: Record<
  AnnotationSeverity,
  { icon: typeof Info; color: string; label: string; activeStyle: React.CSSProperties }
> = {
  info: {
    icon: Info,
    color: 'var(--brand-500)',
    label: 'Info',
    activeStyle: { background: 'var(--brand-500)', color: '#fff' },
  },
  warning: {
    icon: AlertTriangle,
    color: 'var(--warning-500)',
    label: 'Warning',
    activeStyle: { background: 'var(--warning-500)', color: '#000' },
  },
  critical: {
    icon: AlertOctagon,
    color: 'var(--danger-400)',
    label: 'Critical',
    activeStyle: { background: 'var(--danger-400)', color: '#fff' },
  },
}

function formatRelativeTime(isoDate: string): string {
  const diffMs = Date.now() - new Date(isoDate).getTime()
  const diffMins = Math.floor(diffMs / 60_000)
  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) return `${diffHours}h ago`
  const diffDays = Math.floor(diffHours / 24)
  return `${diffDays}d ago`
}

function highlightMentions(content: string): React.ReactNode[] {
  const parts = content.split(/(@\w+)/g)
  return parts.map((part, idx) =>
    part.startsWith('@') ? (
      <strong key={idx} style={{ color: 'var(--brand-500)' }}>
        {part}
      </strong>
    ) : (
      <span key={idx}>{part}</span>
    ),
  )
}

interface AnnotationItemProps {
  annotation: Annotation
  onEdit: (annotation: Annotation) => void
  onDelete: (id: string) => void
  isDeleting: boolean
}

function AnnotationItem({ annotation, onEdit, onDelete, isDeleting }: AnnotationItemProps) {
  const [hovered, setHovered] = useState(false)
  const config = SEVERITY_CONFIG[annotation.severity]
  const Icon = config.icon

  return (
    <div
      className="group relative flex gap-3 py-3"
      style={{ borderBottom: '1px solid var(--border-subtle)' }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <div className="mt-0.5 shrink-0">
        <Icon className="h-4 w-4" style={{ color: config.color }} />
      </div>

      <div className="min-w-0 flex-1">
        <div className="mb-1 flex items-center gap-2">
          <span
            className="text-xs font-semibold"
            style={{ fontFamily: 'monospace', color: 'var(--text-primary)' }}
          >
            {annotation.author}
          </span>
          <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
            {formatRelativeTime(annotation.created_at)}
          </span>
          {annotation.updated_at !== annotation.created_at && (
            <span className="text-xs italic" style={{ color: 'var(--text-tertiary)' }}>
              (edited)
            </span>
          )}
        </div>
        <p className="text-sm leading-relaxed" style={{ color: 'var(--text-primary)' }}>
          {highlightMentions(annotation.content)}
        </p>
      </div>

      {hovered && (
        <div className="absolute right-0 top-3 flex items-center gap-1">
          <button
            onClick={() => onEdit(annotation)}
            className="rounded p-1 transition-colors"
            style={{ color: 'var(--text-tertiary)' }}
            title="Edit annotation"
          >
            <Edit2 className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={() => onDelete(annotation.id)}
            disabled={isDeleting}
            className="rounded p-1 transition-colors disabled:opacity-50"
            style={{ color: 'var(--danger-400)' }}
            title="Delete annotation"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      )}
    </div>
  )
}

export function AnnotationThread({ investigationId, targetId, targetType }: AnnotationThreadProps) {
  const { data: annotations = [], isLoading } = useAnnotations(investigationId, targetId)
  const createMutation = useCreateAnnotation(investigationId)
  const updateMutation = useUpdateAnnotation(investigationId)
  const deleteMutation = useDeleteAnnotation(investigationId)

  const [content, setContent] = useState('')
  const [severity, setSeverity] = useState<AnnotationSeverity>('info')
  const [editingAnnotation, setEditingAnnotation] = useState<Annotation | null>(null)
  const [editContent, setEditContent] = useState('')
  const [editSeverity, setEditSeverity] = useState<AnnotationSeverity>('info')

  const sortedAnnotations = useMemo(
    () => [...annotations].sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()),
    [annotations],
  )

  const handleSubmit = useCallback(() => {
    const trimmed = content.trim()
    if (!trimmed) return
    createMutation.mutate(
      { target_id: targetId, target_type: targetType, content: trimmed, severity },
      {
        onSuccess: () => {
          setContent('')
          setSeverity('info')
        },
      },
    )
  }, [content, severity, targetId, targetType, createMutation])

  const handleEditStart = useCallback((annotation: Annotation) => {
    setEditingAnnotation(annotation)
    setEditContent(annotation.content)
    setEditSeverity(annotation.severity)
  }, [])

  const handleEditSave = useCallback(() => {
    if (!editingAnnotation) return
    updateMutation.mutate(
      {
        annotationId: editingAnnotation.id,
        body: { content: editContent.trim(), severity: editSeverity },
      },
      {
        onSuccess: () => setEditingAnnotation(null),
      },
    )
  }, [editingAnnotation, editContent, editSeverity, updateMutation])

  const handleDelete = useCallback(
    (id: string) => {
      deleteMutation.mutate(id)
    },
    [deleteMutation],
  )

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
        handleSubmit()
      }
    },
    [handleSubmit],
  )

  return (
    <Card>
      <CardBody className="p-0">
        {/* Thread list */}
        <div className="px-4">
          {isLoading && (
            <p className="py-6 text-center text-xs" style={{ color: 'var(--text-tertiary)' }}>
              Loading annotations…
            </p>
          )}

          {!isLoading && sortedAnnotations.length === 0 && (
            <p className="py-6 text-center text-xs" style={{ color: 'var(--text-tertiary)' }}>
              No annotations yet. Be the first to add one.
            </p>
          )}

          {sortedAnnotations.map((annotation) =>
            editingAnnotation?.id === annotation.id ? (
              <div key={annotation.id} className="py-3" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                <SeveritySelector value={editSeverity} onChange={setEditSeverity} />
                <textarea
                  className="mt-2 w-full resize-none rounded-md px-3 py-2 text-sm outline-none"
                  style={{
                    background: 'var(--bg-elevated)',
                    border: '1px solid var(--border-subtle)',
                    color: 'var(--text-primary)',
                    minHeight: '72px',
                  }}
                  value={editContent}
                  onChange={(e) => setEditContent(e.target.value)}
                  autoFocus
                />
                <div className="mt-2 flex items-center gap-2">
                  <button
                    onClick={handleEditSave}
                    disabled={updateMutation.isPending || !editContent.trim()}
                    className="rounded-md px-3 py-1.5 text-xs font-medium transition-colors disabled:opacity-50"
                    style={{ background: 'var(--brand-500)', color: '#fff' }}
                  >
                    {updateMutation.isPending ? 'Saving…' : 'Save'}
                  </button>
                  <button
                    onClick={() => setEditingAnnotation(null)}
                    className="rounded-md px-3 py-1.5 text-xs font-medium transition-colors"
                    style={{ color: 'var(--text-tertiary)', border: '1px solid var(--border-subtle)' }}
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <AnnotationItem
                key={annotation.id}
                annotation={annotation}
                onEdit={handleEditStart}
                onDelete={handleDelete}
                isDeleting={deleteMutation.isPending}
              />
            ),
          )}
        </div>

        {/* Input area */}
        <div
          className="px-4 pb-4 pt-3"
          style={{ borderTop: sortedAnnotations.length > 0 ? '1px solid var(--border-subtle)' : undefined }}
        >
          <SeveritySelector value={severity} onChange={setSeverity} />
          <div className="relative mt-2">
            <textarea
              className="w-full resize-none rounded-md px-3 py-2 pr-10 text-sm outline-none transition-colors"
              style={{
                background: 'var(--bg-elevated)',
                border: '1px solid var(--border-subtle)',
                color: 'var(--text-primary)',
                minHeight: '72px',
              }}
              placeholder="Add an annotation… Use @username to mention someone. ⌘+Enter to submit."
              value={content}
              onChange={(e) => setContent(e.target.value)}
              onKeyDown={handleKeyDown}
            />
            <button
              onClick={handleSubmit}
              disabled={createMutation.isPending || !content.trim()}
              className="absolute bottom-2.5 right-2.5 rounded p-1 transition-colors disabled:opacity-40"
              style={{ color: 'var(--brand-500)' }}
              title="Submit (⌘+Enter)"
            >
              <Send className="h-4 w-4" />
            </button>
          </div>
          {createMutation.isError && (
            <p className="mt-1.5 text-xs" style={{ color: 'var(--danger-400)' }}>
              Failed to post annotation. Please try again.
            </p>
          )}
        </div>
      </CardBody>
    </Card>
  )
}

interface SeveritySelectorProps {
  value: AnnotationSeverity
  onChange: (v: AnnotationSeverity) => void
}

function SeveritySelector({ value, onChange }: SeveritySelectorProps) {
  return (
    <div className="flex items-center gap-1.5">
      {(Object.keys(SEVERITY_CONFIG) as AnnotationSeverity[]).map((s) => {
        const config = SEVERITY_CONFIG[s]
        const Icon = config.icon
        const isActive = value === s
        return (
          <button
            key={s}
            onClick={() => onChange(s)}
            className="flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium transition-all"
            style={
              isActive
                ? config.activeStyle
                : {
                    background: 'var(--bg-overlay)',
                    color: 'var(--text-tertiary)',
                    border: '1px solid var(--border-subtle)',
                  }
            }
          >
            <Icon className="h-3 w-3" />
            {config.label}
          </button>
        )
      })}
    </div>
  )
}
