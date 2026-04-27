import { Link, useLocation } from "react-router-dom";
import { useState } from "react";
import {
  Search,
  Settings,
  CreditCard,
  LogOut,
  LayoutDashboard,
  Radar,
  BookOpen,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  Shield,
  ShieldCheck,
  ScanSearch,
  FileText,
  Mail,
  Cpu,
  Globe,
  Cloud,
  AlertTriangle,
  Package,
  Users,
  Wifi,
  Microscope,
  Network,
  ShieldAlert,
  Globe2,
  ScanLine,
  Network as NetworkIcon,
  UserSearch,
  KeyRound,
  MapPin,
  Brain,
  ClipboardCheck,
  BarChart3,
  Swords,
  Library,
  Sparkles,
  Bell,
  GitBranch,
  Flag,
  FileOutput,
  Scale,
  Plug,
  Eye,
  Database,
  Fingerprint,
  Bitcoin,
  Building2,
  Phone,
  GitMerge,
  Archive,
  Terminal,
  RefreshCw,
  Lock,
  Clock,
  Timer,
  Rss,
  Zap,
  PackageCheck,
  FlaskConical,
  ShoppingBag,
  Radio,
  Gauge,
  Puzzle,
  Layers,
} from "lucide-react";
import { useAuthStore } from "@/features/auth/store";

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

interface NavItem {
  to: string;
  label: string;
  icon: React.ElementType;
}

interface NavGroup {
  label: string;
  icon: React.ElementType;
  key: string;
  children: NavItem[];
}

type NavEntry = NavItem | NavGroup;

function isNavGroup(entry: NavEntry): entry is NavGroup {
  return "children" in entry;
}

