import { useState } from 'react'
import { User, Mail, Phone, Hash, Building2, AtSign, Search, Loader2 } from 'lucide-react'
import { Card, CardBody, CardHeader } from '@/shared/components/Card'
import type { DeepResearchRequest } from '../types'

interface ResearchFormProps {
  onSubmit: (req: DeepResearchRequest) => void
  isLoading: boolean
}

export function ResearchForm({ onSubmit, isLoading }: ResearchFormProps) {
  const [form, setForm] = useState<DeepResearchRequest>({})

  const set = (key: keyof DeepResearchRequest) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((prev) => ({ ...prev, [key]: e.target.value || undefined }))

  const hasInput = Object.values(form).some((v) => v && String(v).trim())

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (hasInput && !isLoading) onSubmit(form)
  }

  return (
    <Card>
      <CardHeader>
        <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
          Research Target
        </h2>
        <p className="text-xs mt-0.5" style={{ color: 'var(--text-tertiary)' }}>
          Fill in any known identifiers — all fields are optional, more data yields better results.
        </p>
      </CardHeader>
      <CardBody>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            {/* Personal */}
            <Field
              icon={<User className="h-4 w-4" />}
              placeholder="First name"
              value={form.first_name ?? ''}
              onChange={set('first_name')}
            />
            <Field
              icon={<User className="h-4 w-4" />}
              placeholder="Last name"
              value={form.last_name ?? ''}
              onChange={set('last_name')}
            />
            <Field
              icon={<AtSign className="h-4 w-4" />}
              placeholder="Username / handle"
              value={form.username ?? ''}
              onChange={set('username')}
            />
            <Field
              icon={<Mail className="h-4 w-4" />}
              placeholder="Email address"
              type="email"
              value={form.email ?? ''}
              onChange={set('email')}
            />
            <Field
              icon={<Phone className="h-4 w-4" />}
              placeholder="Phone number (+48...)"
              value={form.phone ?? ''}
              onChange={set('phone')}
            />
            {/* Corporate */}
            <Field
              icon={<Hash className="h-4 w-4" />}
              placeholder="NIP (Polish tax ID)"
              value={form.nip ?? ''}
              onChange={set('nip')}
              mono
            />
            <Field
              icon={<Building2 className="h-4 w-4" />}
              placeholder="Company name"
              value={form.company_name ?? ''}
              onChange={set('company_name')}
              className="sm:col-span-2"
            />
          </div>

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={!hasInput || isLoading}
              className="inline-flex items-center gap-2 rounded-lg px-5 py-2.5 text-sm font-medium transition-colors disabled:opacity-40"
              style={{
                background: 'var(--brand-500)',
                color: '#fff',
              }}
            >
              {isLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Search className="h-4 w-4" />
              )}
              {isLoading ? 'Researching…' : 'Run Deep Research'}
            </button>
          </div>
        </form>
      </CardBody>
    </Card>
  )
}

interface FieldProps {
  icon: React.ReactNode
  placeholder: string
  value: string
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void
  type?: string
  mono?: boolean
  className?: string
}

function Field({ icon, placeholder, value, onChange, type = 'text', mono, className = '' }: FieldProps) {
  return (
    <div className={`relative ${className}`}>
      <span
        className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2"
        style={{ color: 'var(--text-tertiary)' }}
      >
        {icon}
      </span>
      <input
        type={type}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        className={`w-full rounded-lg border py-2.5 pl-9 pr-3 text-sm outline-none transition-colors placeholder:opacity-50 focus:ring-1 ${mono ? 'font-mono' : ''}`}
        style={{
          background: 'var(--bg-elevated)',
          borderColor: 'var(--border-subtle)',
          color: 'var(--text-primary)',
        }}
      />
    </div>
  )
}
