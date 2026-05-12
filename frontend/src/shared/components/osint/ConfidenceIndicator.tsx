interface ConfidenceIndicatorProps {
  value: number; // 0.0 - 1.0
  showLabel?: boolean;
}

function getLevel(value: number): { label: string; color: string } {
  if (value >= 0.95) return { label: "Certain", color: "var(--success-500)" };
  if (value >= 0.6) return { label: "High", color: "var(--brand-500)" };
  if (value >= 0.3) return { label: "Medium", color: "var(--warning-500)" };
  return { label: "Low", color: "var(--danger-500)" };
}

export function ConfidenceIndicator({ value, showLabel = true }: ConfidenceIndicatorProps) {
  const { label, color } = getLevel(value);
  const percentage = Math.round(value * 100);

  return (
    <div className="flex items-center gap-2">
      <div
        role="meter"
        aria-valuenow={percentage}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Confidence: ${percentage}% (${label})`}
        className="h-1.5 w-16 overflow-hidden rounded-full"
        style={{ background: "var(--bg-elevated)" }}
      >
        <div
          aria-hidden="true"
          className="h-full rounded-full transition-all"
          style={{ width: `${percentage}%`, background: color }}
        />
      </div>
      <span className="text-xs font-mono" style={{ color }} aria-hidden="true">
        {percentage}%
      </span>
      {showLabel && (
        <span className="text-xs" style={{ color: "var(--text-tertiary)" }} aria-hidden="true">
          {label}
        </span>
      )}
    </div>
  );
}
