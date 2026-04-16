import { Link, useLocation } from "react-router-dom";
import {
  Search,
  Settings,
  CreditCard,
  LogOut,
  LayoutDashboard,
  ChevronLeft,
  ChevronRight,
  Shield,
} from "lucide-react";
import { useAuthStore } from "@/features/auth/store";
import { motion } from "framer-motion";

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

const mainNav = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/investigations", label: "Investigations", icon: Search },
];

const bottomNav = [
  { to: "/settings", label: "Settings", icon: Settings },
  { to: "/billing", label: "Billing", icon: CreditCard },
];

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const location = useLocation();
  const { user, logout } = useAuthStore();

  const tierColors: Record<string, string> = {
    free: "text-text-tertiary",
    pro: "text-brand-400",
    enterprise: "text-warning-500",
  };

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
      <nav className="flex-1 space-y-1 p-2">
        {mainNav.map((item) => {
          const isActive = location.pathname.startsWith(item.to);
          return (
            <Link
              key={item.to}
              to={item.to}
              title={collapsed ? item.label : undefined}
              className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-all ${
                isActive
                  ? "bg-brand-900 text-brand-400"
                  : "text-text-secondary hover:bg-bg-overlay hover:text-text-primary"
              }`}
            >
              <item.icon className="h-4 w-4 shrink-0" />
              {!collapsed && <span>{item.label}</span>}
            </Link>
          );
        })}
      </nav>

      {/* Separator */}
      <div className="mx-3 border-t" style={{ borderColor: "var(--border-subtle)" }} />

      {/* Bottom navigation */}
      <nav className="space-y-1 p-2">
        {bottomNav.map((item) => {
          const isActive = location.pathname.startsWith(item.to);
          return (
            <Link
              key={item.to}
              to={item.to}
              title={collapsed ? item.label : undefined}
              className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-all ${
                isActive
                  ? "bg-brand-900 text-brand-400"
                  : "text-text-secondary hover:bg-bg-overlay hover:text-text-primary"
              }`}
            >
              <item.icon className="h-4 w-4 shrink-0" />
              {!collapsed && <span>{item.label}</span>}
            </Link>
          );
        })}
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
