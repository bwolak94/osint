import { useState, useCallback, useMemo, type ElementType } from 'react'
import {
  Key,
  Cloud,
  Archive,
  GitBranch,
  FileCode,
  Package,
  Globe,
  Settings,
  Server,
  ArrowLeftRight,
  Ticket,
  GitGraph,
  AlertOctagon,
  MessageSquare,
  Box,
  Shield,
  EyeOff,
  HardDrive,
  Radio,
  ShieldCheck,
  FileKey,
  Layers,
  Clock,
  Smartphone,
  AlertCircle,
  Map,
  Radar,
  FolderArchive,
  FileText,
  ShieldAlert,
} from 'lucide-react'
import { Card, CardBody } from '@/shared/components/Card'
import { Badge } from '@/shared/components/Badge'
import type { RedTeamModule, RedTeamCategory, RiskLevel } from './types'
import { JWTAuditorPanel } from './components/JWTAuditorPanel'
import { CloudStorageHunterPanel } from './components/CloudStorageHunterPanel'
import { MitreMapperPanel } from './components/MitreMapperPanel'
import { OSCPReportPanel } from './components/OSCPReportPanel'

// ─── Module registry ──────────────────────────────────────────────────────────

interface ModuleDefinition extends RedTeamModule {
  icon: ElementType
}