const mainNav: NavEntry[] = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/hub", label: "AI Hub", icon: Sparkles },
  { to: "/investigations", label: "Investigations", icon: Search },
  { to: "/campaigns", label: "Campaigns", icon: Flag },
  { to: "/investigation-diff", label: "Diff & Merge", icon: GitBranch },
  { to: "/scanners", label: "Scanners", icon: Radar },
  { to: "/custom-scanner", label: "Custom Scanners", icon: Cpu },
  { to: "/playbooks", label: "Playbooks", icon: BookOpen },
  { to: "/deep-research", label: "Deep Research", icon: FlaskConical },
  { to: "/digital-footprint", label: "Footprint Score", icon: Fingerprint },
  { to: "/correlation", label: "Correlation Engine", icon: GitMerge },
  { to: "/multi-graph", label: "Multi-Graph Analysis", icon: Layers },
  { to: "/evidence-locker", label: "Evidence Locker", icon: Archive },
  { to: "/secure-notes", label: "Secure Notes", icon: Lock },
  { to: "/collaboration", label: "Collaboration", icon: Users },
  {
    key: "file-forensics",
    label: "File Forensics",
    icon: Microscope,
    children: [
      { to: "/image-checker", label: "Image Checker", icon: ScanSearch },
      { to: "/doc-metadata", label: "Doc Metadata", icon: FileText },
    ],
  },
  {
    key: "network",
    label: "Network & Domains",
    icon: Network,
    children: [
      { to: "/mac-lookup", label: "MAC Lookup", icon: Cpu },
      { to: "/domain-permutation", label: "Domain Permutation", icon: Globe },
      { to: "/cloud-exposure", label: "Cloud Exposure", icon: Cloud },
      { to: "/wigle", label: "WiGLE", icon: Wifi },
      { to: "/passive-dns", label: "Passive DNS", icon: Database },
      { to: "/cert-transparency", label: "Cert Transparency", icon: Shield },
    ],
  },
  {
    key: "threat-intel",
    label: "Threat Intel",
    icon: ShieldAlert,
    children: [
      { to: "/email-headers", label: "Email Headers", icon: Mail },
      { to: "/stealer-logs", label: "Stealer Logs", icon: AlertTriangle },
      { to: "/supply-chain", label: "Supply Chain", icon: Package },
      { to: "/credential-intel", label: "Credential Intel", icon: KeyRound },
      { to: "/threat-actors", label: "Threat Actors", icon: Shield },
      { to: "/watchlist", label: "Watchlist", icon: Bell },
      { to: "/dark-web", label: "Dark Web Monitor", icon: Eye },
      { to: "/crypto-trace", label: "Crypto Tracing", icon: Bitcoin },
      { to: "/corporate-intel", label: "Corporate Intel", icon: Building2 },
      { to: "/brand-protection", label: "Brand Protection", icon: ShieldAlert },
      { to: "/ioc-feed", label: "IOC Feed", icon: Radio },
      { to: "/attack-surface", label: "Attack Surface", icon: Gauge },
      { to: "/threat-feed", label: "Threat Feed", icon: Rss },
      { to: "/canary-tokens", label: "Canary Tokens", icon: Zap },
    ],
  },
  {
    key: "social-osint",
    label: "Social OSINT",
    icon: Globe2,
    children: [
      { to: "/fediverse", label: "Fediverse", icon: Users },
      { to: "/socmint", label: "SOCMINT", icon: UserSearch },
      { to: "/phone-intel", label: "Phone Intel", icon: Phone },
      { to: "/social-graph", label: "Social Graph", icon: Network },
    ],
  },
  {
    key: "tech-recon",
    label: "Tech Recon",
    icon: ScanLine,
    children: [
      { to: "/tech-recon", label: "Infra Recon", icon: NetworkIcon },
      { to: "/network-topology", label: "Network Topology", icon: Network },
    ],
  },
  {
    key: "imint",
    label: "IMINT / GEOINT",
    icon: MapPin,
    children: [
      { to: "/imint", label: "Image & Geo Intel", icon: MapPin },
    ],
  },
  {
    key: "pentest",
    label: "Pentest",
    icon: Shield,
    children: [
      { to: "/pentest/targets", label: "Targets", icon: Globe },
      { to: "/pentest/dashboard", label: "Dashboard", icon: BarChart3 },
      { to: "/pentest/findings", label: "Findings", icon: ShieldAlert },
      { to: "/pentest/compliance", label: "Compliance", icon: ClipboardCheck },
      { to: "/pentest/bas", label: "Attack Simulation", icon: Swords },
      { to: "/pentest/finding-library", label: "Finding Library", icon: Library },
      { to: "/pentest/attack-planner", label: "Attack Planner", icon: Brain },
      { to: "/pentest/attack-flow", label: "Attack Flow", icon: Zap },
      { to: "/pentest/marketplace", label: "Scenario Marketplace", icon: ShoppingBag },
      { to: "/mitre-attack", label: "MITRE ATT&CK", icon: Swords },
      { to: "/report-builder", label: "Report Builder", icon: FileOutput },
      { to: "/vuln-management", label: "Vuln Management", icon: ShieldAlert },
      { to: "/phishing", label: "Phishing Sim", icon: Mail },
      { to: "/exploit-chain", label: "Exploit Chains", icon: Swords },
      { to: "/c2-integration", label: "C2 Integration", icon: Terminal },
      { to: "/methodology", label: "Methodology", icon: ClipboardCheck },
      { to: "/retest", label: "Retest Engine", icon: RefreshCw },
      { to: "/client-portal", label: "Client Portal", icon: Globe },
      { to: "/time-tracking", label: "Time Tracking", icon: Clock },
      { to: "/sla", label: "SLA Dashboard", icon: Timer },
      { to: "/ai-debrief", label: "AI Debrief", icon: Brain },
      { to: "/knowledge-base", label: "Knowledge Base", icon: BookOpen },
      { to: "/client-handoff", label: "Client Handoff", icon: PackageCheck },
    ],
  },
  {
    key: "legal",
    label: "Compliance & Legal",
    icon: Scale,
    children: [
      { to: "/gdpr", label: "GDPR Requests", icon: Scale },
    ],
  },
  { to: "/scanner-quota", label: "Scanner Quota", icon: Gauge },
  { to: "/browser-extension", label: "Browser Extension", icon: Puzzle },
  {
    key: "integrations",
    label: "Integrations",
    icon: Plug,
    children: [
      { to: "/maltego", label: "Maltego", icon: Plug },
    ],
  },
];

