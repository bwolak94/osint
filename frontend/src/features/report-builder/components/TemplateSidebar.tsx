import { useState, useCallback } from 'react'
import { Save, Trash2, BookOpen, LayoutTemplate } from 'lucide-react'
import { Card, CardHeader, CardBody, CardFooter } from '@/shared/components/Card'
import { useReportTemplates, useSaveTemplate, useDeleteTemplate } from '../hooks'
import type { ReportTemplate } from '../types'

interface TemplateSidebarProps {
  currentSections: string[]
  onLoad: (sections: string[]) => void
}

export function TemplateSidebar({ currentSections, onLoad }: TemplateSidebarProps) {
  const [templateName, setTemplateName] = useState('')

  const { data: templates = [], isLoading } = useReportTemplates()
  const saveTemplate = useSaveTemplate()
  const deleteTemplate = useDeleteTemplate()

  const handleSave = useCallback(() => {
    const trimmed = templateName.trim()
    if (!trimmed || currentSections.length === 0) return
    saveTemplate.mutate(
      { name: trimmed, sections: currentSections },
      { onSuccess: () => setTemplateName('') },
    )
  }, [templateName, currentSections, saveTemplate])

  const handleDelete = useCallback(
    (id: string, e: React.MouseEvent) => {
      e.stopPropagation()
      deleteTemplate.mutate(id)
    },
    [deleteTemplate],
  )

  const handleLoad = useCallback(
    (template: ReportTemplate) => {
      onLoad(template.sections)
    },
    [onLoad],
  )

  return (
    <Card className="flex h-full flex-col">
      <CardHeader>
        <div className="flex items-center gap-2">
          <LayoutTemplate className="h-4 w-4" style={{ color: 'var(--brand-500)' }} />
          <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
            Templates
          </h2>
        </div>
        <p className="mt-0.5 text-xs" style={{ color: 'var(--text-tertiary)' }}>
          Saved section configurations
        </p>
      </CardHeader>

      <CardBody className="flex-1 overflow-y-auto p-0">
        {isLoading ? (
          <div className="space-y-2 px-4 py-3">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-14 animate-pulse rounded-md"
                style={{ background: 'var(--bg-overlay)' }}
              />
            ))}
          </div>
        ) : templates.length === 0 ? (
          <div className="flex flex-col items-center gap-2 px-4 py-8">
            <BookOpen className="h-6 w-6" style={{ color: 'var(--text-tertiary)' }} />
            <p className="text-center text-xs" style={{ color: 'var(--text-tertiary)' }}>
              No saved templates yet. Configure sections and save below.
            </p>
          </div>
        ) : (
          <ul className="divide-y" style={{ borderColor: 'var(--border-subtle)' }}>
            {templates.map((template) => (
              <li key={template.id} className="group px-4 py-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <p
                      className="truncate text-xs font-medium"
                      style={{ color: 'var(--text-primary)' }}
                    >
                      {template.name}
                    </p>
                    <p className="mt-0.5 text-[11px]" style={{ color: 'var(--text-tertiary)' }}>
                      {template.sections.length} section{template.sections.length !== 1 ? 's' : ''}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={(e) => handleDelete(template.id, e)}
                    disabled={deleteTemplate.isPending}
                    className="shrink-0 rounded p-1 opacity-0 transition-all group-hover:opacity-100 disabled:opacity-30"
                    style={{ color: 'var(--text-tertiary)' }}
                    onMouseEnter={(e) =>
                      ((e.currentTarget as HTMLElement).style.color = 'var(--danger-500)')
                    }
                    onMouseLeave={(e) =>
                      ((e.currentTarget as HTMLElement).style.color = 'var(--text-tertiary)')
                    }
                    aria-label={`Delete template ${template.name}`}
                  >
                    <Trash2 className="h-3 w-3" />
                  </button>
                </div>
                <button
                  type="button"
                  onClick={() => handleLoad(template)}
                  className="mt-2 w-full rounded px-2 py-1 text-[11px] font-medium transition-colors"
                  style={{
                    background: 'var(--bg-overlay)',
                    color: 'var(--text-secondary)',
                    border: '1px solid var(--border-subtle)',
                  }}
                  onMouseEnter={(e) => {
                    const el = e.currentTarget as HTMLElement
                    el.style.borderColor = 'var(--brand-500)'
                    el.style.color = 'var(--brand-500)'
                  }}
                  onMouseLeave={(e) => {
                    const el = e.currentTarget as HTMLElement
                    el.style.borderColor = 'var(--border-subtle)'
                    el.style.color = 'var(--text-secondary)'
                  }}
                >
                  Load
                </button>
              </li>
            ))}
          </ul>
        )}
      </CardBody>

      <CardFooter>
        <p className="mb-2 text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>
          Save current as template
        </p>
        <div className="flex gap-2">
          <input
            type="text"
            value={templateName}
            onChange={(e) => setTemplateName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSave()}
            placeholder="Template name..."
            className="min-w-0 flex-1 rounded-md px-2.5 py-1.5 text-xs outline-none transition-colors"
            style={{
              background: 'var(--bg-overlay)',
              border: '1px solid var(--border-subtle)',
              color: 'var(--text-primary)',
            }}
            onFocus={(e) =>
              ((e.currentTarget as HTMLElement).style.borderColor = 'var(--brand-500)')
            }
            onBlur={(e) =>
              ((e.currentTarget as HTMLElement).style.borderColor = 'var(--border-subtle)')
            }
          />
          <button
            type="button"
            onClick={handleSave}
            disabled={
              !templateName.trim() ||
              currentSections.length === 0 ||
              saveTemplate.isPending
            }
            className="flex shrink-0 items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-opacity disabled:opacity-40"
            style={{
              background: 'var(--brand-500)',
              color: '#fff',
            }}
            aria-label="Save template"
          >
            <Save className="h-3 w-3" />
            Save
          </button>
        </div>
      </CardFooter>
    </Card>
  )
}