const MODULES: ModuleDefinition[] = [
  { id: 101, name: 'JWT Security Auditor', description: 'Decode and audit JWTs for algorithm confusion, none-alg, and misconfigured claims.', category: 'CLOUD', mitreAttackIds: ['T1552', 'T1606'], riskLevel: 'Medium', requiresAuth: false, icon: Key },
  { id: 102, name: 'AWS IAM Auditor', description: 'Enumerate and assess AWS IAM policies for over-permissive roles and misconfigurations.', category: 'CLOUD', mitreAttackIds: ['T1078', 'T1580'], riskLevel: 'High', requiresAuth: true, icon: Cloud },
  { id: 103, name: 'Azure / S3 Hunter', description: 'Discover misconfigured public cloud storage buckets across AWS, Azure, and GCP.', category: 'CLOUD', mitreAttackIds: ['T1530'], riskLevel: 'High', requiresAuth: true, icon: Archive },
  { id: 104, name: 'CI/CD Secret Scanner', description: 'Scan CI/CD pipelines and repositories for hardcoded secrets and tokens.', category: 'CLOUD', mitreAttackIds: ['T1552', 'T1213'], riskLevel: 'High', requiresAuth: true, icon: GitBranch },
  { id: 105, name: 'IaC Policy Linter', description: 'Lint Terraform, CloudFormation, and Kubernetes manifests for security policy violations.', category: 'CLOUD', mitreAttackIds: ['T1562', 'T1078'], riskLevel: 'Medium', requiresAuth: false, icon: FileCode },
  { id: 106, name: 'Supply Chain Simulator', description: 'Simulate dependency confusion and typosquatting attacks against package ecosystems.', category: 'NETWORK', mitreAttackIds: ['T1195', 'T1554'], riskLevel: 'Critical', requiresAuth: true, icon: Package },
  { id: 107, name: 'API Security Scanner', description: 'Enumerate REST and GraphQL endpoints for auth bypass, injection, and excessive data exposure.', category: 'NETWORK', mitreAttackIds: ['T1190', 'T1059'], riskLevel: 'High', requiresAuth: true, icon: Globe },
  { id: 108, name: 'Registry Persistence Lab', description: 'Test and demonstrate Windows registry-based persistence mechanisms.', category: 'ACTIVE_DIRECTORY', mitreAttackIds: ['T1547', 'T1112'], riskLevel: 'Critical', requiresAuth: true, icon: Settings },
  { id: 109, name: 'WMI Persistence Engine', description: 'Evaluate WMI subscriptions as a persistence and lateral movement vector.', category: 'ACTIVE_DIRECTORY', mitreAttackIds: ['T1546', 'T1021'], riskLevel: 'Critical', requiresAuth: true, icon: Server },
  { id: 110, name: 'NTLM Relay Automator', description: 'Identify and demonstrate NTLM relay attack paths across network segments.', category: 'ACTIVE_DIRECTORY', mitreAttackIds: ['T1557', 'T1187'], riskLevel: 'Critical', requiresAuth: true, icon: ArrowLeftRight },
  { id: 111, name: 'Kerberoasting Toolkit', description: 'Identify service accounts with weak Kerberos encryption and extract crackable tickets.', category: 'ACTIVE_DIRECTORY', mitreAttackIds: ['T1558'], riskLevel: 'High', requiresAuth: true, icon: Ticket },
  { id: 112, name: 'BloodHound Viz Bridge', description: 'Import BloodHound data and visualize attack paths to Domain Admin.', category: 'ACTIVE_DIRECTORY', mitreAttackIds: ['T1069', 'T1482'], riskLevel: 'High', requiresAuth: true, icon: GitGraph },
  { id: 113, name: 'AD Coercion Simulator', description: 'Test for PrinterBug, PetitPotam, and other coercion vulnerabilities in Active Directory.', category: 'ACTIVE_DIRECTORY', mitreAttackIds: ['T1187', 'T1557'], riskLevel: 'High', requiresAuth: true, icon: AlertOctagon },
  { id: 114, name: 'AI Prompt Injector', description: 'Test AI-powered applications for prompt injection and data exfiltration via LLM abuse.', category: 'NETWORK', mitreAttackIds: ['T1059', 'T1190'], riskLevel: 'Medium', requiresAuth: true, icon: MessageSquare },
  { id: 115, name: 'Container Escape Auditor', description: 'Audit container configurations for escape vectors including privileged mode and host mounts.', category: 'CLOUD', mitreAttackIds: ['T1611', 'T1552'], riskLevel: 'High', requiresAuth: true, icon: Box },
  { id: 116, name: 'Zero Trust Policy Viz', description: 'Visualize and gap-analyse Zero Trust policy implementations across cloud environments.', category: 'CLOUD', mitreAttackIds: ['T1078', 'T1562'], riskLevel: 'Medium', requiresAuth: false, icon: Shield },
  { id: 117, name: 'Payload Evasion Engine', description: 'Generate and test payloads against common EDR/AV signature and heuristic engines.', category: 'EVASION', mitreAttackIds: ['T1027', 'T1055', 'T1562'], riskLevel: 'High', requiresAuth: true, icon: EyeOff },
  { id: 118, name: 'Memory Forensics Tool', description: 'Perform live memory analysis to detect injected code, rootkits, and credential material.', category: 'FORENSICS', mitreAttackIds: ['T1003', 'T1055'], riskLevel: 'Medium', requiresAuth: true, icon: HardDrive },
  { id: 119, name: 'C2 Channel Simulator', description: 'Simulate common C2 communication patterns to test detection and egress filtering.', category: 'EVASION', mitreAttackIds: ['T1071', 'T1572', 'T1095'], riskLevel: 'Critical', requiresAuth: true, icon: Radio },
  { id: 120, name: 'EDR / AV Checker', description: 'Enumerate active endpoint security products and test detection baseline coverage.', category: 'EVASION', mitreAttackIds: ['T1518', 'T1562'], riskLevel: 'Medium', requiresAuth: true, icon: ShieldCheck },
  { id: 121, name: 'AD CS Abuse Module', description: 'Identify vulnerable ADCS certificate templates enabling privilege escalation and persistence.', category: 'ACTIVE_DIRECTORY', mitreAttackIds: ['T1649', 'T1558'], riskLevel: 'High', requiresAuth: true, icon: FileKey },
  { id: 122, name: 'GraphQL Depth Auditor', description: 'Audit GraphQL endpoints for introspection exposure, batch attacks, and depth vulnerabilities.', category: 'NETWORK', mitreAttackIds: ['T1190', 'T1059'], riskLevel: 'Medium', requiresAuth: true, icon: Layers },
  { id: 123, name: 'TOCTOU Visualizer', description: 'Identify and visualise time-of-check time-of-use race conditions in target applications.', category: 'NETWORK', mitreAttackIds: ['T1190', 'T1068'], riskLevel: 'High', requiresAuth: true, icon: Clock },
  { id: 124, name: 'APK Static Analyzer', description: 'Perform static analysis on Android APKs for secrets, insecure storage, and vulnerabilities.', category: 'NETWORK', mitreAttackIds: ['T1409', 'T1426'], riskLevel: 'Medium', requiresAuth: false, icon: Smartphone },
  { id: 125, name: 'Dangling DNS Scanner', description: 'Detect dangling DNS records pointing to unclaimed cloud resources vulnerable to subdomain takeover.', category: 'NETWORK', mitreAttackIds: ['T1584', 'T1583'], riskLevel: 'Medium', requiresAuth: false, icon: AlertCircle },
  { id: 126, name: 'MITRE ATT&CK Mapper', description: 'Map executed techniques to MITRE ATT&CK tactics and generate coverage heatmaps.', category: 'REPORTING', mitreAttackIds: [], riskLevel: 'Low', requiresAuth: false, icon: Map },
  { id: 127, name: 'Threat Intel Aggregator', description: 'Aggregate IOCs from VirusTotal, Shodan, AbuseIPDB, and AlienVault OTX for a target.', category: 'REPORTING', mitreAttackIds: [], riskLevel: 'Low', requiresAuth: false, icon: Radar },
  { id: 128, name: 'Dynamic Firewall Enforcer', description: 'Test and enforce dynamic firewall rule changes triggered by scan events.', category: 'NETWORK', mitreAttackIds: ['T1562', 'T1600'], riskLevel: 'High', requiresAuth: true, icon: ShieldAlert },
  { id: 129, name: 'DFIR Evidence Pipeline', description: 'Collect, hash, and archive forensic artefacts into a tamper-evident evidence pipeline.', category: 'FORENSICS', mitreAttackIds: [], riskLevel: 'Medium', requiresAuth: true, icon: FolderArchive },
  { id: 130, name: 'OSCP-Style Reporter', description: 'Generate professional penetration testing reports with findings, PoC, and remediation.', category: 'REPORTING', mitreAttackIds: [], riskLevel: 'Low', requiresAuth: false, icon: FileText },
]

