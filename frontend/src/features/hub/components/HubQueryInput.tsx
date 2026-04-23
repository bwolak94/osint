/**
 * HubQueryInput — textarea + submit button for agent queries.
 *
 * Submits on Enter (without Shift). Disabled while the agent is running.
 */

import { useId, useRef } from "react";
import { Send } from "lucide-react";

interface HubQueryInputProps {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  disabled?: boolean;
  placeholder?: string;
}

export function HubQueryInput({
  value,
  onChange,
  onSubmit,
  disabled = false,
  placeholder = "Ask anything — news, tasks, knowledge…",
}: HubQueryInputProps) {
  const inputId = useId();
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!disabled && value.trim()) onSubmit();
    }
  }

  return (
    <div className="flex gap-2 items-end">
      <div className="flex-1">
        <label htmlFor={inputId} className="sr-only">
          Query
        </label>
        <textarea
          id={inputId}
          ref={textareaRef}
          rows={2}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          placeholder={placeholder}
          className={`w-full resize-none rounded-lg border px-4 py-3 text-sm leading-relaxed outline-none transition-colors
            ${disabled ? "cursor-not-allowed opacity-60" : ""}
          `}
          style={{
            background: "var(--bg-surface)",
            borderColor: "var(--border-default)",
            color: "var(--text-primary)",
          }}
          aria-multiline="true"
          aria-disabled={disabled}
        />
      </div>

      <button
        type="button"
        onClick={onSubmit}
        disabled={disabled || !value.trim()}
        aria-label="Send query"
        className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg transition-all
          ${
            disabled || !value.trim()
              ? "cursor-not-allowed opacity-40"
              : "hover:scale-105 active:scale-95"
          }`}
        style={{
          background: "var(--brand-500)",
          color: "white",
        }}
      >
        <Send className="h-4 w-4" aria-hidden="true" />
      </button>
    </div>
  );
}
