import { useState, useCallback } from 'react'
import { Network, Download, Play, ChevronRight, CheckCircle } from 'lucide-react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Card, CardHeader, CardBody } from '@/shared/components/Card'
import { Badge } from '@/shared/components/Badge'
import { maltegoApi } from './api'
import type { MaltegoTransformResponse, TransformConfig } from './types'

const ENTITY_TYPES = [
  'maltego.Domain',
  'maltego.IPv4Address',
  'maltego.EmailAddress',
  'maltego.Username',
  'maltego.Person',
  'maltego.PhoneNumber',
  'maltego.URL',
  'maltego.Organization',
]

const SETUP_STEPS = [
  {
    step: 1,
    title: 'Download the ITDS seed file',
    description: 'Click the button below to download the transform configuration file.',
  },
  {
    step: 2,
    title: 'Import into Maltego',
    description: 'Open Maltego → Manage → Import Config → select the downloaded file.',
  },
  {
    step: 3,
    title: 'Start investigating',
    description: 'The "OSINT Platform" transform set will appear in your Transform Hub.',
  },
]

function entityTypeBadgeVariant(entityType: string): 'brand' | 'info' | 'success' | 'warning' | 'neutral' {
  if (entityType.includes('Domain')) return 'brand'
  if (entityType.includes('IPv4')) return 'info'
  if (entityType.includes('Email')) return 'success'
  if (entityType.includes('Username')) return 'warning'
  return 'neutral'
}

function shortEntityType(entityType: string): string {
  return entityType.replace('maltego.', '')
}

