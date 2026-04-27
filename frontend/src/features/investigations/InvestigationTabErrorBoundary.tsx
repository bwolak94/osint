import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangle } from "lucide-react";

interface Props {
  tabName: string;
  children: ReactNode;
}

interface State {
  error: Error | null;
}

/**
 * Per-tab error boundary for InvestigationDetailPage.
 * Catches render errors inside a single tab so the whole page doesn't crash.
 */
export class InvestigationTabErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(`[${this.props.tabName} tab error]`, error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div
          className="flex flex-col items-center gap-3 rounded-lg border px-6 py-10 text-center"
          style={{ borderColor: "var(--danger-500)", background: "var(--danger-950)" }}
          role="alert"
        >
          <AlertTriangle className="h-8 w-8" style={{ color: "var(--danger-400)" }} />
          <p className="text-sm font-semibold" style={{ color: "var(--danger-400)" }}>
            {this.props.tabName} tab encountered an error
          </p>
          <p className="text-xs max-w-sm" style={{ color: "var(--text-tertiary)" }}>
            {this.state.error.message}
          </p>
          <button
            onClick={() => this.setState({ error: null })}
            className="mt-2 rounded-md px-3 py-1.5 text-xs font-medium transition-colors hover:bg-bg-overlay"
            style={{ color: "var(--danger-400)", border: "1px solid var(--danger-500)" }}
          >
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
