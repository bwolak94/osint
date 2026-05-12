// Shadcn/ui-compatible Separator shim.
import type { HTMLAttributes } from 'react'

interface SeparatorProps extends HTMLAttributes<HTMLDivElement> {
  orientation?: 'horizontal' | 'vertical'
}

export function Separator({ orientation = 'horizontal', className = '', ...props }: SeparatorProps) {
  return (
    <div
      role="separator"
      aria-orientation={orientation}
      className={`shrink-0 ${orientation === 'horizontal' ? 'h-px w-full' : 'h-full w-px'} ${className}`}
      style={{ background: 'var(--border-subtle)' }}
      {...props}
    />
  )
}
