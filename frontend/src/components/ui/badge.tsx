// Shadcn/ui-compatible Badge shim.
import type { HTMLAttributes } from 'react'

type Variant = 'default' | 'secondary' | 'destructive' | 'outline' | 'success' | 'warning'

const variantStyles: Record<Variant, string> = {
  default: 'bg-brand-500 text-white',
  secondary: 'bg-bg-elevated text-text-secondary border border-border',
  destructive: 'bg-red-500/20 text-red-400 border border-red-500/30',
  outline: 'border border-border text-text-secondary',
  success: 'bg-green-500/20 text-green-400 border border-green-500/30',
  warning: 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30',
}

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: Variant
}

export function Badge({ variant = 'default', className = '', ...props }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-medium ${variantStyles[variant]} ${className}`}
      {...props}
    />
  )
}
