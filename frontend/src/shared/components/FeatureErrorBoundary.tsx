import { Component, type ErrorInfo, type ReactNode } from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'

interface Props {
  children: ReactNode
  featureName?: string
}

interface State {
  hasError: boolean
  error: Error | null
}

export class FeatureErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(`[${this.props.featureName ?? 'Feature'}] Error:`, error, info)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-[300px] flex-col items-center justify-center gap-4 rounded-xl border p-8 text-center"
          style={{ background: 'var(--bg-surface)', borderColor: 'var(--border-subtle)' }}>
          <div className="flex h-12 w-12 items-center justify-center rounded-full"
            style={{ background: 'var(--danger-900)' }}>
            <AlertTriangle className="h-6 w-6" style={{ color: 'var(--danger-400)' }} />
          </div>
          <div>
            <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              {this.props.featureName ? `${this.props.featureName} failed to load` : 'Something went wrong'}
            </p>
            <p className="mt-1 text-xs" style={{ color: 'var(--text-tertiary)' }}>
              {this.state.error?.message ?? 'An unexpected error occurred'}
            </p>
          </div>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            className="flex items-center gap-2 rounded-md px-3 py-1.5 text-xs font-medium transition-colors"
            style={{ background: 'var(--bg-elevated)', color: 'var(--text-secondary)' }}
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Try again
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
