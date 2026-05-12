import { useState } from 'react'
import type { ComplexityRow } from '../types'

interface PasswordComplexityChartProps {
  rows: ComplexityRow[]
}

// Color scale based on crack time
function getCrackColor(time: string): string {
  if (time.includes('second') || time.includes('minute')) return 'var(--danger-500)'
  if (time.includes('hour') || time.includes('day')) return 'var(--warning-500)'
  if (time.includes('year') && !time.includes('e+')) return 'var(--brand-400)'
  return 'var(--success-500)'
}

const CHARSET_ORDER = ['digits_only', 'lowercase', 'alpha', 'alphanumeric', 'printable_ascii']
const LENGTHS = [6, 8, 10, 12, 16, 20]

export function PasswordComplexityChart({ rows }: PasswordComplexityChartProps) {
  const [selectedCharset, setSelectedCharset] = useState<string>('printable_ascii')

  // Build lookup: charset -> length -> row
  const lookup: Record<string, Record<number, ComplexityRow>> = {}
  for (const row of rows) {
    if (!lookup[row.charset]) lookup[row.charset] = {}
    const charsetLookup = lookup[row.charset]
    if (charsetLookup) charsetLookup[row.length] = row
  }

  const charsets = CHARSET_ORDER.filter((c) => lookup[c])
  const selectedData = lookup[selectedCharset] ?? {}

  return (
    <div className="space-y-4">
      {/* Formula display */}
      <div
        className="rounded-lg border p-4"
        style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-overlay)' }}
      >
        <p className="text-sm font-mono text-center" style={{ color: 'var(--text-primary)' }}>
          C = K<sup>L</sup>
        </p>
        <p className="text-xs text-center mt-1" style={{ color: 'var(--text-tertiary)' }}>
          where <strong>K</strong> = charset size, <strong>L</strong> = password length
        </p>
        <p className="text-xs text-center mt-1" style={{ color: 'var(--text-tertiary)' }}>
          Crack time assumes 4x RTX 4090 GPU running SHA-256
        </p>
      </div>

      {/* Charset selector */}
      <div className="flex flex-wrap gap-2">
        {charsets.map((c) => {
          const sample = Object.values(lookup[c] ?? {})[0]
          return (
            <button
              key={c}
              onClick={() => setSelectedCharset(c)}
              className={`rounded-md border px-3 py-1.5 text-xs font-medium transition-all ${
                selectedCharset === c ? 'border-brand-500 bg-brand-900 text-brand-400' : ''
              }`}
              style={
                selectedCharset !== c
                  ? { borderColor: 'var(--border-subtle)', color: 'var(--text-secondary)' }
                  : {}
              }
            >
              {sample?.charset_description ?? c} (K={sample?.charset_size})
            </button>
          )
        })}
      </div>

      {/* Complexity bar chart */}
      <div className="space-y-2">
        {LENGTHS.map((len) => {
          const row = selectedData[len]
          if (!row) return null
          const color = getCrackColor(row.crack_time_sha256_4gpu)

          // Log-scale bar width (0-100%)
          // Map log10(combinations) from ~7 (10^7) to 40 (10^40) to 0-100%
          const log10 = Math.log10(Number(row.combinations.replace(/[^0-9.e+]/g, '')) || 1)
          const barPct = Math.min(100, Math.max(2, ((log10 - 6) / 34) * 100))

          return (
            <div key={len} className="space-y-1">
              <div className="flex items-center justify-between text-xs">
                <span style={{ color: 'var(--text-secondary)' }}>
                  {len} chars
                </span>
                <span className="font-mono" style={{ color }}>
                  {row.crack_time_sha256_4gpu}
                </span>
              </div>
              <div
                className="h-2 rounded-full overflow-hidden"
                style={{ background: 'var(--bg-base)' }}
              >
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{ width: `${barPct}%`, background: color }}
                />
              </div>
              <p className="text-[10px]" style={{ color: 'var(--text-tertiary)' }}>
                {row.combinations} combinations
              </p>
            </div>
          )
        })}
      </div>

      <p className="text-[10px] italic" style={{ color: 'var(--text-tertiary)' }}>
        Key insight: adding one character increases complexity by xK, while adding a special character only expands K by ~32. Length dominates entropy.
      </p>
    </div>
  )
}
