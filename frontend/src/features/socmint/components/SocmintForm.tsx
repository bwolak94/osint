import { useState } from 'react'
import { Users } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import { Badge } from '@/components/ui/badge'
import { SOCMINT_MODULE_GROUPS, MODULE_DESCRIPTIONS } from '../types'

interface SocmintFormProps {
  onSubmit: (target: string, targetType: string, modules: string[]) => void
  isLoading: boolean
}

const TARGET_TYPES = [
  { value: 'username', label: 'Username' },
  { value: 'email', label: 'Email' },
  { value: 'phone', label: 'Phone' },
  { value: 'url', label: 'Profile URL' },
] as const

type TargetType = (typeof TARGET_TYPES)[number]['value']

export function SocmintForm({ onSubmit, isLoading }: SocmintFormProps) {
  const [target, setTarget] = useState('')
  const [targetType, setTargetType] = useState<TargetType>('username')
  const [selectedGroups, setSelectedGroups] = useState<Set<string>>(
    () => new Set(SOCMINT_MODULE_GROUPS.map((g) => g.key))
  )

  const applicableGroups = SOCMINT_MODULE_GROUPS.filter((g) =>
    g.targetTypes.includes(targetType)
  )

  function toggleGroup(key: string) {
    setSelectedGroups((prev) => {
      const next = new Set(prev)
      if (next.has(key)) {
        next.delete(key)
      } else {
        next.add(key)
      }
      return next
    })
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!target.trim()) return

    const modules = applicableGroups
      .filter((g) => selectedGroups.has(g.key))
      .flatMap((g) => g.modules)

    onSubmit(target.trim(), targetType, modules)
  }

  const inputPlaceholder: Record<TargetType, string> = {
    username: 'johndoe',
    email: 'user@example.com',
    phone: '+1234567890',
    url: 'https://twitter.com/username',
  }

  const inputLabel: Record<TargetType, string> = {
    username: 'Username',
    email: 'Email Address',
    phone: 'Phone Number',
    url: 'Profile URL',
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {/* Target type selector */}
      <div className="space-y-2">
        <Label className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
          Target Type
        </Label>
        <div className="flex flex-wrap gap-2">
          {TARGET_TYPES.map((t) => (
            <button
              key={t.value}
              type="button"
              onClick={() => setTargetType(t.value)}
              className={`rounded-md px-3 py-1.5 text-sm font-medium transition-all border ${
                targetType === t.value
                  ? 'border-brand-500 bg-brand-900 text-brand-400'
                  : 'hover:text-text-primary'
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
        <Label
          htmlFor="socmint-target"
          className="text-sm font-medium"
          style={{ color: 'var(--text-primary)' }}
        >
          {inputLabel[targetType]}
        </Label>
        <Input
          id="socmint-target"
          value={target}
          onChange={(e) => setTarget(e.target.value)}
          placeholder={inputPlaceholder[targetType]}
          disabled={isLoading}
          className="font-mono"
        />
      </div>

      {/* Module group selection */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <Label className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
            Module Groups
          </Label>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-6 text-xs"
            onClick={() =>
              setSelectedGroups(
                selectedGroups.size === applicableGroups.length
                  ? new Set()
                  : new Set(applicableGroups.map((g) => g.key))
              )
            }
          >
            {selectedGroups.size === applicableGroups.length ? 'Deselect all' : 'Select all'}
          </Button>
        </div>
        <div className="grid gap-2 sm:grid-cols-2">
          {applicableGroups.map((group) => {
            const isChecked = selectedGroups.has(group.key)
            return (
              <div
                key={group.key}
                onClick={() => toggleGroup(group.key)}
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
                  onCheckedChange={() => toggleGroup(group.key)}
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
                      <Badge key={m} variant="outline" className="px-1 py-0 text-[10px]">
                        {MODULE_DESCRIPTIONS[m]?.split('—')[0].trim() ?? m.replace(/_/g, ' ')}
                      </Badge>
                    ))}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      <Button
        type="submit"
        disabled={isLoading || !target.trim() || selectedGroups.size === 0}
        className="w-full sm:w-auto"
      >
        <Users className="mr-2 h-4 w-4" />
        {isLoading ? 'Running SOCMINT Analysis…' : 'Run SOCMINT Analysis'}
      </Button>
    </form>
  )
}
