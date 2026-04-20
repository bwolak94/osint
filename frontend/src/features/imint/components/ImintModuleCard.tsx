import { CheckCircle2, XCircle, AlertCircle, Minus } from 'lucide-react'
import { MODULE_LABELS } from '../types'
import type { ModuleResultData } from '../types'

interface ImintModuleCardProps {
  moduleName: string
  result: ModuleResultData
}

export function ImintModuleCard({ moduleName, result }: ImintModuleCardProps) {
  const label = MODULE_LABELS[moduleName] ?? moduleName.replace(/_/g, ' ')

  const icon = result.skipped ? (
    <Minus className="h-4 w-4" style={{ color: 'var(--text-tertiary)' }} />
  ) : result.error ? (
    <AlertCircle className="h-4 w-4" style={{ color: 'var(--warning-500)' }} />
  ) : result.found ? (
    <CheckCircle2 className="h-4 w-4" style={{ color: 'var(--success-500)' }} />
  ) : (
    <XCircle className="h-4 w-4" style={{ color: 'var(--text-tertiary)' }} />
  )

  const statusText = result.skipped
    ? 'Skipped'
    : result.error
    ? 'Error'
    : result.found
    ? 'Found'
    : 'No results'

  // Pull key highlights from result data
  const data = result.data ?? {}
  const highlights: string[] = []

  if (data.coordinates && typeof data.coordinates === 'object') {
    const c = data.coordinates as Record<string, number>
    if (c.latitude && c.longitude) {
      highlights.push(`GPS: ${c.latitude.toFixed(5)}, ${c.longitude.toFixed(5)}`)
    }
  }
  if (typeof data.climate_zone === 'string') highlights.push(`Climate: ${data.climate_zone}`)
  if (typeof data.vegetation_type === 'string') highlights.push(`Vegetation: ${data.vegetation_type}`)
  if (typeof data.scene_count === 'number') highlights.push(`Scenes: ${data.scene_count}`)
  if (typeof data.is_suspicious === 'boolean') {
    highlights.push(data.is_suspicious ? 'Suspicious: YES' : 'Suspicious: No')
  }
  if (typeof data.calculated_height_m === 'number') {
    highlights.push(`Height: ~${data.calculated_height_m.toFixed(1)} m`)
  }
  if (typeof data.networks_count === 'number') highlights.push(`WiFi nets: ${data.networks_count}`)
  if (Array.isArray(data.aircraft) && (data.aircraft as unknown[]).length > 0) {
    highlights.push(`Aircraft: ${(data.aircraft as unknown[]).length}`)
  }
  if (Array.isArray(data.vessels) && (data.vessels as unknown[]).length > 0) {
    highlights.push(`Vessels: ${(data.vessels as unknown[]).length}`)
  }
  if (typeof data.image_format === 'string') highlights.push(`Format: ${data.image_format}`)
  if (typeof data.confidence_score === 'number') {
    highlights.push(`Confidence: ${(data.confidence_score * 100).toFixed(0)}%`)
  }
  if (typeof data.sunrise_utc === 'string') highlights.push(`Sunrise: ${data.sunrise_utc}`)

  return (
    <div
      className="rounded-lg border p-3 space-y-1.5"
      style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-surface)' }}
    >
      <div className="flex items-center gap-2">
        {icon}
        <span className="text-sm font-medium truncate" style={{ color: 'var(--text-primary)' }}>
          {label}
        </span>
        <span
          className="ml-auto shrink-0 text-xs"
          style={{ color: result.found ? 'var(--success-500)' : 'var(--text-tertiary)' }}
        >
          {statusText}
        </span>
      </div>

      {highlights.length > 0 && (
        <ul className="space-y-0.5 pl-6">
          {highlights.slice(0, 3).map((h) => (
            <li key={h} className="text-xs truncate" style={{ color: 'var(--text-secondary)' }}>
              {h}
            </li>
          ))}
        </ul>
      )}

      {result.error && (
        <p className="text-xs pl-6 truncate" style={{ color: 'var(--warning-500)' }}>
          {result.error}
        </p>
      )}
    </div>
  )
}
