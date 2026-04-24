import { useState, useCallback, useEffect } from 'react'
import { FileText, Download, FlaskConical } from 'lucide-react'
import { Card, CardHeader, CardBody } from '@/shared/components/Card'
import { useReportSections, useBuildReport } from './hooks'
import { SectionPicker } from './components/SectionPicker'
import { TemplateSidebar } from './components/TemplateSidebar'
import type { ReportFormat, ReportClassification } from './types'

const FORMAT_OPTIONS: { value: ReportFormat; label: string }[] = [
  { value: 'pdf', label: 'PDF' },
  { value: 'html', label: 'HTML' },
  { value: 'docx', label: 'DOCX' },
]

const CLASSIFICATION_OPTIONS: { value: ReportClassification; label: string }[] = [
  { value: 'UNCLASSIFIED', label: 'UNCLASSIFIED' },
  { value: 'CONFIDENTIAL', label: 'CONFIDENTIAL' },
  { value: 'SECRET', label: 'SECRET' },
]

const inputStyle: React.CSSProperties = {
  background: 'var(--bg-overlay)',
  border: '1px solid var(--border-subtle)',
  color: 'var(--text-primary)',
  borderRadius: '0.375rem',
  padding: '0.375rem 0.625rem',
  fontSize: '0.75rem',
  width: '100%',
  outline: 'none',
  transition: 'border-color 0.15s',
}

const labelStyle: React.CSSProperties = {
  display: 'block',
  fontSize: '0.6875rem',
  fontWeight: 500,
  color: 'var(--text-tertiary)',
  marginBottom: '0.25rem',
  textTransform: 'uppercase',
  letterSpacing: '0.04em',
}

interface ReportPrefill {
  title: string
  markdown: string
  source: string
  requestId: string
}