// ─── Risk badge helpers ───────────────────────────────────────────────────────

type BadgeVariant = 'danger' | 'warning' | 'info' | 'neutral'

const riskVariant: Record<RiskLevel, BadgeVariant> = {
  Critical: 'danger',
  High: 'danger',
  Medium: 'warning',
  Low: 'info',
}

const riskDot: Record<RiskLevel, boolean> = {
  Critical: true,
  High: false,
  Medium: false,
  Low: false,
}

// ─── Category tabs ────────────────────────────────────────────────────────────

const CATEGORY_LABELS: Record<RedTeamCategory | 'ALL', string> = {
  ALL: 'All',
  CLOUD: 'Cloud',
  ACTIVE_DIRECTORY: 'Active Directory',
  NETWORK: 'Network',
  EVASION: 'Evasion',
  FORENSICS: 'Forensics',
  REPORTING: 'Reporting',
}

const CATEGORIES = ['ALL', 'CLOUD', 'ACTIVE_DIRECTORY', 'NETWORK', 'EVASION', 'FORENSICS', 'REPORTING'] as const
type CategoryFilter = (typeof CATEGORIES)[number]

// ─── Detail panels (rendered when a module is activated) ──────────────────────

const PANEL_MODULES: Partial<Record<number, React.FC>> = {
  101: JWTAuditorPanel,
  103: CloudStorageHunterPanel,
  126: MitreMapperPanel,
  130: OSCPReportPanel,
}

// ─── Module Card ──────────────────────────────────────────────────────────────

interface ModuleCardProps {
  module: ModuleDefinition
  isActive: boolean
  onActivate: (id: number) => void
}

function ModuleCard({ module, isActive, onActivate }: ModuleCardProps) {
  const IconComponent = module.icon
  const handleClick = useCallback(() => onActivate(module.id), [module.id, onActivate])

  return (
    <button
      type="button"
      onClick={handleClick}
      className="group relative flex w-full flex-col rounded-lg border p-4 text-left transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
      style={{
        background: isActive ? 'var(--brand-900)' : 'var(--bg-surface)',
        borderColor: isActive ? 'var(--brand-500)' : 'var(--border-subtle)',
      }}
      aria-pressed={isActive}
      aria-label={`${module.name} — module ${module.id}`}
    >
      <div className="mb-2 flex items-start justify-between gap-2">
        <div
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
          style={{ background: isActive ? 'var(--brand-500)' : 'var(--bg-overlay)' }}
          aria-hidden="true"
        >
          <IconComponent
            className="h-4 w-4"
            style={{ color: isActive ? '#fff' : 'var(--brand-400)' }}
          />
        </div>
        <div className="flex flex-col items-end gap-1">
          <Badge variant={riskVariant[module.riskLevel]} size="sm" dot={riskDot[module.riskLevel]}>
            {module.riskLevel}
          </Badge>
          {module.requiresAuth && (
            <span className="text-[10px]" style={{ color: 'var(--text-tertiary)' }}>Auth required</span>
          )}
        </div>
      </div>

      <div className="flex-1">
        <span
          className="text-[10px] font-mono"
          style={{ color: isActive ? 'var(--brand-400)' : 'var(--text-tertiary)' }}
        >
          #{module.id}
        </span>
        <h3
          className="mt-0.5 text-sm font-semibold leading-tight"
          style={{ color: 'var(--text-primary)' }}
        >
          {module.name}
        </h3>
        <p
          className="mt-1 text-xs leading-relaxed"
          style={{ color: 'var(--text-secondary)' }}
        >
          {module.description}
        </p>
      </div>

      {module.mitreAttackIds.length > 0 && (
        <div className="mt-2.5 flex flex-wrap gap-1" aria-label="MITRE ATT&CK techniques">
          {module.mitreAttackIds.slice(0, 3).map((id) => (
            <span
              key={id}
              className="rounded px-1.5 py-0.5 font-mono text-[10px]"
              style={{ background: 'var(--bg-overlay)', color: 'var(--text-tertiary)' }}
            >
              {id}
            </span>
          ))}
          {module.mitreAttackIds.length > 3 && (
            <span
              className="rounded px-1.5 py-0.5 font-mono text-[10px]"
              style={{ background: 'var(--bg-overlay)', color: 'var(--text-tertiary)' }}
            >
              +{module.mitreAttackIds.length - 3}
            </span>
          )}
        </div>
      )}

      {!PANEL_MODULES[module.id] && (
        <div
          className="absolute bottom-3 right-3 text-[10px] opacity-0 transition-opacity group-hover:opacity-100"
          style={{ color: 'var(--text-tertiary)' }}
          aria-hidden="true"
        >
          Coming soon
        </div>
      )}
    </button>
  )
}

