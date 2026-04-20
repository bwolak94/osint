import { useEffect, useId } from "react";
import { X } from "lucide-react";
import type { Shortcut } from "../hooks/useKeyboardShortcuts";
import { SHORTCUT_CATEGORIES } from "../hooks/useKeyboardShortcuts";

interface KeyboardShortcutsHelpProps {
  shortcuts: Shortcut[];
  open: boolean;
  onClose: () => void;
}

// Built-in shortcuts always shown regardless of registered list
const BUILTIN_SHORTCUTS: Array<{ key: string; description: string; category: Shortcut["category"] }> = [
  { key: "?", description: "Show keyboard shortcuts", category: "global" },
  { key: "Escape", description: "Close dialogs / cancel", category: "global" },
];

export function KeyboardShortcutsHelp({
  shortcuts,
  open,
  onClose,
}: KeyboardShortcutsHelpProps) {
  const titleId = useId();

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, onClose]);

  if (!open) return null;

  // Merge built-ins with registered shortcuts per category
  const allShortcuts = [...BUILTIN_SHORTCUTS, ...shortcuts];

  const byCategory = SHORTCUT_CATEGORIES.reduce<
    Record<Shortcut["category"], Array<{ key: string; description: string }>>
  >(
    (acc, cat) => {
      const items = allShortcuts
        .filter((s) => s.category === cat)
        .map(({ key, description }) => ({ key, description }));
      if (items.length > 0) acc[cat] = items;
      return acc;
    },
    {} as Record<Shortcut["category"], Array<{ key: string; description: string }>>,
  );

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Dialog */}
      <div
        className="relative z-10 w-full max-w-lg rounded-xl border shadow-2xl"
        style={{
          background: "var(--bg-surface)",
          borderColor: "var(--border-default)",
        }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between border-b px-6 py-4"
          style={{ borderColor: "var(--border-subtle)" }}
        >
          <h2
            id={titleId}
            className="text-base font-semibold"
            style={{ color: "var(--text-primary)" }}
          >
            Keyboard Shortcuts
          </h2>
          <button
            onClick={onClose}
            aria-label="Close shortcuts help"
            className="rounded-md p-1 transition-colors hover:bg-bg-overlay"
          >
            <X className="h-4 w-4" style={{ color: "var(--text-secondary)" }} />
          </button>
        </div>

        {/* Shortcuts grid */}
        <div className="max-h-[60vh] overflow-y-auto px-6 py-4 space-y-5">
          {(Object.entries(byCategory) as Array<[Shortcut["category"], Array<{ key: string; description: string }>]>).map(
            ([category, items]) => (
              <section key={category} aria-label={`${category} shortcuts`}>
                <h3
                  className="mb-2 text-xs font-semibold uppercase tracking-wider"
                  style={{ color: "var(--text-tertiary)" }}
                >
                  {category}
                </h3>
                <dl className="space-y-0.5">
                  {items.map(({ key, description }) => (
                    <div
                      key={key}
                      className="flex items-center justify-between rounded-md px-2 py-1.5 transition-colors hover:bg-bg-elevated"
                    >
                      <dt className="text-sm" style={{ color: "var(--text-secondary)" }}>
                        {description}
                      </dt>
                      <dd className="flex items-center gap-1" aria-label={`Shortcut: ${key}`}>
                        {key.split("+").map((part, i) => (
                          <kbd
                            key={i}
                            className="inline-flex items-center justify-center rounded px-1.5 py-0.5 text-[11px] font-mono font-medium"
                            style={{
                              background: "var(--bg-elevated)",
                              border: "1px solid var(--border-default)",
                              color: "var(--text-primary)",
                              minWidth: 22,
                            }}
                          >
                            {part}
                          </kbd>
                        ))}
                      </dd>
                    </div>
                  ))}
                </dl>
              </section>
            ),
          )}
        </div>

        {/* Footer */}
        <div
          className="rounded-b-xl border-t px-6 py-3"
          style={{
            borderColor: "var(--border-subtle)",
            background: "var(--bg-elevated)",
          }}
        >
          <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
            Press{" "}
            <kbd
              className="rounded px-1 py-0.5 font-mono text-[11px]"
              style={{
                background: "var(--bg-surface)",
                border: "1px solid var(--border-default)",
              }}
            >
              ?
            </kbd>{" "}
            to toggle this dialog
          </p>
        </div>
      </div>
    </div>
  );
}
