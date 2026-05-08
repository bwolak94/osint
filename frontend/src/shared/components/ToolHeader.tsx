import { useState, useId } from 'react'
import { X } from 'lucide-react'

interface ToolHeaderProps {
  title: string
  description: string
  details: string
}

export function ToolHeader({ title, description, details }: ToolHeaderProps) {
  const [open, setOpen] = useState(false)
  const dialogId = useId()
  const titleId = `${dialogId}-title`

  return (
    <>
      <div>
        <h1 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>
          {title}
        </h1>
        <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)' }}>
          {description}
          {' '}
          <button
            onClick={() => setOpen(true)}
            className="inline font-medium underline-offset-2 hover:underline transition-colors"
            style={{ color: 'var(--brand-500)' }}
            aria-haspopup="dialog"
          >
            Learn more
          </button>
        </p>
      </div>

      {open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          role="presentation"
        >
          {/* Backdrop */}
          <div
            className="absolute inset-0"
            style={{ backgroundColor: 'rgba(0,0,0,0.55)' }}
            onClick={() => setOpen(false)}
            aria-hidden="true"
          />

          {/* Dialog */}
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            className="relative z-10 w-full max-w-lg rounded-lg shadow-xl"
            style={{ backgroundColor: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)' }}
          >
            {/* Header */}
            <div
              className="flex items-center justify-between px-5 py-4"
              style={{ borderBottom: '1px solid var(--border-subtle)' }}
            >
              <h2
                id={titleId}
                className="text-sm font-semibold"
                style={{ color: 'var(--text-primary)' }}
              >
                {title}
              </h2>
              <button
                onClick={() => setOpen(false)}
                className="flex h-6 w-6 items-center justify-center rounded transition-colors hover:opacity-70"
                style={{ color: 'var(--text-tertiary)' }}
                aria-label="Close"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Body */}
            <div className="px-5 py-4">
              <p
                className="text-sm leading-relaxed whitespace-pre-wrap"
                style={{ color: 'var(--text-secondary)' }}
              >
                {details}
              </p>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
