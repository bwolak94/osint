import {
  useState,
  useEffect,
  useCallback,
  useId,
} from "react";
import { Sun, Moon, Monitor } from "lucide-react";
import apiClient from "@/shared/api/client";

type ColorScheme = "light" | "dark" | "system";

const STORAGE_KEY = "osint-color-scheme";
const CYCLE_ORDER: ColorScheme[] = ["light", "dark", "system"];

function resolveEffectiveScheme(scheme: ColorScheme): "light" | "dark" {
  if (scheme !== "system") return scheme;
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

function applyScheme(scheme: ColorScheme): void {
  const effective = resolveEffectiveScheme(scheme);
  document.documentElement.classList.toggle("dark", effective === "dark");
}

function readStoredScheme(): ColorScheme {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark" || stored === "system") {
      return stored;
    }
  } catch {
    // localStorage may be unavailable
  }
  return "system";
}

function storeScheme(scheme: ColorScheme): void {
  try {
    localStorage.setItem(STORAGE_KEY, scheme);
  } catch {
    // ignore
  }
}

async function persistSchemeToServer(scheme: ColorScheme): Promise<void> {
  try {
    await apiClient.patch("/auth/me/settings", { color_scheme: scheme });
  } catch {
    // Non-critical — local preference is already applied
  }
}

// ─── Hook ────────────────────────────────────────────────────────────────────

export function useDarkMode(): {
  scheme: ColorScheme;
  setScheme: (scheme: ColorScheme) => void;
  effectiveScheme: "light" | "dark";
  cycleScheme: () => void;
} {
  const [scheme, setSchemeState] = useState<ColorScheme>(() => {
    const stored = readStoredScheme();
    return stored;
  });

  // Apply on mount and system change
  useEffect(() => {
    applyScheme(scheme);

    if (scheme === "system") {
      const mq = window.matchMedia("(prefers-color-scheme: dark)");
      const handler = () => applyScheme("system");
      mq.addEventListener("change", handler);
      return () => mq.removeEventListener("change", handler);
    }
    return undefined;
  }, [scheme]);

  const setScheme = useCallback((next: ColorScheme) => {
    setSchemeState(next);
    storeScheme(next);
    applyScheme(next);
    void persistSchemeToServer(next);
  }, []);

  const cycleScheme = useCallback(() => {
    const currentIndex = CYCLE_ORDER.indexOf(scheme);
    const next = CYCLE_ORDER[(currentIndex + 1) % CYCLE_ORDER.length] ?? "system";
    setScheme(next);
  }, [scheme, setScheme]);

  const effectiveScheme = resolveEffectiveScheme(scheme);

  return { scheme, setScheme, effectiveScheme, cycleScheme };
}

// ─── Component ───────────────────────────────────────────────────────────────

const SCHEME_CONFIG: Record<
  ColorScheme,
  { Icon: typeof Sun; label: string; next: ColorScheme }
> = {
  light: { Icon: Sun, label: "Light mode", next: "dark" },
  dark: { Icon: Moon, label: "Dark mode", next: "system" },
  system: { Icon: Monitor, label: "System preference", next: "light" },
};

interface DarkModeToggleProps {
  className?: string;
  showLabel?: boolean;
}

export function DarkModeToggle({
  className = "",
  showLabel = false,
}: DarkModeToggleProps) {
  const { scheme, cycleScheme } = useDarkMode();
  const tooltipId = useId();
  const { Icon, label } = SCHEME_CONFIG[scheme];

  return (
    <button
      onClick={cycleScheme}
      aria-label={`Current: ${label}. Click to change`}
      aria-describedby={tooltipId}
      className={`inline-flex items-center gap-2 rounded-md px-2 py-1.5 text-xs font-medium transition-colors hover:bg-bg-overlay focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 ${className}`}
      style={{ color: "var(--text-secondary)" }}
    >
      <Icon className="h-4 w-4 shrink-0" />
      {showLabel && <span>{label}</span>}
      <span id={tooltipId} className="sr-only">
        Click to cycle through light, dark, and system color scheme modes
      </span>
    </button>
  );
}
