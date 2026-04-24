import type { CSSProperties, ReactNode } from "react";

type BadgeVariant = "success" | "warning" | "danger" | "info" | "neutral" | "brand";
type BadgeSize = "sm" | "md";

interface BadgeProps {
  variant?: BadgeVariant;
  size?: BadgeSize;
  dot?: boolean;
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
}

const variantStyles: Record<BadgeVariant, string> = {
  success: "bg-success-900 text-success-500 border-success-500/20",
  warning: "bg-warning-900 text-warning-500 border-warning-500/20",
  danger: "bg-danger-900 text-danger-500 border-danger-500/20",
  info: "bg-info-900 text-info-500 border-info-500/20",
  neutral: "bg-bg-overlay text-text-secondary border-border",
  brand: "bg-brand-900 text-brand-400 border-brand-500/20",
};

const sizeStyles: Record<BadgeSize, string> = {
  sm: "px-1.5 py-0.5 text-[10px]",
  md: "px-2 py-0.5 text-xs",
};

export function Badge({ variant = "neutral", size = "md", dot, children, className = "", style }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border font-medium ${variantStyles[variant]} ${sizeStyles[size]} ${className}`}
      style={style}
    >
      {dot && (
        <span
          className="h-1.5 w-1.5 rounded-full"
          style={{
            backgroundColor: "currentColor",
          }}
        />
      )}
      {children}
    </span>
  );
}
