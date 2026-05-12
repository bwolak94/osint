import type { TechReconScan } from '../types'
import { ModuleCard } from './ModuleCard'

interface TechReconResultsProps {
  scan: TechReconScan
}

export function TechReconResults({ scan }: TechReconResultsProps) {
  const entries = Object.entries(scan.results ?? {})
  const foundCount = entries.filter(([, r]) => r.found).length

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-base font-semibold" style={{ color: 'var(--text-primary)' }}>
            Results for{' '}
            <span className="font-mono text-brand-400">{scan.target}</span>
          </h3>
          <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
            {foundCount} of {entries.length} modules returned results
          </p>
        </div>
        <span
          className="rounded-md border px-2 py-0.5 font-mono text-xs"
          style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-tertiary)' }}
        >
          {scan.target_type.toUpperCase()}
        </span>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {entries.map(([module, result]) => (
          <ModuleCard key={module} moduleName={module} result={result} />
        ))}
      </div>
    </div>
  )
}
