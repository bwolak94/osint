import { useState, useCallback, useEffect, useId } from 'react'
import { X } from 'lucide-react'
import type { Campaign, CreateCampaignPayload, UpdateCampaignPayload, TLP, CampaignStatus } from '../types'

// ─── Types ────────────────────────────────────────────────────────────────────

interface CampaignFormProps {
  initialData?: Campaign | null
  onSubmit: (payload: CreateCampaignPayload | UpdateCampaignPayload) => void
  onCancel: () => void
  isSubmitting?: boolean
}

interface FormState {
  title: string
  description: string
  tlp: TLP
  tagsRaw: string
  status: CampaignStatus
  start_date: string
  end_date: string
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function parseTags(raw: string): string[] {
  return raw
    .split(',')
    .map((t) => t.trim())
    .filter(Boolean)
}

function toDateInputValue(iso: string | null | undefined): string {
  if (!iso) return ''
  return iso.slice(0, 10)
}

// ─── Styled form field ────────────────────────────────────────────────────────

function Field({ label, htmlFor, children }: { label: string; htmlFor: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <label
        htmlFor={htmlFor}
        className="text-xs font-medium"
        style={{ color: 'var(--text-secondary)' }}
      >
        {label}
      </label>
      {children}
    </div>
  )
}

const inputClass =
  'w-full rounded-lg border px-3 py-2 text-sm outline-none transition-colors focus:ring-2 focus:ring-brand-500'

const inputStyle = {
  background: 'var(--bg-overlay)',
  borderColor: 'var(--border-subtle)',
  color: 'var(--text-primary)',
}

// ─── Component ────────────────────────────────────────────────────────────────

export function CampaignForm({ initialData, onSubmit, onCancel, isSubmitting = false }: CampaignFormProps) {
  const titleId = useId()
  const descId = useId()
  const tlpId = useId()
  const tagsId = useId()
  const statusId = useId()
  const startId = useId()
  const endId = useId()

  const [form, setForm] = useState<FormState>({
    title: initialData?.title ?? '',
    description: initialData?.description ?? '',
    tlp: initialData?.tlp ?? 'WHITE',
    tagsRaw: initialData?.tags.join(', ') ?? '',
    status: initialData?.status ?? 'active',
    start_date: toDateInputValue(initialData?.start_date),
    end_date: toDateInputValue(initialData?.end_date),
  })

  const [errors, setErrors] = useState<Partial<Record<keyof FormState, string>>>({})

  useEffect(() => {
    setForm({
      title: initialData?.title ?? '',
      description: initialData?.description ?? '',
      tlp: initialData?.tlp ?? 'WHITE',
      tagsRaw: initialData?.tags.join(', ') ?? '',
      status: initialData?.status ?? 'active',
      start_date: toDateInputValue(initialData?.start_date),
      end_date: toDateInputValue(initialData?.end_date),
    })
    setErrors({})
  }, [initialData])

  const update = useCallback(<K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }))
    setErrors((prev) => ({ ...prev, [key]: undefined }))
  }, [])

  const validate = useCallback((): boolean => {
    const next: Partial<Record<keyof FormState, string>> = {}
    if (!form.title.trim()) next.title = 'Title is required'
    if (form.end_date && form.start_date && form.end_date < form.start_date) {
      next.end_date = 'End date must be after start date'
    }
    setErrors(next)
    return Object.keys(next).length === 0
  }, [form])

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault()
      if (!validate()) return

      const payload: CreateCampaignPayload | UpdateCampaignPayload = {
        title: form.title.trim(),
        description: form.description.trim(),
        tlp: form.tlp,
        tags: parseTags(form.tagsRaw),
        status: form.status,
        start_date: form.start_date || null,
        end_date: form.end_date || null,
      }

      onSubmit(payload)
    },
    [form, validate, onSubmit],
  )

  const isEdit = Boolean(initialData)

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-label={isEdit ? 'Edit campaign' : 'Create campaign'}
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0"
        style={{ background: 'rgba(0,0,0,0.6)' }}
        onClick={onCancel}
        aria-hidden="true"
      />

      {/* Panel */}
      <div
        className="relative z-10 w-full max-w-lg rounded-xl border shadow-2xl"
        style={{
          background: 'var(--bg-surface)',
          borderColor: 'var(--border-subtle)',
        }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between border-b px-5 py-4"
          style={{ borderColor: 'var(--border-subtle)' }}
        >
          <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
            {isEdit ? 'Edit Campaign' : 'New Campaign'}
          </h2>
          <button
            type="button"
            onClick={onCancel}
            className="rounded p-1 transition-colors hover:bg-bg-overlay focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
            style={{ color: 'var(--text-tertiary)' }}
            aria-label="Close form"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Body */}
        <form onSubmit={handleSubmit} noValidate>
          <div className="space-y-4 px-5 py-5">
            {/* Title */}
            <Field label="Title *" htmlFor={titleId}>
              <input
                id={titleId}
                type="text"
                value={form.title}
                onChange={(e) => update('title', e.target.value)}
                placeholder="Campaign name"
                className={inputClass}
                style={inputStyle}
                aria-required="true"
                aria-invalid={Boolean(errors.title)}
                aria-describedby={errors.title ? `${titleId}-err` : undefined}
              />
              {errors.title && (
                <span id={`${titleId}-err`} className="text-[10px]" style={{ color: 'var(--danger-400)' }}>
                  {errors.title}
                </span>
              )}
            </Field>

            {/* Description */}
            <Field label="Description" htmlFor={descId}>
              <textarea
                id={descId}
                value={form.description}
                onChange={(e) => update('description', e.target.value)}
                placeholder="Describe the campaign objective…"
                rows={3}
                className={`${inputClass} resize-none`}
                style={inputStyle}
              />
            </Field>

            {/* TLP + Status row */}
            <div className="grid grid-cols-2 gap-4">
              <Field label="TLP Classification" htmlFor={tlpId}>
                <select
                  id={tlpId}
                  value={form.tlp}
                  onChange={(e) => update('tlp', e.target.value as TLP)}
                  className={inputClass}
                  style={inputStyle}
                >
                  <option value="WHITE">TLP:WHITE</option>
                  <option value="GREEN">TLP:GREEN</option>
                  <option value="AMBER">TLP:AMBER</option>
                  <option value="RED">TLP:RED</option>
                </select>
              </Field>

              {isEdit && (
                <Field label="Status" htmlFor={statusId}>
                  <select
                    id={statusId}
                    value={form.status}
                    onChange={(e) => update('status', e.target.value as CampaignStatus)}
                    className={inputClass}
                    style={inputStyle}
                  >
                    <option value="active">Active</option>
                    <option value="completed">Completed</option>
                    <option value="archived">Archived</option>
                  </select>
                </Field>
              )}
            </div>

            {/* Tags */}
            <Field label="Tags (comma-separated)" htmlFor={tagsId}>
              <input
                id={tagsId}
                type="text"
                value={form.tagsRaw}
                onChange={(e) => update('tagsRaw', e.target.value)}
                placeholder="apt29, phishing, infrastructure"
                className={inputClass}
                style={inputStyle}
              />
              {parseTags(form.tagsRaw).length > 0 && (
                <div className="flex flex-wrap gap-1 pt-1" aria-label="Tag preview">
                  {parseTags(form.tagsRaw).map((tag) => (
                    <span
                      key={tag}
                      className="rounded px-1.5 py-0.5 font-mono text-[10px]"
                      style={{ background: 'var(--bg-overlay)', color: 'var(--text-tertiary)' }}
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              )}
            </Field>

            {/* Dates row */}
            <div className="grid grid-cols-2 gap-4">
              <Field label="Start Date" htmlFor={startId}>
                <input
                  id={startId}
                  type="date"
                  value={form.start_date}
                  onChange={(e) => update('start_date', e.target.value)}
                  className={inputClass}
                  style={inputStyle}
                />
              </Field>

              <Field label="End Date" htmlFor={endId}>
                <input
                  id={endId}
                  type="date"
                  value={form.end_date}
                  onChange={(e) => update('end_date', e.target.value)}
                  className={inputClass}
                  style={inputStyle}
                  aria-invalid={Boolean(errors.end_date)}
                  aria-describedby={errors.end_date ? `${endId}-err` : undefined}
                />
                {errors.end_date && (
                  <span id={`${endId}-err`} className="text-[10px]" style={{ color: 'var(--danger-400)' }}>
                    {errors.end_date}
                  </span>
                )}
              </Field>
            </div>
          </div>

          {/* Footer */}
          <div
            className="flex items-center justify-end gap-2 border-t px-5 py-3"
            style={{ borderColor: 'var(--border-subtle)' }}
          >
            <button
              type="button"
              onClick={onCancel}
              disabled={isSubmitting}
              className="rounded-lg px-4 py-2 text-sm font-medium transition-colors hover:bg-bg-overlay focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 disabled:opacity-50"
              style={{ color: 'var(--text-secondary)' }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="rounded-lg px-4 py-2 text-sm font-medium transition-colors hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 disabled:opacity-50"
              style={{
                background: 'var(--brand-500)',
                color: '#fff',
              }}
            >
              {isSubmitting ? 'Saving…' : isEdit ? 'Save Changes' : 'Create Campaign'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
