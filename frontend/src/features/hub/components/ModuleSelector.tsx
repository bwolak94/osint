/**
 * ModuleSelector — tab strip for choosing which Hub module to query.
 *
 * Maps each module to a human-readable label + icon.
 */

import { useId } from "react";
import { Newspaper, Calendar, CheckSquare, Database, MessageSquare } from "lucide-react";
import type { HubModule } from "../types";

interface ModuleSelectorProps {
  value: HubModule;
  onChange: (module: HubModule) => void;
  disabled?: boolean;
}

const MODULES: { value: HubModule; label: string; Icon: React.ElementType }[] = [
  { value: "chat", label: "Chat", Icon: MessageSquare },
  { value: "news", label: "News", Icon: Newspaper },
  { value: "tasks", label: "Tasks", Icon: CheckSquare },
  { value: "knowledge", label: "Knowledge", Icon: Database },
  { value: "calendar", label: "Calendar", Icon: Calendar },
];

export function ModuleSelector({ value, onChange, disabled = false }: ModuleSelectorProps) {
  const groupId = useId();

  return (
    <div
      role="tablist"
      aria-label="Hub module"
      className="flex gap-1 rounded-lg p-1"
      style={{ background: "var(--bg-overlay)" }}
    >
      {MODULES.map(({ value: mod, label, Icon }) => {
        const isActive = value === mod;
        const tabId = `${groupId}-${mod}`;
        return (
          <button
            key={mod}
            id={tabId}
            role="tab"
            aria-selected={isActive}
            disabled={disabled}
            onClick={() => onChange(mod)}
            className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-all
              ${disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer"}
              ${
                isActive
                  ? "shadow-sm"
                  : "hover:bg-bg-surface"
              }`}
            style={
              isActive
                ? {
                    background: "var(--bg-surface)",
                    color: "var(--brand-400)",
                    boxShadow: "0 1px 3px rgba(0,0,0,0.12)",
                  }
                : { color: "var(--text-secondary)" }
            }
          >
            <Icon className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            {label}
          </button>
        );
      })}
    </div>
  );
}
