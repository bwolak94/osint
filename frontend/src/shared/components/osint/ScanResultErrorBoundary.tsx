import { Component, ReactNode } from "react";

interface Props {
  scannerName: string;
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

/**
 * Isolates render errors in individual scanner result panels.
 *
 * Without this boundary, a bad `raw_data` shape from a single scanner would
 * crash the entire investigation detail page. With it, only the affected
 * scanner card shows an error while the rest of the page remains functional.
 */
export class ScanResultErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  override render() {
    if (this.state.hasError) {
      return (
        <div
          className="rounded-md border p-3 text-xs"
          style={{
            borderColor: "var(--color-danger, #ef4444)",
            color: "var(--text-secondary)",
            background: "var(--surface-secondary)",
          }}
          role="alert"
        >
          <strong style={{ color: "var(--color-danger, #ef4444)" }}>
            Failed to render {this.props.scannerName} results
          </strong>
          <p className="mt-1 opacity-75">
            {this.state.error?.message ?? "An unexpected rendering error occurred."}
          </p>
        </div>
      );
    }
    return this.props.children;
  }
}
