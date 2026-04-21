// Shadcn/ui-compatible Input shim.
import { forwardRef, type InputHTMLAttributes } from 'react'

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className = '', ...props }, ref) => (
    <input
      ref={ref}
      className={`w-full rounded-md border bg-transparent px-3 py-2 text-sm transition-colors focus:outline-none focus:ring-1 focus:ring-brand-500 disabled:cursor-not-allowed disabled:opacity-50 ${className}`}
      style={{ borderColor: 'var(--border-default)', color: 'var(--text-primary)' }}
      {...props}
    />
  ),
)
Input.displayName = 'Input'
