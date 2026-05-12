import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import {
  Users, Activity, Search, Shield, BarChart3,
  ShoppingBag, Wrench, GitBranch, Zap, Scale,
  Play, Trash2, Plus, Loader2,
  ChevronRight, History, RefreshCw, Network, Terminal, ArrowUpRight,
} from 'lucide-react'
import { Card, CardBody, CardHeader } from '@/shared/components/Card'
import { Badge } from '@/shared/components/Badge'
import { EmptyState } from '@/shared/components/EmptyState'
import { apiClient } from '@/shared/api/client'
import { useAuth } from '@/shared/hooks/useAuth'
import { toast } from '@/shared/components/Toast'
import { ScannerHealthPanel } from './components/ScannerHealthPanel'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface AdminStats {
  total_users: number
  total_investigations: number
  total_scans: number
  successful_scans: number
  failed_scans: number
  active_users: number
}

interface AdminUser {
  id: string
  email: string
  role: string
  subscription_tier: string
  is_active: boolean
  created_at: string
}

interface RoleInfo {
  role: string
  description: string
  permissions: Record<string, string[]>
}

interface CustomTool {
  id: string
  name: string
  docker_image: string
  description: string
  output_parser: string
  tags: string[]
  created_at: string
}

interface MarketplaceScenario {
  id: string
  name: string
  category: string
  difficulty: string
  description: string
  avg_duration_min: number
  steps_count: number
  mitre_tactics: string[]
}

interface ErasureRequest {
  id: string
  user_email: string
  requested_at: string
  status: string
  reason: string
}

interface WorkflowInfo {
  name: string
  webhook_url: string
  description: string
}

// ---------------------------------------------------------------------------
// Tab definitions
// ---------------------------------------------------------------------------

type Tab = 'overview' | 'investigations' | 'attack-runner' | 'rbac' | 'scenarios' | 'tools' | 'workflows' | 'gdpr'

const TABS: { id: Tab; label: string; icon: React.ElementType }[] = [
  { id: 'overview', label: 'Overview', icon: BarChart3 },
  { id: 'investigations', label: 'Investigations', icon: Search },
  { id: 'attack-runner', label: 'Attack Runner', icon: Terminal },
  { id: 'rbac', label: 'Roles & Users', icon: Shield },
  { id: 'scenarios', label: 'Attack Scenarios', icon: ShoppingBag },
  { id: 'tools', label: 'Custom Tools', icon: Wrench },
  { id: 'workflows', label: 'n8n Workflows', icon: GitBranch },
  { id: 'gdpr', label: 'GDPR', icon: Scale },
]

const DIFFICULTY_VARIANT: Record<string, 'neutral' | 'info' | 'warning' | 'danger'> = {
  easy: 'info', medium: 'warning', hard: 'danger', expert: 'danger',
}

// ---------------------------------------------------------------------------
// Investigations tab
// ---------------------------------------------------------------------------

interface InvestigationItem {
  id: string
  title: string
  status: string
  owner_id: string
  seed_inputs: { type: string; value: string }[]
  created_at: string
  updated_at: string
}

const STATUS_VARIANT: Record<string, 'neutral' | 'info' | 'success' | 'warning' | 'danger'> = {
  draft: 'neutral', running: 'info', completed: 'success', paused: 'warning', failed: 'danger',
}

