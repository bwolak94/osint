// Shadcn/ui-compatible Label shim.
import { forwardRef, type LabelHTMLAttributes } from 'react'

export const Label = forwardRef<HTMLLabelElement, LabelHTMLAttributes<HTMLLabelElement>>(
  ({ className = '', ...props }, ref) => (
    <label
      ref={ref}
      className={`text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 ${className}`}
      style={{ color: 'var(--text-secondary)' }}
      {...props}
    />
  ),
)
Label.displayName = 'Label'
