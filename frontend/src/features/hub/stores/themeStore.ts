import { create } from "zustand";
import { persist } from "zustand/middleware";

export type HubTheme = "default" | "deep-work" | "review";

interface ThemeState {
  theme: HubTheme;
  autoTheme: boolean;
  setTheme: (theme: HubTheme) => void;
  toggleTheme: (target: "deep-work" | "review") => void;
  setAutoTheme: (enabled: boolean) => void;
  /**
   * Suggests a theme based on the cognitive load score.
   * Fires a toast notification only — never auto-switches theme.
   * Real toast dispatch happens in the component that consumes this store.
   */
  suggestTheme: (cognitiveScore: number) => void;
}

const applyTheme = (theme: HubTheme): void => {
  if (theme === "default") {
    document.documentElement.removeAttribute("data-theme");
  } else {
    document.documentElement.setAttribute("data-theme", theme);
  }
};

export const useThemeStore = create<ThemeState>()(
  persist(
    (set, get) => ({
      theme: "default",
      autoTheme: false,

      setTheme: (theme) => {
        applyTheme(theme);
        set({ theme });
      },

      toggleTheme: (target) => {
        const current = get().theme;
        const next: HubTheme = current === target ? "default" : target;
        applyTheme(next);
        set({ theme: next });
      },

      setAutoTheme: (enabled) => set({ autoTheme: enabled }),

      // Toast integration is handled by the consuming component.
      // This action is intentionally side-effect-free to keep the store pure.
      suggestTheme: (_cognitiveScore) => {
        // no-op: component reads theme + cognitiveScore and fires its own toast
      },
    }),
    {
      name: "hub-theme",
      partialize: (s) => ({ theme: s.theme, autoTheme: s.autoTheme }),
    }
  )
);
