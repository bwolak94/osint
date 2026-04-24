import { CREDENTIAL_INTEL_GROUPS } from '../types'
import { CredentialIntelModuleCard } from './ModuleCard'
import type { CredentialIntelScan } from '../types'

interface CredentialIntelResultsProps {
  scan: CredentialIntelScan
}

export function CredentialIntelResults({ scan }: CredentialIntelResultsProps) {
  const safeResults = scan.results ?? {}
  const foundCount = Object.values(safeResults).filter((r) => r.found).length
  const total = Object.keys(safeResults).length
  const allGroupModules = new Set(CREDENTIAL_INTEL_GROUPS.flatMap((g) => g.modules))

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold" style={{ color: 'var(--text-primary)' }}>
            Results for <span className="font-mono text-brand-400">{scan.target}</span>
          </h2>
          <p className="text-xs mt-0.5" style={{ color: 'var(--text-tertiary)' }}>
            {foundCount} / {total} modules returned data &bull;{' '}
            {new Date(scan.created_at).toLocaleString()} &bull; {scan.target_type}
          </p>
        </div>
        <div
          className="rounded-full px-3 py-1 text-xs font-medium"
          style={{
            background: foundCount > 0 ? 'var(--danger-900)' : 'var(--bg-overlay)',
            color: foundCount > 0 ? 'var(--danger-400)' : 'var(--text-tertiary)',
          }}
        >
          {foundCount > 0 ? `${foundCount} findings` : 'Clean'}
        </div>
      </div>

      {CREDENTIAL_INTEL_GROUPS.map((group) => {
        const groupModules = group.modules.filter((m) => safeResults[m] !== undefined)
        if (groupModules.length === 0) return null
        return (
          <div key={group.key} className="space-y-2">
            <h3 className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>
              {group.label}
            </h3>
            <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
              {groupModules.map((m) => safeResults[m] ? (
                <CredentialIntelModuleCard key={m} name={m} result={safeResults[m]!} />
              ) : null)}
            </div>
          </div>
        )
      })}

      {/* Ungrouped modules */}
      {(() => {
        const ungrouped = Object.keys(safeResults).filter((m) => !allGroupModules.has(m))
        if (!ungrouped.length) return null
        return (
          <div className="space-y-2">
            <h3 className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>Other</h3>
            <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
              {ungrouped.map((m) => safeResults[m] ? (
                <CredentialIntelModuleCard key={m} name={m} result={safeResults[m]!} />
              ) : null)}
            </div>
          </div>
        )
      })()}
    </div>
  )
}