export function ReportBuilderPage() {
  const [investigationId, setInvestigationId] = useState('')
  const [title, setTitle] = useState('')
  const [prefill, setPrefill] = useState<ReportPrefill | null>(null)

  // Read pre-fill data from sessionStorage (set by Deep Research export)
  useEffect(() => {
    const raw = sessionStorage.getItem('report_prefill')
    if (raw) {
      try {
        const data = JSON.parse(raw) as ReportPrefill
        setPrefill(data)
        setTitle(data.title)
        sessionStorage.removeItem('report_prefill')
      } catch { /* ignore */ }
    }
  }, [])
  const [classification, setClassification] = useState<ReportClassification>('UNCLASSIFIED')
  const [format, setFormat] = useState<ReportFormat>('pdf')
  const [selectedSections, setSelectedSections] = useState<string[]>([])
  const [builtReportId, setBuiltReportId] = useState<string | null>(null)

  const { data: sections = [], isLoading: sectionsLoading } = useReportSections()
  const buildReport = useBuildReport()

  // Pre-select required sections when sections load
  const requiredIds = sections.filter((s) => s.required).map((s) => s.id)

  // Merge required sections that aren't yet in selection
  const mergedSelected = useCallback(() => {
    const missing = requiredIds.filter((id) => !selectedSections.includes(id))
    if (missing.length > 0) {
      return [...missing, ...selectedSections]
    }
    return selectedSections
  }, [requiredIds, selectedSections])

  const handleSectionsChange = useCallback(
    (next: string[]) => {
      // Ensure required sections are always present
      const missing = requiredIds.filter((id) => !next.includes(id))
      setSelectedSections([...missing, ...next.filter((id) => !missing.includes(id))])
    },
    [requiredIds],
  )

  const handleTemplateLoad = useCallback(
    (templateSections: string[]) => {
      const missing = requiredIds.filter((id) => !templateSections.includes(id))
      setSelectedSections([...missing, ...templateSections])
    },
    [requiredIds],
  )

  const handleBuild = useCallback(() => {
    if (!investigationId.trim()) return
    setBuiltReportId(null)
    buildReport.mutate(
      {
        investigation_id: investigationId.trim(),
        sections: mergedSelected(),
        format,
        ...(title.trim() ? { title: title.trim() } : {}),
        classification,
      },
      {
        onSuccess: (data) => {
          setBuiltReportId(data.report_id)
        },
      },
    )
  }, [investigationId, title, classification, format, mergedSelected, buildReport])

  const effectiveSelected = mergedSelected()
  const canBuild = investigationId.trim().length > 0 && effectiveSelected.length > 0

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>
          Report Builder
        </h1>
        <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)' }}>
          Compose, customise, and export investigation reports in your preferred format
        </p>
      </div>

      {/* Deep Research pre-fill banner */}
      {prefill && (
        <div
          className="flex items-start gap-3 rounded-lg border px-4 py-3"
          style={{ background: 'var(--brand-900)', borderColor: 'var(--brand-500)' }}
        >
          <FlaskConical className="h-4 w-4 mt-0.5 shrink-0" style={{ color: 'var(--brand-400)' }} />
          <div className="text-sm">
            <p className="font-medium" style={{ color: 'var(--brand-300)' }}>
              Pre-filled from Deep Research
            </p>
            <p className="text-xs mt-0.5" style={{ color: 'var(--text-tertiary)' }}>
              Title and content have been imported from research on <strong>{prefill.title.replace('Deep Research: ', '')}</strong>.
              Set an Investigation ID and click Build Report to generate the document.
            </p>
          </div>
        </div>
      )}

      {/* Two-column layout */}
      <div className="flex gap-6">
        {/* Left — 3/4 */}
        <div className="min-w-0 flex-[3] space-y-4">
          {/* Build settings */}
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <FileText className="h-4 w-4" style={{ color: 'var(--brand-500)' }} />
                <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                  Build Settings
                </h2>
              </div>
            </CardHeader>
            <CardBody>
              <div className="grid grid-cols-2 gap-4">
                <div className="col-span-2">
                  <label style={labelStyle} htmlFor="investigation-id">
                    Investigation ID
                  </label>
                  <input
                    id="investigation-id"
                    type="text"
                    value={investigationId}
                    onChange={(e) => setInvestigationId(e.target.value)}
                    placeholder="e.g. inv_01j2abc..."
                    style={inputStyle}
                    onFocus={(e) =>
                      ((e.currentTarget as HTMLElement).style.borderColor = 'var(--brand-500)')
                    }
                    onBlur={(e) =>
                      ((e.currentTarget as HTMLElement).style.borderColor = 'var(--border-subtle)')
                    }
                  />
                </div>

                <div className="col-span-2">
                  <label style={labelStyle} htmlFor="report-title">
                    Report Title{' '}
                    <span style={{ color: 'var(--text-tertiary)', fontWeight: 400 }}>
                      (optional)
                    </span>
                  </label>
                  <input
                    id="report-title"
                    type="text"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="e.g. Threat Actor Infrastructure Analysis"
                    style={inputStyle}
                    onFocus={(e) =>
                      ((e.currentTarget as HTMLElement).style.borderColor = 'var(--brand-500)')
                    }
                    onBlur={(e) =>
                      ((e.currentTarget as HTMLElement).style.borderColor = 'var(--border-subtle)')
                    }
                  />
                </div>

                <div>
                  <label style={labelStyle} htmlFor="classification">
                    Classification
                  </label>
                  <select
                    id="classification"
                    value={classification}
                    onChange={(e) => setClassification(e.target.value as ReportClassification)}
                    style={inputStyle}
                    onFocus={(e) =>
                      ((e.currentTarget as HTMLElement).style.borderColor = 'var(--brand-500)')
                    }
                    onBlur={(e) =>
                      ((e.currentTarget as HTMLElement).style.borderColor = 'var(--border-subtle)')
                    }
                  >
                    {CLASSIFICATION_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label style={labelStyle} htmlFor="format">
                    Output Format
                  </label>
                  <select
                    id="format"
                    value={format}
                    onChange={(e) => setFormat(e.target.value as ReportFormat)}
                    style={inputStyle}
                    onFocus={(e) =>
                      ((e.currentTarget as HTMLElement).style.borderColor = 'var(--brand-500)')
                    }
                    onBlur={(e) =>
                      ((e.currentTarget as HTMLElement).style.borderColor = 'var(--border-subtle)')
                    }
                  >
                    {FORMAT_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </CardBody>
          </Card>

          {/* Section picker */}
          <div>
            <h2 className="mb-3 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              Report Sections
            </h2>
            {sectionsLoading ? (
              <div className="grid grid-cols-2 gap-4">
                {[1, 2].map((i) => (
                  <div
                    key={i}
                    className="h-64 animate-pulse rounded-lg"
                    style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}
                  />
                ))}
              </div>
            ) : (
              <SectionPicker
                sections={sections}
                selected={effectiveSelected}
                onChange={handleSectionsChange}
              />
            )}
          </div>

          {/* Build button + success message */}
          <div className="flex items-center gap-4">
            <button
              type="button"
              onClick={handleBuild}
              disabled={!canBuild || buildReport.isPending}
              className="flex items-center gap-2 rounded-lg px-5 py-2.5 text-sm font-medium transition-opacity disabled:opacity-40"
              style={{
                background: 'var(--brand-500)',
                color: '#fff',
              }}
            >
              <Download className="h-4 w-4" />
              {buildReport.isPending ? 'Queuing...' : 'Build Report'}
            </button>

            {builtReportId !== null && !buildReport.isPending && (
              <div
                className="animate-in fade-in slide-in-from-left-2 rounded-md px-3 py-2 text-xs duration-300"
                style={{
                  background: 'var(--success-900)',
                  border: '1px solid var(--success-500)',
                  color: 'var(--success-500)',
                }}
                role="status"
                aria-live="polite"
              >
                Report queued — ID:{' '}
                <span className="font-mono font-medium">{builtReportId}</span>
              </div>
            )}
          </div>
        </div>

        {/* Right — 1/4 */}
        <div className="w-72 shrink-0">
          <TemplateSidebar
            currentSections={effectiveSelected}
            onLoad={handleTemplateLoad}
          />
        </div>
      </div>
    </div>
  )
}
