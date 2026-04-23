import { SOCMINT_MODULE_GROUPS } from '../types'
import { SocmintModuleCard } from './ModuleCard'
import type { SocmintScan } from '../types'

interface SocmintResultsProps {
  scan: SocmintScan
}

export function SocmintResults({ scan }: SocmintResultsProps) {
  const safeResults = scan.results ?? {}
  const foundCount = Object.values(safeResults).filter((r) => r.found).length
  const totalCount = Object.keys(safeResults).length

  const allGroupModules = new Set(SOCMINT_MODULE_GROUPS.flatMap((g) => g.modules))
  const ungrouped = Object.keys(safeResults).filter((m) => !allGroupModules.has(m))

  return (
    <div className="space-y-5">
      {/* Summary bar */}
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold" style={{ color: 'var(--text-primary)' }}>
            Results for{' '}
            <span className="font-mono text-brand-400">{scan.target}</span>
          </h2>
          <p className="text-xs mt-0.5" style={{ color: 'var(--text-tertiary)' }}>
            {foundCount} / {totalCount} modules returned data &bull;{' '}
            {new Date(scan.created_at).toLocaleString()} &bull;{' '}
            <span className="uppercase">{scan.target_type}</span>
          </p>
        </div>
        <div
          className="shrink-0 rounded-full px-3 py-1 text-xs font-medium"
          style={{
            background: foundCount > 0 ? 'var(--success-900)' : 'var(--bg-overlay)',
            color: foundCount > 0 ? 'var(--success-400)' : 'var(--text-tertiary)',
          }}
        >
          {foundCount > 0 ? `${foundCount} hits` : 'No data found'}
        </div>
      </div>

      {/* Group results by category */}
      {SOCMINT_MODULE_GROUPS.map((group) => {
        const groupModules = group.modules.filter((m) => safeResults[m] !== undefined)
        if (groupModules.length === 0) return null

        return (
          <div key={group.key} className="space-y-2">
            <h3
              className="text-xs font-semibold uppercase tracking-wider"
              style={{ color: 'var(--text-tertiary)' }}
            >
              {group.label}
            </h3>
            <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
              {groupModules.map((module) => (
                <SocmintModuleCard key={module} name={module} result={safeResults[module]} />
              ))}
            </div>
          </div>
        )
      })}

      {/* Modules not in any group */}
      {ungrouped.length > 0 && (
        <div className="space-y-2">
          <h3
            className="text-xs font-semibold uppercase tracking-wider"
            style={{ color: 'var(--text-tertiary)' }}
          >
            Other
          </h3>
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
            {ungrouped.map((module) => (
              <SocmintModuleCard key={module} name={module} result={safeResults[module]} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
