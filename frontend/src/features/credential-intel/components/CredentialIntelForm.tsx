import { useState } from 'react'
import { Shield } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import { Badge } from '@/components/ui/badge'
import { CREDENTIAL_INTEL_GROUPS } from '../types'
import type { CredentialIntelScan } from '../types'

interface CredentialIntelFormProps {
  onSubmit: (target: string, targetType: CredentialIntelScan['target_type'], modules: string[]) => void
  isLoading: boolean
}

const TARGET_TYPES = [
  { value: 'email' as const,  label: 'Email',   placeholder: 'user@example.com' },
  { value: 'domain' as const, label: 'Domain',  placeholder: 'example.com' },
  { value: 'ip' as const,     label: 'IP',      placeholder: '1.2.3.4' },
  { value: 'hash' as const,   label: 'Hash',    placeholder: '5f4dcc3b5aa765d61d8327deb882cf99' },
]

export function CredentialIntelForm({ onSubmit, isLoading }: CredentialIntelFormProps) {
  const [target, setTarget] = useState('')
  const [targetType, setTargetType] = useState<CredentialIntelScan['target_type']>('email')
  const [selectedGroups, setSelectedGroups] = useState<Set<string>>(
    new Set(CREDENTIAL_INTEL_GROUPS.map((g) => g.key))
  )

  const applicable = CREDENTIAL_INTEL_GROUPS.filter((g) => g.targetTypes.includes(targetType))

  function toggle(key: string) {
    setSelectedGroups((prev) => {
      const next = new Set(prev)
      next.has(key) ? next.delete(key) : next.add(key)
      return next
    })
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!target.trim()) return
    const modules = applicable.filter((g) => selectedGroups.has(g.key)).flatMap((g) => g.modules)
    onSubmit(target.trim(), targetType, modules)
  }

  const placeholder = TARGET_TYPES.find((t) => t.value === targetType)?.placeholder ?? ''

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {/* Target type tabs */}
      <div className="space-y-2">
        <Label style={{ color: 'var(--text-primary)' }}>Target Type</Label>
        <div className="flex flex-wrap gap-2">
          {TARGET_TYPES.map((t) => (
            <button
              key={t.value}
              type="button"
              onClick={() => setTargetType(t.value)}
              className={`rounded-md border px-3 py-1.5 text-sm font-medium transition-all ${
                targetType === t.value ? 'border-brand-500 bg-brand-900 text-brand-400' : ''
              }`}
              style={
                targetType !== t.value
                  ? { borderColor: 'var(--border-subtle)', color: 'var(--text-secondary)' }
                  : {}
              }
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Target input */}
      <div className="space-y-2">
        <Label htmlFor="cred-intel-target" style={{ color: 'var(--text-primary)' }}>
          {TARGET_TYPES.find((t) => t.value === targetType)?.label}
        </Label>
        <Input
          id="cred-intel-target"
          value={target}
          onChange={(e) => setTarget(e.target.value)}
          placeholder={placeholder}
          disabled={isLoading}
          className="font-mono"
        />
      </div>

      {/* Module groups */}
      <div className="space-y-2">
        <Label style={{ color: 'var(--text-primary)' }}>Intelligence Modules</Label>
        <div className="grid gap-2 sm:grid-cols-2">
          {applicable.map((group) => {
            const isChecked = selectedGroups.has(group.key)
            return (
              <div
                key={group.key}
                onClick={() => toggle(group.key)}
                className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-all ${
                  isChecked ? 'border-brand-500 bg-brand-900/30' : ''
                }`}
                style={
                  !isChecked
                    ? { borderColor: 'var(--border-subtle)', background: 'var(--bg-overlay)' }
                    : {}
                }
              >
                <Checkbox
                  checked={isChecked}
                  onCheckedChange={() => toggle(group.key)}
                  className="mt-0.5 shrink-0"
                  onClick={(e) => e.stopPropagation()}
                />
                <div className="min-w-0">
                  <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                    {group.label}
                  </p>
                  <p className="mt-0.5 text-xs" style={{ color: 'var(--text-tertiary)' }}>
                    {group.description}
                  </p>
                  <div className="mt-1.5 flex flex-wrap gap-1">
                    {group.modules.map((m) => (
                      <Badge key={m} variant="outline" className="text-[10px] px-1 py-0">
                        {m.replace(/_/g, ' ')}
                      </Badge>
                    ))}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      <Button type="submit" disabled={isLoading || !target.trim()} className="w-full sm:w-auto">
        <Shield className="mr-2 h-4 w-4" />
        {isLoading ? 'Analyzing...' : 'Run Credential Intelligence'}
      </Button>
    </form>
  )
}
