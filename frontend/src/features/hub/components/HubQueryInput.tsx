/**
 * HubQueryInput — textarea + submit button for agent queries.
 *
 * - Submits on Enter (Shift+Enter inserts a newline as expected).
 * - Disabled while the agent is running.
 * - Shows character count when approaching the 2000-char limit.
 */

import { useId, useRef } from "react";
import { Send } from "lucide-react";

const MAX_CHARS = 2000;

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

  const remaining = MAX_CHARS - value.length;
  const showCounter = value.length > MAX_CHARS * 0.8; // show when > 80% used
  const isOverLimit = value.length > MAX_CHARS;

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!disabled && value.trim() && !isOverLimit) onSubmit();
    }
  }

  function handleChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    onChange(e.target.value);
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
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          placeholder={placeholder}
          className={`w-full resize-none rounded-lg border px-4 py-3 text-sm leading-relaxed outline-none transition-colors
            ${disabled ? "cursor-not-allowed opacity-60" : ""}
            ${isOverLimit ? "border-red-500" : ""}
          `}
          style={{
            background: "var(--bg-surface)",
            borderColor: isOverLimit ? "var(--danger-500)" : "var(--border-default)",
            color: "var(--text-primary)",
          }}
          aria-multiline="true"
          aria-disabled={disabled}
          maxLength={MAX_CHARS + 100} // allow slight overflow so user sees counter
        />
        {showCounter && (
          <p
            className="text-right text-xs mt-0.5 pr-1"
            style={{ color: isOverLimit ? "var(--danger-500)" : "var(--text-tertiary)" }}
            aria-live="polite"
          >
            {isOverLimit ? `${Math.abs(remaining)} over limit` : `${remaining} left`}
          </p>
        )}
      </div>

      <button
        type="button"
        onClick={onSubmit}
        disabled={disabled || !value.trim() || isOverLimit}
        aria-label="Send query"
        className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg transition-all
          ${
            disabled || !value.trim() || isOverLimit
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