export function MaltegoPage() {
  const [selectedEntityType, setSelectedEntityType] = useState<string>(ENTITY_TYPES[0])
  const [entityValue, setEntityValue] = useState('')
  const [selectedTransform, setSelectedTransform] = useState<string>('')
  const [testResult, setTestResult] = useState<MaltegoTransformResponse | null>(null)

  const { data: transforms = [], isLoading: transformsLoading } = useQuery({
    queryKey: ['maltego', 'transforms'],
    queryFn: maltegoApi.listTransforms,
  })

  const availableTransforms = transforms.filter(
    (t) => t.entity_type === selectedEntityType,
  )

  const runMutation = useMutation({
    mutationFn: maltegoApi.runTransform,
    onSuccess: (data) => setTestResult(data),
  })

  const handleDownloadItds = useCallback(async () => {
    const data = await maltegoApi.getItdsConfig()
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'osint-platform-maltego.itds.json'
    a.click()
    URL.revokeObjectURL(url)
  }, [])

  const handleRunTransform = useCallback(() => {
    if (!entityValue.trim() || !selectedTransform) return
    setTestResult(null)
    runMutation.mutate({
      entity: { type: selectedEntityType, value: entityValue.trim(), properties: {} },
      transform_name: selectedTransform,
      limit: 50,
    })
  }, [entityValue, selectedEntityType, selectedTransform, runMutation])

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center gap-3">
        <div
          className="flex h-9 w-9 items-center justify-center rounded-lg"
          style={{ background: 'var(--brand-900)', border: '1px solid var(--brand-500, #6366f1)20' }}
        >
          <Network className="h-5 w-5" style={{ color: 'var(--brand-500)' }} />
        </div>
        <div>
          <h1 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>
            Maltego Integration
          </h1>
          <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
            Use OSINT Platform scanners as remote transforms inside Maltego
          </p>
        </div>
      </div>

      {/* Setup guide */}
      <Card>
        <CardHeader>
          <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
            Setup Guide
          </h2>
        </CardHeader>
        <CardBody>
          <div className="space-y-4">
            {SETUP_STEPS.map(({ step, title, description }) => (
              <div key={step} className="flex items-start gap-4">
                <div
                  className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold"
                  style={{ background: 'var(--brand-900)', color: 'var(--brand-400, #818cf8)' }}
                >
                  {step}
                </div>
                <div className="flex-1">
                  <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                    {title}
                  </p>
                  <p className="mt-0.5 text-xs" style={{ color: 'var(--text-secondary)' }}>
                    {description}
                  </p>
                  {step === 1 && (
                    <button
                      onClick={handleDownloadItds}
                      className="mt-2 inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-xs font-medium transition-colors"
                      style={{
                        background: 'var(--brand-900)',
                        color: 'var(--brand-400, #818cf8)',
                        border: '1px solid var(--brand-500, #6366f1)30',
                      }}
                    >
                      <Download className="h-3.5 w-3.5" />
                      Download ITDS Config
                    </button>
                  )}
                  {step === 2 && (
                    <div className="mt-2 flex items-center gap-1.5 text-xs" style={{ color: 'var(--text-tertiary)' }}>
                      <span className="font-mono rounded px-1.5 py-0.5" style={{ background: 'var(--bg-overlay)' }}>Manage</span>
                      <ChevronRight className="h-3 w-3" />
                      <span className="font-mono rounded px-1.5 py-0.5" style={{ background: 'var(--bg-overlay)' }}>Import Config</span>
                      <ChevronRight className="h-3 w-3" />
                      <span className="font-mono rounded px-1.5 py-0.5" style={{ background: 'var(--bg-overlay)' }}>Select file</span>
                    </div>
                  )}
                  {step === 3 && (
                    <div className="mt-2 flex items-center gap-1.5 text-xs" style={{ color: 'var(--text-tertiary)' }}>
                      <CheckCircle className="h-3.5 w-3.5 text-success-500" />
                      <span>Look for the "OSINT Platform" set in your Transform Hub</span>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </CardBody>
      </Card>

      {/* Available transforms table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              Available Transforms
            </h2>
            {transformsLoading && (
              <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>Loading…</span>
            )}
            {!transformsLoading && (
              <Badge variant="neutral">{transforms.length} transforms</Badge>
            )}
          </div>
        </CardHeader>
        <CardBody className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                  {['Entity Type', 'Transform', 'Scanner', 'Action'].map((h) => (
                    <th
                      key={h}
                      className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wide"
                      style={{ color: 'var(--text-tertiary)' }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {transforms.map((t: TransformConfig) => (
                  <tr
                    key={`${t.entity_type}-${t.transform_name}`}
                    className="transition-colors hover:bg-bg-overlay/50"
                    style={{ borderBottom: '1px solid var(--border-subtle)' }}
                  >
                    <td className="px-5 py-3">
                      <Badge variant={entityTypeBadgeVariant(t.entity_type)} size="sm">
                        {shortEntityType(t.entity_type)}
                      </Badge>
                    </td>
                    <td className="px-5 py-3 font-medium" style={{ color: 'var(--text-primary)' }}>
                      {t.display_name}
                    </td>
                    <td className="px-5 py-3">
                      <span
                        className="font-mono text-xs rounded px-1.5 py-0.5"
                        style={{ background: 'var(--bg-overlay)', color: 'var(--text-secondary)' }}
                      >
                        {t.scanner_type}
                      </span>
                    </td>
                    <td className="px-5 py-3">
                      <button
                        onClick={() => {
                          setSelectedEntityType(t.entity_type)
                          setSelectedTransform(t.transform_name)
                          window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' })
                        }}
                        className="inline-flex items-center gap-1 rounded px-2 py-1 text-xs font-medium transition-colors"
                        style={{
                          background: 'var(--bg-overlay)',
                          color: 'var(--text-secondary)',
                          border: '1px solid var(--border-subtle)',
                        }}
                      >
                        <Play className="h-3 w-3" />
                        Run Test
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardBody>
      </Card>

      {/* Test transform section */}
      <Card>
        <CardHeader>
          <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
            Test a Transform
          </h2>
        </CardHeader>
        <CardBody className="space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            {/* Entity type selector */}
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>
                Entity Type
              </label>
              <select
                value={selectedEntityType}
                onChange={(e) => {
                  setSelectedEntityType(e.target.value)
                  setSelectedTransform('')
                  setTestResult(null)
                }}
                className="rounded-md border px-3 py-2 text-sm"
                style={{
                  background: 'var(--bg-overlay)',
                  borderColor: 'var(--border-subtle)',
                  color: 'var(--text-primary)',
                }}
              >
                {ENTITY_TYPES.map((t) => (
                  <option key={t} value={t}>{shortEntityType(t)}</option>
                ))}
              </select>
            </div>

            {/* Entity value input */}
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>
                Entity Value
              </label>
              <input
                type="text"
                value={entityValue}
                onChange={(e) => setEntityValue(e.target.value)}
                placeholder={
                  selectedEntityType === 'maltego.Domain' ? 'example.com' :
                  selectedEntityType === 'maltego.IPv4Address' ? '8.8.8.8' :
                  selectedEntityType === 'maltego.EmailAddress' ? 'user@example.com' :
                  'Enter value…'
                }
                className="rounded-md border px-3 py-2 text-sm"
                style={{
                  background: 'var(--bg-overlay)',
                  borderColor: 'var(--border-subtle)',
                  color: 'var(--text-primary)',
                }}
              />
            </div>

            {/* Transform selector */}
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>
                Transform
              </label>
              <select
                value={selectedTransform}
                onChange={(e) => {
                  setSelectedTransform(e.target.value)
                  setTestResult(null)
                }}
                className="rounded-md border px-3 py-2 text-sm"
                style={{
                  background: 'var(--bg-overlay)',
                  borderColor: 'var(--border-subtle)',
                  color: 'var(--text-primary)',
                }}
              >
                <option value="">Select transform…</option>
                {availableTransforms.map((t) => (
                  <option key={t.transform_name} value={t.transform_name}>
                    {t.display_name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={handleRunTransform}
              disabled={!entityValue.trim() || !selectedTransform || runMutation.isPending}
              className="inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-colors disabled:opacity-50"
              style={{
                background: 'var(--brand-500, #6366f1)',
                color: '#fff',
              }}
            >
              <Play className="h-4 w-4" />
              {runMutation.isPending ? 'Running…' : 'Run Transform'}
            </button>
            {testResult && (
              <button
                onClick={() => setTestResult(null)}
                className="text-xs transition-colors hover:underline"
                style={{ color: 'var(--text-tertiary)' }}
              >
                Clear result
              </button>
            )}
          </div>

          {/* Result viewer */}
          {testResult && (
            <div className="animate-in fade-in slide-in-from-top-2 duration-300 space-y-3">
              {testResult.messages.length > 0 && (
                <div
                  className="rounded-md border px-4 py-3"
                  style={{
                    background: 'var(--bg-overlay)',
                    borderColor: 'var(--border-subtle)',
                  }}
                >
                  {testResult.messages.map((msg, i) => (
                    <p key={i} className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                      {msg}
                    </p>
                  ))}
                </div>
              )}
              {testResult.error && (
                <div
                  className="rounded-md border px-4 py-3"
                  style={{
                    background: 'var(--danger-900, #450a0a)',
                    borderColor: 'var(--danger-500, #ef4444)30',
                  }}
                >
                  <p className="text-sm text-danger-500">{testResult.error}</p>
                </div>
              )}
              <div
                className="rounded-md border"
                style={{ background: 'var(--bg-overlay)', borderColor: 'var(--border-subtle)' }}
              >
                <div
                  className="border-b px-4 py-2 text-xs font-semibold uppercase tracking-wide"
                  style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-tertiary)' }}
                >
                  JSON Result
                </div>
                <pre
                  className="overflow-x-auto p-4 text-xs"
                  style={{ color: 'var(--text-secondary)' }}
                >
                  {JSON.stringify(testResult, null, 2)}
                </pre>
              </div>
            </div>
          )}

          {runMutation.isError && (
            <div
              className="rounded-md border px-4 py-3"
              style={{
                background: 'var(--danger-900, #450a0a)',
                borderColor: 'var(--danger-500, #ef4444)30',
              }}
            >
              <p className="text-sm text-danger-500">
                {runMutation.error instanceof Error
                  ? runMutation.error.message
                  : 'Transform failed. Check the entity type and transform combination.'}
              </p>
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  )
}
