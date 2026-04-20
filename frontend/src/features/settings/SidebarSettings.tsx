import { useState } from "react";
import { GripVertical, Eye, EyeOff } from "lucide-react";

interface NavItem {
  id: string;
  label: string;
  visible: boolean;
  order: number;
}

const DEFAULT_NAV_ITEMS: NavItem[] = [
  { id: "dashboard", label: "Dashboard", visible: true, order: 0 },
  { id: "investigations", label: "Investigations", visible: true, order: 1 },
  { id: "scanners", label: "Scanners", visible: true, order: 2 },
  { id: "playbooks", label: "Playbooks", visible: true, order: 3 },
  { id: "templates", label: "Templates", visible: true, order: 4 },
  { id: "watchlist", label: "Watch List", visible: true, order: 5 },
  { id: "ioc-feed", label: "IOC Feed", visible: false, order: 6 },
  { id: "reports", label: "Reports", visible: false, order: 7 },
];

export function SidebarSettings() {
  const [items, setItems] = useState<NavItem[]>(() => {
    const saved = localStorage.getItem("sidebar-config");
    return saved ? JSON.parse(saved) : DEFAULT_NAV_ITEMS;
  });

  const toggleVisibility = (id: string) => {
    const updated = items.map((item) =>
      item.id === id ? { ...item, visible: !item.visible } : item
    );
    setItems(updated);
    localStorage.setItem("sidebar-config", JSON.stringify(updated));
  };

  const resetDefaults = () => {
    setItems(DEFAULT_NAV_ITEMS);
    localStorage.removeItem("sidebar-config");
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>
            Sidebar Navigation
          </h3>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Customize which items appear in your sidebar
          </p>
        </div>
        <button
          onClick={resetDefaults}
          className="text-sm px-3 py-1 rounded-md border transition-colors hover:bg-bg-overlay"
          style={{ borderColor: "var(--border-default)", color: "var(--text-secondary)" }}
        >
          Reset
        </button>
      </div>

      <div className="space-y-2">
        {items
          .sort((a, b) => a.order - b.order)
          .map((item) => (
            <div
              key={item.id}
              className="flex items-center gap-3 rounded-lg border p-3"
              style={{
                borderColor: "var(--border-subtle)",
                background: "var(--bg-surface)",
                opacity: item.visible ? 1 : 0.5,
              }}
            >
              <GripVertical className="h-4 w-4 shrink-0 cursor-grab" style={{ color: "var(--text-tertiary)" }} />
              <span className="flex-1 text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                {item.label}
              </span>
              <button
                onClick={() => toggleVisibility(item.id)}
                className="rounded p-1 transition-colors hover:bg-bg-overlay"
              >
                {item.visible ? (
                  <Eye className="h-4 w-4" style={{ color: "var(--brand-400)" }} />
                ) : (
                  <EyeOff className="h-4 w-4" style={{ color: "var(--text-tertiary)" }} />
                )}
              </button>
            </div>
          ))}
      </div>
    </div>
  );
}
