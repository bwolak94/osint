import { Outlet, Link, useLocation } from "react-router-dom";
import {
  Search,
  Network,
  Settings,
  CreditCard,
  LogOut,
} from "lucide-react";
import { useAuthStore } from "@/features/auth/store";

const navItems = [
  { to: "/investigations", label: "Investigations", icon: Search },
  { to: "/settings", label: "Settings", icon: Settings },
  { to: "/payments", label: "Payments", icon: CreditCard },
];

export function Layout() {
  const location = useLocation();
  const logout = useAuthStore((s) => s.logout);

  return (
    <div className="flex h-screen bg-gray-950">
      {/* Sidebar */}
      <aside className="flex w-64 flex-col border-r border-gray-800 bg-gray-900">
        <div className="flex h-16 items-center gap-2 border-b border-gray-800 px-6">
          <Network className="h-6 w-6 text-indigo-400" />
          <span className="text-lg font-bold text-white">OSINT</span>
        </div>

        <nav className="flex-1 space-y-1 p-4">
          {navItems.map((item) => {
            const isActive = location.pathname.startsWith(item.to);
            return (
              <Link
                key={item.to}
                to={item.to}
                className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-gray-800 text-white"
                    : "text-gray-400 hover:bg-gray-800 hover:text-white"
                }`}
              >
                <item.icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="border-t border-gray-800 p-4">
          <button
            onClick={logout}
            className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-gray-400 transition-colors hover:bg-gray-800 hover:text-white"
          >
            <LogOut className="h-4 w-4" />
            Sign Out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto p-8">
        <Outlet />
      </main>
    </div>
  );
}