function InvestigationsTab() {
  const navigate = useNavigate()
  const [statusFilter, setStatusFilter] = useState('all')
  const [search, setSearch] = useState('')

  const { data, isLoading, refetch } = useQuery<{ items: InvestigationItem[]; total: number }>({
    queryKey: ['admin', 'investigations', statusFilter],
    queryFn: async () => {
      const params = new URLSearchParams({ limit: '100' })
      if (statusFilter !== 'all') params.set('status', statusFilter)
      return (await apiClient.get(`/investigations/?${params}`)).data
    },
    refetchInterval: 10_000,
  })

  const items = (data?.items ?? []).filter((i) =>
    !search || i.title.toLowerCase().includes(search.toLowerCase()) ||
    i.seed_inputs?.some((s) => s.value.toLowerCase().includes(search.toLowerCase()))
  )

  const byStatus = (data?.items ?? []).reduce<Record<string, number>>((acc, i) => {
    acc[i.status] = (acc[i.status] ?? 0) + 1; return acc
  }, {})

  return (
    <div className="space-y-4">
      {/* Status summary chips */}
      <div className="flex flex-wrap gap-2">
        {['all', 'running', 'completed', 'draft', 'paused', 'failed'].map((s) => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className="rounded-full border px-3 py-1 text-xs font-medium transition-colors"
            style={{
              borderColor: statusFilter === s ? 'var(--brand-500)' : 'var(--border-subtle)',
              background: statusFilter === s ? 'var(--brand-900)' : 'var(--bg-surface)',
              color: statusFilter === s ? 'var(--brand-400)' : 'var(--text-secondary)',
            }}
          >
            {s === 'all' ? `All (${data?.total ?? 0})` : `${s} (${byStatus[s] ?? 0})`}
          </button>
        ))}
        <button onClick={() => refetch()} className="ml-auto hover:opacity-70" title="Refresh">
          <RefreshCw className="h-3.5 w-3.5" style={{ color: 'var(--text-tertiary)' }} />
        </button>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4" style={{ color: 'var(--text-tertiary)' }} />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search by title or seed value…"
          className="w-full rounded-lg border pl-9 pr-4 py-2 text-sm"
          style={{ background: 'var(--bg-surface)', borderColor: 'var(--border-subtle)', color: 'var(--text-primary)' }}
        />
      </div>

      {/* Table */}
      <Card>
        <CardBody className="p-0">
          {isLoading ? (
            <div className="flex justify-center py-12">
              <Loader2 className="h-5 w-5 animate-spin" style={{ color: 'var(--brand-500)' }} />
            </div>
          ) : items.length === 0 ? (
            <p className="px-5 py-8 text-center text-sm" style={{ color: 'var(--text-tertiary)' }}>No investigations found.</p>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b text-left text-xs font-medium"
                  style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-tertiary)' }}>
                  <th className="px-5 py-3">Title</th>
                  <th className="px-5 py-3">Status</th>
                  <th className="px-5 py-3">Seeds</th>
                  <th className="px-5 py-3">Updated</th>
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody>
                {items.map((inv) => (
                  <tr
                    key={inv.id}
                    className="border-b hover:bg-bg-overlay transition-colors cursor-pointer"
                    style={{ borderColor: 'var(--border-subtle)' }}
                    onClick={() => navigate(`/investigations/${inv.id}`)}
                  >
                    <td className="px-5 py-3">
                      <p className="text-sm font-medium truncate max-w-xs" style={{ color: 'var(--text-primary)' }}>{inv.title}</p>
                      <p className="text-[10px] font-mono mt-0.5" style={{ color: 'var(--text-tertiary)' }}>{inv.id.slice(0, 8)}</p>
                    </td>
                    <td className="px-5 py-3">
                      <Badge variant={STATUS_VARIANT[inv.status] ?? 'neutral'} size="sm" dot>{inv.status}</Badge>
                    </td>
                    <td className="px-5 py-3">
                      <div className="flex flex-wrap gap-1">
                        {(inv.seed_inputs ?? []).slice(0, 3).map((s, i) => (
                          <span key={i} className="text-[10px] rounded px-1.5 py-0.5 font-mono"
                            style={{ background: 'var(--bg-overlay)', color: 'var(--text-secondary)' }}>
                            {s.type}:{s.value.slice(0, 20)}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-5 py-3 text-xs" style={{ color: 'var(--text-tertiary)' }}>
                      {inv.updated_at ? new Date(inv.updated_at).toLocaleString() : '—'}
                    </td>
                    <td className="px-5 py-3">
                      <ArrowUpRight className="h-4 w-4" style={{ color: 'var(--brand-400)' }} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardBody>
      </Card>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Attack Runner tab
// ---------------------------------------------------------------------------

interface PortResult {
  port: number
  protocol: string
  service: string
  version: string
  state: string
  severity: string
  cve: string[]
}

interface AttackOption {
  id: string
  title: string
  tactic: string
  technique_id: string
  technique_name: string
  tools: string[]
  severity: string
  llm_risk_score: number
  steps: string[]
}

const SEV_COLOR: Record<string, string> = {
  critical: '#ef4444', high: '#f97316', medium: '#eab308', low: '#3b82f6', info: '#94a3b8',
}

function AttackRunnerTab() {
  const [target, setTarget] = useState('')
  const [scanId, setScanId] = useState<string | null>(null)
  const [ports, setPorts] = useState<PortResult[]>([])
  const [attacks, setAttacks] = useState<Record<string, AttackOption[]>>({})
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [runId, setRunId] = useState<string | null>(null)
  const [logs, setLogs] = useState<string[]>([])
  const [step, setStep] = useState<'target' | 'ports' | 'attacks' | 'executing'>('target')

  const scanMutation = useMutation({
    mutationFn: async () => {
      const r = await apiClient.post<{ scan_id: string; ports: PortResult[] }>('/attack-flow/scan', { target })
      return r.data
    },
    onSuccess: (data) => {
      setScanId(data.scan_id)
      setPorts(data.ports)
      setStep('ports')
    },
    onError: () => toast.error('Port scan failed'),
  })

  const attacksMutation = useMutation({
    mutationFn: async () => {
      const r = await apiClient.post<{ attacks_by_port: Record<string, AttackOption[]> }>(
        '/attack-flow/attacks', { target, ports }
      )
      return r.data
    },
    onSuccess: (data) => {
      setAttacks(data.attacks_by_port)
      setStep('attacks')
    },
    onError: () => toast.error('Failed to load attacks'),
  })

  const executeMutation = useMutation({
    mutationFn: async () => {
      const selectedAttacks = Object.values(attacks).flat().filter((a) => selected.has(a.id))
      const r = await apiClient.post<{ run_id: string }>('/attack-flow/execute', {
        target, scan_id: scanId, selected_attacks: selectedAttacks,
      })
      return r.data
    },
    onSuccess: (data) => {
      setRunId(data.run_id)
      setStep('executing')
      setLogs([`[${new Date().toISOString()}] Execution started — run_id: ${data.run_id}`])
    },
    onError: () => toast.error('Execution failed'),
  })

  // Poll logs while executing
  useQuery({
    queryKey: ['attack-logs', runId],
    queryFn: async () => {
      const r = await apiClient.get<{ logs: string[] }>(`/attack-flow/${runId}/logs`)
      setLogs(r.data.logs ?? [])
      return r.data
    },
    enabled: !!runId && step === 'executing',
    refetchInterval: 2_000,
  })

  const toggleAttack = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const selectAll = () => {
    const allIds = Object.values(attacks).flat().map((a) => a.id)
    setSelected(new Set(allIds))
  }

  return (
    <div className="space-y-6">
      {/* Step indicator */}
      <div className="flex items-center gap-2 text-xs">
        {(['target', 'ports', 'attacks', 'executing'] as const).map((s, i) => (
          <div key={s} className="flex items-center gap-2">
            {i > 0 && <div className="h-px w-6" style={{ background: 'var(--border-subtle)' }} />}
            <span
              className="rounded-full px-3 py-1 font-medium"
              style={{
                background: step === s ? 'var(--brand-900)' : 'var(--bg-surface)',
                color: step === s ? 'var(--brand-400)' : 'var(--text-tertiary)',
                border: `1px solid ${step === s ? 'var(--brand-700)' : 'var(--border-subtle)'}`,
              }}
            >
              {i + 1}. {s.charAt(0).toUpperCase() + s.slice(1)}
            </span>
          </div>
        ))}
      </div>

      {/* Step: Target */}
      {step === 'target' && (
        <Card>
          <CardBody className="space-y-4">
            <div className="flex items-center gap-3">
              <Network className="h-5 w-5" style={{ color: 'var(--brand-400)' }} />
              <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Enter Target</h3>
            </div>
            <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              Domain or IP address to scan for open ports and applicable attack vectors.
            </p>
            <input
              value={target}
              onChange={(e) => setTarget(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && target.trim() && scanMutation.mutate()}
              placeholder="example.com or 192.168.1.1"
              className="w-full rounded-lg border px-4 py-2.5 text-sm font-mono"
              style={{ background: 'var(--bg-overlay)', borderColor: 'var(--border-subtle)', color: 'var(--text-primary)' }}
            />
            <button
              onClick={() => scanMutation.mutate()}
              disabled={!target.trim() || scanMutation.isPending}
              className="flex items-center gap-2 rounded-lg px-5 py-2.5 text-sm font-semibold disabled:opacity-40"
              style={{ background: 'var(--brand-500)', color: '#fff' }}
            >
              {scanMutation.isPending
                ? <><Loader2 className="h-4 w-4 animate-spin" /> Scanning…</>
                : <><Network className="h-4 w-4" /> Scan Ports</>}
            </button>
          </CardBody>
        </Card>
      )}

      {/* Step: Ports */}
      {step === 'ports' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              Open Ports on <span style={{ color: 'var(--brand-400)' }}>{target}</span>
            </h3>
            <div className="flex gap-2">
              <button onClick={() => { setStep('target'); setPorts([]) }}
                className="text-xs px-3 py-1.5 rounded border"
                style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-secondary)' }}>
                ← Back
              </button>
              <button
                onClick={() => attacksMutation.mutate()}
                disabled={attacksMutation.isPending}
                className="flex items-center gap-2 rounded-lg px-4 py-1.5 text-xs font-semibold disabled:opacity-40"
                style={{ background: 'var(--brand-500)', color: '#fff' }}
              >
                {attacksMutation.isPending
                  ? <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading attacks…</>
                  : <><Zap className="h-3.5 w-3.5" /> Load Attacks</>}
              </button>
            </div>
          </div>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {ports.map((p) => (
              <div key={p.port} className="rounded-xl border p-3 space-y-1"
                style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-surface)', borderLeftColor: SEV_COLOR[p.severity] ?? 'var(--border-subtle)', borderLeftWidth: 3 }}>
                <div className="flex items-center justify-between">
                  <span className="font-mono text-sm font-bold" style={{ color: 'var(--text-primary)' }}>:{p.port}</span>
                  <Badge variant={p.severity === 'critical' ? 'danger' : p.severity === 'high' ? 'warning' : p.severity === 'medium' ? 'warning' : 'neutral'} size="sm">
                    {p.severity}
                  </Badge>
                </div>
                <p className="text-xs font-medium" style={{ color: 'var(--brand-400)' }}>{p.service}</p>
                {p.version && <p className="text-[10px] font-mono" style={{ color: 'var(--text-tertiary)' }}>{p.version}</p>}
                {p.cve.length > 0 && (
                  <p className="text-[10px]" style={{ color: '#ef4444' }}>{p.cve.slice(0, 2).join(', ')}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Step: Select Attacks */}
      {step === 'attacks' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              Select Attacks — <span style={{ color: 'var(--text-tertiary)' }}>{selected.size} selected</span>
            </h3>
            <div className="flex gap-2">
              <button onClick={() => setStep('ports')}
                className="text-xs px-3 py-1.5 rounded border"
                style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-secondary)' }}>
                ← Back
              </button>
              <button onClick={selectAll}
                className="text-xs px-3 py-1.5 rounded border"
                style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-secondary)' }}>
                Select All
              </button>
              <button
                onClick={() => executeMutation.mutate()}
                disabled={selected.size === 0 || executeMutation.isPending}
                className="flex items-center gap-2 rounded-lg px-4 py-1.5 text-xs font-semibold disabled:opacity-40"
                style={{ background: '#ef4444', color: '#fff' }}
              >
                {executeMutation.isPending
                  ? <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Launching…</>
                  : <><Play className="h-3.5 w-3.5" /> Execute ({selected.size})</>}
              </button>
            </div>
          </div>
          {Object.entries(attacks).map(([port, portAttacks]) => (
            <div key={port} className="space-y-2">
              <h4 className="text-xs font-semibold font-mono" style={{ color: 'var(--text-tertiary)' }}>Port {port}</h4>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {portAttacks.map((a) => (
                  <div
                    key={a.id}
                    onClick={() => toggleAttack(a.id)}
                    className="rounded-xl border p-3 cursor-pointer transition-all space-y-1.5"
                    style={{
                      borderColor: selected.has(a.id) ? 'var(--brand-500)' : 'var(--border-subtle)',
                      background: selected.has(a.id) ? 'var(--brand-900)' : 'var(--bg-surface)',
                    }}
                  >
                    <div className="flex items-start justify-between gap-1">
                      <p className="text-xs font-semibold leading-tight" style={{ color: 'var(--text-primary)' }}>{a.title}</p>
                      <Badge variant={a.severity === 'critical' ? 'danger' : a.severity === 'high' ? 'warning' : 'neutral'} size="sm">
                        {a.severity}
                      </Badge>
                    </div>
                    <p className="text-[10px] font-mono" style={{ color: 'var(--brand-400)' }}>{a.technique_id} · {a.tactic}</p>
                    <p className="text-[10px]" style={{ color: 'var(--text-secondary)' }}>
                      Risk: <strong>{a.llm_risk_score}/100</strong> · {a.tools.slice(0, 2).join(', ')}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Step: Executing */}
      {step === 'executing' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="h-2.5 w-2.5 rounded-full animate-pulse" style={{ background: '#ef4444' }} />
              <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                Executing against <span style={{ color: 'var(--brand-400)' }}>{target}</span>
              </h3>
            </div>
            <button
              onClick={() => { setStep('target'); setRunId(null); setLogs([]); setSelected(new Set()); setPorts([]); setAttacks({}) }}
              className="text-xs px-3 py-1.5 rounded border"
              style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-secondary)' }}
            >
              New Scan
            </button>
          </div>
          <div className="rounded-xl border p-4 font-mono text-xs space-y-1 max-h-96 overflow-auto"
            style={{ background: '#0a0a0a', borderColor: 'var(--border-subtle)', color: '#22c55e' }}>
            {logs.length === 0
              ? <span style={{ color: '#94a3b8' }}>Waiting for output…</span>
              : logs.map((line, i) => <div key={i}>{line}</div>)}
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Overview tab
// ---------------------------------------------------------------------------

function OverviewTab() {
  const { data: stats } = useQuery<AdminStats>({
    queryKey: ['admin', 'stats'],
    queryFn: async () => (await apiClient.get('/admin/stats')).data,
  })
  const { data: users = [] } = useQuery<AdminUser[]>({
    queryKey: ['admin', 'users'],
    queryFn: async () => (await apiClient.get('/admin/users')).data,
  })

  return (
    <div className="space-y-6">
      {stats && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[
            { label: 'Total Users', value: stats.total_users, icon: Users },
            { label: 'Total Investigations', value: stats.total_investigations, icon: Search },
            { label: 'Total Scans', value: stats.total_scans, icon: Activity },
            { label: 'Successful Scans', value: stats.successful_scans, icon: Shield },
            { label: 'Failed Scans', value: stats.failed_scans, icon: BarChart3 },
            { label: 'Active Users', value: stats.active_users, icon: Users },
          ].map((s) => (
            <Card key={s.label}>
              <CardBody className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg"
                  style={{ background: 'var(--brand-900)' }}>
                  <s.icon className="h-5 w-5" style={{ color: 'var(--brand-400)' }} />
                </div>
                <div>
                  <p className="text-2xl font-bold font-mono" style={{ color: 'var(--text-primary)' }}>
                    {s.value}
                  </p>
                  <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>{s.label}</p>
                </div>
              </CardBody>
            </Card>
          ))}
        </div>
      )}

      <ScannerHealthPanel />

      <Card>
        <CardHeader>
          <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Users</h2>
        </CardHeader>
        <CardBody className="p-0">
          <table className="w-full">
            <thead>
              <tr className="border-b text-left text-xs font-medium"
                style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-tertiary)' }}>
                <th className="px-5 py-3">Email</th>
                <th className="px-5 py-3">Role</th>
                <th className="px-5 py-3">Tier</th>
                <th className="px-5 py-3">Status</th>
                <th className="px-5 py-3">Joined</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-b" style={{ borderColor: 'var(--border-subtle)' }}>
                  <td className="px-5 py-3 text-sm font-mono" style={{ color: 'var(--text-primary)' }}>{u.email}</td>
                  <td className="px-5 py-3">
                    <Badge variant={u.role === 'admin' ? 'danger' : 'neutral'} size="sm">{u.role}</Badge>
                  </td>
                  <td className="px-5 py-3">
                    <Badge variant={u.subscription_tier === 'enterprise' ? 'warning' : u.subscription_tier === 'pro' ? 'brand' : 'neutral'} size="sm">
                      {u.subscription_tier}
                    </Badge>
                  </td>
                  <td className="px-5 py-3">
                    <Badge variant={u.is_active ? 'success' : 'danger'} size="sm" dot>
                      {u.is_active ? 'Active' : 'Inactive'}
                    </Badge>
                  </td>
                  <td className="px-5 py-3 text-xs" style={{ color: 'var(--text-tertiary)' }}>
                    {new Date(u.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardBody>
      </Card>
    </div>
  )
}

// ---------------------------------------------------------------------------
// RBAC tab
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// RBAC Audit Log component (#22)
// ---------------------------------------------------------------------------

interface RbacAuditEntry {
  timestamp: string
  action: string
  target_email: string
  old_role: string
  new_role: string
  by_email: string
}

function RbacAuditLog() {
  const { data: log = [], isLoading, refetch } = useQuery<RbacAuditEntry[]>({
    queryKey: ['rbac', 'audit-log'],
    queryFn: async () => (await apiClient.get('/rbac/audit-log')).data,
    refetchInterval: 30_000,
  })

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <History className="h-4 w-4" style={{ color: 'var(--text-tertiary)' }} />
            <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Role Change Audit Log</h3>
          </div>
          <button onClick={() => refetch()} className="hover:opacity-70" title="Refresh">
            <RefreshCw className="h-3.5 w-3.5" style={{ color: 'var(--text-tertiary)' }} />
          </button>
        </div>
      </CardHeader>
      <CardBody className="p-0">
        {isLoading ? (
          <div className="flex justify-center py-6"><Loader2 className="h-5 w-5 animate-spin" style={{ color: 'var(--brand-400)' }} /></div>
        ) : log.length === 0 ? (
          <p className="text-xs px-5 py-4" style={{ color: 'var(--text-tertiary)' }}>No role changes recorded yet.</p>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b text-left text-[11px] font-medium"
                style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-tertiary)' }}>
                <th className="px-5 py-2">Time</th>
                <th className="px-5 py-2">Target</th>
                <th className="px-5 py-2">Change</th>
                <th className="px-5 py-2">By</th>
              </tr>
            </thead>
            <tbody>
              {[...log].reverse().map((e, i) => (
                <tr key={i} className="border-b text-xs" style={{ borderColor: 'var(--border-subtle)' }}>
                  <td className="px-5 py-2 font-mono text-[10px]" style={{ color: 'var(--text-tertiary)' }}>
                    {new Date(e.timestamp).toLocaleString()}
                  </td>
                  <td className="px-5 py-2" style={{ color: 'var(--text-primary)' }}>{e.target_email}</td>
                  <td className="px-5 py-2">
                    <span className="font-mono text-[10px]" style={{ color: '#ef4444' }}>{e.old_role}</span>
                    {' → '}
                    <span className="font-mono text-[10px]" style={{ color: '#22c55e' }}>{e.new_role}</span>
                  </td>
                  <td className="px-5 py-2" style={{ color: 'var(--text-secondary)' }}>{e.by_email}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </CardBody>
    </Card>
  )
}

function RbacTab() {
  const qc = useQueryClient()
  const [editingUser, setEditingUser] = useState<string | null>(null)
  const [newRole, setNewRole] = useState('')

  const { data: roles = [] } = useQuery<RoleInfo[]>({
    queryKey: ['rbac', 'roles'],
    queryFn: async () => (await apiClient.get('/rbac/roles')).data,
  })
  const { data: users = [] } = useQuery<AdminUser[]>({
    queryKey: ['rbac', 'users'],
    queryFn: async () => (await apiClient.get('/rbac/users')).data,
  })

  const assignRole = useMutation({
    mutationFn: async ({ userId, role }: { userId: string; role: string }) => {
      await apiClient.put(`/rbac/users/${userId}/role`, { role })
    },
    onSuccess: () => {
      toast.success('Role updated')
      setEditingUser(null)
      qc.invalidateQueries({ queryKey: ['rbac', 'users'] })
    },
    onError: () => toast.error('Failed to update role'),
  })

  return (
    <div className="space-y-6">
      {/* Roles matrix */}
      <div>
        <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>
          Role Permissions Matrix
        </h3>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {roles.map((r) => (
            <div key={r.role} className="rounded-xl border p-4"
              style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-surface)' }}>
              <div className="flex items-center gap-2 mb-2">
                <Badge variant={r.role === 'admin' ? 'danger' : r.role === 'operator' ? 'warning' : r.role === 'auditor' ? 'info' : 'neutral'} size="sm">
                  {r.role}
                </Badge>
              </div>
              <p className="text-xs mb-3" style={{ color: 'var(--text-secondary)' }}>{r.description}</p>
              <div className="space-y-1">
                {Object.entries(r.permissions).map(([res, perms]) => (
                  <div key={res} className="flex items-center justify-between text-[10px]">
                    <span style={{ color: 'var(--text-tertiary)' }}>{res}</span>
                    <span className="font-mono" style={{ color: 'var(--brand-400)' }}>
                      {(perms as string[]).join(' ')}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Users with role assignment */}
      <Card>
        <CardHeader>
          <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>User Role Assignment</h3>
        </CardHeader>
        <CardBody className="p-0">
          <table className="w-full">
            <thead>
              <tr className="border-b text-left text-xs font-medium"
                style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-tertiary)' }}>
                <th className="px-5 py-3">Email</th>
                <th className="px-5 py-3">Current Role</th>
                <th className="px-5 py-3">Tier</th>
                <th className="px-5 py-3">Action</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-b" style={{ borderColor: 'var(--border-subtle)' }}>
                  <td className="px-5 py-3 text-sm font-mono" style={{ color: 'var(--text-primary)' }}>{u.email}</td>
                  <td className="px-5 py-3">
                    <Badge variant={u.role === 'admin' ? 'danger' : 'neutral'} size="sm">{u.role}</Badge>
                  </td>
                  <td className="px-5 py-3 text-xs" style={{ color: 'var(--text-secondary)' }}>{u.subscription_tier}</td>
                  <td className="px-5 py-3">
                    {editingUser === u.id ? (
                      <div className="flex items-center gap-2">
                        <select
                          value={newRole}
                          onChange={(e) => setNewRole(e.target.value)}
                          className="rounded border px-2 py-1 text-xs"
                          style={{ background: 'var(--bg-overlay)', borderColor: 'var(--border-subtle)', color: 'var(--text-primary)' }}
                        >
                          <option value="">Select role…</option>
                          {['admin', 'operator', 'auditor', 'viewer'].map((r) => (
                            <option key={r} value={r}>{r}</option>
                          ))}
                        </select>
                        <button
                          onClick={() => newRole && assignRole.mutate({ userId: u.id, role: newRole })}
                          disabled={!newRole || assignRole.isPending}
                          className="text-xs px-2 py-1 rounded"
                          style={{ background: 'var(--brand-500)', color: '#fff' }}
                        >
                          Save
                        </button>
                        <button onClick={() => setEditingUser(null)} className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => { setEditingUser(u.id); setNewRole(u.role) }}
                        className="text-xs hover:opacity-70"
                        style={{ color: 'var(--brand-400)' }}
                      >
                        Change Role
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardBody>
      </Card>
      {/* RBAC Audit Trail (#22) */}
      <RbacAuditLog />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Attack Scenarios tab (Marketplace + builder access)
// ---------------------------------------------------------------------------

function ScenariosTab() {
  const navigate = useNavigate()

  const { data: scenarios = [], isLoading } = useQuery<MarketplaceScenario[]>({
    queryKey: ['marketplace-scenarios', 'all', 'all'],
    queryFn: async () => (await apiClient.get('/marketplace/scenarios')).data,
  })

  const categoryCount = scenarios.reduce<Record<string, number>>((acc, s) => {
    acc[s.category] = (acc[s.category] ?? 0) + 1
    return acc
  }, {})

  return (
    <div className="space-y-6">
      {/* Summary */}
      <div className="flex items-center gap-4 flex-wrap">
        <div className="rounded-xl border px-5 py-3 flex items-center gap-3"
          style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-surface)' }}>
          <ShoppingBag className="h-5 w-5" style={{ color: 'var(--brand-400)' }} />
          <div>
            <p className="text-xl font-bold font-mono" style={{ color: 'var(--text-primary)' }}>{scenarios.length}</p>
            <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>Total scenarios</p>
          </div>
        </div>
        {Object.entries(categoryCount).map(([cat, count]) => (
          <div key={cat} className="rounded-xl border px-4 py-3 text-center"
            style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-surface)' }}>
            <p className="text-lg font-bold font-mono" style={{ color: 'var(--text-primary)' }}>{count}</p>
            <p className="text-[10px] capitalize" style={{ color: 'var(--text-tertiary)' }}>{cat}</p>
          </div>
        ))}
      </div>

      {/* Quick access to full marketplace */}
      <div className="flex gap-3">
        <button
          onClick={() => navigate('/pentest/marketplace')}
          className="flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold"
          style={{ background: 'var(--brand-500)', color: '#fff' }}
        >
          <ShoppingBag className="h-4 w-4" /> Open Marketplace
        </button>
        <button
          onClick={() => navigate('/pentest/attack-planner')}
          className="flex items-center gap-2 rounded-lg border px-4 py-2.5 text-sm font-medium"
          style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-secondary)', background: 'var(--bg-overlay)' }}
        >
          <Zap className="h-4 w-4" /> Attack Planner
        </button>
      </div>

      {/* Scenario grid */}
      {isLoading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin" style={{ color: 'var(--brand-500)' }} />
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {scenarios.map((s) => (
            <div key={s.id} className="rounded-xl border p-4 flex flex-col gap-2 hover:border-brand-500 transition-colors"
              style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-surface)' }}>
              <div className="flex items-start justify-between gap-2">
                <p className="text-sm font-semibold truncate" style={{ color: 'var(--text-primary)' }}>{s.name}</p>
                <Badge variant={DIFFICULTY_VARIANT[s.difficulty] ?? 'neutral'} size="sm">{s.difficulty}</Badge>
              </div>
              <p className="text-xs line-clamp-2" style={{ color: 'var(--text-secondary)' }}>{s.description}</p>
              <div className="flex items-center justify-between text-[10px] mt-1" style={{ color: 'var(--text-tertiary)' }}>
                <span>{s.steps_count} steps · ~{s.avg_duration_min}m</span>
                <span className="capitalize px-1.5 py-0.5 rounded"
                  style={{ background: 'var(--bg-overlay)' }}>{s.category}</span>
              </div>
              <button
                onClick={() => navigate('/pentest/marketplace')}
                className="flex items-center justify-center gap-1 rounded-lg py-1.5 text-xs font-medium mt-1"
                style={{ background: 'var(--bg-overlay)', color: 'var(--text-secondary)', border: '1px solid var(--border-subtle)' }}
              >
                Clone to Scan <ChevronRight className="h-3 w-3" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Custom Tools tab
// ---------------------------------------------------------------------------

function ToolsTab() {
  const qc = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ name: '', docker_image: '', description: '', output_parser: 'text' })

  const { data: tools = [], isLoading } = useQuery<CustomTool[]>({
    queryKey: ['custom-tools'],
    queryFn: async () => (await apiClient.get('/tools/custom')).data,
  })

  const create = useMutation({
    mutationFn: async () => apiClient.post('/tools/custom', form),
    onSuccess: () => {
      toast.success('Tool registered')
      setShowForm(false)
      setForm({ name: '', docker_image: '', description: '', output_parser: 'text' })
      qc.invalidateQueries({ queryKey: ['custom-tools'] })
    },
    onError: () => toast.error('Failed to register tool'),
  })

  const remove = useMutation({
    mutationFn: async (id: string) => apiClient.delete(`/tools/custom/${id}`),
    onSuccess: () => {
      toast.success('Tool removed')
      qc.invalidateQueries({ queryKey: ['custom-tools'] })
    },
  })

  const testTool = useMutation({
    mutationFn: async (id: string) => {
      const r = await apiClient.post(`/tools/custom/${id}/test`)
      return r.data
    },
    onSuccess: (data) => toast.success(`Exit code: ${data.exit_code} · ${data.duration_ms}ms`),
    onError: () => toast.error('Test run failed'),
  })

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
          Register custom Docker-based tools for use in scan profiles and scenarios.
        </p>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold"
          style={{ background: 'var(--brand-500)', color: '#fff' }}
        >
          <Plus className="h-4 w-4" /> Add Tool
        </button>
      </div>

      {showForm && (
        <div className="rounded-xl border p-5 space-y-3"
          style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-surface)' }}>
          <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Register Custom Tool</h3>
          {[
            { key: 'name', label: 'Tool Name', placeholder: 'my-scanner' },
            { key: 'docker_image', label: 'Docker Image', placeholder: 'ghcr.io/myorg/my-scanner:latest' },
            { key: 'description', label: 'Description', placeholder: 'What this tool does' },
          ].map(({ key, label, placeholder }) => (
            <div key={key}>
              <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-tertiary)' }}>{label}</label>
              <input
                value={form[key as keyof typeof form]}
                onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
                placeholder={placeholder}
                className="w-full rounded border px-3 py-2 text-sm"
                style={{ background: 'var(--bg-overlay)', borderColor: 'var(--border-subtle)', color: 'var(--text-primary)' }}
              />
            </div>
          ))}
          <div>
            <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-tertiary)' }}>Output Parser</label>
            <select
              value={form.output_parser}
              onChange={(e) => setForm((f) => ({ ...f, output_parser: e.target.value }))}
              className="rounded border px-2 py-1.5 text-sm"
              style={{ background: 'var(--bg-overlay)', borderColor: 'var(--border-subtle)', color: 'var(--text-primary)' }}
            >
              {['text', 'json', 'sarif'].map((o) => <option key={o}>{o}</option>)}
            </select>
          </div>
          <div className="flex gap-2 pt-2">
            <button
              onClick={() => create.mutate()}
              disabled={!form.name || !form.docker_image || create.isPending}
              className="rounded-lg px-4 py-2 text-sm font-semibold disabled:opacity-40"
              style={{ background: 'var(--brand-500)', color: '#fff' }}
            >
              {create.isPending ? 'Registering…' : 'Register'}
            </button>
            <button onClick={() => setShowForm(false)} className="text-sm" style={{ color: 'var(--text-tertiary)' }}>Cancel</button>
          </div>
        </div>
      )}

      {isLoading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin" style={{ color: 'var(--brand-500)' }} />
        </div>
      ) : tools.length === 0 ? (
        <div className="py-16 text-center" style={{ color: 'var(--text-tertiary)' }}>
          <Wrench className="h-10 w-10 mx-auto mb-3 opacity-30" />
          <p className="text-sm">No custom tools registered yet.</p>
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {tools.map((t) => (
            <div key={t.id} className="rounded-xl border p-4"
              style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-surface)' }}>
              <div className="flex items-start justify-between gap-2 mb-2">
                <div>
                  <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>{t.name}</p>
                  <p className="font-mono text-[10px] mt-0.5" style={{ color: 'var(--text-tertiary)' }}>{t.docker_image}</p>
                </div>
                <Badge variant="neutral" size="sm">{t.output_parser}</Badge>
              </div>
              {t.description && (
                <p className="text-xs mb-3" style={{ color: 'var(--text-secondary)' }}>{t.description}</p>
              )}
              <div className="flex gap-2">
                <button
                  onClick={() => testTool.mutate(t.id)}
                  disabled={testTool.isPending}
                  className="flex items-center gap-1 rounded px-2.5 py-1.5 text-xs"
                  style={{ background: 'var(--bg-overlay)', color: 'var(--text-secondary)', border: '1px solid var(--border-subtle)' }}
                >
                  <Play className="h-3 w-3" /> Test
                </button>
                <button
                  onClick={() => remove.mutate(t.id)}
                  className="flex items-center gap-1 rounded px-2.5 py-1.5 text-xs"
                  style={{ background: 'var(--danger-900)', color: 'var(--danger-400)' }}
                >
                  <Trash2 className="h-3 w-3" /> Remove
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Workflows tab (n8n)
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Live n8n execution log (#21)
// ---------------------------------------------------------------------------

interface N8nExecution {
  execution_id: string
  status: string
  error?: string
  n8n_execution_id?: string
}

function N8nExecutionLog() {
  const { data: executions = [], isLoading, refetch } = useQuery<N8nExecution[]>({
    queryKey: ['n8n-executions'],
    queryFn: async () => (await apiClient.get('/workflows/n8n/executions')).data,
    refetchInterval: 5_000,
  })

  const statusColor = (s: string) => {
    if (s === 'success') return '#22c55e'
    if (s === 'error') return '#ef4444'
    if (s === 'running') return '#eab308'
    return 'var(--text-tertiary)'
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4" style={{ color: 'var(--text-tertiary)' }} />
            <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Live Execution Log</h3>
            <span className="text-[10px] rounded-full px-2 py-0.5"
              style={{ background: 'var(--bg-overlay)', color: 'var(--text-tertiary)' }}>
              auto-refreshes every 5s
            </span>
          </div>
          <button onClick={() => refetch()} className="hover:opacity-70">
            <RefreshCw className="h-3.5 w-3.5" style={{ color: 'var(--text-tertiary)' }} />
          </button>
        </div>
      </CardHeader>
      <CardBody className="p-0">
        {isLoading ? (
          <div className="flex justify-center py-4"><Loader2 className="h-5 w-5 animate-spin" style={{ color: 'var(--brand-400)' }} /></div>
        ) : executions.length === 0 ? (
          <p className="text-xs px-5 py-4" style={{ color: 'var(--text-tertiary)' }}>No executions yet.</p>
        ) : (
          <div className="divide-y" style={{ borderColor: 'var(--border-subtle)' }}>
            {[...executions].reverse().slice(0, 20).map((e) => (
              <div key={e.execution_id} className="flex items-center gap-3 px-5 py-2.5">
                <span className="h-2 w-2 rounded-full shrink-0" style={{ background: statusColor(e.status) }} />
                <span className="font-mono text-[10px] flex-1 truncate" style={{ color: 'var(--text-primary)' }}>
                  {e.execution_id}
                </span>
                <span className="text-[10px] font-medium" style={{ color: statusColor(e.status) }}>{e.status}</span>
                {e.error && (
                  <span className="text-[10px] truncate max-w-[200px]" style={{ color: '#ef4444' }}>{e.error}</span>
                )}
              </div>
            ))}
          </div>
        )}
      </CardBody>
    </Card>
  )
}

function WorkflowsTab() {
  const [triggering, setTriggering] = useState<string | null>(null)
  const [payload, setPayload] = useState('{}')

  const { data: workflows = [] } = useQuery<WorkflowInfo[]>({
    queryKey: ['n8n-workflows'],
    queryFn: async () => (await apiClient.get('/workflows/n8n')).data,
  })

  const trigger = useMutation({
    mutationFn: async ({ name }: { name: string }) => {
      let parsed: unknown = {}
      try { parsed = JSON.parse(payload) } catch { /* ignore */ }
      const r = await apiClient.post('/workflows/n8n/trigger', { workflow_name: name, payload: parsed })
      return r.data
    },
    onSuccess: (data) => {
      toast.success(`Workflow triggered · exec: ${data.execution_id.slice(0, 8)}`)
      setTriggering(null)
    },
    onError: () => toast.error('Trigger failed'),
  })

  return (
    <div className="space-y-4">
      <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
        Trigger n8n automation workflows. Set <code className="font-mono text-xs px-1 py-0.5 rounded"
          style={{ background: 'var(--bg-overlay)' }}>N8N_BASE_URL</code> env var to enable.
      </p>

      <div className="space-y-3">
        {workflows.map((w) => (
          <div key={w.name} className="rounded-xl border p-4"
            style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-surface)' }}>
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <p className="text-sm font-semibold font-mono" style={{ color: 'var(--text-primary)' }}>{w.name}</p>
                <p className="text-xs mt-0.5" style={{ color: 'var(--text-secondary)' }}>{w.description}</p>
                <p className="font-mono text-[10px] mt-1 truncate" style={{ color: 'var(--text-tertiary)' }}>{w.webhook_url}</p>
              </div>
              <button
                onClick={() => setTriggering(triggering === w.name ? null : w.name)}
                className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium shrink-0"
                style={{ background: 'var(--brand-900)', color: 'var(--brand-400)', border: '1px solid var(--brand-800)' }}
              >
                <Play className="h-3.5 w-3.5" /> Trigger
              </button>
            </div>

            {triggering === w.name && (
              <div className="mt-3 space-y-2">
                <label className="block text-xs font-medium" style={{ color: 'var(--text-tertiary)' }}>Payload (JSON)</label>
                <textarea
                  rows={3}
                  value={payload}
                  onChange={(e) => setPayload(e.target.value)}
                  className="w-full rounded border px-3 py-2 font-mono text-xs resize-none"
                  style={{ background: 'var(--bg-overlay)', borderColor: 'var(--border-subtle)', color: 'var(--text-primary)' }}
                />
                <div className="flex gap-2">
                  <button
                    onClick={() => trigger.mutate({ name: w.name })}
                    disabled={trigger.isPending}
                    className="rounded-lg px-3 py-1.5 text-xs font-semibold disabled:opacity-40"
                    style={{ background: 'var(--brand-500)', color: '#fff' }}
                  >
                    {trigger.isPending ? 'Sending…' : 'Send'}
                  </button>
                  <button onClick={() => setTriggering(null)} className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
      {/* Live execution log (#21) */}
      <N8nExecutionLog />
    </div>
  )
}

// ---------------------------------------------------------------------------
// GDPR tab
// ---------------------------------------------------------------------------

function GdprTab() {
  const qc = useQueryClient()

  const { data: requests = [], isLoading } = useQuery<ErasureRequest[]>({
    queryKey: ['gdpr', 'erasure-requests'],
    queryFn: async () => (await apiClient.get('/gdpr/erasure-requests')).data,
  })

  const { data: policy = [] } = useQuery({
    queryKey: ['gdpr', 'retention'],
    queryFn: async () => (await apiClient.get('/gdpr/retention-policy')).data,
  })

  const execute = useMutation({
    mutationFn: async (id: string) => apiClient.post(`/gdpr/erasure-requests/${id}/execute`),
    onSuccess: () => {
      toast.success('Erasure executed — user data deleted')
      qc.invalidateQueries({ queryKey: ['gdpr', 'erasure-requests'] })
    },
    onError: () => toast.error('Erasure failed'),
  })

  return (
    <div className="space-y-6">
      {/* Retention policy */}
      <div>
        <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>Data Retention Policy</h3>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {(policy as Array<{ data_type: string; days: number; description: string; purge_after_date: string }>).map((p) => (
            <div key={p.data_type} className="rounded-lg border p-3"
              style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-surface)' }}>
              <p className="text-xs font-semibold font-mono mb-0.5" style={{ color: 'var(--text-primary)' }}>{p.data_type}</p>
              <p className="text-[10px] mb-1" style={{ color: 'var(--text-secondary)' }}>{p.description}</p>
              <p className="text-[10px]" style={{ color: 'var(--text-tertiary)' }}>
                Retention: <strong>{p.days}d</strong>
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Erasure requests */}
      <div>
        <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>
          Erasure Requests (Art. 17 GDPR)
        </h3>
        {isLoading ? (
          <div className="flex justify-center py-8">
            <Loader2 className="h-5 w-5 animate-spin" style={{ color: 'var(--brand-500)' }} />
          </div>
        ) : requests.length === 0 ? (
          <div className="py-12 text-center" style={{ color: 'var(--text-tertiary)' }}>
            <Scale className="h-8 w-8 mx-auto mb-2 opacity-30" />
            <p className="text-sm">No erasure requests pending.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {requests.map((r) => (
              <div key={r.id} className="rounded-xl border p-4 flex items-center gap-4"
                style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-surface)' }}>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{r.user_email}</p>
                  <p className="text-xs truncate" style={{ color: 'var(--text-secondary)' }}>{r.reason}</p>
                  <p className="text-[10px] mt-0.5" style={{ color: 'var(--text-tertiary)' }}>
                    {new Date(r.requested_at).toLocaleString()}
                  </p>
                </div>
                <Badge
                  variant={r.status === 'completed' ? 'success' : r.status === 'pending' ? 'warning' : 'neutral'}
                  size="sm"
                >
                  {r.status}
                </Badge>
                {r.status === 'pending' && (
                  <button
                    onClick={() => execute.mutate(r.id)}
                    disabled={execute.isPending}
                    className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold"
                    style={{ background: 'var(--danger-900)', color: 'var(--danger-400)' }}
                  >
                    <Trash2 className="h-3.5 w-3.5" /> Execute Erasure
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main AdminPage
// ---------------------------------------------------------------------------

export function AdminPage() {
  const { isAdmin } = useAuth()
  const [activeTab, setActiveTab] = useState<Tab>('overview')

  if (!isAdmin) {
    return (
      <EmptyState
        variant="error"
        title="Access Denied"
        description="You need admin privileges to view this page."
      />
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>Admin Panel</h1>
        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
          Platform management — users, roles, scenarios, tools, workflows, and compliance
        </p>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 border-b" style={{ borderColor: 'var(--border-subtle)' }}>
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className="flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors"
            style={{
              borderColor: activeTab === tab.id ? 'var(--brand-500)' : 'transparent',
              color: activeTab === tab.id ? 'var(--brand-400)' : 'var(--text-secondary)',
            }}
          >
            <tab.icon className="h-4 w-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === 'overview' && <OverviewTab />}
      {activeTab === 'investigations' && <InvestigationsTab />}
      {activeTab === 'attack-runner' && <AttackRunnerTab />}
      {activeTab === 'rbac' && <RbacTab />}
      {activeTab === 'scenarios' && <ScenariosTab />}
      {activeTab === 'tools' && <ToolsTab />}
      {activeTab === 'workflows' && <WorkflowsTab />}
      {activeTab === 'gdpr' && <GdprTab />}
    </div>
  )
}
