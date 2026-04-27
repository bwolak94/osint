interface ProgressBarProps {
  value: number;
  max?: number;
  label?: string;
  showPercentage?: boolean;
  size?: "sm" | "md";
}

export function ProgressBar({
  value,
  max = 100,
  label,
  showPercentage = true,
  size = "md",
}: ProgressBarProps) {
  const percentage = Math.min(100, Math.max(0, (value / max) * 100));

  return (
    <div className="space-y-1">
      {(label || showPercentage) && (
        <div className="flex items-center justify-between">
          {label && (
            <span className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
              {label}
            </span>
          )}
          {showPercentage && (
            <span className="text-xs font-mono" style={{ color: "var(--text-secondary)" }}>
              {percentage.toFixed(0)}%
            </span>
          )}
        </div>
      )}
      <div
        className={`w-full overflow-hidden rounded-full ${size === "sm" ? "h-1" : "h-2"}`}
        style={{ background: "var(--bg-elevated)" }}
      >
        <div
          className="h-full rounded-full transition-[width] duration-500 ease-out"
          style={{ background: "var(--brand-500)", width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}
