import { useState } from 'react'
import { Search } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import type { ModuleGroup } from '../types'
import { MODULE_GROUPS } from '../types'

interface TechReconFormProps {
  onSubmit: (target: string, modules: string[]) => void
  isLoading: boolean
}

export function TechReconForm({ onSubmit, isLoading }: TechReconFormProps) {
  const [target, setTarget] = useState('')
  const [selectedGroups, setSelectedGroups] = useState<Set<string>>(
    () => new Set(MODULE_GROUPS.map((g) => g.key))
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
    const modules = MODULE_GROUPS.filter((g) => selectedGroups.has(g.key)).flatMap((g) => g.modules)
    onSubmit(target.trim(), modules)
  }

  const allSelected = selectedGroups.size === MODULE_GROUPS.length
  const noneSelected = selectedGroups.size === 0

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-1.5">
        <Label htmlFor="tech-recon-target">Target domain or IP address</Label>
        <div className="flex gap-2">
          <Input
            id="tech-recon-target"
            placeholder="example.com or 1.2.3.4"
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            disabled={isLoading}
            className="flex-1"
          />
          <Button type="submit" disabled={isLoading || !target.trim() || noneSelected}>
            <Search className="mr-2 h-4 w-4" />
            {isLoading ? 'Scanning…' : 'Scan'}
          </Button>
        </div>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label className="text-sm font-medium">Module groups</Label>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-6 text-xs"
            onClick={() =>
              setSelectedGroups(allSelected ? new Set() : new Set(MODULE_GROUPS.map((g) => g.key)))
            }
          >
            {allSelected ? 'Deselect all' : 'Select all'}
          </Button>
        </div>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {MODULE_GROUPS.map((group: ModuleGroup) => (
            <label
              key={group.key}
              className="flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm transition-colors hover:bg-bg-overlay"
              style={{ borderColor: 'var(--border-subtle)' }}
            >
              <Checkbox
                checked={selectedGroups.has(group.key)}
                onCheckedChange={() => toggleGroup(group.key)}
                id={`group-${group.key}`}
              />
              <span style={{ color: 'var(--text-secondary)' }}>{group.label}</span>
            </label>
          ))}
        </div>
      </div>
    </form>
  )
}
