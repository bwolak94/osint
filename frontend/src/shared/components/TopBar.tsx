import { useLocation } from "react-router-dom";
import { Bell, Search } from "lucide-react";
import { useAuthStore } from "@/features/auth/store";

const routeNames: Record<string, string> = {
  "/dashboard": "Dashboard",
  "/investigations": "Investigations",
  "/scanners": "Scanners",
  "/playbooks": "Playbooks",
  "/settings": "Settings",
  "/billing": "Billing",
};

export function TopBar() {
  const location = useLocation();
  const user = useAuthStore((s) => s.user);

  const pageName =
    Object.entries(routeNames).find(([path]) =>
      location.pathname.startsWith(path),
    )?.[1] ?? "Dashboard";

  return (
    <header
      className="flex h-14 items-center justify-between border-b px-6"
      style={{
        background: "var(--bg-surface)",
        borderColor: "var(--border-subtle)",
      }}
    >
      <div>
        <h1 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
          {pageName}
        </h1>
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={() => {
            window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true }));
          }}
          className="flex items-center gap-2 rounded-md border px-3 py-1.5 text-xs transition-colors hover:bg-bg-overlay"
          style={{ borderColor: "var(--border-default)", color: "var(--text-tertiary)" }}
        >
          <Search className="h-3.5 w-3.5" />
          Search...
          <kbd className="rounded border px-1 py-0.5 text-[10px]" style={{ borderColor: "var(--border-default)" }}>&#x2318;K</kbd>
        </button>

        <button className="relative rounded-md p-2 transition-colors hover:bg-bg-overlay">
          <Bell className="h-4 w-4" style={{ color: "var(--text-secondary)" }} />
        </button>

        {user && (
          <div className="flex items-center gap-2">
            <div
              className="flex h-8 w-8 items-center justify-center rounded-full text-xs font-bold"
              style={{ background: "var(--brand-900)", color: "var(--brand-400)" }}
            >
              {user.email.charAt(0).toUpperCase()}
            </div>
          </div>
        )}
      </div>
    </header>
  );
}
