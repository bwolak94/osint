// Shadcn/ui-compatible Card components — thin wrappers over the shared Card primitives.
import type { HTMLAttributes, ReactNode } from 'react'

function cn(...classes: (string | undefined | false)[]) {
  return classes.filter(Boolean).join(' ')
}

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('rounded-lg border transition-all', className)}
      style={{ background: 'var(--bg-surface)', borderColor: 'var(--border-subtle)' }}
      {...props}
    />
  )
}

export function CardHeader({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('flex flex-col space-y-1.5 border-b px-5 py-4', className)}
      style={{ borderColor: 'var(--border-subtle)' }}
      {...props}
    />
  )
}

export function CardTitle({ className, children, ...props }: HTMLAttributes<HTMLHeadingElement> & { children?: ReactNode }) {
  return (
    <h3
      className={cn('text-sm font-semibold leading-none tracking-tight', className)}
      style={{ color: 'var(--text-primary)' }}
      {...props}
    >
      {children}
    </h3>
  )
}

export function CardDescription({ className, ...props }: HTMLAttributes<HTMLParagraphElement>) {
  return (
    <p
      className={cn('text-xs', className)}
      style={{ color: 'var(--text-secondary)' }}
      {...props}
    />
  )
}

export function CardContent({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('px-5 py-4', className)} {...props} />
}

export function CardFooter({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('flex items-center border-t px-5 py-3', className)}
      style={{ borderColor: 'var(--border-subtle)' }}
      {...props}
    />
  )
}