// ─── Authorization disclaimer ─────────────────────────────────────────────────

function AuthDisclaimer() {
  return (
    <div
      className="flex items-start gap-3 rounded-lg border px-4 py-3"
      role="alert"
      aria-label="Authorization disclaimer"
      style={{ background: 'var(--warning-900)', borderColor: 'var(--warning-500)' }}
    >
      <ShieldAlert
        className="mt-0.5 h-4 w-4 shrink-0"
        style={{ color: 'var(--warning-500)' }}
        aria-hidden="true"
      />
      <div>
        <p className="text-sm font-semibold" style={{ color: 'var(--warning-500)' }}>
          Authorized Use Only
        </p>
        <p className="mt-0.5 text-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
          Red team tools must only be used against systems you own or have <strong>explicit written authorization</strong> to test.
          Unauthorized use may violate computer fraud laws. Always obtain permission before engaging any target.
        </p>
      </div>
    </div>
  )
}

// ─── Main dashboard ───────────────────────────────────────────────────────────

export function RedTeamDashboard() {
  const [activeCategory, setActiveCategory] = useState<CategoryFilter>('ALL')
  const [activeModuleId, setActiveModuleId] = useState<number | null>(null)

  const filteredModules = useMemo(
    () =>
      activeCategory === 'ALL'
        ? MODULES
        : MODULES.filter((m) => m.category === activeCategory),
    [activeCategory],
  )

  const handleActivate = useCallback((id: number) => {
    setActiveModuleId((prev) => (prev === id ? null : id))
  }, [])

  const ActivePanel = activeModuleId !== null ? PANEL_MODULES[activeModuleId] : undefined

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>
          Red Team Toolkit
        </h1>
        <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)' }}>
          Modules 101–130 — adversary simulation, infrastructure attack chains, and reporting
        </p>
      </div>

      <AuthDisclaimer />

      {/* Category filter */}
      <nav aria-label="Module category filter">
        <div className="flex flex-wrap gap-1.5">
          {CATEGORIES.map((cat) => (
            <button
              key={cat}
              type="button"
              onClick={() => { setActiveCategory(cat); setActiveModuleId(null) }}
              className="rounded-full px-3 py-1 text-xs font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
              style={{
                background: activeCategory === cat ? 'var(--brand-500)' : 'var(--bg-overlay)',
                color: activeCategory === cat ? '#fff' : 'var(--text-secondary)',
              }}
              aria-pressed={activeCategory === cat}
            >
              {CATEGORY_LABELS[cat]}
              {cat !== 'ALL' && (
                <span className="ml-1.5 opacity-60">
                  {MODULES.filter((m) => m.category === cat).length}
                </span>
              )}
            </button>
          ))}
        </div>
      </nav>

      {/* Active tool panel */}
      {ActivePanel && (
        <div className="animate-in fade-in slide-in-from-top-2 duration-300" role="region" aria-label="Active module panel">
          <ActivePanel />
        </div>
      )}

      {/* Module grid */}
      <section aria-label="Red team module grid">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {filteredModules.map((module) => (
            <ModuleCard
              key={module.id}
              module={module}
              isActive={activeModuleId === module.id}
              onActivate={handleActivate}
            />
          ))}
        </div>

        {filteredModules.length === 0 && (
          <Card>
            <CardBody>
              <p className="text-center text-sm" style={{ color: 'var(--text-tertiary)' }}>
                No modules in this category
              </p>
            </CardBody>
          </Card>
        )}
      </section>

      {/* Stats footer */}
      <div className="flex flex-wrap items-center gap-4 border-t pt-4" style={{ borderColor: 'var(--border-subtle)' }}>
        {(['Critical', 'High', 'Medium', 'Low'] as RiskLevel[]).map((level) => {
          const count = MODULES.filter((m) => m.riskLevel === level).length
          return (
            <div key={level} className="flex items-center gap-1.5">
              <Badge variant={riskVariant[level]} size="sm">{level}</Badge>
              <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>{count}</span>
            </div>
          )
        })}
        <span className="ml-auto text-xs" style={{ color: 'var(--text-tertiary)' }}>
          {MODULES.length} total modules
        </span>
      </div>
    </div>
  )
}
