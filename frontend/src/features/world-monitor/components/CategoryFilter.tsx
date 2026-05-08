import type { NewsCategory } from '../types'

const CATEGORY_LABELS: Record<string, string> = {
  geopolitics: 'Geopolitics',
  military: 'Military',
  cyber: 'Cyber',
  economy: 'Economy',
  climate: 'Climate',
  disaster: 'Disasters',
  health: 'Health',
  energy: 'Energy',
  tech: 'Tech',
}

const CATEGORY_COLORS: Record<string, string> = {
  geopolitics: 'var(--brand-500)',
  military: '#ef4444',
  cyber: '#f59e0b',
  economy: '#10b981',
  climate: '#06b6d4',
  disaster: '#f97316',
  health: '#ec4899',
  energy: '#8b5cf6',
  tech: '#6366f1',
}

interface CategoryFilterProps {
  categories: string[]
  active: NewsCategory | null
  onChange: (cat: NewsCategory | null) => void
}

export function CategoryFilter({ categories, active, onChange }: CategoryFilterProps) {
  const all = [null, ...categories] as (NewsCategory | null)[]

  return (
    <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter by category">
      {all.map((cat) => {
        const isActive = cat === active
        const label = cat ? (CATEGORY_LABELS[cat] ?? cat) : 'All'
        const color = cat ? CATEGORY_COLORS[cat] : 'var(--brand-500)'

        return (
          <button
            key={cat ?? 'all'}
            onClick={() => onChange(cat)}
            aria-pressed={isActive}
            className="rounded-full px-3 py-0.5 text-xs font-medium transition-all"
            style={{
              background: isActive ? color : 'var(--bg-elevated)',
              color: isActive ? '#fff' : 'var(--text-secondary)',
              border: `1px solid ${isActive ? color : 'var(--border-subtle)'}`,
            }}
          >
            {label}
          </button>
        )
      })}
    </div>
  )
}
