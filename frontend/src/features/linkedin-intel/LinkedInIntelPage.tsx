import { useState } from "react";
import { Linkedin } from "lucide-react";
import { LinkedInSearchForm } from "./components/LinkedInSearchForm";
import { LinkedInResults } from "./components/LinkedInResults";
import { LinkedInHistory } from "./components/LinkedInHistory";
import { useScanLinkedInIntel } from "./hooks";
import type { LinkedInIntelScan } from "./types";

export function LinkedInIntelPage() {
  const [currentScan, setCurrentScan] = useState<LinkedInIntelScan | null>(null);
  const scanMutation = useScanLinkedInIntel();

  const handleSearch = (query: string, queryType: "username" | "name") => {
    scanMutation.mutate(
      { query, query_type: queryType },
      { onSuccess: (data) => setCurrentScan(data) }
    );
  };

  return (
    <div className="flex flex-1 flex-col gap-6 p-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div
          className="flex h-10 w-10 items-center justify-center rounded-lg"
          style={{ background: "var(--bg-overlay)" }}
        >
          <Linkedin className="h-5 w-5" style={{ color: "var(--brand-500)" }} />
        </div>
        <div>
          <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>
            LinkedIn Intel
          </h1>
          <p className="text-sm" style={{ color: "var(--text-tertiary)" }}>
            Search LinkedIn profiles via public OG metadata
          </p>
        </div>
      </div>

      {/* Search */}
      <div
        className="rounded-xl border p-5"
        style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}
      >
        <LinkedInSearchForm onSearch={handleSearch} isLoading={scanMutation.isPending} />
      </div>

      {/* Error */}
      {scanMutation.isError && (
        <div
          className="rounded-md border px-4 py-3 text-sm"
          style={{ borderColor: "var(--danger-500)", color: "var(--danger-500)", background: "var(--bg-overlay)" }}
        >
          Search failed. LinkedIn may have blocked the request or no profiles were found.
        </div>
      )}

      {/* Results */}
      {currentScan && (
        <div
          className="rounded-xl border p-5"
          style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}
        >
          <h2 className="mb-4 text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
            Results
          </h2>
          <LinkedInResults scan={currentScan} />
        </div>
      )}

      {/* History */}
      <div
        className="rounded-xl border p-5"
        style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}
      >
        <h2 className="mb-3 text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
          Scan History
        </h2>
        <LinkedInHistory onSelect={setCurrentScan} />
      </div>
    </div>
  );
}
