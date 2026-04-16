import { forwardRef, type InputHTMLAttributes, type ReactNode } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  helperText?: string;
  error?: string;
  prefixIcon?: ReactNode;
  suffixIcon?: ReactNode;
  mono?: boolean;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, helperText, error, prefixIcon, suffixIcon, mono, className = "", id, ...props }, ref) => {
    const inputId = id ?? label?.toLowerCase().replace(/\s+/g, "-");

    return (
      <div className="space-y-1.5">
        {label && (
          <label
            htmlFor={inputId}
            className="block text-sm font-medium"
            style={{ color: "var(--text-secondary)" }}
          >
            {label}
          </label>
        )}
        <div className="relative">
          {prefixIcon && (
            <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
              <span style={{ color: "var(--text-tertiary)" }}>{prefixIcon}</span>
            </div>
          )}
          <input
            ref={ref}
            id={inputId}
            className={`block w-full rounded-md border px-3 py-2 text-sm transition-colors placeholder:text-text-tertiary focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent disabled:opacity-50 ${
              error
                ? "border-danger-500 bg-danger-900/20"
                : "border-border bg-bg-elevated hover:border-border-strong"
            } ${prefixIcon ? "pl-10" : ""} ${suffixIcon ? "pr-10" : ""} ${
              mono ? "font-mono text-[13px]" : ""
            } ${className}`}
            style={{ color: "var(--text-primary)" }}
            {...props}
          />
          {suffixIcon && (
            <div className="absolute inset-y-0 right-0 flex items-center pr-3">
              <span style={{ color: "var(--text-tertiary)" }}>{suffixIcon}</span>
            </div>
          )}
        </div>
        {error && (
          <p className="text-xs" style={{ color: "var(--danger-500)" }}>
            {error}
          </p>
        )}
        {helperText && !error && (
          <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
            {helperText}
          </p>
        )}
      </div>
    );
  },
);

Input.displayName = "Input";
