import { useState, useMemo } from 'react'
import { Search } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import { IMAGE_MODULE_GROUPS, COORDINATES_MODULE_GROUPS } from '../types'
import type { ModuleGroup } from '../types'

interface ImintFormProps {
  onSubmit: (target: string, modules: string[]) => void
  isLoading: boolean
}

const COORDS_RE = /^-?\d{1,3}(\.\d+)?,-?\d{1,3}(\.\d+)?/

function detectTargetMode(value: string): 'coordinates' | 'image' {
  return COORDS_RE.test(value.trim()) ? 'coordinates' : 'image'
}

export function ImintForm({ onSubmit, isLoading }: ImintFormProps) {
  const [target, setTarget] = useState('')
  const [selectedGroups, setSelectedGroups] = useState<Set<string>>(new Set())

  const mode = useMemo(() => detectTargetMode(target), [target])
  const groups: ModuleGroup[] = mode === 'coordinates' ? COORDINATES_MODULE_GROUPS : IMAGE_MODULE_GROUPS

  // Reset selection when mode changes
  const allGroupKeys = new Set(groups.map((g) => g.key))

  function toggleGroup(key: string) {
    setSelectedGroups((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const activeSelected = [...selectedGroups].filter((k) => allGroupKeys.has(k))
  const allSelected = activeSelected.length === groups.length
  const noneSelected = activeSelected.length === 0

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!target.trim()) return
    const selected = noneSelected ? groups : groups.filter((g) => activeSelected.includes(g.key))
    const modules = selected.flatMap((g) => g.modules)
    onSubmit(target.trim(), modules)
  }

  const placeholder =
    mode === 'coordinates'
      ? 'e.g. 48.8566,2.3522 (lat,lon)'
      : 'Image URL — https://example.com/photo.jpg'

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-1.5">
        <Label htmlFor="imint-target">Target — image URL or GPS coordinates</Label>
        <div className="flex gap-2">
          <Input
            id="imint-target"
            placeholder={placeholder}
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            disabled={isLoading}
            className="flex-1 font-mono text-sm"
          />
          <Button type="submit" disabled={isLoading || !target.trim()}>
            <Search className="mr-2 h-4 w-4" />
            {isLoading ? 'Scanning…' : 'Scan'}
          </Button>
        </div>
        <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
          {mode === 'coordinates'
            ? 'Coordinates mode — geospatial modules active'
            : 'Image mode — visual analysis modules active'}
        </p>
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
              setSelectedGroups(
                allSelected ? new Set() : new Set(groups.map((g) => g.key))
              )
            }
          >
            {allSelected ? 'Deselect all' : 'Select all'}
          </Button>
        </div>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {groups.map((group: ModuleGroup) => (
            <label
              key={group.key}
              className="flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm transition-colors hover:bg-bg-overlay"
              style={{ borderColor: 'var(--border-subtle)' }}
            >
              <Checkbox
                checked={selectedGroups.has(group.key)}
                onCheckedChange={() => toggleGroup(group.key)}
                id={`imint-group-${group.key}`}
              />
              <span style={{ color: 'var(--text-secondary)' }}>{group.label}</span>
            </label>
          ))}
        </div>
      </div>
    </form>
  )
}