const bottomNav: NavItem[] = [
  { to: "/admin", label: "Admin", icon: ShieldCheck },
  { to: "/settings", label: "Settings", icon: Settings },
  { to: "/billing", label: "Billing", icon: CreditCard },
];

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const location = useLocation();
  const { user, logout } = useAuthStore();

  const getDefaultOpen = (): Record<string, boolean> => {
    const open: Record<string, boolean> = {};
    for (const entry of mainNav) {
      if (isNavGroup(entry)) {
        const anyActive = entry.children.some((c) =>
          location.pathname.startsWith(c.to)
        );
        open[entry.key] = anyActive;
      }
    }
    return open;
  };

  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>(() => {
    try {
      const stored = localStorage.getItem('sidebar-groups')
      if (stored) return { ...getDefaultOpen(), ...JSON.parse(stored) as Record<string, boolean> }
    } catch { /* storage unavailable */ }
    return getDefaultOpen()
  });

  const tierColors: Record<string, string> = {
    free: "text-text-tertiary",
    pro: "text-brand-400",
    enterprise: "text-warning-500",
  };

  function toggleGroup(key: string) {
    setOpenGroups((prev) => {
      const next = { ...prev, [key]: !prev[key] }
      try { localStorage.setItem('sidebar-groups', JSON.stringify(next)) } catch { /* storage unavailable */ }
      return next
    })
  }

  function renderItem(item: NavItem, indent = false) {
    const isActive = location.pathname.startsWith(item.to);
    return (
      <Link
        key={item.to}
        to={item.to}
        title={collapsed ? item.label : undefined}
        className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-all ${
          indent && !collapsed ? "pl-7" : ""
        } ${
          isActive
            ? "bg-brand-900 text-brand-400"
            : "text-text-secondary hover:bg-bg-overlay hover:text-text-primary"
        }`}
      >
        <item.icon className="h-4 w-4 shrink-0" />
        {!collapsed && <span>{item.label}</span>}
      </Link>
    );
  }

  function renderGroup(group: NavGroup) {
    const isOpen = openGroups[group.key] ?? false;
    const anyChildActive = group.children.some((c) =>
      location.pathname.startsWith(c.to)
    );

    if (collapsed) {
      return (
        <div key={group.key} className="space-y-0.5">
          {group.children.map((child) => renderItem(child, false))}
        </div>
      );
    }

    return (
      <div key={group.key}>
        <button
          onClick={() => toggleGroup(group.key)}
          className={`flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-all ${
            anyChildActive && !isOpen
              ? "text-brand-400"
              : "text-text-secondary hover:bg-bg-overlay hover:text-text-primary"
          }`}
        >
          <group.icon className="h-4 w-4 shrink-0" />
          <span className="flex-1 text-left">{group.label}</span>
          <ChevronDown
            className={`h-3.5 w-3.5 shrink-0 transition-transform duration-200 ${
              isOpen ? "rotate-180" : ""
            }`}
            style={{ color: "var(--text-tertiary)" }}
          />
        </button>
        {isOpen && (
          <div className="overflow-hidden mt-0.5 space-y-0.5 border-l ml-5 pl-1" style={{ borderColor: "var(--border-subtle)" }}>
            {group.children.map((child) => renderItem(child, true))}
          </div>
        )}
      </div>
    );
  }

  return (
    <aside
      className="flex flex-col border-r overflow-hidden transition-[width] duration-200"
      style={{
        width: collapsed ? 64 : 240,
        background: "var(--bg-surface)",
        borderColor: "var(--border-subtle)",
      }}
    >
      {/* Logo */}
      <div
        className="flex h-14 items-center gap-2 border-b px-4"
        style={{ borderColor: "var(--border-subtle)" }}
      >
        <Shield className="h-6 w-6 shrink-0" style={{ color: "var(--brand-500)" }} />
        {!collapsed && (
          <span className="text-base font-bold" style={{ color: "var(--text-primary)" }}>
            OSINT
          </span>
        )}
        <button
          onClick={onToggle}
          className="ml-auto rounded p-1 transition-colors hover:bg-bg-overlay"
        >
          {collapsed ? (
            <ChevronRight className="h-4 w-4" style={{ color: "var(--text-secondary)" }} />
          ) : (
            <ChevronLeft className="h-4 w-4" style={{ color: "var(--text-secondary)" }} />
          )}
        </button>
      </div>

      {/* Main navigation */}
      <nav className="flex-1 overflow-y-auto space-y-0.5 p-2">
        {mainNav.map((entry) =>
          isNavGroup(entry) ? renderGroup(entry) : renderItem(entry)
        )}
      </nav>

      {/* Separator */}
      <div className="mx-3 border-t" style={{ borderColor: "var(--border-subtle)" }} />

      {/* Bottom navigation */}
      <nav className="space-y-0.5 p-2">
        {bottomNav.map((item) => renderItem(item))}
      </nav>

      {/* User section */}
      <div className="border-t p-3" style={{ borderColor: "var(--border-subtle)" }}>
        {!collapsed && user && (
          <div className="mb-2 truncate px-1">
            <p className="truncate text-sm font-medium" style={{ color: "var(--text-primary)" }}>
              {user.email}
            </p>
            <p className={`text-xs font-medium uppercase ${tierColors[user.subscription_tier] ?? ""}`}>
              {user.subscription_tier}
            </p>
          </div>
        )}
        <button
          onClick={logout}
          title={collapsed ? "Sign Out" : undefined}
          className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors text-text-secondary hover:bg-bg-overlay hover:text-danger-500"
        >
          <LogOut className="h-4 w-4 shrink-0" />
          {!collapsed && <span>Sign Out</span>}
        </button>
      </div>
    </aside>
  );
}
