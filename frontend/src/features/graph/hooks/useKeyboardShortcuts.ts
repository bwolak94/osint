import { useEffect, useCallback, useState, useRef } from "react";

export interface Shortcut {
  key: string;
  description: string;
  action: () => void;
  category: "navigation" | "graph" | "investigation" | "global";
}

interface ParsedKey {
  ctrl: boolean;
  shift: boolean;
  alt: boolean;
  key: string;
}

function parseShortcut(raw: string): ParsedKey {
  const parts = raw.toLowerCase().split("+");
  const modifiers = new Set(parts.slice(0, -1));
  const key = parts[parts.length - 1] ?? "";
  return {
    ctrl: modifiers.has("ctrl") || modifiers.has("cmd"),
    shift: modifiers.has("shift"),
    alt: modifiers.has("alt"),
    key,
  };
}

function matchesEvent(parsed: ParsedKey, e: KeyboardEvent): boolean {
  const eventKey = e.key.toLowerCase();
  return (
    eventKey === parsed.key &&
    e.ctrlKey === parsed.ctrl &&
    e.shiftKey === parsed.shift &&
    e.altKey === parsed.alt
  );
}

function isInputFocused(): boolean {
  const el = document.activeElement;
  if (!el) return false;
  const tag = el.tagName.toLowerCase();
  return (
    tag === "input" ||
    tag === "textarea" ||
    tag === "select" ||
    (el as HTMLElement).isContentEditable
  );
}

export const SHORTCUT_CATEGORIES: ReadonlyArray<Shortcut["category"]> = [
  "global",
  "navigation",
  "graph",
  "investigation",
];

export interface UseKeyboardShortcutsReturn {
  showHelp: boolean;
  setShowHelp: (show: boolean) => void;
}

export function useKeyboardShortcuts(
  shortcuts: Shortcut[],
): UseKeyboardShortcutsReturn {
  const [showHelp, setShowHelp] = useState(false);
  const shortcutsRef = useRef<Shortcut[]>(shortcuts);
  shortcutsRef.current = shortcuts;
  const showHelpRef = useRef(showHelp);
  showHelpRef.current = showHelp;

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    // "?" toggles help (allowed even when help is open)
    if (e.key === "?" && !isInputFocused()) {
      e.preventDefault();
      setShowHelp((v) => !v);
      return;
    }

    // Escape closes help
    if (e.key === "Escape" && showHelpRef.current) {
      e.preventDefault();
      setShowHelp(false);
      return;
    }

    // Skip all other shortcuts when an input is focused
    if (isInputFocused()) return;

    for (const shortcut of shortcutsRef.current) {
      const parsed = parseShortcut(shortcut.key);
      if (matchesEvent(parsed, e)) {
        e.preventDefault();
        shortcut.action();
        return;
      }
    }
  }, []);

  useEffect(() => {
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  return { showHelp, setShowHelp };
}
