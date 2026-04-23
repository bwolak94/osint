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
} from "lucide-react";
import { useAuthStore } from "@/features/auth/store";
import { motion, AnimatePresence } from "framer-motion";

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
  { to: "/scanners", label: "Scanners", icon: Radar },
  { to: "/playbooks", label: "Playbooks", icon: BookOpen },
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
    ],
  },
  {
    key: "social-osint",
    label: "Social OSINT",
    icon: Globe2,
    children: [
      { to: "/fediverse", label: "Fediverse", icon: Users },
      { to: "/socmint", label: "SOCMINT", icon: UserSearch },
    ],
  },
  {
    key: "tech-recon",
    label: "Tech Recon",
    icon: ScanLine,
    children: [
      { to: "/tech-recon", label: "Infra Recon", icon: NetworkIcon },
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

  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>(getDefaultOpen);

  const tierColors: Record<string, string> = {
    free: "text-text-tertiary",
    pro: "text-brand-400",
    enterprise: "text-warning-500",
  };

  function toggleGroup(key: string) {
    setOpenGroups((prev) => ({ ...prev, [key]: !prev[key] }));
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
        <AnimatePresence initial={false}>
          {isOpen && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.18 }}
              className="overflow-hidden"
            >
              <div className="mt-0.5 space-y-0.5 border-l ml-5 pl-1" style={{ borderColor: "var(--border-subtle)" }}>
                {group.children.map((child) => renderItem(child, true))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    );
  }

  return (
    <motion.aside
      animate={{ width: collapsed ? 64 : 240 }}
      transition={{ duration: 0.2 }}
      className="flex flex-col border-r overflow-hidden"
      style={{
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
    </motion.aside>
  );
}
