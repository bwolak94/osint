import { useState } from "react";
import { Download, Loader2 } from "lucide-react";
import { apiClient, ApiError } from "@/shared/api/client";

interface Props {
  investigationId: string;
}

export function STIXExportButton({ investigationId }: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleExport() {
    setLoading(true);
    setError(null);
    try {
      const resp = await apiClient.get(
        `/investigations/${investigationId}/export/stix`,
        { responseType: "blob" }
      );
      const url = URL.createObjectURL(new Blob([resp.data], { type: "application/stix+json" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `investigation-${investigationId}.stix.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        if (err.status === 403) {
          setError("Access denied. You do not have permission to export this investigation.");
        } else if (err.status === 404) {
          setError("Investigation not found.");
        } else {
          setError(`Export failed (${err.status}). Please try again.`);
        }
      } else {
        setError("Network error. Check your connection and try again.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="inline-flex flex-col gap-1">
      <button
        onClick={handleExport}
        disabled={loading}
        className="flex items-center gap-2 rounded-md px-3 py-1.5 text-xs font-medium transition-colors hover:bg-bg-overlay disabled:opacity-50"
        style={{ color: "var(--text-secondary)", border: "1px solid var(--border-subtle)" }}
        title="Export as STIX 2.1 bundle"
        aria-label="Export investigation as STIX 2.1"
      >
        {loading ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : (
          <Download className="h-3.5 w-3.5" />
        )}
        STIX 2.1
      </button>
      {error && (
        <p className="text-xs" style={{ color: "var(--danger-400)" }}>
          {error}
        </p>
      )}
    </div>
  );
}
