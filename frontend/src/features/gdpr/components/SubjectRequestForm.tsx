import { useState, useCallback } from 'react'
import { AlertCircle, Shield } from 'lucide-react'
import { Button } from '@/shared/components/Button'
import { useCreateGdprReport } from '../hooks'
import type { GdprReport, GdprSubjectRequest } from '../types'

interface Props {
  onSuccess: (report: GdprReport) => void
}

interface FormState {
  full_name: string
  email: string
  phone: string
  requester_reference: string
  include_breach_check: boolean
  include_social_scan: boolean
  include_paste_check: boolean
  include_stealer_logs: boolean
}

const INITIAL_STATE: FormState = {
  full_name: '',
  email: '',
  phone: '',
  requester_reference: '',
  include_breach_check: true,
  include_social_scan: true,
  include_paste_check: true,
  include_stealer_logs: true,
}

export function SubjectRequestForm({ onSuccess }: Props) {
  const [form, setForm] = useState<FormState>(INITIAL_STATE)
  const createMutation = useCreateGdprReport()

  const handleChange = useCallback(
    (key: keyof FormState, value: string | boolean) => {
      setForm((prev) => ({ ...prev, [key]: value }))
    },
    [],
  )

  const isValid = form.full_name.trim() !== '' && form.email.trim() !== ''

  const handleSubmit = useCallback(() => {
    if (!isValid) return

    const request: GdprSubjectRequest = {
      full_name: form.full_name.trim(),
      email: form.email.trim(),
      phone: form.phone.trim() || undefined,
      requester_reference: form.requester_reference.trim() || undefined,
      include_breach_check: form.include_breach_check,
      include_social_scan: form.include_social_scan,
      include_paste_check: form.include_paste_check,
      include_stealer_logs: form.include_stealer_logs,
    }

    createMutation.mutate(request, { onSuccess })
  }, [form, isValid, createMutation, onSuccess])

  const errorMessage = createMutation.error?.message

  const inputClass =
    'w-full rounded-lg border bg-transparent px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500'

  const labelClass = 'mb-1.5 block text-sm font-medium'

  return (
    <div className="space-y-4">
      {/* Full name */}
      <div>
        <label htmlFor="gdpr-full-name" className={labelClass} style={{ color: 'var(--text-primary)' }}>
          Full Name <span style={{ color: 'var(--danger-500)' }}>*</span>
        </label>
        <input
          id="gdpr-full-name"
          type="text"
          value={form.full_name}
          onChange={(e) => handleChange('full_name', e.target.value)}
          placeholder="Jane Doe"
          className={inputClass}
          style={{ borderColor: 'var(--border-default)', color: 'var(--text-primary)' }}
        />
      </div>

      {/* Email */}
      <div>
        <label htmlFor="gdpr-email" className={labelClass} style={{ color: 'var(--text-primary)' }}>
          Email Address <span style={{ color: 'var(--danger-500)' }}>*</span>
        </label>
        <input
          id="gdpr-email"
          type="email"
          value={form.email}
          onChange={(e) => handleChange('email', e.target.value)}
          placeholder="jane.doe@example.com"
          className={inputClass}
          style={{ borderColor: 'var(--border-default)', color: 'var(--text-primary)' }}
        />
      </div>

      {/* Phone */}
      <div>
        <label htmlFor="gdpr-phone" className={labelClass} style={{ color: 'var(--text-primary)' }}>
          Phone{' '}
          <span className="text-xs font-normal" style={{ color: 'var(--text-tertiary)' }}>
            (optional)
          </span>
        </label>
        <input
          id="gdpr-phone"
          type="tel"
          value={form.phone}
          onChange={(e) => handleChange('phone', e.target.value)}
          placeholder="+1 555 000 0000"
          className={inputClass}
          style={{ borderColor: 'var(--border-default)', color: 'var(--text-primary)' }}
        />
      </div>

      {/* Requester reference */}
      <div>
        <label htmlFor="gdpr-reference" className={labelClass} style={{ color: 'var(--text-primary)' }}>
          Requester Reference{' '}
          <span className="text-xs font-normal" style={{ color: 'var(--text-tertiary)' }}>
            (optional)
          </span>
        </label>
        <input
          id="gdpr-reference"
          type="text"
          value={form.requester_reference}
          onChange={(e) => handleChange('requester_reference', e.target.value)}
          placeholder="Ticket #1234 or case ID"
          className={inputClass}
          style={{ borderColor: 'var(--border-default)', color: 'var(--text-primary)' }}
        />
      </div>

      {/* Scan modules */}
      <div>
        <p className="mb-2 text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
          Scan Modules
        </p>
        <div className="space-y-2 rounded-lg border p-3" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-elevated)' }}>
          {(
            [
              { key: 'include_breach_check', label: 'Data Breach Check', description: 'HIBP, known breach databases' },
              { key: 'include_social_scan', label: 'Social Profile Scan', description: 'Public social media exposure' },
              { key: 'include_paste_check', label: 'Paste Site Check', description: 'Pastebin, Ghostbin, etc.' },
              { key: 'include_stealer_logs', label: 'Stealer Logs', description: 'Infostealer credential dumps' },
            ] as const
          ).map(({ key, label, description }) => (
            <label key={key} className="flex cursor-pointer items-start gap-3">
              <input
                type="checkbox"
                checked={form[key]}
                onChange={(e) => handleChange(key, e.target.checked)}
                className="mt-0.5 h-4 w-4 rounded accent-brand-500"
              />
              <span>
                <span className="block text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                  {label}
                </span>
                <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
                  {description}
                </span>
              </span>
            </label>
          ))}
        </div>
      </div>

      {/* Error state */}
      {errorMessage && (
        <div
          className="flex items-start gap-2 rounded-lg border px-3 py-2 text-sm"
          role="alert"
          style={{
            background: 'var(--danger-900)',
            borderColor: 'var(--danger-500)',
            color: 'var(--danger-500)',
          }}
        >
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Submit */}
      <Button
        onClick={handleSubmit}
        disabled={!isValid}
        loading={createMutation.isPending}
        className="w-full"
        size="lg"
        leftIcon={<Shield className="h-4 w-4" />}
      >
        Run Exposure Check
      </Button>
    </div>
  )
}
