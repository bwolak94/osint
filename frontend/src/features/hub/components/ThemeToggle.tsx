import { BookOpen, Focus, Sun } from "lucide-react";
import { useCallback } from "react";
import { useThemeStore } from "../stores/themeStore";
import type { HubTheme } from "../stores/themeStore";

interface ThemeOption {
  value: HubTheme;
  label: string;
  icon: React.ReactNode;
}

const THEME_OPTIONS: ThemeOption[] = [
  {
    value: "default",
    label: "Default",
    icon: <Sun className="h-4 w-4" aria-hidden="true" />,
  },
  {
    value: "deep-work",
    label: "Deep Work",
    icon: <Focus className="h-4 w-4" aria-hidden="true" />,
  },
  {
    value: "review",
    label: "Review",
    icon: <BookOpen className="h-4 w-4" aria-hidden="true" />,
  },
];

export function ThemeToggle() {
  const theme = useThemeStore((s) => s.theme);
  const setTheme = useThemeStore((s) => s.setTheme);

  const handleSelect = useCallback(
    (value: HubTheme) => {
      setTheme(value);
    },
    [setTheme]
  );

  return (
    <div
      role="group"
      aria-label="Hub theme selection"
      className="flex items-center gap-1 rounded-lg p-1"
      style={{
        background: "var(--bg-surface)",
        border: "1px solid var(--border-subtle)",
      }}
    >
      {THEME_OPTIONS.map(({ value, label, icon }) => {
        const isActive = theme === value;

        return (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={isActive}
            aria-pressed={isActive}
            aria-label={`${label} theme`}
            onClick={() => handleSelect(value)}
            className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-all"
            style={{
              background: isActive ? "var(--brand-500)" : "transparent",
              color: isActive ? "#fff" : "var(--text-secondary)",
              border: isActive
                ? "1px solid transparent"
                : "1px solid transparent",
            }}
          >
            {icon}
            <span>{label}</span>
          </button>
        );
      })}
    </div>
  );
}
