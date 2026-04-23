import { useCallback } from 'react'
import { ChevronUp, ChevronDown, Plus, Minus } from 'lucide-react'
import { Badge } from '@/shared/components/Badge'
import { Card, CardHeader, CardBody } from '@/shared/components/Card'
import type { ReportSection } from '../types'

interface SectionPickerProps {
  sections: ReportSection[]
  selected: string[]
  onChange: (selected: string[]) => void
}

export function SectionPicker({ sections, selected, onChange }: SectionPickerProps) {
  const selectedSections = selected
    .map((id) => sections.find((s) => s.id === id))
    .filter((s): s is ReportSection => s !== undefined)

  const availableSections = sections.filter((s) => !selected.includes(s.id))

  const handleAdd = useCallback(
    (id: string) => {
      onChange([...selected, id])
    },
    [selected, onChange],
  )

  const handleRemove = useCallback(
    (id: string) => {
      onChange(selected.filter((s) => s !== id))
    },
    [selected, onChange],
  )

  const handleMoveUp = useCallback(
    (index: number) => {
      if (index === 0) return
      const next = [...selected]
      ;[next[index - 1], next[index]] = [next[index], next[index - 1]]
      onChange(next)
    },
    [selected, onChange],
  )

  const handleMoveDown = useCallback(
    (index: number) => {
      if (index === selected.length - 1) return
      const next = [...selected]
      ;[next[index], next[index + 1]] = [next[index + 1], next[index]]
      onChange(next)
    },
    [selected, onChange],
  )

  return (
    <div className="grid grid-cols-2 gap-4">
      {/* Available sections */}
      <Card>
        <CardHeader>
          <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
            Available Sections
          </h3>
          <p className="mt-0.5 text-xs" style={{ color: 'var(--text-tertiary)' }}>
            Click a section to add it to the report
          </p>
        </CardHeader>
        <CardBody className="p-0">
          {availableSections.length === 0 ? (
            <p
              className="px-5 py-6 text-center text-xs"
              style={{ color: 'var(--text-tertiary)' }}
            >
              All sections have been added
            </p>
          ) : (
            <ul className="divide-y" style={{ borderColor: 'var(--border-subtle)' }}>
              {availableSections.map((section) => (
                <li key={section.id}>
                  <button
                    type="button"
                    onClick={() => handleAdd(section.id)}
                    className="group flex w-full items-start gap-3 px-5 py-3 text-left transition-colors"
                    style={
                      {
                        '--hover-bg': 'var(--bg-overlay)',
                      } as React.CSSProperties
                    }
                    onMouseEnter={(e) =>
                      ((e.currentTarget as HTMLElement).style.background = 'var(--bg-overlay)')
                    }
                    onMouseLeave={(e) =>
                      ((e.currentTarget as HTMLElement).style.background = 'transparent')
                    }
                  >
                    <Plus
                      className="mt-0.5 h-3.5 w-3.5 shrink-0 opacity-0 transition-opacity group-hover:opacity-100"
                      style={{ color: 'var(--brand-500)' }}
                    />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span
                          className="text-xs font-medium"
                          style={{ color: 'var(--text-primary)' }}
                        >
                          {section.name}
                        </span>
                        {section.required && (
                          <Badge variant="brand" size="sm">
                            Required
                          </Badge>
                        )}
                      </div>
                      <p
                        className="mt-0.5 text-[11px] leading-relaxed"
                        style={{ color: 'var(--text-tertiary)' }}
                      >
                        {section.description}
                      </p>
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </CardBody>
      </Card>

      {/* Selected sections */}
      <Card>
        <CardHeader>
          <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
            Selected Sections
          </h3>
          <p className="mt-0.5 text-xs" style={{ color: 'var(--text-tertiary)' }}>
            {selected.length} section{selected.length !== 1 ? 's' : ''} — reorder with arrows
          </p>
        </CardHeader>
        <CardBody className="p-0">
          {selectedSections.length === 0 ? (
            <p
              className="px-5 py-6 text-center text-xs"
              style={{ color: 'var(--text-tertiary)' }}
            >
              No sections selected. Add sections from the left.
            </p>
          ) : (
            <ul className="divide-y" style={{ borderColor: 'var(--border-subtle)' }}>
              {selectedSections.map((section, index) => (
                <li key={section.id} className="flex items-start gap-3 px-5 py-3">
                  <span
                    className="mt-0.5 w-5 shrink-0 text-center text-[11px] font-medium tabular-nums"
                    style={{ color: 'var(--text-tertiary)' }}
                  >
                    {index + 1}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span
                        className="text-xs font-medium"
                        style={{ color: 'var(--text-primary)' }}
                      >
                        {section.name}
                      </span>
                      {section.required && (
                        <Badge variant="brand" size="sm">
                          Required
                        </Badge>
                      )}
                    </div>
                    <p
                      className="mt-0.5 text-[11px] leading-relaxed"
                      style={{ color: 'var(--text-tertiary)' }}
                    >
                      {section.description}
                    </p>
                  </div>
                  <div className="flex shrink-0 flex-col gap-0.5">
                    <button
                      type="button"
                      onClick={() => handleMoveUp(index)}
                      disabled={index === 0}
                      className="rounded p-0.5 transition-colors disabled:opacity-30"
                      style={{ color: 'var(--text-tertiary)' }}
                      onMouseEnter={(e) =>
                        !e.currentTarget.disabled &&
                        ((e.currentTarget as HTMLElement).style.color = 'var(--text-primary)')
                      }
                      onMouseLeave={(e) =>
                        ((e.currentTarget as HTMLElement).style.color = 'var(--text-tertiary)')
                      }
                      aria-label="Move section up"
                    >
                      <ChevronUp className="h-3 w-3" />
                    </button>
                    <button
                      type="button"
                      onClick={() => handleMoveDown(index)}
                      disabled={index === selectedSections.length - 1}
                      className="rounded p-0.5 transition-colors disabled:opacity-30"
                      style={{ color: 'var(--text-tertiary)' }}
                      onMouseEnter={(e) =>
                        !e.currentTarget.disabled &&
                        ((e.currentTarget as HTMLElement).style.color = 'var(--text-primary)')
                      }
                      onMouseLeave={(e) =>
                        ((e.currentTarget as HTMLElement).style.color = 'var(--text-tertiary)')
                      }
                      aria-label="Move section down"
                    >
                      <ChevronDown className="h-3 w-3" />
                    </button>
                  </div>
                  {!section.required && (
                    <button
                      type="button"
                      onClick={() => handleRemove(section.id)}
                      className="shrink-0 rounded p-0.5 transition-colors"
                      style={{ color: 'var(--text-tertiary)' }}
                      onMouseEnter={(e) =>
                        ((e.currentTarget as HTMLElement).style.color = 'var(--danger-500)')
                      }
                      onMouseLeave={(e) =>
                        ((e.currentTarget as HTMLElement).style.color = 'var(--text-tertiary)')
                      }
                      aria-label={`Remove ${section.name}`}
                    >
                      <Minus className="h-3 w-3" />
                    </button>
                  )}
                  {section.required && <div className="w-5 shrink-0" />}
                </li>
              ))}
            </ul>
          )}
        </CardBody>
      </Card>
    </div>
  )
}
