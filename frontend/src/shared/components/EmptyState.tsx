import type { ReactNode } from "react";
import { SearchX, Inbox, AlertTriangle, Loader2 } from "lucide-react";

type EmptyVariant = "no-data" | "search-empty" | "error" | "loading";

interface EmptyStateProps {
  variant?: EmptyVariant;
  title: string;
  description?: string;
  action?: ReactNode;
}

const icons: Record<EmptyVariant, typeof Inbox> = {
  "no-data": Inbox,
  "search-empty": SearchX,
  error: AlertTriangle,
  loading: Loader2,
};

export function EmptyState({
  variant = "no-data",
  title,
  description,
  action,
}: EmptyStateProps) {
  const Icon = icons[variant];

  return (
    <div
      role="status"
      aria-live="polite"
      className="flex flex-col items-center justify-center py-16 text-center"
    >
      <div
        className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl"
        style={{ background: "var(--bg-elevated)" }}
      >
        <Icon
          className={`h-6 w-6 ${variant === "loading" ? "animate-spin" : ""}`}
          style={{ color: "var(--text-tertiary)" }}
        />
      </div>
      <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
        {title}
      </h3>
      {description && (
        <p className="mt-1 max-w-sm text-sm" style={{ color: "var(--text-secondary)" }}>
          {description}
        </p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
