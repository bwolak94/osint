import { useEffect } from "react";
import { useThemeStore } from "../stores/themeStore";

/**
 * Registers global keyboard shortcuts for hub theme switching.
 *
 * Ctrl/Cmd + Shift + D → toggle deep-work theme
 * Ctrl/Cmd + Shift + R → toggle review theme
 */
export function useThemeShortcut(): void {
  const toggleTheme = useThemeStore((s) => s.toggleTheme);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent): void {
      const isModifier = event.metaKey || event.ctrlKey;
      if (!isModifier || !event.shiftKey) return;

      switch (event.key.toUpperCase()) {
        case "D":
          event.preventDefault();
          toggleTheme("deep-work");
          break;
        case "R":
          event.preventDefault();
          toggleTheme("review");
          break;
        default:
          break;
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [toggleTheme]);
}
